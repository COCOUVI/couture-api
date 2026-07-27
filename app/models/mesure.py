"""Modèle ORM de la table mesures."""
from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class Mesure(Base):
    """Stocke chaque mesure calculée (une ligne par type de mesure)."""
    __tablename__ = "mesures"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(UUID(as_uuid=True), unique=True, nullable=True)
    fiche_mesure_id = Column(Integer, ForeignKey("fiche_mesures.id"), nullable=False)
    type_mesure_id = Column(Integer, ForeignKey("type_mesures.id"), nullable=False)
    valeur = Column(Float, nullable=False)
    source = Column(String)
    confiance = Column(Float)
    commentaire = Column(String)

    fiche = relationship("FicheMesure", back_populates="mesures")
    type_mesure = relationship("TypeMesure")
