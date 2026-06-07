# Couture API — Microservice FastAPI

Microservice Python pour la prise de mesures corporelles automatique  
via **MediaPipe** (3 angles : face, dos, profil) + stockage **PostgreSQL (Supabase)**.

---

## Stack

- **FastAPI** — serveur API async
- **MediaPipe** — détection de pose (world landmarks 3D)
- **SQLAlchemy** — ORM PostgreSQL
- **httpx** — téléchargement des images Cloudinary

---

## Installation en local

### 1. Prérequis

- Python 3.10+
- pip

### 2. Cloner / copier le dossier

```bash
cd couture-api
```

### 3. Environnement virtuel

```bash
python -m venv venv
source venv/bin/activate        # Linux / Mac
venv\Scripts\activate           # Windows
```

### 4. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 5. Configurer les variables d'environnement

```bash
cp .env.example .env
```

Éditez `.env` et remplissez :

```env
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
SECRET_KEY=votre_cle_secrete
```

### 6. Lancer le serveur

```bash
uvicorn app.main:app --reload --port 8000
```

L'API est disponible sur : http://localhost:8000  
Documentation Swagger : http://localhost:8000/docs

---

## Endpoints

### `GET /health`
Vérifie que l'API tourne.

```json
{ "statut": "ok", "environnement": "development", "version": "1.0.0" }
```

---

### `POST /measure`
Reçoit les 3 URLs Cloudinary, traite les images et stocke les mesures.

**Body JSON :**
```json
{
  "fiche_id":   "uuid-de-la-fiche-cree-par-laravel",
  "client_id":  "uuid-du-client",
  "face_url":   "https://res.cloudinary.com/.../face.jpg",
  "dos_url":    "https://res.cloudinary.com/.../dos.jpg",
  "profil_url": "https://res.cloudinary.com/.../profil.jpg"
}
```

**Réponse :**
```json
{
  "fiche_id":   "...",
  "client_id":  "...",
  "methode":    "mediapipe_3angles",
  "nb_mesures": 16,
  "statut":     "ok",
  "mesures": [
    { "type_mesure_code": "EPAULES", "label": "Largeur épaules (É)",
      "unite": "cm", "categorie": "largeur",
      "valeur": 42.5, "source": "face+dos", "confiance": 0.94 },
    ...
  ]
}
```

---

### `GET /measure/{fiche_id}`
Retourne les mesures déjà stockées pour une fiche.

---

## Flow complet avec Laravel

```
Flutter upload 3 photos
      ↓
Laravel crée FicheMesure + attache médias (Spatie → Cloudinary)
      ↓
Laravel POST /measure  →  FastAPI
                              ↓
                         Télécharge images Cloudinary
                         MediaPipe traite les 3 vues
                         Stocke Mesures en DB (Supabase)
                              ↓
                         Retourne JSON { statut: "ok", mesures: [...] }
      ↓
Laravel reçoit confirmation
Laravel supprime les 3 médias Spatie (+ Cloudinary automatiquement)
      ↓
Flutter affiche les mesures ✅
```

---

## Structure du projet

```
couture-api/
├── app/
│   ├── main.py                         # Point d'entrée FastAPI
│   ├── core/
│   │   ├── config.py                   # Variables d'environnement
│   │   └── database.py                 # Connexion SQLAlchemy
│   ├── models/
│   │   ├── type_mesure.py              # Table type_mesures (lecture)
│   │   ├── fiche_mesure.py             # Table fiche_mesures
│   │   └── mesure.py                   # Table mesures (écriture)
│   ├── schemas/
│   │   └── mesure.py                   # Schémas Pydantic (validation)
│   ├── routers/
│   │   ├── health.py                   # GET /health
│   │   └── mesures.py                  # POST /measure, GET /measure/{id}
│   └── services/
│       ├── download_service.py         # Téléchargement images Cloudinary
│       ├── pose_service.py             # MediaPipe — détection de pose
│       └── measurement_service.py      # Calcul + fusion des mesures
├── .env.example                        # Template variables d'environnement
├── requirements.txt
└── README.md
```
