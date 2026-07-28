"""Détection de pose MediaPipe et outils géométriques partagés."""

import logging
import math
import os
import urllib.request

import cv2
import mediapipe as mp
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task"
)


def ensure_model() -> None:
    """Télécharge le modèle MediaPipe si le fichier local est absent."""
    if not os.path.exists(settings.MODEL_PATH):
        logger.info("Téléchargement du modèle MediaPipe - %s", settings.MODEL_PATH)
        urllib.request.urlretrieve(MODEL_URL, settings.MODEL_PATH)
        logger.info("Modèle MediaPipe prêt.")


NOSE         = 0
LEFT_EAR     = 7
RIGHT_EAR    = 8

L_SHOULDER   = 11;  R_SHOULDER   = 12   # Épaules
L_ELBOW      = 13;  R_ELBOW      = 14   # Coudes
L_WRIST      = 15;  R_WRIST      = 16   # Poignets

L_HIP        = 23;  R_HIP        = 24   # Hanches

L_KNEE       = 25;  R_KNEE       = 26   # Genoux
L_ANKLE      = 27;  R_ANKLE      = 28   # Chevilles
L_HEEL       = 29;  R_HEEL       = 30   # Talons (utilisés pour la hauteur sol - genou)
L_FOOT_INDEX = 31;  R_FOOT_INDEX = 32   # Orteils (pointe du pied)

BaseOptions           = mp.tasks.BaseOptions
PoseLandmarker        = mp.tasks.vision.PoseLandmarker
PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
VisionRunningMode     = mp.tasks.vision.RunningMode


_detector: PoseLandmarker | None = None


def _get_detector() -> PoseLandmarker:
    """Retourne l'instance unique du détecteur de pose."""
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


def detect_world_landmarks(img_rgb: np.ndarray) -> list:
    """Détecte la pose sur une image RGB et retourne les world_landmarks."""
    detector = _get_detector()
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
    result = detector.detect(mp_image)

    if not result.pose_world_landmarks:
        raise ValueError(
            "Aucune pose détectée. "
            "Vérifiez que la personne est entièrement visible sur la photo."
        )

    return result.pose_world_landmarks[0]


def w3d(world_landmarks: list, index_a: int, index_b: int) -> float:
    """Calcule la distance 3D entre deux landmarks, en centimètres."""
    point_a = world_landmarks[index_a]
    point_b = world_landmarks[index_b]
    distance_metres = math.sqrt(
        (point_a.x - point_b.x) ** 2
        + (point_a.y - point_b.y) ** 2
        + (point_a.z - point_b.z) ** 2
    )
    return round(distance_metres * 100, 1)


def avg(*valeurs: float) -> float:
    """Calcule la moyenne arithmétique de valeurs numériques."""
    return round(sum(valeurs) / len(valeurs), 1)


def ellipse_circumference(demi_axe_a: float, demi_axe_b: float) -> float:
    """Approxime le périmètre d'une ellipse avec la formule de Ramanujan."""
    return round(
        math.pi * (
            3 * (demi_axe_a + demi_axe_b)
            - math.sqrt((3 * demi_axe_a + demi_axe_b) * (demi_axe_a + 3 * demi_axe_b))
        ),
        1,
    )
