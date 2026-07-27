"""Configuration SQLAlchemy et accès à la base PostgreSQL."""
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

connect_args = {}
if "supabase" in settings.DATABASE_URL.lower() or "sslmode" not in settings.DATABASE_URL:
    connect_args["sslmode"] = "require"

database_url = settings.DATABASE_URL
if database_url.startswith("postgresql://") and "+psycopg" not in database_url:
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(
    database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Classe de base SQLAlchemy utilisée par les modèles ORM."""
    pass


def get_db():
    """Fournit une session SQLAlchemy utilisée comme dépendance FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """Teste la connexion à la base de données et retourne un booléen."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Connexion DB reussie")
        return True
    except Exception as e:
        logger.error("Connexion DB echouee: %s", e)
        return False
