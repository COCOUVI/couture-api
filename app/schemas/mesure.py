from pydantic import BaseModel, Field
from typing import List


class CleanupRequest(BaseModel):
    urls: list[str] = Field(..., description="Liste des URLs Cloudinary à supprimer")


class MesureOut(BaseModel):
    type_mesure_code: str
    label:            str
    unite:            str
    categorie:        str
    valeur:           float
    source:           str
    confiance:        float

    model_config = {"from_attributes": True}


class MesureRequest(BaseModel):
    fiche_id:        str  = Field(..., description="ID de la FicheMesure")
    client_id:       str  = Field(..., description="ID du client")
    face_url:        str  = Field(..., description="URL Cloudinary vue de face")
    dos_url:         str  = Field(..., description="URL Cloudinary vue de dos")
    profil_url:      str  = Field(..., description="URL Cloudinary vue de profil")
    known_height_cm: float = Field(..., description="Taille reelle en cm")
    sexe:            str  = Field("mixte", description="Sexe du client : homme, femme, mixte")


class MesureResponse(BaseModel):
    fiche_id:   str
    client_id:  str
    methode:    str
    nb_mesures: int
    statut:     str
    mesures:    List[MesureOut]
