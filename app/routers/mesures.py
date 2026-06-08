import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import get_db
from app.models.fiche_mesure import FicheMesure
from app.models.mesure import Mesure
from app.models.type_mesure import TypeMesure
from app.schemas.mesure import MesureRequest, MesureResponse, MesureOut
from app.services.download_service import download_image_as_rgb
from app.services.measurement_service import extraire_face, extraire_dos, extraire_profil, fusionner
from app.services.pose_service import detect_world_landmarks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/measure", tags=["Mesures"])


@router.post("", response_model=MesureResponse, status_code=status.HTTP_201_CREATED)
async def analyser_et_stocker(payload: MesureRequest, db: Session = Depends(get_db)):
    try:
        fiche = db.query(FicheMesure).filter(
            FicheMesure.external_id == uuid.UUID(payload.fiche_id)
        ).first()
        if not fiche:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"FicheMesure '{payload.fiche_id}' introuvable.",
            )

        m_face = m_dos = m_profil = {}

        try:
            img_face = await download_image_as_rgb(payload.face_url)
            wlms_face = detect_world_landmarks(img_face)
            m_face = extraire_face(wlms_face)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Vue face — {str(e)}",
            )

        try:
            img_dos = await download_image_as_rgb(payload.dos_url)
            wlms_dos = detect_world_landmarks(img_dos)
            m_dos = extraire_dos(wlms_dos)
        except Exception:
            pass

        try:
            img_profil = await download_image_as_rgb(payload.profil_url)
            wlms_profil = detect_world_landmarks(img_profil)
            m_profil = extraire_profil(wlms_profil)
        except Exception:
            pass

        mesures_calculees = fusionner(m_face, m_dos, m_profil)

        db.query(Mesure).filter(Mesure.fiche_mesure_id == fiche.id).delete()

        for m in mesures_calculees:
            type_mesure = (
                db.query(TypeMesure)
                .filter(TypeMesure.code == m["type_mesure_code"])
                .first()
            )
            if not type_mesure:
                type_mesure = TypeMesure(
                    external_id=uuid.uuid4(),
                    code=m["type_mesure_code"],
                    nom=m["label"],
                    unite=m["unite"],
                    categorie=m["categorie"],
                    est_actif=True,
                )
                db.add(type_mesure)
                db.flush()

            mesure = Mesure(
                external_id=uuid.uuid4(),
                fiche_mesure_id=fiche.id,
                type_mesure_id=type_mesure.id,
                valeur=m["valeur"],
                source=m["source"],
                confiance=m["confiance"],
            )
            db.add(mesure)

        db.commit()

        return MesureResponse(
            fiche_id=payload.fiche_id,
            client_id=payload.client_id,
            methode="mediapipe_3angles",
            nb_mesures=len(mesures_calculees),
            statut="ok",
            mesures=[MesureOut(**m) for m in mesures_calculees],
        )

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error("Erreur DB: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Erreur base de donnees: {str(e)}",
        )
    except Exception as e:
        db.rollback()
        logger.error("Erreur inattendue: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur interne: {str(e)}",
        )


@router.get("/{fiche_id}", response_model=MesureResponse)
def get_mesures(fiche_id: str, db: Session = Depends(get_db)):
    try:
        fiche = db.query(FicheMesure).filter(
            FicheMesure.external_id == uuid.UUID(fiche_id)
        ).first()
        if not fiche:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"FicheMesure '{fiche_id}' introuvable.",
            )

        mesures_db = (
            db.query(Mesure, TypeMesure)
            .join(TypeMesure, Mesure.type_mesure_id == TypeMesure.id)
            .filter(Mesure.fiche_mesure_id == fiche.id)
            .all()
        )

        mesures_out = [
            MesureOut(
                type_mesure_code=tm.code,
                label=tm.nom,
                unite=tm.unite or "cm",
                categorie=tm.categorie or "autre",
                valeur=m.valeur,
                source=m.source or "",
                confiance=m.confiance or 0.0,
            )
            for m, tm in mesures_db
        ]

        return MesureResponse(
            fiche_id=fiche_id,
            client_id=fiche.client_id,
            methode=fiche.methode or "mediapipe_3angles",
            nb_mesures=len(mesures_out),
            statut="ok",
            mesures=mesures_out,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erreur recuperation mesures: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur interne: {str(e)}",
        )
