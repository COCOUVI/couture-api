from sqlalchemy import Boolean, Column, Integer, String
from app.core.database import Base


class TypeMesure(Base):
    __tablename__ = "type_mesures"
    __table_args__ = {"extend_existing": True}

    id          = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String, unique=True, nullable=True)
    code        = Column(String, unique=True, nullable=False)
    nom         = Column(String, nullable=False)
    unite       = Column(String, default="cm")
    categorie   = Column(String)
    description = Column(String)
    est_actif   = Column(Boolean, default=True)
