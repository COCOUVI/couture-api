import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import check_db_connection
from app.routers import mesures, health

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Couture API — Mesures Corporelles",
    description=(
        "Microservice Python pour la prise de mesures corporelles automatique "
        "via MediaPipe (3 angles : face, dos, profil). "
        "Stocke directement dans PostgreSQL (Supabase)."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(mesures.router)


@app.get("/", include_in_schema=False)
def root():
    return {"message": "Couture API — voir /docs pour la documentation"}


@app.on_event("startup")
def on_startup():
    """Verifie la connexion DB au demarrage."""
    ok = check_db_connection()
    if ok:
        logger.info("API prete")
    else:
        logger.warning("API demarree sans connexion DB")
