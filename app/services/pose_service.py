# ── Service de détection de pose via MediaPipe ───────────────────────
import math
import os
import urllib.request

import cv2
import mediapipe as mp
import numpy as np

from app.core.config import settings

# ── Téléchargement automatique du modèle ────────────────────────────
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task"
)


def ensure_model():
    """Télécharge le modèle MediaPipe s'il n'existe pas encore."""
    if not os.path.exists(settings.MODEL_PATH):
        print(f"  Téléchargement du modèle MediaPipe → {settings.MODEL_PATH}")
        urllib.request.urlretrieve(MODEL_URL, settings.MODEL_PATH)
        print(" Modèle prêt.")


# Indices des landmarks MediaPipe Pose
# la convention est definie par le modèle MediaPipe Pose Landmarker par defaut 


NOSE = 0
LEFT_EAR = 7;    RIGHT_EAR = 8       # Oreilles
L_SHOULDER = 11; R_SHOULDER = 12     # Épaules
L_ELBOW = 13;    R_ELBOW = 14        # Coudes
L_WRIST = 15;    R_WRIST = 16        # Poignets
L_HIP = 23;      R_HIP = 24          # Hanches
L_KNEE = 25;     R_KNEE = 26         # Genoux
L_ANKLE = 27;    R_ANKLE = 28        # Chevilles


# Alias vers l'API Tasks de MediaPipe
BaseOptions           = mp.tasks.BaseOptions
PoseLandmarker        = mp.tasks.vision.PoseLandmarker
PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
VisionRunningMode     = mp.tasks.vision.RunningMode


# ── Cache du detecteur (cree une seule fois) ─────────────────────────
_detector = None


def _get_detector():
    """Retourne le PoseLandmarker global (cree une seule fois)."""
    global _detector
    if _detector is None:
        ensure_model()
        opts = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=settings.MODEL_PATH),
            running_mode=VisionRunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=settings.MIN_CONFIDENCE,
            min_pose_presence_confidence=settings.MIN_CONFIDENCE,
            min_tracking_confidence=settings.MIN_CONFIDENCE,
        )
        _detector = PoseLandmarker.create_from_options(opts)
        logger = __import__('logging').getLogger(__name__)
        logger.info("PoseLandmarker cree (modele charge en memoire)")
    return _detector


#  Détection principale 
def detect_world_landmarks(img_rgb: np.ndarray) -> list:
    """
    Détecte la pose sur une image RGB numpy array.
    Retourne les world_landmarks (coordonnées 3D en mètres).
    Lève une ValueError si aucune pose n'est détectée.
    """
    detector = _get_detector()

    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
    result   = detector.detect(mp_image)

    if not result.pose_world_landmarks:
        raise ValueError("Pose non détectée — vérifiez que la personne est entièrement visible.")

    return result.pose_world_landmarks[0]


# ── Outils mathématiques ─────────────────────────────────────────────
def w3d(wlms: list, a: int, b: int) -> float:
    """Distance 3D en cm entre deux world_landmarks."""
    la, lb = wlms[a], wlms[b]
    return round(
        math.sqrt((la.x - lb.x) ** 2 + (la.y - lb.y) ** 2 + (la.z - lb.z) ** 2) * 100,
        1,
    )


def avg(*values: float) -> float:
    """Moyenne arrondie à 1 décimale."""
    return round(sum(values) / len(values), 1)


def ellipse_circumference(a: float, b: float) -> float:
    """Périmètre d'une ellipse (formule de Ramanujan), a et b en cm."""
    return round(math.pi * (3 * (a + b) - math.sqrt((3 * a + b) * (a + 3 * b))), 1)
