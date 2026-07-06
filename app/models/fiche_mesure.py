# ── Modèle ORM : table "fiche_mesures" (session de scan) ─────────────
from sqlalchemy import Column, Date, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class FicheMesure(Base):
    """Représente une session de scan (créée par Laravel, lue par FastAPI)."""
    __tablename__ = "fiche_mesures"
    __table_args__ = {"extend_existing": True}

    id         = Column(Integer, primary_key=True, autoincrement=True)        # PK auto-incrémentée
    external_id = Column(UUID(as_uuid=True), unique=True, nullable=False)     # UUID exposé via l'API
    client_id  = Column(Integer, ForeignKey("clients.id"), nullable=True)     # FK vers le client (optionnel)
    date       = Column(Date)                                                 # Date du scan
    methode    = Column(String, default="mediapipe_3angles")                  # Méthode utilisée

    # Une fiche contient plusieurs mesures (relation 1-N)
    mesures    = relationship("Mesure", back_populates="fiche", cascade="all, delete-orphan")
