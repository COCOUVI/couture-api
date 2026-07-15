# Service de calcul des mesures corporelles
import logging
from typing import Optional

from app.services.pose_service import (
    NOSE, LEFT_EAR, RIGHT_EAR,
    L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW,
    L_WRIST, R_WRIST, L_HIP, R_HIP,
    L_KNEE, R_KNEE, L_ANKLE, R_ANKLE,
    w3d, avg, ellipse_circumference,
)

logger = logging.getLogger(__name__)

# Fallback : largeur d'epaules de reference (moyenne adulte)
# Utilisee uniquement quand known_height_cm n'est pas fourni.
#The ration are used to estimate the height from the shoulder width when the known height is not provided. The average shoulder width is assumed to be 39.0 cm for adults, which is used as a reference for scaling the measurements obtained from the MediaPipe landmarks, and come from anthropometric data. This value is used to calculate a scale factor that converts the raw distances measured in the MediaPipe coordinate system into real-world centimeters. The scale factor is computed by dividing the assumed shoulder width (39.0 cm) by the raw shoulder width obtained from the landmarks. This allows for an estimation of the person's height and other measurements when the actual height is not known.
ASSUMED_SHOULDER_WIDTH_CM = 39.0


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
    "CEINTURE"     : {"label": "Tour de ceinture (C)", "unite": "cm", "categorie": "circonference"},
    "TOUR_HANCHES" : {"label": "Tour de hanches (H)",   "unite": "cm", "categorie": "circonference"},
    "TOUR_COU"     : {"label": "Tour de cou (TC)",      "unite": "cm", "categorie": "circonference"},
    "TOUR_GENOU"   : {"label": "Tour de genou (TG)",    "unite": "cm", "categorie": "circonference"},
    "TOUR_POIGNET" : {"label": "Tour de poignet (TP)",  "unite": "cm", "categorie": "circonference"},
}

# Codes intermediaires utilises pour le calcul mais non stockes en DB
_INTERNAL_CODES = {
    "PROFONDEUR_BUSTE", "PROFONDEUR_HANCHE", "PROFONDEUR_CEINTURE",
    "TORSE_LONGUEUR_DOS", "TORSE_LONGUEUR_PROFIL", "EPAULES_DOS", "HANCHES_LARGEUR_DOS",
    "BUSTE_LARGEUR", "CEINTURE_LARGEUR",
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
    """Limite une valeur entre un minimum et un maximum."""
    return round(min(max(value, low), high), 1)


def _compute_scale(wlms: list, known_height_cm: Optional[float] = None) -> float:
    """
    Calcule le facteur d'echelle pour convertir les distances MediaPipe en cm reels.

    Deux modes :
    1. known_height_cm fourni -> scale = taille_connue / hauteur_brute_mediapipe
    2. fallback -> scale = 39.0 / largeur_epaules_brute
    """
    epaules_raw = w3d(wlms, L_SHOULDER, R_SHOULDER)

    if known_height_cm:
        shoulder_y = (wlms[L_SHOULDER].y + wlms[R_SHOULDER].y) / 2
        ankle_y = (wlms[L_ANKLE].y + wlms[R_ANKLE].y) / 2

        nose_to_ankle = abs(wlms[NOSE].y - ankle_y) * 100
        shoulder_to_ankle = abs(shoulder_y - ankle_y) * 100
        ear_width = w3d(wlms, LEFT_EAR, RIGHT_EAR)

        head_top_extra = max(ear_width * 0.45, epaules_raw * 0.14)
        foot_extra = max(epaules_raw * 0.07, 3.0)

        height_from_nose = nose_to_ankle + head_top_extra + foot_extra
        height_from_shoulders = shoulder_to_ankle / 0.82

        raw_height = (height_from_nose * 0.65) + (height_from_shoulders * 0.35)
        scale = known_height_cm / max(raw_height, 1.0)
        logger.info("Calibration via taille connue: %.1f cm → facteur %.2f", known_height_cm, scale)
        return scale

    scale = ASSUMED_SHOULDER_WIDTH_CM / max(epaules_raw, 1.0)
    logger.info("Calibration via epaules: brute %.1f cm, facteur %.2f", epaules_raw, scale)
    return scale


def extraire_face(wlms: list, known_height_cm: Optional[float] = None) -> dict:
    """Mesures depuis la vue de face : longueurs, largeurs, hauteur."""
    distance_landmarks = lambda a, b: w3d(wlms, a, b)
    scale = _compute_scale(wlms, known_height_cm)
    distance_landmarks_scaled = lambda a, b: round(distance_landmarks(a, b) * scale, 1)

    largeur_hanches = distance_landmarks_scaled(L_HIP, R_HIP)
    largeur_buste = round(_interpolated_torso_width(wlms, 0.30) * scale, 1)
    largeur_ceinture = round(_interpolated_torso_width(wlms, 0.62) * scale, 1)
    longueur_torse = avg(distance_landmarks_scaled(L_SHOULDER, L_HIP), distance_landmarks_scaled(R_SHOULDER, R_HIP))
    longueur_bras_total = avg(distance_landmarks_scaled(L_SHOULDER, L_WRIST), distance_landmarks_scaled(R_SHOULDER, R_WRIST))
    longueur_bras_haut = avg(distance_landmarks_scaled(L_SHOULDER, L_ELBOW), distance_landmarks_scaled(R_SHOULDER, R_ELBOW))
    longueur_avant_bras = avg(distance_landmarks_scaled(L_ELBOW, L_WRIST), distance_landmarks_scaled(R_ELBOW, R_WRIST))
    longueur_jambe = avg(distance_landmarks_scaled(L_HIP, L_ANKLE), distance_landmarks_scaled(R_HIP, R_ANKLE))
    longueur_cuisse = avg(distance_landmarks_scaled(L_HIP, L_KNEE), distance_landmarks_scaled(R_HIP, R_KNEE))
    longueur_mollet = avg(distance_landmarks_scaled(L_KNEE, L_ANKLE), distance_landmarks_scaled(R_KNEE, R_ANKLE))

    # Hauteur : calculee a partir des memes donnees brutes, puis scalée via _compute_scale
    shoulder_y = (wlms[L_SHOULDER].y + wlms[R_SHOULDER].y) / 2
    ankle_y = (wlms[L_ANKLE].y + wlms[R_ANKLE].y) / 2
    nose_to_ankle = abs(wlms[NOSE].y - ankle_y) * 100 * scale
    shoulder_to_ankle = abs(shoulder_y - ankle_y) * 100 * scale
    ear_width = w3d(wlms, LEFT_EAR, RIGHT_EAR) * scale
    largeur_epaules_scaled = w3d(wlms, L_SHOULDER, R_SHOULDER) * scale
    head_top_extra = max(ear_width * 0.45, largeur_epaules_scaled * 0.14)
    foot_extra = max(largeur_epaules_scaled * 0.07, 3.0)
    height_from_nose = nose_to_ankle + head_top_extra + foot_extra
    height_from_shoulders = shoulder_to_ankle / 0.82
    hauteur = round((height_from_nose * 0.65) + (height_from_shoulders * 0.35), 1)

    return {
        "HAUTEUR"          : (hauteur,   "face_stature", 0.84),
        "EPAULES"          : (round(largeur_epaules_scaled, 1), "face", 0.92),
        "BUSTE_LARGEUR"    : (largeur_buste,   "face", 0.82),
        "CEINTURE_LARGEUR" : (largeur_ceinture, "face", 0.84),
        "HANCHES_L"        : (largeur_hanches,   "face", 0.90),
        "TORSE"            : (longueur_torse,     "face", 0.88),
        "BRA_TOTAL"        : (longueur_bras_total,      "face", 0.85),
        "BRA_HAUT"         : (longueur_bras_haut, "face", 0.87),
        "BRA_AV"           : (longueur_avant_bras,   "face", 0.87),
        "JAMBE"            : (longueur_jambe,     "face", 0.88),
        "CUISSE"           : (longueur_cuisse,    "face", 0.86),
        "MOLLET"           : (longueur_mollet,    "face", 0.86),
    }


def extraire_dos(wlms: list, known_height_cm: Optional[float] = None) -> dict:
    """Mesures depuis la vue de dos : validation largeurs epaules, hanches, torse."""
    distance_landmarks = lambda a, b: w3d(wlms, a, b)
    scale = _compute_scale(wlms, known_height_cm)
    distance_landmarks_scaled = lambda a, b: round(distance_landmarks(a, b) * scale, 1)
    return {
        "EPAULES_DOS"          : (round(w3d(wlms, L_SHOULDER, R_SHOULDER) * scale, 1), "dos", 0.90),
        "HANCHES_LARGEUR_DOS"  : (distance_landmarks_scaled(L_HIP, R_HIP), "dos", 0.88),
        "TORSE_LONGUEUR_DOS"   : (avg(distance_landmarks_scaled(L_SHOULDER, L_HIP), distance_landmarks_scaled(R_SHOULDER, R_HIP)), "dos", 0.86),
    }


def extraire_profil(wlms: list, known_height_cm: Optional[float] = None) -> dict:
    """Mesures depuis la vue de profil : profondeurs buste, taille, hanches."""
    profondeur_buste = round(abs(wlms[L_SHOULDER].z - wlms[R_SHOULDER].z) * 100, 1)
    profondeur_ceinture = _interpolated_torso_depth(wlms, 0.62)
    profondeur_hanche = round(abs(wlms[L_HIP].z - wlms[R_HIP].z) * 100, 1)
    longueur_torse_profil = round(abs(wlms[L_SHOULDER].y - wlms[L_HIP].y) * 100, 1)

    scale = _compute_scale(wlms, known_height_cm)

    return {
        "PROFONDEUR_BUSTE"       : (round(profondeur_buste * scale, 1),    "profil", 0.75),
        "PROFONDEUR_CEINTURE"    : (round(profondeur_ceinture * scale, 1), "profil", 0.78),
        "PROFONDEUR_HANCHE"      : (round(profondeur_hanche * scale, 1),   "profil", 0.75),
        "TORSE_LONGUEUR_PROFIL"  : (round(longueur_torse_profil * scale, 1),"profil", 0.82),
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

    torses = [raw[k][0] for k in ("TORSE", "TORSE_LONGUEUR_DOS", "TORSE_LONGUEUR_PROFIL") if k in raw]
    if torses:
        raw["TORSE"] = (avg(*torses), "face+dos+profil", 0.93)

    largeur_epaules = raw.get("EPAULES", (0,))[0]
    largeur_buste = raw.get("BUSTE_LARGEUR", (0,))[0] or largeur_epaules * 0.86
    largeur_ceinture = raw.get("CEINTURE_LARGEUR", (0,))[0]
    largeur_hanches = raw.get("HANCHES_L", (0,))[0]
    profondeur_buste = raw.get("PROFONDEUR_BUSTE", (0,))[0]
    profondeur_ceinture = raw.get("PROFONDEUR_CEINTURE", (0,))[0]
    profondeur_hanche = raw.get("PROFONDEUR_HANCHE", (0,))[0]

    if profondeur_buste > 0 and profondeur_ceinture > 0 and largeur_buste > 0 and largeur_ceinture > 0:
        # Calcul par ellipse (Ramanujan) : largeur = grand axe, profondeur = petit axe.
        demi_largeur_buste = largeur_buste / 2
        demi_profondeur_buste = max(profondeur_buste / 2, demi_largeur_buste * 0.45)
        demi_largeur_ceinture = largeur_ceinture / 2
        demi_profondeur_ceinture = max(profondeur_ceinture / 2, demi_largeur_ceinture * 0.45)
        demi_largeur_hanches = largeur_hanches / 2
        demi_profondeur_hanches = max(profondeur_hanche / 2, demi_largeur_hanches * 0.50)
        tour_poitrine = ellipse_circumference(demi_largeur_buste, demi_profondeur_buste)
        tour_ceinture = ellipse_circumference(demi_largeur_ceinture, demi_profondeur_ceinture)
        tour_hanches = ellipse_circumference(demi_largeur_hanches, demi_profondeur_hanches)
        source_poitrine = source_ceinture = source_hanches = "ellipse(face+profil)"
        confiance_poitrine = 0.88
        confiance_ceinture = 0.86
        confiance_hanches = 0.86
    else:
        # Fallback : ratios approximatifs quand la vue profil manque.
        tour_poitrine = round(largeur_buste * 3.35, 1)
        tour_hanches = round(largeur_hanches * 3.35, 1)
        tour_ceinture = round((largeur_ceinture or largeur_hanches * 0.82) * 3.20, 1)
        source_poitrine = source_ceinture = source_hanches = "ratio_iso8559"
        confiance_poitrine = confiance_ceinture = confiance_hanches = 0.72

    if tour_poitrine > 0 and tour_hanches > 0 and tour_ceinture > 0:
        # Garde-fou morphologique contre les petites rotations et poses asymetriques.
        min_tour_ceinture = min(tour_poitrine, tour_hanches) * 0.62
        max_tour_ceinture = min(tour_poitrine, tour_hanches) * 1.03
        tour_ceinture = _clamp(tour_ceinture, min_tour_ceinture, max_tour_ceinture)

    largeur_oreilles = round(largeur_epaules * 0.35, 1)
    longueur_mollet = raw.get("MOLLET", (0,))[0]
    longueur_avant_bras = raw.get("BRA_AV", (0,))[0]

    raw["POITRINE"] = (tour_poitrine, source_poitrine, confiance_poitrine)
    raw["CEINTURE"] = (tour_ceinture, source_ceinture, confiance_ceinture)
    raw["TOUR_HANCHES"] = (tour_hanches, source_hanches, confiance_hanches)
    raw["TOUR_COU"] = (round(largeur_oreilles * 1.73, 1), "ratio", 0.70)
    raw["TOUR_GENOU"] = (round(longueur_mollet * 1.20, 1), "ratio", 0.72)
    raw["TOUR_POIGNET"] = (round(longueur_avant_bras * 0.65, 1), "ratio", 0.72)

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
