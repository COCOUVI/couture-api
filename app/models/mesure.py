# ── Modèle ORM : table "mesures" (résultat du scan) ──────────────────
from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class Mesure(Base):
    """Stocke chaque mesure calculée (une ligne par type de mesure)."""
    __tablename__ = "mesures"
    __table_args__ = {"extend_existing": True}

    id              = Column(Integer, primary_key=True, autoincrement=True)      # PK auto-incrémentée
    external_id     = Column(UUID(as_uuid=True), unique=True, nullable=True)     # UUID exposé via l'API
    fiche_mesure_id = Column(Integer, ForeignKey("fiche_mesures.id"), nullable=False)  # FK vers la fiche
    type_mesure_id  = Column(Integer, ForeignKey("type_mesures.id"), nullable=False)   # FK vers le type
    valeur          = Column(Float, nullable=False)                              # Valeur mesurée en cm
    source          = Column(String)                                             # Origine (face, dos, profil, ratio...)
    confiance       = Column(Float)                                              # Score de confiance [0-1]
    commentaire     = Column(String)                                             # Note optionnelle

    # Relations ORM
    fiche           = relationship("FicheMesure", back_populates="mesures")
    type_mesure     = relationship("TypeMesure")
