# Service de calcul des mesures corporelles
from app.services.pose_service import (
    NOSE, LEFT_EAR, RIGHT_EAR,
    L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW,
    L_WRIST, R_WRIST, L_HIP, R_HIP,
    L_KNEE, R_KNEE, L_ANKLE, R_ANKLE,
    w3d, avg, ellipse_circumference,
)

'''
 estimate the torse because mediapipe does not give the landmarks for the front and back of the torso, we need to estimate it from the landmarks we have. We can use the shoulder and hip landmarks to estimate the width and depth of the torso at different heights. We can also use the nose and ankle landmarks to estimate the height of the person. We can then combine these estimates to get a final set of measurements for the person.
'''


# Metadonnees des 16 mesures finales (doit correspondre aux TypeMesure.code en DB)
TYPE_MESURE_META = {
    "HAUTEUR"      : {"label": "Hauteur totale",        "unite": "cm", "categorie": "longueur"},
    "EPAULES"      : {"label": "Largeur epaules (E)",   "unite": "cm", "categorie": "largeur"},
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

# Codes intermediaires utilises pour le calcul mais non stockes en DB
_INTERNAL_CODES = {
    "PROF_BUSTE", "PROF_HANCHE", "PROF_TAILLE",
    "TORSE_DOS", "TORSE_PROF", "EPAULES_DOS", "HANCHES_DOS_L",
    "BUSTE_L", "TAILLE_L",
}


def _point_between(a, b, ratio: float) -> tuple[float, float, float]:
    """Point 3D interpole entre deux landmarks MediaPipe."""
    return (
        a.x + (b.x - a.x) * ratio,
        a.y + (b.y - a.y) * ratio,
        a.z + (b.z - a.z) * ratio,
    )


def _distance_cm(p1: tuple[float, float, float], p2: tuple[float, float, float]) -> float:
    """Distance 3D en cm entre deux points (x, y, z)."""
    return round(
        ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2 + (p1[2] - p2[2]) ** 2) ** 0.5 * 100,
        1,
    )


def _interpolated_torso_width(wlms: list, ratio: float) -> float:
    """Largeur du torse a une hauteur donnee entre epaules et hanches."""
    left = _point_between(wlms[L_SHOULDER], wlms[L_HIP], ratio)
    right = _point_between(wlms[R_SHOULDER], wlms[R_HIP], ratio)
    return _distance_cm(left, right)


def _interpolated_torso_depth(wlms: list, ratio: float) -> float:
    """Profondeur laterale a une hauteur donnee entre epaules et hanches."""
    left = _point_between(wlms[L_SHOULDER], wlms[L_HIP], ratio)
    right = _point_between(wlms[R_SHOULDER], wlms[R_HIP], ratio)
    return round(abs(left[2] - right[2]) * 100, 1)


def _clamp(value: float, low: float, high: float) -> float:
    return round(min(max(value, low), high), 1)


def _estimate_body_height(wlms: list, shoulder_width_cm: float) -> float:
    """
    Estime la taille reelle (stature) depuis la vue de face.

    MediaPipe ne donne pas le sommet du crane ni le sol sous les pieds.
    On combine donc deux estimations:
    - nez -> chevilles + correction sommet du crane + correction pieds;
    - epaules -> chevilles converti par ratio anthropometrique.
    """
    shoulder_y = (wlms[L_SHOULDER].y + wlms[R_SHOULDER].y) / 2
    ankle_y = (wlms[L_ANKLE].y + wlms[R_ANKLE].y) / 2

    nose_to_ankle = abs(wlms[NOSE].y - ankle_y) * 100
    shoulder_to_ankle = abs(shoulder_y - ankle_y) * 100
    ear_width = w3d(wlms, LEFT_EAR, RIGHT_EAR)

    head_top_extra = max(ear_width * 0.45, shoulder_width_cm * 0.14)
    foot_extra = max(shoulder_width_cm * 0.07, 3.0)

    height_from_nose = nose_to_ankle + head_top_extra + foot_extra
    height_from_shoulders = shoulder_to_ankle / 0.82

    estimated = (height_from_nose * 0.65) + (height_from_shoulders * 0.35)
    min_height = shoulder_to_ankle * 1.08
    max_height = shoulder_to_ankle * 1.30
    return _clamp(estimated, min_height, max_height)


def extraire_face(wlms: list) -> dict:
    """Calcule les mesures depuis la vue de face (longueurs, largeurs)."""
    d = lambda a, b: w3d(wlms, a, b)

    epaules = d(L_SHOULDER, R_SHOULDER)
    hanches = d(L_HIP, R_HIP)
    buste_l = _interpolated_torso_width(wlms, 0.30)
    taille_l = _interpolated_torso_width(wlms, 0.62)
    torse = avg(d(L_SHOULDER, L_HIP), d(R_SHOULDER, R_HIP))
    bras = avg(d(L_SHOULDER, L_WRIST), d(R_SHOULDER, R_WRIST))
    haut_bras = avg(d(L_SHOULDER, L_ELBOW), d(R_SHOULDER, R_ELBOW))
    av_bras = avg(d(L_ELBOW, L_WRIST), d(R_ELBOW, R_WRIST))
    jambe = avg(d(L_HIP, L_ANKLE), d(R_HIP, R_ANKLE))
    cuisse = avg(d(L_HIP, L_KNEE), d(R_HIP, R_KNEE))
    mollet = avg(d(L_KNEE, L_ANKLE), d(R_KNEE, R_ANKLE))

    hauteur = _estimate_body_height(wlms, epaules)

    return {
        "HAUTEUR"  : (hauteur,   "face_stature", 0.84),
        "EPAULES"  : (epaules,   "face", 0.92),
        "BUSTE_L"  : (buste_l,   "face", 0.82),
        "TAILLE_L" : (taille_l,  "face", 0.84),
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
    """Calcule les mesures depuis la vue de dos (validation des largeurs)."""
    d = lambda a, b: w3d(wlms, a, b)
    return {
        "EPAULES_DOS"  : (d(L_SHOULDER, R_SHOULDER),                       "dos", 0.90),
        "HANCHES_DOS_L": (d(L_HIP, R_HIP),                                  "dos", 0.88),
        "TORSE_DOS"    : (avg(d(L_SHOULDER, L_HIP), d(R_SHOULDER, R_HIP)),  "dos", 0.86),
    }


def extraire_profil(wlms: list) -> dict:
    """Calcule les profondeurs (axe Z) depuis la vue de profil."""
    prof_epaule = round(abs(wlms[L_SHOULDER].z - wlms[R_SHOULDER].z) * 100, 1)
    prof_taille = _interpolated_torso_depth(wlms, 0.62)
    prof_hanche = round(abs(wlms[L_HIP].z - wlms[R_HIP].z) * 100, 1)
    torse_profil = round(abs(wlms[L_SHOULDER].y - wlms[L_HIP].y) * 100, 1)
    return {
        "PROF_BUSTE" : (prof_epaule,  "profil", 0.75),
        "PROF_TAILLE": (prof_taille,  "profil", 0.78),
        "PROF_HANCHE": (prof_hanche,  "profil", 0.75),
        "TORSE_PROF" : (torse_profil, "profil", 0.82),
    }


def fusionner(m_face: dict, m_dos: dict, m_profil: dict) -> list[dict]:
    """
    Fusionne les 3 vues, calcule les circonferences,
    retourne une liste de dicts prets pour la DB.
    """
    raw = {**m_face, **m_dos, **m_profil}

    if "EPAULES" in raw and "EPAULES_DOS" in raw:
        v = avg(raw["EPAULES"][0], raw["EPAULES_DOS"][0])
        raw["EPAULES"] = (v, "face+dos", 0.94)

    torses = [raw[k][0] for k in ("TORSE", "TORSE_DOS", "TORSE_PROF") if k in raw]
    if torses:
        raw["TORSE"] = (avg(*torses), "face+dos+profil", 0.93)

    epaules_cm = raw.get("EPAULES", (0,))[0]
    buste_cm = raw.get("BUSTE_L", (0,))[0] or epaules_cm * 0.86
    taille_cm = raw.get("TAILLE_L", (0,))[0]
    hanches_cm = raw.get("HANCHES_L", (0,))[0]
    prof_buste = raw.get("PROF_BUSTE", (0,))[0]
    prof_taille = raw.get("PROF_TAILLE", (0,))[0]
    prof_hanche = raw.get("PROF_HANCHE", (0,))[0]

    if prof_buste > 0 and prof_taille > 0 and buste_cm > 0 and taille_cm > 0:
        # Calcul par ellipse (Ramanujan) : largeur = grand axe, profondeur = petit axe.
        a_p = buste_cm / 2
        b_p = max(prof_buste / 2, a_p * 0.45)
        a_t = taille_cm / 2
        b_t = max(prof_taille / 2, a_t * 0.45)
        a_h = hanches_cm / 2
        b_h = max(prof_hanche / 2, a_h * 0.50)
        tour_p = ellipse_circumference(a_p, b_p)
        tour_t = ellipse_circumference(a_t, b_t)
        tour_h = ellipse_circumference(a_h, b_h)
        src_p = src_t = src_h = "ellipse(face+profil)"
        conf_p = 0.88
        conf_t = 0.86
        conf_h = 0.86
    else:
        # Fallback : ratios approximatifs quand la vue profil manque.
        tour_p = round(buste_cm * 3.35, 1)
        tour_h = round(hanches_cm * 3.35, 1)
        tour_t = round((taille_cm or hanches_cm * 0.82) * 3.20, 1)
        src_p = src_t = src_h = "ratio_iso8559"
        conf_p = conf_t = conf_h = 0.72

    if tour_p > 0 and tour_h > 0 and tour_t > 0:
        # Garde-fou morphologique contre les petites rotations et poses asymetriques.
        min_taille = min(tour_p, tour_h) * 0.62
        max_taille = min(tour_p, tour_h) * 1.03
        tour_t = _clamp(tour_t, min_taille, max_taille)

    oreilles_cm = round(epaules_cm * 0.35, 1)
    mollet_cm = raw.get("MOLLET", (0,))[0]
    av_bras_cm = raw.get("BRA_AV", (0,))[0]

    raw["POITRINE"] = (tour_p, src_p, conf_p)
    raw["TAILLE"] = (tour_t, src_t, conf_t)
    raw["TOUR_HANCHES"] = (tour_h, src_h, conf_h)
    raw["TOUR_COU"] = (round(oreilles_cm * 1.73, 1), "ratio", 0.70)
    raw["TOUR_GENOU"] = (round(mollet_cm * 1.20, 1), "ratio", 0.72)
    raw["TOUR_POIGNET"] = (round(av_bras_cm * 0.65, 1), "ratio", 0.72)

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
