# Couture API — Microservice FastAPI

Microservice Python pour la **prise de mesures corporelles automatique** par analyse d'images via **MediaPipe Pose Landmarker**.

Le service s'intègre dans l'architecture suivante :

```
Flutter (scan 3 photos) → Cloudinary → Laravel → FastAPI (ce service) → Supabase
```

---

## Stack

- **FastAPI** — serveur API async (Python 3.10+)
- **MediaPipe** — détection de pose (world landmarks 3D)
- **SQLAlchemy 2.0** — ORM PostgreSQL
- **httpx** — téléchargement des images Cloudinary
- **PostgreSQL (Supabase)** — base de données partagée avec Laravel

---

## Fonctionnement général

1. **Flutter** prend 3 photos (face, dos, profil) et les upload sur **Cloudinary** (unsigned preset)
2. **Laravel** crée une `FicheMesure` en DB et appelle ce service via `POST /measure`
3. **FastAPI** télécharge chaque image, exécute MediaPipe pour extraire les landmarks 3D, calcule les mesures (hauteur, largeurs, circonférences) et les stocke dans la table `mesures`
4. **Après succès**, les images sont supprimées de Cloudinary (cleanup automatique)
5. **Laravel** reçoit la confirmation et retourne le résultat à Flutter

---

## Installation en local

### Prérequis

- Python 3.10+
- pip

### Mise en place

```bash
cd couture-api
python -m venv venv
source venv/bin/activate          # Linux / Mac
# venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
```

Éditez `.env` avec vos valeurs :

```env
# Supabase (SSL obligatoire)
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres?sslmode=require

# Cloudinary (pour suppression des images après traitement)
CLOUDINARY_API_KEY=votre_api_key
CLOUDINARY_API_SECRET=votre_api_secret

# Securite
SECRET_KEY=une_cle_secrete_aleatoire
```

### Lancer le serveur

```bash
uvicorn app.main:app --reload --port 8000
```

L'API est disponible sur : http://localhost:8000  
Documentation Swagger : http://localhost:8000/docs

---

## Endpoints

### `GET /health`
Vérifie que l'API et la base de données sont accessibles.

```json
{
  "statut": "ok",
  "environnement": "development",
  "db_connectee": true
}
```

---

### `POST /measure`
Reçoit les 3 URLs Cloudinary, traite les images, stocke et retourne les mesures.

**Body :**
```json
{
  "fiche_id":   "550e8400-e29b-41d4-a716-446655440000",
  "client_id":  "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "face_url":   "https://res.cloudinary.com/dvne7dd7h/image/upload/v1/koda_uploads/.../face.jpg",
  "dos_url":    "https://res.cloudinary.com/dvne7dd7h/image/upload/v1/koda_uploads/.../dos.jpg",
  "profil_url": "https://res.cloudinary.com/dvne7dd7h/image/upload/v1/koda_uploads/.../profil.jpg"
}
```

**Réponse :**
```json
{
  "fiche_id":   "550e8400-...",
  "client_id":  "a1b2c3d4-...",
  "methode":    "mediapipe_3angles",
  "nb_mesures": 16,
  "statut":     "ok",
  "mesures": [
    { "type_mesure_code": "EPAULES", "label": "Largeur epaules (E)",
      "unite": "cm", "categorie": "largeur",
      "valeur": 42.5, "source": "face+dos", "confiance": 0.94 },
    ...
  ]
}
```

**Cas d'erreur :**
- `404` → `fiche_id` introuvable en DB
- `422` → une vue (face/dos/profil) n'a pas pu être analysée
- `503` → erreur base de données

---

### `GET /measure/{fiche_id}`
Retourne les mesures déjà stockées pour une fiche.

---

## Pipeline MediaPipe (détail)

| Vue | Fonction | Landmarks extraits |
|-----|----------|-------------------|
| Face | `extraire_face()` | Hauteur, épaules, hanches, torse, bras, jambe, cuisse, mollet |
| Dos | `extraire_dos()` | Validation épaules + hanches, torse (vue arrière) |
| Profil | `extraire_profil()` | Profondeur buste + hanche, torse (vue latérale) |
| Fusion | `fusionner()` | Agrège les 3 vues, calcule les circonférences par ellipse ou ratio ISO 8559 |

Les 16 mesures produites correspondent aux codes `TypeMesure` de la base Supabase (seedée par Laravel).

---

## Suppression automatique des images Cloudinary

Après un traitement réussi, le service supprime les 3 images de Cloudinary via l'API Admin.

**Configuration requise :**
| Variable | Description |
|---|---|
| `CLOUDINARY_API_KEY` | API Key (Dashboard Cloudinary > Settings > Security) |
| `CLOUDINARY_API_SECRET` | API Secret associé |

Si ces variables ne sont pas définies, la suppression est ignorée (warning dans les logs) — le scan fonctionne quand même.

---

## Déploiement (Railway)

L'API est déployée automatiquement sur Railway via GitHub.

1. Connecter le dépôt GitHub `couture-api` (branche `main`)
2. Ajouter les variables d'environnement dans le dashboard Railway (voir `.env.example`)
3. Le `Dockerfile` à la racine construit l'image avec le modèle MediaPipe pré-téléchargé (~130 Mo)
4. Railway build et déploie automatiquement à chaque push sur `main`

**Dépendances systèmes installées dans le Dockerfile :**
- `libgl1-mesa-glx`, `libglib2.0-0` — OpenCV
- `libgles2`, `libegl1` — MediaPipe (rendu OpenGL ES)

---

## Structure du projet

```
couture-api/
├── app/
│   ├── main.py                       # Point d'entree FastAPI
│   ├── core/
│   │   ├── config.py                 # Variables d'environnement (Pydantic)
│   │   └── database.py               # Connexion SQLAlchemy + session
│   ├── models/
│   │   ├── type_mesure.py            # Table type_mesures (read)
│   │   ├── fiche_mesure.py           # Table fiche_mesures (read)
│   │   └── mesure.py                 # Table mesures (write)
│   ├── schemas/
│   │   └── mesure.py                 # Schemas Pydantic (validation I/O)
│   ├── routers/
│   │   ├── health.py                 # GET /health
│   │   └── mesures.py                # POST /measure, GET /measure/{id}
│   └── services/
│       ├── download_service.py       # Telechargement + correction EXIF
│       ├── pose_service.py           # MediaPipe — detection de pose
│       ├── measurement_service.py    # Calcul + fusion des mesures (3 vues)
│       └── cloudinary_cleanup.py     # Suppression images Cloudinary
├── Dockerfile
├── .env.example
├── requirements.txt
└── README.md
```

---

## Base de données

Tables partagées avec Laravel (mêmes schémas Supabase) :

| Table | Rôle |
|---|---|
| `fiche_mesures` | Session de scan créée par Laravel |
| `type_mesures` | Référentiel des 16 codes mesure (seedé) |
| `mesures` | Résultats du scan (écrits par FastAPI, lus par Laravel) |
