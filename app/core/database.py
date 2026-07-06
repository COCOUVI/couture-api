# ── Configuration de la base de données PostgreSQL (Supabase) ────────
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Connexion SSL (obligatoire pour Supabase) ────────────────────────
connect_args = {}
if "supabase" in settings.DATABASE_URL.lower() or "sslmode" not in settings.DATABASE_URL:
    connect_args["sslmode"] = "require"

# ── Moteur SQLAlchemy avec pool de connexions ────────────────────────
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,      # Vérifie la connexion avant utilisation
    pool_size=5,              # 5 connexions dans le pool
    max_overflow=10,          # 10 connexions supplémentaires si nécessaire
    connect_args=connect_args,
)

# ── Factory de sessions ──────────────────────────────────────────────
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── Classe de base pour les modèles ORM ──────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Dépendance FastAPI — injection de session DB ─────────────────────
def get_db():
    """Fournit une session SQLAlchemy (utilisée comme dépendance FastAPI)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Test de connexion ────────────────────────────────────────────────
def check_db_connection() -> bool:
    """Teste la connexion à la base de donnees."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Connexion DB reussie")
        return True
    except Exception as e:
        logger.error("Connexion DB echouee: %s", e)
        return False
