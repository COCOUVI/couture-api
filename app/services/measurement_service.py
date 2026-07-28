import logging

from app.services.pose_service import (
    NOSE, LEFT_EAR, RIGHT_EAR,
    L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW,
    L_WRIST, R_WRIST, L_HIP, R_HIP,
    L_KNEE, R_KNEE, L_ANKLE, R_ANKLE, L_HEEL, R_HEEL,
    w3d, avg, ellipse_circumference,
)

logger = logging.getLogger(__name__)

TYPE_MESURE_META: dict[str, dict] = {
    "HAUTEUR"             : {"label": "Hauteur totale",                        "unite": "cm", "categorie": "longueur"},
    "TORSE"               : {"label": "Longueur torse (épaule - hanche)",      "unite": "cm", "categorie": "longueur"},
    "HAUT_SEIN"           : {"label": "Hauteur de sein (épaule - buste)",      "unite": "cm", "categorie": "longueur"},
    "LONGUEUR_TAILLE"     : {"label": "Longueur taille (épaule - nombril)",    "unite": "cm", "categorie": "longueur"},
    "LONGUEUR_CHEMISE"    : {"label": "Longueur chemise (nombril - hanche)",   "unite": "cm", "categorie": "longueur"},
    "LONGUEUR_SOUS_SEINS" : {"label": "Longueur sous-poitrine (épaule - sous-sein)", "unite": "cm", "categorie": "longueur"},
    "JAMBE"               : {"label": "Longueur pantalon (hanche - cheville)", "unite": "cm", "categorie": "longueur"},
    "LONGUEUR_JUPE"       : {"label": "Longueur jupe longue (hanche - cheville)", "unite": "cm", "categorie": "longueur"},
    "LONGUEUR_ROBE"       : {"label": "Longueur robe (épaule - cheville)",     "unite": "cm", "categorie": "longueur"},
    "CUISSE"              : {"label": "Longueur cuisse (hanche - genou)",      "unite": "cm", "categorie": "longueur"},
    "MOLLET"              : {"label": "Longueur mollet (genou - cheville)",    "unite": "cm", "categorie": "longueur"},
    "HAUTEUR_GENOU"       : {"label": "Hauteur genou (sol - genou)",           "unite": "cm", "categorie": "longueur"},
    "MANCHE_LONGUE"       : {"label": "Longueur manche longue (épaule - poignet)", "unite": "cm", "categorie": "longueur"},
    "MANCHE_COURTE"       : {"label": "Longueur manche courte (épaule - coude)",   "unite": "cm", "categorie": "longueur"},
    "BRA_AV"              : {"label": "Longueur avant-bras (coude - poignet)", "unite": "cm", "categorie": "longueur"},
    "EPAULES"             : {"label": "Largeur épaules",                       "unite": "cm", "categorie": "largeur"},
    "CARRURE_DEVANT"      : {"label": "Carrure devant (entre emmanchures)",    "unite": "cm", "categorie": "largeur"},
    "CARRURE_DOS"         : {"label": "Carrure dos (entre emmanchures)",       "unite": "cm", "categorie": "largeur"},
    "HANCHES_L"           : {"label": "Largeur hanches",                       "unite": "cm", "categorie": "largeur"},
    "POITRINE"            : {"label": "Tour de poitrine",                      "unite": "cm", "categorie": "circonference"},
    "TOUR_SOUS_SEINS"     : {"label": "Tour de sous-poitrine",                  "unite": "cm", "categorie": "circonference"},
    "CEINTURE"            : {"label": "Tour de ceinture",                      "unite": "cm", "categorie": "circonference"},
    "TOUR_FESSES"         : {"label": "Tour de fesses",                         "unite": "cm", "categorie": "circonference"},
    "TOUR_COU"            : {"label": "Tour de cou",                           "unite": "cm", "categorie": "circonference"},
    "TOUR_GENOU"          : {"label": "Tour de genou",                         "unite": "cm", "categorie": "circonference"},
    "TOUR_BAS"            : {"label": "Tour du bas / cheville",                "unite": "cm", "categorie": "circonference"},
    "TOUR_POIGNET"        : {"label": "Tour de poignet",                       "unite": "cm", "categorie": "circonference"},
}

_CODES_INTERMEDIAIRES: set[str] = {
    "BUSTE_LARGEUR_FACE",
    "SOUS_SEINS_LARGEUR_FACE",
    "CEINTURE_LARGEUR_FACE",
    "PROFONDEUR_BUSTE",
    "PROFONDEUR_SOUS_SEINS",
    "PROFONDEUR_CEINTURE",
    "PROFONDEUR_HANCHE",
    "EPAULES_DOS",
    "HANCHES_LARGEUR_DOS",
    "TORSE_LONGUEUR_DOS",
    "TORSE_LONGUEUR_PROFIL",
}

MESURES_EXCLUES_HOMME: set[str] = {
    "LONGUEUR_SOUS_SEINS",
    "TOUR_SOUS_SEINS",
    "LONGUEUR_JUPE",
    "LONGUEUR_ROBE",
}


def _point_interpole(a, b, ratio: float) -> tuple[float, float, float]:
    """Retourne un point 3D interpolé entre deux landmarks."""
    return (
        a.x + (b.x - a.x) * ratio,
        a.y + (b.y - a.y) * ratio,
        a.z + (b.z - a.z) * ratio,
    )


def _distance_entre_points_cm(pa: tuple[float, float, float], pb: tuple[float, float, float]) -> float:
    """Calcule la distance 3D entre deux points en centimètres."""
    return round(
        ((pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2 + (pa[2] - pb[2]) ** 2) ** 0.5 * 100,
        1,
    )


def _largeur_torse_interpolee(wlms: list, ratio: float) -> float:
    """Mesure la largeur du torse à un niveau donné entre épaule et hanche."""
    g = _point_interpole(wlms[L_SHOULDER], wlms[L_HIP], ratio)
    d = _point_interpole(wlms[R_SHOULDER], wlms[R_HIP], ratio)
    return _distance_entre_points_cm(g, d)


def _profondeur_torse_interpolee(wlms: list, ratio: float) -> float:
    """Mesure la profondeur du torse à un niveau donné entre épaule et hanche."""
    g = _point_interpole(wlms[L_SHOULDER], wlms[L_HIP], ratio)
    d = _point_interpole(wlms[R_SHOULDER], wlms[R_HIP], ratio)
    return round(abs(g[2] - d[2]) * 100, 1)


def _clamp(val: float, low: float, high: float) -> float:
    """Limite une valeur dans un intervalle fermé."""
    return round(min(max(val, low), high), 1)


def _compute_scale(wlms: list, taille_connue_cm: float) -> float:
    """Estime le facteur de conversion entre les landmarks et les centimètres."""
    largeur_epaules_brute = w3d(wlms, L_SHOULDER, R_SHOULDER)
    y_ep_moy = (wlms[L_SHOULDER].y + wlms[R_SHOULDER].y) / 2
    y_ch_moy = (wlms[L_ANKLE].y + wlms[R_ANKLE].y) / 2
    dist_nez_cheville = abs(wlms[NOSE].y - y_ch_moy) * 100
    dist_ep_cheville = abs(y_ep_moy - y_ch_moy) * 100
    largeur_bi_auric = w3d(wlms, LEFT_EAR, RIGHT_EAR)
    extension_cranienne = max(largeur_bi_auric * 0.45, largeur_epaules_brute * 0.14)
    hauteur_semelle = max(largeur_epaules_brute * 0.07, 3.0)
    h_nez = dist_nez_cheville + extension_cranienne + hauteur_semelle
    h_ep = dist_ep_cheville / 0.82
    hauteur_brute = (h_nez * 0.65) + (h_ep * 0.35)
    scale = taille_connue_cm / max(hauteur_brute, 1.0)
    logger.info("Calibration: %.1f cm / %.1f brute = scale %.4f", taille_connue_cm, hauteur_brute, scale)
    return scale


def extraire_face(wlms: list, known_height_cm: float) -> dict:
    """Extrait les mesures de la vue de face."""
    scale = _compute_scale(wlms, known_height_cm)

    def s(ia: int, ib: int) -> float:
        """Convertit une distance MediaPipe en centimètres."""
        return round(w3d(wlms, ia, ib) * scale, 1)

    def avg_bilat(iga, igb, ida, idb) -> float:
        """Moyenne les mesures gauche et droite d'une même zone."""
        return avg(s(iga, igb), s(ida, idb))

    largeur_epaules = s(L_SHOULDER, R_SHOULDER)
    carrure_devant = round(_largeur_torse_interpolee(wlms, 0.12) * scale, 1)
    largeur_buste_face = round(_largeur_torse_interpolee(wlms, 0.30) * scale, 1)
    largeur_sous_seins_face = round(_largeur_torse_interpolee(wlms, 0.20) * scale, 1)
    largeur_ceinture_face = round(_largeur_torse_interpolee(wlms, 0.62) * scale, 1)
    largeur_hanches = s(L_HIP, R_HIP)
    longueur_torse = avg_bilat(L_SHOULDER, L_HIP, R_SHOULDER, R_HIP)
    haut_sein = round(longueur_torse * 0.29, 1)
    longueur_sous_seins = round(longueur_torse * 0.20, 1)
    longueur_taille = round(longueur_torse * 0.62, 1)
    longueur_chemise = round(longueur_torse - longueur_taille, 1)
    longueur_manche = avg_bilat(L_SHOULDER, L_WRIST, R_SHOULDER, R_WRIST)
    longueur_manche_courte = avg_bilat(L_SHOULDER, L_ELBOW, R_SHOULDER, R_ELBOW)
    longueur_avant_bras = avg_bilat(L_ELBOW, L_WRIST, R_ELBOW, R_WRIST)
    longueur_pantalon = avg_bilat(L_HIP, L_ANKLE, R_HIP, R_ANKLE)
    longueur_jupe = avg_bilat(L_HIP, L_ANKLE, R_HIP, R_ANKLE)
    longueur_robe = avg_bilat(L_SHOULDER, L_ANKLE, R_SHOULDER, R_ANKLE)
    longueur_cuisse = avg_bilat(L_HIP, L_KNEE, R_HIP, R_KNEE)
    longueur_mollet = avg_bilat(L_KNEE, L_ANKLE, R_KNEE, R_ANKLE)
    hauteur_genou = round(avg_bilat(L_KNEE, L_HEEL, R_KNEE, R_HEEL) + 6.0, 1)

    return {
        "HAUTEUR"               : (round(known_height_cm, 1), "saisie_utilisateur", 1.00),
        "EPAULES"               : (largeur_epaules,           "face",               0.92),
        "CARRURE_DEVANT"        : (carrure_devant,            "face_emmanchure",    0.80),
        "HANCHES_L"             : (largeur_hanches,           "face",               0.90),
        "BUSTE_LARGEUR_FACE"    : (largeur_buste_face,         "face",               0.82),
        "SOUS_SEINS_LARGEUR_FACE": (largeur_sous_seins_face,   "face",               0.82),
        "CEINTURE_LARGEUR_FACE" : (largeur_ceinture_face,      "face",               0.84),
        "TORSE"                 : (longueur_torse,             "face",               0.88),
        "HAUT_SEIN"             : (haut_sein,                  "ratio_torse_0.29",   0.75),
        "LONGUEUR_SOUS_SEINS"   : (longueur_sous_seins,        "ratio_torse_0.20",   0.75),
        "LONGUEUR_TAILLE"       : (longueur_taille,            "ratio_torse_0.62",   0.78),
        "LONGUEUR_CHEMISE"      : (longueur_chemise,           "ratio_torse_0.38",   0.78),
        "MANCHE_LONGUE"         : (longueur_manche,            "face",               0.85),
        "MANCHE_COURTE"         : (longueur_manche_courte,     "face",               0.87),
        "BRA_AV"                : (longueur_avant_bras,        "face",               0.87),
        "JAMBE"                 : (longueur_pantalon,          "face",               0.88),
        "LONGUEUR_JUPE"         : (longueur_jupe,              "face",               0.87),
        "LONGUEUR_ROBE"         : (longueur_robe,              "face",               0.84),
        "CUISSE"                : (longueur_cuisse,            "face",               0.86),
        "MOLLET"                : (longueur_mollet,            "face",               0.86),
        "HAUTEUR_GENOU"         : (hauteur_genou,              "face_talon+6cm",     0.80),
    }


def extraire_dos(wlms: list, known_height_cm: float) -> dict:
    """Extrait les mesures de la vue de dos."""
    scale = _compute_scale(wlms, known_height_cm)

    def s(ia: int, ib: int) -> float:
        """Convertit une distance MediaPipe en centimètres."""
        return round(w3d(wlms, ia, ib) * scale, 1)

    def avg_bilat(iga, igb, ida, idb) -> float:
        """Moyenne les mesures gauche et droite d'une même zone."""
        return avg(s(iga, igb), s(ida, idb))

    carrure_dos = round(_largeur_torse_interpolee(wlms, 0.12) * scale, 1)

    return {
        "EPAULES_DOS"        : (s(L_SHOULDER, R_SHOULDER),                     "dos", 0.90),
        "HANCHES_LARGEUR_DOS": (s(L_HIP, R_HIP),                              "dos", 0.88),
        "TORSE_LONGUEUR_DOS" : (avg_bilat(L_SHOULDER, L_HIP, R_SHOULDER, R_HIP), "dos", 0.86),
        "CARRURE_DOS"        : (carrure_dos,                                   "dos_emmanchure", 0.80),
    }


def extraire_profil(wlms: list, known_height_cm: float) -> dict:
    """Extrait les mesures de la vue de profil."""
    scale = _compute_scale(wlms, known_height_cm)
    profond_buste = abs(wlms[L_SHOULDER].z - wlms[R_SHOULDER].z) * 100
    profond_sous_seins = _profondeur_torse_interpolee(wlms, 0.20)
    profond_ceinture = _profondeur_torse_interpolee(wlms, 0.62)
    profond_hanche = abs(wlms[L_HIP].z - wlms[R_HIP].z) * 100
    torse_profil = abs(wlms[L_SHOULDER].y - wlms[L_HIP].y) * 100

    return {
        "PROFONDEUR_BUSTE"      : (round(profond_buste     * scale, 1), "profil", 0.75),
        "PROFONDEUR_SOUS_SEINS" : (round(profond_sous_seins * scale, 1), "profil", 0.75),
        "PROFONDEUR_CEINTURE"   : (round(profond_ceinture  * scale, 1), "profil", 0.78),
        "PROFONDEUR_HANCHE"     : (round(profond_hanche    * scale, 1), "profil", 0.75),
        "TORSE_LONGUEUR_PROFIL" : (round(torse_profil      * scale, 1), "profil", 0.82),
    }


def filtrer_par_sexe(mesures: list[dict], sexe: str) -> list[dict]:
    """Retire les mesures non pertinentes pour un profil homme."""
    norm = sexe.strip().lower()
    if norm in ("homme", "masculin", "h", "M"):
        return [m for m in mesures if m["type_mesure_code"] not in MESURES_EXCLUES_HOMME]
    return mesures


def fusionner(m_face: dict, m_dos: dict, m_profil: dict) -> list[dict]:
    """Fusionne les mesures des trois vues et produit les mesures finales."""
    raw: dict = {**m_face, **m_dos, **m_profil}

    if "EPAULES" in raw and "EPAULES_DOS" in raw:
        raw["EPAULES"] = (avg(raw["EPAULES"][0], raw["EPAULES_DOS"][0]), "face+dos", 0.94)

    torses = [raw[k][0] for k in ("TORSE", "TORSE_LONGUEUR_DOS", "TORSE_LONGUEUR_PROFIL") if k in raw]
    if torses:
        raw["TORSE"] = (avg(*torses), "face+dos+profil", 0.93)

    if "HANCHES_L" in raw and "HANCHES_LARGEUR_DOS" in raw:
        raw["HANCHES_L"] = (avg(raw["HANCHES_L"][0], raw["HANCHES_LARGEUR_DOS"][0]), "face+dos", 0.92)

    l_ep = raw.get("EPAULES",            (0.0,))[0]
    l_bu = raw.get("BUSTE_LARGEUR_FACE",  (0.0,))[0] or l_ep * 0.86
    l_ss = raw.get("SOUS_SEINS_LARGEUR_FACE", (0.0,))[0] or l_bu * 0.88
    l_ce = raw.get("CEINTURE_LARGEUR_FACE", (0.0,))[0]
    l_ha = raw.get("HANCHES_L",           (0.0,))[0]
    p_bu = raw.get("PROFONDEUR_BUSTE",    (0.0,))[0]
    p_ss = raw.get("PROFONDEUR_SOUS_SEINS", (0.0,))[0]
    p_ce = raw.get("PROFONDEUR_CEINTURE", (0.0,))[0]
    p_ha = raw.get("PROFONDEUR_HANCHE",   (0.0,))[0]

    profil_ok = p_bu > 0 and p_ce > 0 and l_bu > 0 and l_ce > 0

    if profil_ok:
        dl_bu = l_bu / 2
        dp_bu = max(p_bu / 2, dl_bu * 0.45)
        dl_ss = l_ss / 2
        dp_ss = max(p_ss / 2, dl_ss * 0.45) if p_ss > 0 else dl_ss * 0.45
        dl_ce = l_ce / 2
        dp_ce = max(p_ce / 2, dl_ce * 0.45)
        dl_ha = l_ha / 2
        dp_ha = max(p_ha / 2, dl_ha * 0.50)

        tour_poitrine = ellipse_circumference(dl_bu, dp_bu)
        tour_sous_seins = ellipse_circumference(dl_ss, dp_ss)
        tour_ceinture = ellipse_circumference(dl_ce, dp_ce)
        tour_hanches = ellipse_circumference(dl_ha, dp_ha)
        source_tours = "ellipse_ramanujan(face+profil)"
        c_poitrine, c_sous_seins, c_ceinture, c_hanches = 0.88, 0.84, 0.86, 0.86
    else:
        tour_poitrine = round(l_bu * 3.35, 1)
        tour_sous_seins = round(l_ss * 3.20, 1)
        tour_hanches = round(l_ha * 3.35, 1)
        tour_ceinture = round((l_ce or l_ha * 0.82) * 3.20, 1)
        source_tours = "ratio_iso8559(face_seule)"
        c_poitrine = c_sous_seins = c_ceinture = c_hanches = 0.72

    if tour_poitrine > 0 and tour_hanches > 0 and tour_ceinture > 0:
        ref = min(tour_poitrine, tour_hanches)
        tour_ceinture = _clamp(tour_ceinture, ref * 0.62, ref * 1.03)

    l_mollet = raw.get("MOLLET", (0.0,))[0]
    l_av_bras = raw.get("BRA_AV", (0.0,))[0]
    largeur_bi_auric = round(l_ep * 0.35, 1)

    raw["POITRINE"]      = (tour_poitrine,  source_tours, c_poitrine)
    raw["TOUR_SOUS_SEINS"] = (tour_sous_seins, source_tours, c_sous_seins)
    raw["CEINTURE"]      = (tour_ceinture,  source_tours, c_ceinture)
    raw["TOUR_FESSES"]   = (tour_hanches,   source_tours, c_hanches)
    raw["TOUR_COU"]      = (round(largeur_bi_auric * 1.73, 1), "ratio_din61506", 0.70)
    raw["TOUR_GENOU"]    = (round(l_mollet * 1.20, 1),        "ratio_iso8559",  0.72)
    raw["TOUR_BAS"]      = (round(l_mollet * 0.65, 1),        "ratio_pheasant", 0.70)
    raw["TOUR_POIGNET"]  = (round(l_av_bras * 0.65, 1),       "ratio_pheasant", 0.72)

    result = []
    for code, (valeur, source, confiance) in raw.items():
        if code in _CODES_INTERMEDIAIRES or valeur <= 0:
            continue
        meta = TYPE_MESURE_META.get(code, {"label": code, "unite": "cm", "categorie": "autre"})
        result.append({
            "type_mesure_code": code,
            "label": meta["label"],
            "unite": meta["unite"],
            "categorie": meta["categorie"],
            "valeur": valeur,
            "source": source,
            "confiance": confiance,
        })

    logger.info("Fusion: %d mesures finales (%s)", len(result), "ellipse" if profil_ok else "ratio")
    return result
