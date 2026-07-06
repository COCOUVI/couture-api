# ── Route de santé — GET /health ─────────────────────────────────────
from fastapi import APIRouter
from app.core.config import settings
from app.core.database import check_db_connection

router = APIRouter(tags=["Sante"])


@router.get("/health")
def health_check():
    """Verifie que l'API et la DB sont operationnelles."""
    db_ok = check_db_connection()
    return {
        "statut": "ok" if db_ok else "degrage",
        "environnement": settings.ENVIRONMENT,
        "version": "1.0.0",
        "db_connectee": db_ok,
    }
