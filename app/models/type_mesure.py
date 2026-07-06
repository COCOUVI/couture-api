# ── Modèle ORM : table "type_mesures" (référentiel des mesures) ──────
from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class TypeMesure(Base):
    """Référentiel des 16 types de mesures (seedé par Laravel, lu par FastAPI)."""
    __tablename__ = "type_mesures"
    __table_args__ = {"extend_existing": True}

    id          = Column(Integer, primary_key=True, autoincrement=True)    # PK auto-incrémentée
    external_id = Column(UUID(as_uuid=True), unique=True, nullable=True)   # UUID exposé via l'API
    code        = Column(String, unique=True, nullable=False)              # Code machine (ex: EPAULES)
    nom         = Column(String, nullable=False)                           # Nom lisible (ex: Largeur épaules)
    unite       = Column(String, default="cm")                             # Unité de mesure
    categorie   = Column(String)                                           # Catégorie (longueur, largeur, circonférence)
    description = Column(String)                                           # Description optionnelle
    est_actif   = Column(Boolean, default=True)                            # Actif ou désactivé
