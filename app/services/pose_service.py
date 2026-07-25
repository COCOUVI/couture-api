# =============================================================================
# Service de détection de pose via MediaPipe Pose Landmarker
# =============================================================================
# Responsabilités :
#   - Téléchargement automatique du modèle MediaPipe (une seule fois)
#   - Instanciation et mise en cache du PoseLandmarker (singleton)
#   - Détection des world_landmarks 3D (coordonnées en mètres, référentiel hanche)
#   - Outils géométriques partagés (distance, moyenne, périmètre d'ellipse)
#
# Référence des indices : MediaPipe Pose Landmarker — 33 points anatomiques
# https://developers.google.com/mediapipe/solutions/vision/pose_landmarker
# =============================================================================

import logging
import math
import os
import urllib.request

import cv2
import mediapipe as mp
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# URL et chemin du modèle MediaPipe (heavy = meilleure précision)
# -----------------------------------------------------------------------------
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task"
)


def ensure_model() -> None:
    """Télécharge le modèle MediaPipe si absent du disque local."""
    if not os.path.exists(settings.MODEL_PATH):
        logger.info("Téléchargement du modèle MediaPipe → %s", settings.MODEL_PATH)
        urllib.request.urlretrieve(MODEL_URL, settings.MODEL_PATH)
        logger.info("Modèle MediaPipe prêt.")


# -----------------------------------------------------------------------------
# Indices des 33 landmarks MediaPipe Pose Landmarker
# Convention officielle — ne pas modifier sans mettre à jour measurement_service
# -----------------------------------------------------------------------------

# Visage
NOSE         = 0
LEFT_EAR     = 7
RIGHT_EAR    = 8

# Membres supérieurs
L_SHOULDER   = 11;  R_SHOULDER   = 12   # Épaules
L_ELBOW      = 13;  R_ELBOW      = 14   # Coudes
L_WRIST      = 15;  R_WRIST      = 16   # Poignets

# Tronc
L_HIP        = 23;  R_HIP        = 24   # Hanches

# Membres inférieurs
L_KNEE       = 25;  R_KNEE       = 26   # Genoux
L_ANKLE      = 27;  R_ANKLE      = 28   # Chevilles
L_HEEL       = 29;  R_HEEL       = 30   # Talons  (utilisés pour la hauteur sol → genou)
L_FOOT_INDEX = 31;  R_FOOT_INDEX = 32   # Orteils (pointe du pied)

# -----------------------------------------------------------------------------
# Alias vers l'API Tasks de MediaPipe
# -----------------------------------------------------------------------------
BaseOptions           = mp.tasks.BaseOptions
PoseLandmarker        = mp.tasks.vision.PoseLandmarker
PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
VisionRunningMode     = mp.tasks.vision.RunningMode


# -----------------------------------------------------------------------------
# Singleton du détecteur (instancié une seule fois au premier appel)
# -----------------------------------------------------------------------------
_detector: PoseLandmarker | None = None


def _get_detector() -> PoseLandmarker:
    """
    Retourne le PoseLandmarker global.
    Le modèle est chargé en mémoire une seule fois (pattern singleton),
    ce qui évite de recharger ~25 Mo à chaque requête.
    """
    global _detector
    if _detector is None:
        ensure_model()
        options = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=settings.MODEL_PATH),
            running_mode=VisionRunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=settings.MIN_CONFIDENCE,
            min_pose_presence_confidence=settings.MIN_CONFIDENCE,
            min_tracking_confidence=settings.MIN_CONFIDENCE,
        )
        _detector = PoseLandmarker.create_from_options(options)
        logger.info("PoseLandmarker initialisé (modèle chargé en mémoire).")
    return _detector


# -----------------------------------------------------------------------------
# Détection principale
# -----------------------------------------------------------------------------
def detect_world_landmarks(img_rgb: np.ndarray) -> list:
    """
    Détecte la pose sur une image RGB (numpy array H×W×3).

    Retourne les world_landmarks de la première pose détectée.
    Les world_landmarks sont des coordonnées 3D métriques (en mètres),
    centrées sur la hanche — indépendantes de la taille de l'image.

    Lève ValueError si aucune pose n'est détectée (personne absente,
    image trop sombre, occlusion majeure, etc.).
    """
    detector  = _get_detector()
    mp_image  = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
    result    = detector.detect(mp_image)

    if not result.pose_world_landmarks:
        raise ValueError(
            "Aucune pose détectée. "
            "Vérifiez que la personne est entièrement visible sur la photo."
        )

    return result.pose_world_landmarks[0]


# -----------------------------------------------------------------------------
# Outils géométriques partagés
# -----------------------------------------------------------------------------

def w3d(world_landmarks: list, index_a: int, index_b: int) -> float:
    """
    Distance euclidienne 3D entre deux world_landmarks, exprimée en cm.

    Les coordonnées MediaPipe sont en mètres → multiplication par 100.
    Le résultat est arrondi à 1 décimale.
    """
    point_a = world_landmarks[index_a]
    point_b = world_landmarks[index_b]
    distance_metres = math.sqrt(
        (point_a.x - point_b.x) ** 2
        + (point_a.y - point_b.y) ** 2
        + (point_a.z - point_b.z) ** 2
    )
    return round(distance_metres * 100, 1)


def avg(*valeurs: float) -> float:
    """Moyenne arithmétique d'une liste de valeurs, arrondie à 1 décimale."""
    return round(sum(valeurs) / len(valeurs), 1)


def ellipse_circumference(demi_axe_a: float, demi_axe_b: float) -> float:
    """
    Périmètre approché d'une ellipse par la formule de Ramanujan (1914).

    P ≈ π × [3(a+b) − √((3a+b)(a+3b))]
    Précision < 0.04 % pour tout rapport a/b.

    Paramètres :
        demi_axe_a : premier demi-axe en cm (ex. demi-largeur buste)
        demi_axe_b : second demi-axe en cm  (ex. demi-profondeur buste)

    Retourne le périmètre en cm, arrondi à 1 décimale.
    """
    return round(
        math.pi * (
            3 * (demi_axe_a + demi_axe_b)
            - math.sqrt((3 * demi_axe_a + demi_axe_b) * (demi_axe_a + 3 * demi_axe_b))
        ),
        1,
    )
