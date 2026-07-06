# ── Configuration via variables d'environnement (.env) ───────────────
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variables d'environnement chargées depuis .env ou les variables système."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Base de données PostgreSQL (Supabase) ─────────────────────────
    DATABASE_URL: str

    # ── Sécurité ──────────────────────────────────────────────────────
    SECRET_KEY: str = "dev_secret_key"

    # ── Environnement ─────────────────────────────────────────────────
    ENVIRONMENT: str = "development"

    # ── MediaPipe ─────────────────────────────────────────────────────
    MODEL_PATH: str = "pose_landmarker_heavy.task"   # Fichier modèle pré-téléchargé
    MIN_CONFIDENCE: float = 0.5                      # Seuil de confiance minimale

    # ── Cloudinary (suppression des images après traitement) ──────────
    CLOUDINARY_CLOUD_NAME: str = "dvne7dd7h"          # Nom du cloud (fixe)
    CLOUDINARY_API_KEY: str = ""                       # Optionnel : clé API
    CLOUDINARY_API_SECRET: str = ""                    # Optionnel : secret API


# Instance singleton des settings
settings = Settings()
