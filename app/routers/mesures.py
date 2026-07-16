# ── Routes de mesures — POST /measure, GET /measure/{id} ─────────────
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import get_db
from app.models.fiche_mesure import FicheMesure
from app.models.mesure import Mesure
from app.models.type_mesure import TypeMesure
from app.schemas.mesure import CleanupRequest, MesureRequest, MesureResponse, MesureOut
from app.services.download_service import download_image_as_rgb
from app.services.measurement_service import extraire_face, extraire_dos, extraire_profil, fusionner
from app.services.pose_service import detect_world_landmarks
from app.services.cloudinary_cleanup import cleanup_cloudinary_images

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/measure", tags=["Mesures"])


# ── POST /measure — analyse et stocke les mesures ────────────────────
@router.post("", response_model=MesureResponse, status_code=status.HTTP_201_CREATED)
async def analyser_et_stocker(payload: MesureRequest, db: Session = Depends(get_db)):
    """
    Reçoit 3 URLs Cloudinary (face, dos, profil),
    télécharge les images, exécute MediaPipe,
    calcule les mesures et les stocke en DB.
    """
    urls = [payload.face_url, payload.dos_url, payload.profil_url]

    try:
        # 1. Vérification de l'existence de la fiche en DB
        fiche = db.query(FicheMesure).filter(
            FicheMesure.external_id == uuid.UUID(payload.fiche_id)
        ).first()
        if not fiche:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"FicheMesure '{payload.fiche_id}' introuvable.",
            )

        m_face = m_dos = m_profil = {}

        # 2. Traitement de la vue de face (obligatoire)
        try:
            img_face = await download_image_as_rgb(payload.face_url)
            logger.info("Image face téléchargée (%s)", payload.face_url)
            wlms_face = detect_world_landmarks(img_face)
            m_face = extraire_face(wlms_face, known_height_cm=payload.known_height_cm)
        except Exception as e:
            logger.error("Vue face — %s: %s", type(e).__name__, e)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Vue face — {str(e)}",
            )

        # 3. Traitement de la vue de dos (optionnelle)
        try:
            img_dos = await download_image_as_rgb(payload.dos_url)
            wlms_dos = detect_world_landmarks(img_dos)
            m_dos = extraire_dos(wlms_dos, known_height_cm=payload.known_height_cm)
        except Exception:
            pass

        # 4. Traitement de la vue de profil (optionnelle)
        try:
            img_profil = await download_image_as_rgb(payload.profil_url)
            wlms_profil = detect_world_landmarks(img_profil)
            m_profil = extraire_profil(wlms_profil, known_height_cm=payload.known_height_cm)
        except Exception:
            pass

        # 5. Fusion des 3 vues et calcul des circonférences
        mesures_calculees = fusionner(m_face, m_dos, m_profil)

        # 6. Suppression des anciennes mesures pour cette fiche
        db.query(Mesure).filter(Mesure.fiche_mesure_id == fiche.id).delete()

        # 7. Insertion des nouvelles mesures
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
    finally:
        try:
            await cleanup_cloudinary_images(urls)
        except Exception:
            pass


# ── POST /measure/cleanup — suppression manuelle d'images Cloudinary ──
@router.post("/cleanup", status_code=status.HTTP_200_OK)
async def cleanup_images(payload: CleanupRequest):
    """
    Supprime une ou plusieurs images de Cloudinary.
    Utile pour le nettoyage manuel depuis le client mobile ou Laravel
    après un échec d'upload ou d'analyse.
    """
    try:
        await cleanup_cloudinary_images(payload.urls)
        return {"status": "ok", "deleted": len(payload.urls)}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur nettoyage Cloudinary: {str(e)}",
        )


# ── GET /measure/{fiche_id} — récupération des mesures stockées ──────
@router.get("/{fiche_id}", response_model=MesureResponse)
def get_mesures(fiche_id: str, db: Session = Depends(get_db)):
    """
    Retourne toutes les mesures déjà stockées pour une fiche donnée.
    """
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
