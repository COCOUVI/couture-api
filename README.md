# Couture API

Couture API est un microservice FastAPI chargé de transformer trois photos du corps humain en mesures utilisables pour la couture sur mesure. Il récupère les images depuis Cloudinary, détecte la pose avec MediaPipe, calcule les mesures, puis enregistre le résultat dans PostgreSQL.

## Rôle dans l’architecture

Le service s’insère dans la chaîne suivante:

```text
Flutter -> Cloudinary -> Laravel -> FastAPI -> Supabase
```

Son rôle est précis: recevoir une fiche de mesure déjà créée, analyser les vues face, dos et profil, produire les mesures normalisées, puis retourner un résultat exploitable par Laravel et Flutter.

## Ce que fait le service

L’API télécharge les images, corrige leur orientation si nécessaire, détecte les landmarks 3D du corps, calcule des longueurs et des circonférences, enregistre les mesures en base, puis supprime les images Cloudinary lorsque la configuration le permet.

Les mesures produites servent à alimenter la fabrication de vêtements sur mesure, avec des valeurs annotées par leur source et leur niveau de confiance.

## Stack technique

- FastAPI pour l’API HTTP
- MediaPipe pour la détection de pose
- SQLAlchemy 2.0 pour la persistance PostgreSQL
- httpx pour le téléchargement distant des images
- Pillow et NumPy pour le prétraitement image
- Supabase comme base partagée avec Laravel

## Installation locale

### Prérequis

- Python 3.10 ou plus
- pip
- accès à une base PostgreSQL compatible Supabase

### Installation

```bash
cd couture-api
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Sous Linux ou macOS:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Configuration

Créer un fichier `.env` à partir du modèle fourni, puis renseigner les variables principales:

```env
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres?sslmode=require
CLOUDINARY_API_KEY=votre_api_key
CLOUDINARY_API_SECRET=votre_api_secret
SECRET_KEY=une_cle_secrete_aleatoire
```

`DATABASE_URL` pointe vers la base PostgreSQL. Les variables Cloudinary servent uniquement au nettoyage des images après traitement.

### Lancement

```bash
uvicorn app.main:app --reload --port 8000
```

L’API est alors disponible sur `http://localhost:8000` et la documentation interactive sur `http://localhost:8000/docs`.

## Endpoints

### `GET /health`

Renvoie l’état de santé de l’API et le statut de connexion à la base.

Réponse type:

```json
{
  "statut": "ok",
  "environnement": "development",
  "version": "1.0.0",
  "db_connectee": true
}
```

### `POST /measure`

Traite trois images Cloudinary correspondant aux vues face, dos et profil.

Exemple de body:

```json
{
  "fiche_id": "550e8400-e29b-41d4-a716-446655440000",
  "client_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "face_url": "https://.../face.jpg",
  "dos_url": "https://.../dos.jpg",
  "profil_url": "https://.../profil.jpg"
}
```

Réponse type:

```json
{
  "fiche_id": "550e8400-...",
  "client_id": "a1b2c3d4-...",
  "methode": "mediapipe_3angles",
  "nb_mesures": 16,
  "statut": "ok",
  "mesures": []
}
```

Erreurs possibles:

- `404` si la fiche n’existe pas
- `422` si la vue face ne peut pas être analysée
- `503` si la base de données est indisponible

### `GET /measure/{fiche_id}`

Retourne les mesures déjà enregistrées pour une fiche donnée.

### `POST /measure/cleanup`

Supprime manuellement une liste d’URLs Cloudinary passées dans la requête.

## Comment les mesures sont calculées

Le calcul repose sur trois vues complémentaires.

La vue de face fournit la base des longueurs visibles et permet la calibration à partir de la taille connue. La vue de dos consolide certaines largeurs, en particulier les épaules et les hanches. La vue de profil ajoute les profondeurs nécessaires au calcul de circonférences plus réalistes.

Quand la vue de profil est exploitable, le service estime les tours de poitrine, sous-poitrine, taille et hanches par approximation elliptique. Sinon, il utilise des ratios anthropométriques plus simples.

Les principales familles de mesures sont:

- hauteur totale
- largeurs d’épaules, de carrure et de hanches
- longueurs du torse, des bras, des jambes, des cuisses et des mollets
- profondeurs du buste, de la taille et de la hanche
- circonférences poitrine, sous-poitrine, taille, hanches, cou, genou, bas et poignet

## Pipeline de traitement

| Étape | Fonction | Résultat |
|---|---|---|
| Téléchargement | `download_image_as_rgb()` | Image normalisée en RGB |
| Détection | `detect_world_landmarks()` | Landmarks 3D MediaPipe |
| Vue face | `extraire_face()` | Mesures visibles de face |
| Vue dos | `extraire_dos()` | Mesures visibles de dos |
| Vue profil | `extraire_profil()` | Profondeurs utiles |
| Fusion | `fusionner()` | Mesures finales prêtes à stocker |

## Nettoyage Cloudinary

Après un traitement réussi, les trois images peuvent être supprimées de Cloudinary via l’API Admin. Si les variables d’API ne sont pas renseignées, le nettoyage est ignoré et le scan continue normalement.

## Déploiement

Le projet est prévu pour un déploiement Docker. Le `Dockerfile` prépare l’environnement, installe les dépendances système nécessaires à OpenCV et MediaPipe, puis lance l’API FastAPI.

Points à vérifier avant mise en production:

- définir toutes les variables d’environnement
- vérifier l’accès réseau à Cloudinary et à PostgreSQL
- s’assurer que le modèle MediaPipe peut être téléchargé au premier lancement ou qu’il est déjà présent dans l’image

## Structure du projet

```text
couture-api/
├── app/
│   ├── main.py
│   ├── core/
│   ├── models/
│   ├── routers/
│   ├── schemas/
│   └── services/
├── Dockerfile
├── requirements.txt
└── README.md
```

## Points à retenir pour la soutenance

- le service traite trois vues pour réduire les erreurs de mesure
- la vue de profil améliore le calcul des circonférences
- chaque mesure enregistrée garde sa source et son niveau de confiance
- le nettoyage Cloudinary évite de laisser des fichiers inutiles après traitement
- l’ensemble est conçu pour être consommé par Laravel et affiché dans Flutter
