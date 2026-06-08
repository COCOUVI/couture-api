from sqlalchemy import Column, Date, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class FicheMesure(Base):
    __tablename__ = "fiche_mesures"
    __table_args__ = {"extend_existing": True}

    id         = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(UUID(as_uuid=True), unique=True, nullable=False)
    client_id  = Column(Integer, ForeignKey("clients.id"), nullable=True)
    date       = Column(Date)
    methode    = Column(String, default="mediapipe_3angles")

    mesures    = relationship("Mesure", back_populates="fiche", cascade="all, delete-orphan")
