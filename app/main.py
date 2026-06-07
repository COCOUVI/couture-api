from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import mesures, health

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

# ── CORS — autorise Laravel et Flutter (dev) ────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restreignez en production à votre domaine Laravel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routeurs ────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(mesures.router)


@app.get("/", include_in_schema=False)
def root():
    return {"message": "Couture API — voir /docs pour la documentation"}
