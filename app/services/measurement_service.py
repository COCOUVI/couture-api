from app.services.pose_service import (
    L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW,
    L_WRIST, R_WRIST, L_HIP, R_HIP,
    L_KNEE, R_KNEE, L_ANKLE, R_ANKLE,
    LEFT_EAR, RIGHT_EAR,
    w3d, avg, ellipse_circumference,
)


# ── Labels (doit correspondre aux TypeMesure.code en DB) ────────────
TYPE_MESURE_META = {
    "HAUTEUR"      : {"label": "Hauteur totale",        "unite": "cm", "categorie": "longueur"},
    "EPAULES"      : {"label": "Largeur épaules (É)",   "unite": "cm", "categorie": "largeur"},
    "TORSE"        : {"label": "Longueur torse",        "unite": "cm", "categorie": "longueur"},
    "BRA_TOTAL"    : {"label": "Longueur bras total",   "unite": "cm", "categorie": "longueur"},
    "BRA_HAUT"     : {"label": "Haut du bras",          "unite": "cm", "categorie": "longueur"},
    "BRA_AV"       : {"label": "Avant-bras",            "unite": "cm", "categorie": "longueur"},
    "JAMBE"        : {"label": "Longueur jambe (LP)",   "unite": "cm", "categorie": "longueur"},
    "CUISSE"       : {"label": "Longueur cuisse",       "unite": "cm", "categorie": "longueur"},
    "MOLLET"       : {"label": "Longueur mollet",       "unite": "cm", "categorie": "longueur"},
    "HANCHES_L"    : {"label": "Largeur hanches",       "unite": "cm", "categorie": "largeur"},
    "POITRINE"     : {"label": "Tour de poitrine (P)",  "unite": "cm", "categorie": "circonference"},
    "TAILLE"       : {"label": "Tour de taille (T)",    "unite": "cm", "categorie": "circonference"},
    "TOUR_HANCHES" : {"label": "Tour de hanches (H)",   "unite": "cm", "categorie": "circonference"},
    "TOUR_COU"     : {"label": "Tour de cou (TC)",      "unite": "cm", "categorie": "circonference"},
    "TOUR_GENOU"   : {"label": "Tour de genou (TG)",    "unite": "cm", "categorie": "circonference"},
    "TOUR_POIGNET" : {"label": "Tour de poignet (TP)",  "unite": "cm", "categorie": "circonference"},
}

# Codes intermédiaires non stockés en DB
_INTERNAL_CODES = {"PROF_BUSTE", "PROF_HANCHE", "TORSE_DOS", "TORSE_PROF",
                   "EPAULES_DOS", "HANCHES_DOS_L"}


def extraire_face(wlms: list) -> dict:
    d = lambda a, b: w3d(wlms, a, b)

    epaules  = d(L_SHOULDER, R_SHOULDER)
    hanches  = d(L_HIP,      R_HIP)
    torse    = avg(d(L_SHOULDER, L_HIP),    d(R_SHOULDER, R_HIP))
    bras     = avg(d(L_SHOULDER, L_WRIST),  d(R_SHOULDER, R_WRIST))
    haut_bras= avg(d(L_SHOULDER, L_ELBOW),  d(R_SHOULDER, R_ELBOW))
    av_bras  = avg(d(L_ELBOW,    L_WRIST),  d(R_ELBOW,    R_WRIST))
    jambe    = avg(d(L_HIP,  L_ANKLE),      d(R_HIP,  R_ANKLE))
    cuisse   = avg(d(L_HIP,  L_KNEE),       d(R_HIP,  R_KNEE))
    mollet   = avg(d(L_KNEE, L_ANKLE),      d(R_KNEE, R_ANKLE))

    my_sh  = (wlms[L_SHOULDER].y + wlms[R_SHOULDER].y) / 2
    my_an  = (wlms[L_ANKLE].y   + wlms[R_ANKLE].y)    / 2
    hauteur = round(abs(my_sh - my_an) * 100 + epaules * 0.15, 1)

    return {
        "HAUTEUR"  : (hauteur,   "face", 0.80),
        "EPAULES"  : (epaules,   "face", 0.92),
        "HANCHES_L": (hanches,   "face", 0.90),
        "TORSE"    : (torse,     "face", 0.88),
        "BRA_TOTAL": (bras,      "face", 0.85),
        "BRA_HAUT" : (haut_bras, "face", 0.87),
        "BRA_AV"   : (av_bras,   "face", 0.87),
        "JAMBE"    : (jambe,     "face", 0.88),
        "CUISSE"   : (cuisse,    "face", 0.86),
        "MOLLET"   : (mollet,    "face", 0.86),
    }


def extraire_dos(wlms: list) -> dict:
    d = lambda a, b: w3d(wlms, a, b)
    return {
        "EPAULES_DOS"  : (d(L_SHOULDER, R_SHOULDER),                          "dos", 0.90),
        "HANCHES_DOS_L": (d(L_HIP,      R_HIP),                               "dos", 0.88),
        "TORSE_DOS"    : (avg(d(L_SHOULDER, L_HIP), d(R_SHOULDER, R_HIP)),    "dos", 0.86),
    }


def extraire_profil(wlms: list) -> dict:
    prof_epaule  = round(abs(wlms[L_SHOULDER].z - wlms[R_SHOULDER].z) * 100, 1)
    prof_hanche  = round(abs(wlms[L_HIP].z      - wlms[R_HIP].z)      * 100, 1)
    torse_profil = round(abs(wlms[L_SHOULDER].y  - wlms[L_HIP].y)     * 100, 1)
    return {
        "PROF_BUSTE" : (prof_epaule,  "profil", 0.75),
        "PROF_HANCHE": (prof_hanche,  "profil", 0.75),
        "TORSE_PROF" : (torse_profil, "profil", 0.82),
    }


def fusionner(m_face: dict, m_dos: dict, m_profil: dict) -> list[dict]:
    """
    Fusionne les 3 vues, calcule les circonférences,
    retourne une liste de dicts prêts pour la DB.
    """
    raw = {**m_face, **m_dos, **m_profil}

    # Validation épaules (face + dos)
    if "EPAULES" in raw and "EPAULES_DOS" in raw:
        v = avg(raw["EPAULES"][0], raw["EPAULES_DOS"][0])
        raw["EPAULES"] = (v, "face+dos", 0.94)

    # Validation torse (face + dos + profil)
    torses = [raw[k][0] for k in ("TORSE", "TORSE_DOS", "TORSE_PROF") if k in raw]
    if torses:
        raw["TORSE"] = (avg(*torses), "face+dos+profil", 0.93)

    # Circonférences
    epaules_cm  = raw.get("EPAULES",   (0,))[0]
    hanches_cm  = raw.get("HANCHES_L", (0,))[0]
    prof_buste  = raw.get("PROF_BUSTE",  (0,))[0]
    prof_hanche = raw.get("PROF_HANCHE", (0,))[0]

    if prof_buste > 0 and epaules_cm > 0:
        a_p = epaules_cm / 2;  b_p = max(prof_buste  / 2, a_p * 0.5)
        a_h = hanches_cm / 2;  b_h = max(prof_hanche / 2, a_h * 0.5)
        tour_p = ellipse_circumference(a_p, b_p);  src_p = "ellipse(face+profil)"; conf_p = 0.88
        tour_h = ellipse_circumference(a_h, b_h);  src_h = "ellipse(face+profil)"; conf_h = 0.86
        tour_t = round(tour_h * 0.80, 1);          src_t = "ellipse+ratio";        conf_t = 0.78
    else:
        tour_p = round(epaules_cm * 3.55, 1);  src_p = "ratio_iso8559"; conf_p = 0.72
        tour_h = round(hanches_cm * 3.35, 1);  src_h = "ratio_iso8559"; conf_h = 0.72
        tour_t = round(hanches_cm * 2.80, 1);  src_t = "ratio_iso8559"; conf_t = 0.72

    oreilles_cm   = round(epaules_cm * 0.35, 1)
    mollet_cm     = raw.get("MOLLET",  (0,))[0]
    av_bras_cm    = raw.get("BRA_AV",  (0,))[0]

    raw["POITRINE"]     = (tour_p,                       src_p,     conf_p)
    raw["TAILLE"]       = (tour_t,                       src_t,     conf_t)
    raw["TOUR_HANCHES"] = (tour_h,                       src_h,     conf_h)
    raw["TOUR_COU"]     = (round(oreilles_cm * 1.73, 1), "ratio",   0.70)
    raw["TOUR_GENOU"]   = (round(mollet_cm  * 1.20, 1), "ratio",   0.72)
    raw["TOUR_POIGNET"] = (round(av_bras_cm * 0.65, 1), "ratio",   0.72)

    # Filtrage + formatage final
    result = []
    for code, (valeur, source, confiance) in raw.items():
        if code in _INTERNAL_CODES or valeur <= 0:
            continue
        meta = TYPE_MESURE_META.get(code, {"label": code, "unite": "cm", "categorie": "autre"})
        result.append({
            "type_mesure_code": code,
            "label"           : meta["label"],
            "unite"           : meta["unite"],
            "categorie"       : meta["categorie"],
            "valeur"          : valeur,
            "source"          : source,
            "confiance"       : confiance,
        })

    return result
