"""Route de santé de l'API."""
from fastapi import APIRouter
from app.core.config import settings
from app.core.database import check_db_connection

router = APIRouter(tags=["Sante"])


@router.get("/health")
def health_check():
    """Indique si l'API et la base de données répondent correctement."""
    db_ok = check_db_connection()
    return {
        "statut": "ok" if db_ok else "degrage",
        "environnement": settings.ENVIRONMENT,
        "version": "1.0.0",
        "db_connectee": db_ok,
    }
