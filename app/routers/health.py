from fastapi import APIRouter
from app.core.config import settings

router = APIRouter(tags=["Santé"])


@router.get("/health")
def health_check():
    """Vérifie que l'API est opérationnelle."""
    return {
        "statut"      : "ok",
        "environnement": settings.ENVIRONMENT,
        "version"     : "1.0.0",
    }
