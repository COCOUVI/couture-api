# ── Schémas Pydantic pour les mesures ────────────────────────────────
from pydantic import BaseModel, Field
from typing import List


class MesureOut(BaseModel):
    """Schéma de sortie : une mesure individuelle."""
    type_mesure_code: str
    label:            str
    unite:            str
    categorie:        str
    valeur:           float
    source:           str
    confiance:        float

    model_config = {"from_attributes": True}


class MesureRequest(BaseModel):
    """Schéma d'entrée : requête POST /measure."""
    fiche_id:       str  = Field(..., description="ID de la FicheMesure créée par Laravel")
    client_id:      str  = Field(..., description="ID du client")
    face_url:       str  = Field(..., description="URL Cloudinary — vue de face")
    dos_url:        str  = Field(..., description="URL Cloudinary — vue de dos")
    profil_url:     str  = Field(..., description="URL Cloudinary — vue de profil")
    known_height_cm: float | None = Field(None, description="Taille reelle de la personne en cm (optionnel, pour calibration exacte)")


class MesureResponse(BaseModel):
    """Schéma de sortie : réponse complète avec la liste des mesures."""
    fiche_id:   str
    client_id:  str
    methode:    str
    nb_mesures: int
    statut:     str
    mesures:    List[MesureOut]
