"""Modèle ORM de la table type_mesures."""
from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class TypeMesure(Base):
    """Référentiel des 16 types de mesures (seedé par Laravel, lu par FastAPI)."""
    __tablename__ = "type_mesures"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(UUID(as_uuid=True), unique=True, nullable=True)
    code = Column(String, unique=True, nullable=False)
    nom = Column(String, nullable=False)
    unite = Column(String, default="cm")
    categorie = Column(String)
    description = Column(String)
    est_actif = Column(Boolean, default=True)
