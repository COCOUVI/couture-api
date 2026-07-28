# Architecture générale

```
Flutter (koda) → Laravel (e-couture) → FastAPI (couture-api) → MediaPipe
                                          ↑
                                    Supabase (PostgreSQL)
```

- **Flutter** : prend 3 photos (face, dos, profil) + taille utilisateur → upload Cloudinary → envoie à Laravel
- **Laravel** : valide les entrées, crée la fiche mesure (`fiche_mesures`), appelle FastAPI via `MeasureCvGateway`
- **FastAPI** : télécharge les images, détecte les landmarks MediaPipe, calcule les mesures couture, stocke en base
- **Supabase** : base PostgreSQL partagée entre Laravel et FastAPI (mêmes tables)

---

# Pipeline complet du scan

```
1. Utilisateur prend 3 photos (face, dos, profil)
2. Flutter upload chaque photo → Cloudinary
3. Flutter envoie à Laravel : {face_url, dos_url, profil_url, known_height_cm}
4. Laravel crée FicheMesure + attache les medias
5. Laravel appelle FastAPI : POST /measure
6. FastAPI télécharge les 3 images depuis Cloudinary
7. MediaPipe détecte 33 landmarks 3D sur chaque image
8. measurement_service.py calcule les mesures à partir des landmarks
9. Résultats stockés dans mesures + type_mesures
10. Images Cloudinary nettoyées
```

---

# `measurement_service.py` — Le cœur du calcul

## Problème fondamental

MediaPipe fournit des `world_landmarks` en **mètres** estimés depuis une image unique (monoculaire). Sans connaître la distance caméra-sujet ni la focale, l'échelle absolue est imprécise.

**Exemple concret** : une personne de 160 cm obtenait 66 cm estimés par MediaPipe → facteur d'erreur de 2.4×.

**Solution** : calibrer l'échelle en divisant une référence connue par la valeur brute estimée. Toutes les mesures sont ensuite multipliées par ce facteur.

---

## `_compute_scale(wlms, known_height_cm)` — Calibration de l'échelle

```python
def _compute_scale(wlms, known_height_cm) -> float:
```

### Pourquoi cette fonction existe

MediaPipe donne des distances en unités arbitraires (world landmarks en mètres, mais l'échelle n'est pas fiable). Il faut un facteur de conversion pour obtenir des centimètres réels.

### Comment elle fonctionne

1. Estime la hauteur brute de la personne à partir des landmarks 3D
2. Compare avec la taille réelle fournie par l'utilisateur
3. `scale = known_height_cm / hauteur_brute`

### Détail du calcul de la hauteur brute

```python
dist_nez_cheville = abs(wlms[NOSE].y - y_ch_moy) * 100
dist_ep_cheville = abs(y_ep_moy - y_ch_moy) * 100
largeur_bi_auric = w3d(wlms, LEFT_EAR, RIGHT_EAR)

# Portion du crâne au-dessus du nez (non couverte par le landmark NOSE)
extension_cranienne = max(largeur_bi_auric * 0.45, largeur_epaules_brute * 0.14)

# Distance entre la cheville et le sol
hauteur_semelle = max(largeur_epaules_brute * 0.07, 3.0)

# Deux estimations indépendantes
h_nez = dist_nez_cheville + extension_cranienne + hauteur_semelle
h_ep = dist_ep_cheville / 0.82  # 0.82 = ratio épaule→cheville / stature

# Moyenne pondérée (65% nez, 35% épaules)
hauteur_brute = (h_nez * 0.65) + (h_ep * 0.35)
```

### Pourquoi `known_height_cm` est obligatoire

Avant, il y avait un fallback : `ASSUMED_SHOULDER_WIDTH_CM = 39.0`. Problème :

- Une personne large d'épaules (44 cm) → mesures sous-estimées
- Une personne étroite (35 cm) → mesures surestimées
- Un enfant (28 cm) → mesures fortement erronées

Décision : supprimer le fallback. L'utilisateur **doit** entrer sa taille. C'est une contrainte d'usage mais la seule façon d'avoir des mesures fiables.

---

## `extraire_face(wlms, known_height_cm)` — Mesures depuis la vue de face

```python
def extraire_face(wlms, known_height_cm) -> dict:
```

### Pourquoi cette fonction existe

La photo de face est la vue principale. Elle permet de mesurer :

- Les largeurs (épaules, buste, ceinture, hanches)
- Les longueurs verticales (torse, bras, jambes)
- La hauteur totale

### Fonctions de base utilisées

#### `_point_between(a, b, ratio)` — Interpolation de points

```python
def _point_between(a, b, ratio: float) -> tuple[float, float, float]:
```

**Pourquoi :** MediaPipe donne des points précis (épaule, hanche, coude) mais pas "le point ceinture" ou "le point buste". Personne n'a un landmark à la ceinture. On fabrique ce point nous-mêmes.

```
Épaule (0%) ----×----------------- Hanche (100%)
                ^
             0.62 = ceinture estimée
             0.30 = buste estimé
```

**Utilité :** Créer des points anatomiques intermédiaires que MediaPipe ne fournit pas.

#### `_distance_cm(p1, p2)` — Distance entre points 3D quelconques

```python
def _distance_cm(p1, p2) -> float:
    return round(
        ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2 + (p1[2] - p2[2]) ** 2) ** 0.5 * 100,
        1,
    )
```

**Pourquoi son nom est `_distance_cm` et pas `_distance_3d` ?**

Parce que le nom indique **ce qu'elle retourne** (des centimètres), pas **comment elle calcule** (en 3D). Toutes les distances dans ce fichier sont en 3D — il n'y a pas de mesure 2D. Préciser `_3d` serait redondant. Ce qui est important pour le lecteur, c'est l'unité : `_cm` garantit que le résultat est en centimètres exploitables pour la couture.

**Pourquoi ne pas utiliser `w3d()` ?**

`w3d(wlms, L_SHOULDER, R_SHOULDER)` attend :

- `wlms` : la liste des landmarks MediaPipe
- `L_SHOULDER`, `R_SHOULDER` : des **index** (entiers) dans cette liste

Mais `_point_between()` retourne un **tuple** `(x, y, z)` — ce n'est pas un index MediaPipe. On ne peut donc pas passer ce tuple à `w3d()`. Il faut une fonction qui mesure la distance entre **n'importe quels points 3D**, qu'ils viennent de MediaPipe ou d'ailleurs.

```python
# w3d  : fonctionne avec des INDEX MediaPipe
w3d(wlms, L_SHOULDER, R_SHOULDER)

# _distance_cm : fonctionne avec des TUPLE (x, y, z)
gauche = _point_between(wlms[L_SHOULDER], wlms[L_HIP], 0.62)
droite = _point_between(wlms[R_SHOULDER], wlms[R_HIP], 0.62)
_distance_cm(gauche, droite)
```

**Pourquoi le `* 100` ?**

MediaPipe retourne les `world_landmarks` en **mètres**. Mais la couture utilise les **centimètres**. Sans `* 100`, une largeur d'épaules de 0.42 m deviendrait 0.42 cm — inexploitable. Le `* 100` convertit simplement m → cm.

**Pourquoi `round(..., 1)` ?**

La couture n'a pas besoin de micromètres. Un arrondi au millimètre (1 décimale) est suffisant pour un tailleur.

#### `_interpolated_torso_width(wlms, ratio)` — Largeur du torse à un niveau donné

```python
def _interpolated_torso_width(wlms, ratio) -> float:
```

**Pourquoi :** Le corps n'a pas la même largeur partout. Épaules larges, ceinture étroite, hanches larges. Il faut mesurer à chaque niveau anatomique spécifique.

**Comment :** Combine `_point_between` (crée point gauche + point droit au ratio donné) + `_distance_cm` (mesure la distance entre eux).

**Utilité :**

- `ratio = 0.30` → largeur buste (poitrine)
- `ratio = 0.62` → largeur ceinture

### Qu'est-ce qui est calculé dans `extraire_face`

| Code                    | Signification       | Comment c'est calculé                             |
| ----------------------- | ------------------- | -------------------------------------------------- |
| `HAUTEUR`             | Stature totale      | nose_to_ankle × scale + corrections tête/pieds   |
| `EPAULES`             | Largeur épaules    | `w3d(L_SHOULDER, R_SHOULDER) × scale`           |
| `BUSTE_LARGEUR`       | Largeur buste       | `_interpolated_torso_width(wlms, 0.30) × scale` |
| `CEINTURE_LARGEUR`    | Largeur ceinture    | `_interpolated_torso_width(wlms, 0.62) × scale` |
| `HANCHES_L`           | Largeur hanches     | `_distance_cm(points_hanches) × scale`          |
| `TORSE`               | Longueur torse      | distance épaule→entrejambe × scale              |
| `BRA_TOTAL`           | Longueur bras total | épaule→poignet × scale                          |
| `BRA_AV`              | Longueur avant-bras | coude→poignet × scale                            |
| `JAMBE`               | Longueur jambe      | hanche→cheville × scale                          |
| `CUISSE`              | Longueur cuisse     | hanche→genou × scale                             |
| `MOLLET`              | Longueur mollet     | genou→cheville × scale                           |
| `LONGUEUR_SOUS_SEINS` | Sous-poitrine       | torse × 0.20 (ratio)                              |

---

## `extraire_dos(wlms, known_height_cm)` — Validation par la vue de dos

```python
def extraire_dos(wlms, known_height_cm) -> dict:
```

### Pourquoi cette fonction existe

La vue de dos sert à **valider ou corriger** les mesures de face. Trois mesures sont reprises :

- `EPAULES_DOS` : largeur épaules depuis le dos
- `HANCHES_LARGEUR_DOS` : largeur hanches depuis le dos
- `TORSE_LONGUEUR_DOS` : longueur torse depuis le dos

Si la vue face est imparfaite (personne légèrement tournée), la vue dos permet une meilleure estimation.

### Pourquoi c'est optionnel

```python
try:
    img_dos = await download_image_as_rgb(payload.dos_url)
    wlms_dos = detect_world_landmarks(img_dos)
    m_dos = extraire_dos(wlms_dos, known_height_cm=payload.known_height_cm)
except Exception:
    pass
```

Si la photo de dos est manquante ou inexploitable, on continue sans. Les mesures de face sont suffisantes.

---

## `extraire_profil(wlms, known_height_cm)` — Profondeurs depuis la vue de profil

```python
def extraire_profil(wlms, known_height_cm) -> dict:
```

### Pourquoi cette fonction existe

La largeur seule (vue de face) ne suffit pas pour calculer un **tour** (circonférence). Le corps est en 3D. De profil, on mesure l'épaisseur (profondeur).

### `_interpolated_torso_depth(wlms, ratio)` — Profondeur du torse

```python
def _interpolated_torso_depth(wlms, ratio) -> float:
```

**Comment :** Prend la différence sur l'axe Z entre le point gauche et le point droit à un niveau donné (buste, ceinture, hanche). De profil, un côté est plus proche de la caméra que l'autre → la différence donne la profondeur.

**Pourquoi c'est crucial :** Sans profondeur → pas d'ellipse → tours estimés par des ratios approximatifs (moins précis).

### Qu'est-ce qui est calculé

| Code                      | Signification                         |
| ------------------------- | ------------------------------------- |
| `PROFONDEUR_BUSTE`      | Profondeur au niveau buste (poitrine) |
| `PROFONDEUR_CEINTURE`   | Profondeur au niveau ceinture         |
| `PROFONDEUR_HANCHE`     | Profondeur au niveau hanches          |
| `TORSE_LONGUEUR_PROFIL` | Longueur torse depuis le profil       |

---

## `fusionner(m_face, m_dos, m_profil)` — Fusion des 3 vues + calcul des tours

```python
def fusionner(m_face, m_dos, m_profil) -> list[dict]:
```

### Pourquoi cette fonction existe

Chaque vue donne des mesures partielles. La face donne largeurs et longueurs, le profil donne profondeurs, le dos valide. Il faut :

1. Fusionner les trois dictionnaires
2. Valider/moyenner les mesures redondantes (épaules, torse)
3. Calculer les tours (circonférences) à partir des largeurs + profondeurs
4. Ajouter les mesures dérivées (tour de cou, genou, poignet)
5. Filtrer les mesures internes et invalides

### Validation des mesures redondantes

**Épaules :** si disponibles depuis face ET dos → moyenne des deux

```python
if "EPAULES" in raw and "EPAULES_DOS" in raw:
    v = avg(raw["EPAULES"][0], raw["EPAULES_DOS"][0])
    raw["EPAULES"] = (v, "face+dos", 0.94)
```

**Torse :** si disponible depuis face + dos + profil → moyenne des trois

```python
torses = [raw[k][0] for k in ("TORSE", "TORSE_LONGUEUR_DOS", "TORSE_LONGUEUR_PROFIL") if k in raw]
raw["TORSE"] = (avg(*torses), "face+dos+profil", 0.93)
```

### Calcul des tours par ellipse (Ramanujan)

Quand le profil est disponible (largeur + profondeur) :

```python
tour = ellipse_circumference(demi_largeur, demi_profondeur)
```

**`ellipse_circumference(a, b)`** — Approximation de Ramanujan

```python
def ellipse_circumference(a, b) -> float:
    return pi * (3 * (a + b) - sqrt((3 * a + b) * (a + 3 * b)))
```

Précision < 0.04% pour toute forme d'ellipse. C'est la meilleure approximation simple connue.

**Pourquoi pas π × (a + b) ?** Cette formule simple (Mensuration) surestime de ~10%. Ramanujan est quasi exact.

### Fallback sans profil

Si la vue de profil manque, on utilise des ratios :

```python
tour_poitrine = round(largeur_buste * 3.35, 1)
tour_hanches = round(largeur_hanches * 3.35, 1)
tour_ceinture = round(largeur_ceinture * 3.20, 1)
```

Moins précis mais permet quand même de retourner des mesures.

### Garde-fou (`_clamp`)

```python
def _clamp(value, low, high) -> float:
```

**Pourquoi :** Les photos peuvent produire des aberrations : personne tournée, bras trop proches, vêtements larges, mauvaise détection MediaPipe.

```python
tour_ceinture = _clamp(tour_ceinture, min_tour_ceinture, max_tour_ceinture)
```

Limite la ceinture entre 62% et 103% du plus petit des tours (poitrine, hanches) — norme NF EN 13402-2.

### Mesures dérivées par ratio

```python
raw["TOUR_COU"]     = (round(largeur_oreilles * 1.73, 1), "ratio", 0.70)
raw["TOUR_GENOU"]   = (round(mollet * 1.20, 1),           "ratio", 0.72)
raw["TOUR_POIGNET"] = (round(avant_bras * 0.65, 1),       "ratio", 0.72)
```

**Pourquoi :** MediaPipe ne fournit pas assez de points précis pour calculer ces tours directement. On utilise des ratios anthropométriques issus de la littérature.

### Filtrage final

```python
for code, (valeur, source, confiance) in raw.items():
    if code in _CODES_INTERMEDIAIRES or valeur <= 0:
        continue
```

Retire :

- Les codes internes (`BUSTE_LARGEUR`, `CEINTURE_LARGEUR`, `PROFONDEUR_*`, etc.) — ils ont servi à calculer les tours mais ne doivent pas être stockés
- Les valeurs nulles ou négatives (erreur de détection)

---

## `filtrer_par_sexe(mesures, sexe)` — Filtrage genre

```python
MESURES_EXCLUES_HOMME = {
    "LONGUEUR_SOUS_SEINS",
    "TOUR_SOUS_SEINS",
    "LONGUEUR_JUPE",
    "LONGUEUR_ROBE",
}
```

**Pourquoi :** Un homme n'a pas besoin de mesure de sous-seins ou de longueur de jupe. Ces codes sont exclus pour les genres `homme`, `masculin`, `h`, `m`.

**Valeurs acceptées :** `homme`/`femme`/`autre`/`masculin`/`feminin`

---

# `routers/mesures.py` — L'API

## `POST /measure` — Analyser et stocker

```python
async def analyser_et_stocker(payload: MesureRequest, db: Session = Depends(get_db)):
```

### Étapes détaillées

1. **Valider la fiche mesure** : cherche `FicheMesure` par UUID dans la base
2. **Face** : obligatoire. Télécharge l'image → détecte landmarks → extrait mesures
3. **Dos** : optionnel. Si échec → on continue sans
4. **Profil** : optionnel. Si échec → tours calculés par ratio (moins précis)
5. **Fusion** : combine les 3 vues
6. **Filtrage sexe** : exclut les mesures inappropriées
7. **Sauvegarde** : supprime les anciennes mesures remplacées, insère les nouvelles
8. **Nettoyage** : supprime les images Cloudinary (toujours, même en cas d'erreur)

### Gestion des `TypeMesure`

Si un code de mesure n'existe pas encore dans `type_mesures` :

```python
type_mesure = TypeMesure(
    external_id=uuid.uuid4(),
    code=m["type_mesure_code"],
    nom=m["label"],
    description=m["label"],  # ATTENTION : colonne NOT NULL dans PostgreSQL
    unite=m["unite"],
    categorie=m["categorie"],
    est_actif=True,
)
```

**Piège** : la migration Laravel a créé `description TEXT NOT NULL`. Si `description` n'est pas fournie → `NotNullViolation`.

## `POST /measure/cleanup` — Nettoyage Cloudinary

Appelé par Laravel quand `/measure` échoue, pour nettoyer les images déjà uploadées.

## `GET /measure/{fiche_id}` — Récupérer les mesures

Retourne les mesures stockées pour une fiche donnée.

---

# `download_service.py` — Téléchargement d'images

```python
async def download_image_as_rgb(url: str) -> np.ndarray:
```

Télécharge une image depuis Cloudinary et la convertit en tableau numpy RGB pour MediaPipe.

**Pourquoi une fonction dédiée :** Gère les timeouts, les erreurs HTTP, la conversion d'image, et le redimensionnement si nécessaire.

---

# `cloudinary_cleanup.py` — Nettoyage

```python
async def cleanup_cloudinary_images(urls: list[str]):
```

Supprime les images de Cloudinary après traitement (ou en cas d'échec) pour ne pas accumuler de fichiers inutiles.

---

# Schéma des données

## `MesureRequest` (entrée)

```python
{
    fiche_id: str,         # UUID de la FicheMesure
    client_id: str,        # UUID du client
    face_url: str,         # URL Cloudinary face
    dos_url: str,          # URL Cloudinary dos
    profil_url: str,       # URL Cloudinary profil
    known_height_cm: float,# Taille utilisateur (obligatoire)
    sexe: str,             # homme/femme/autre
}
```

## `MesureOut` (sortie par mesure)

```python
{
    type_mesure_code: str, # Ex: "CEINTURE"
    label: str,            # Ex: "Tour de ceinture (T)"
    unite: str,            # "cm"
    categorie: str,        # "circonference"
    valeur: float,         # 79.3
    source: str,           # "ellipse(face+profil)"
    confiance: float,      # 0.86
}
```

---

# Erreurs connues et corrections

| Erreur                                   | Cause                                        | Correction                                                   |
| ---------------------------------------- | -------------------------------------------- | ------------------------------------------------------------ |
| "Le service de mesures est indisponible" | Timeout Laravel→Render (cold start ~30-60s) | `MEASURE_CV_CONNECT_TIMEOUT=60` + uptime monitor           |
| `invalid input syntax for type uuid`   | envoi de`client_xxx` comme UUID            | `createClient()` Flutter appelle API→récupère vrai UUID |
| `NotNullViolation: description`        | `TypeMesure` créé sans `description`   | ajouter`description=m["label"]`                            |
| Mesures hommes incluent sous-seins/jupe  | Filtrage sexe manquant                       | `filtrer_par_sexe()` dans le routeur                       |

---

# Ratios anthropométriques (pour le jury)

| Ratio                              | Usage                            | Justification                      | Source                   |
| ---------------------------------- | -------------------------------- | ---------------------------------- | ------------------------ |
| 0.30                               | Position buste                   | ~30% épaule→hanche               | Pheasant (1986)          |
| 0.62                               | Position ceinture                | ~60-65% épaule→hanche            | ISO 8559-1:2017          |
| 0.82                               | Épaule→cheville / stature      | Tête+cou = 18% de la stature      | Drillis & Contini (1966) |
| 0.45                               | Largeur tête / oreilles         | Dimension antéro-postérieure     | Empirique                |
| 0.14                               | Hauteur crâne / épaules        | Ratio crâne                       | Empirique                |
| 3.35                               | Largeur → tour poitrine/hanches | π × correction aspect            | NF EN 13402-3            |
| 3.20                               | Largeur → tour ceinture         | π × correction aspect elliptique | Empirique                |
| 0.82                               | WHR (ceinture/hanches)           | Rapport moyen                      | OMS (2008)               |
| 1.73                               | Tour de cou                      | × largeur bi-auriculaire          | DIN 61506                |
| 1.20                               | Tour de genou                    | × longueur mollet                 | ISO 8559-1:2017          |
| 0.65                               | Tour de poignet                  | × longueur avant-bras             | Pheasant (1986)          |
| π × [3(a+b) − √((3a+b)(a+3b))] | Circonférence ellipse           | Précision < 0.04%                 | Ramanujan (1914)         |

---

# Noms de variables (justification)

Chaque nom a été choisi pour être **auto-descriptif**, **conforme aux conventions anatomiques françaises**, et **sans anglicismes**.

## Calibration (`_compute_scale`)

| Variable | Traduction | Pourquoi ce nom |
|---|---|---|
| `largeur_epaules_brute` | largeur d'épaules brute | "Largeur" = mesure horizontale ; "épaules" = landmarks shoulders ; "brute" = en coordonnées normalisées, pas encore en cm |
| `y_ep_moy` | y épaule moyen | "y" = coordonnée verticale dans l'image ; "ep" = abréviation d'épaules ; "moy" = moyenne des deux côtés |
| `y_ch_moy` | y cheville moyen | "ch" = cheville ; même logique que y_ep_moy |
| `dist_nez_cheville` | distance nez→cheville | "dist" = distance ; "nez" = parce qu'on utilise le landmark du nez (visible même de dos) ; "cheville" = landmark ankle |
| `dist_ep_cheville` | distance épaules→cheville | Deuxième estimation verticale indépendante pour croiser avec le nez |
| `largeur_bi_auric` | largeur bi-auriculaire | "Bi-auriculaire" = entre les deux oreilles (latin *auricula* = oreille), terme anatomique standard |
| `extension_cranienne` | extension crânienne | Remplace l'anglicisme `head_top_extra` ; "extension" = ce qui dépasse du point NOSE ; "crânienne" = relatif au crâne (vs crane = grue) |
| `hauteur_semelle` | hauteur de semelle | Remplace l'anglicisme `foot_extra` ; "semelle" = sous le pied, comme une semelle de chaussure ; immédiatement compris comme "distance cheville→sol" |
| `h_nez` | hauteur estimée par le nez | Abréviation claire : "h" = hauteur, "nez" = méthode employée |
| `h_ep` | hauteur estimée par les épaules | Idem, "ep" = épaules |
| `hauteur_brute` | hauteur brute | "Brute" = calculée par somme de segments, avant application du scale |
| `scale` | facteur d'échelle | Terme universel en imagerie (pixels/cm → cm) |

## Vue de face (`extraire_face`)

| Variable | Traduction | Pourquoi ce nom |
|---|---|---|
| `largeur_epaules` | largeur d'épaules | Même terme que dans `_compute_scale` mais en cm cette fois |
| `carrure_devant` | carrure devant | "Carrure" = terme du tailoring pour la largeur entre emmanchures ; "devant" = vue de face (≠ dos) |
| `largeur_buste_face` | largeur de buste (face) | "Buste" = torse au niveau de la poitrine ; "face" = précision de la vue |
| `largeur_sous_seins_face` | largeur sous la poitrine | "Sous-seins" = sous la poitrine, terminologie lingerie ; pas "underbust" |
| `largeur_ceinture_face` | largeur de ceinture | "Ceinture" = taille, au niveau du nombril |
| `largeur_hanches` | largeur de hanches | "Hanches" = niveau trochanters (landmark HIP) |
| `longueur_torse` | longueur du torse | "Longueur" = verticale ; "torse" = épaule→hanche ; pas "torso" |
| `haut_sein` | hauteur de sein | "Hauteur" car mesurée de l'épaule vers le bas jusqu'au niveau du buste |
| `longueur_sous_seins` | longueur sous-poitrine | Ne pas confondre avec `largeur_sous_seins_face` — ici c'est une longueur verticale |
| `longueur_taille` | longueur taille | Position du nombril mesurée depuis l'épaule |
| `longueur_chemise` | longueur chemise | Nom issue du métier (la chemise descend du nombril à la hanche) |
| `longueur_manche` | longueur manche longue | "Manche" tout court = la manche longue complète épaule→poignet |
| `longueur_manche_courte` | longueur manche courte | Précis : épaule→coude, nom utilisé dans les fiches de mesure |
| `longueur_avant_bras` | longueur avant-bras | "Avant-bras" = coude→poignet, terme anatomique français standard |
| `longueur_pantalon` | longueur pantalon | Hanche→cheville ; le nom du vêtement final plutôt que "jambe" |
| `longueur_jupe` | longueur jupe | Hanche→cheville pour une jupe longue ; distingué de "pantalon" bien que la mesure soit identique (permet filtrage par sexe) |
| `longueur_robe` | longueur robe | Épaule→cheville ; idem, nom orienté usage |
| `longueur_cuisse` | longueur cuisse | Hanche→genou ; "cuisse" plutôt que "thigh" |
| `longueur_mollet` | longueur mollet | Genou→cheville ; "mollet" plutôt que "calf" |
| `hauteur_genou` | hauteur du genou | "Hauteur" = sol→genou (≠ longueur qui serait genou→cheville) ; +6 cm de correction talon |

## Vue de profil (`extraire_profil`)

| Variable | Traduction | Pourquoi ce nom |
|---|---|---|
| `profond_buste` | profondeur de buste | "Profond" = abréviation de profondeur (axe Z, pas Y) ; "buste" = niveau poitrine |
| `profond_sous_seins` | profondeur sous-poitrine | Idem, niveau sous les seins |
| `profond_ceinture` | profondeur de ceinture | Idem, niveau taille |
| `profond_hanche` | profondeur de hanche | Idem, niveau hanches |
| `torse_profil` | longueur torse (profil) | Même mesure que `longueur_torse` mais depuis la vue de profil ; utilisée dans la fusion |

## Fusion des vues (`fusionner`)

| Variable | Traduction | Pourquoi ce nom |
|---|---|---|
| `l_ep`, `l_bu`, `l_ss`, `l_ce`, `l_ha` | largeur épaule / buste / sous-seins / ceinture / hanches | Préfixe `l_` = largeur ; abréviations de 2-3 lettres pour éviter les lignes trop longues |
| `p_bu`, `p_ss`, `p_ce`, `p_ha` | profondeur buste / sous-seins / ceinture / hanches | Préfixe `p_` = profondeur ; même abréviations |
| `dl_bu`, `dp_bu` | demi-largeur / demi-profondeur de buste | `d` = demi (half) ; utilisé pour les demi-axes de l'ellipse |
| `tour_poitrine` | tour de poitrine | "Tour" = circonférence (en français, un tour est une mesure de circonférence) ; "poitrine" plutôt que "chest" |
| `tour_sous_seins` | tour sous-poitrine | Idem ; "sous-seins" = sous la poitrine, standard lingerie |
| `tour_ceinture` | tour de ceinture | "Ceinture" = taille, standard tailoring |
| `tour_hanches` | tour de hanches | "Fesses" dans la sortie = `TOUR_FESSES` car = le tour au niveau le plus large des fesses ; ici "hanches" dans le code car vient de PROFONDEUR_HANCHE |
| `source_tours` | source des tours | Chaîne décrivant la méthode de calcul ("ellipse_ramanujan(face+profil)" ou "ratio_iso8559(face_seule)") |
| `c_poitrine`, `c_sous_seins`, `c_ceinture`, `c_hanches` | confiance des tours | `c_` = confiance ; valeur entre 0 et 1 |
| `l_mollet` | longueur mollet | Idem `longueur_mollet` ; abrégé ici car réutilisé pour plusieurs tours |
| `l_av_bras` | longueur avant-bras | Abréviation de `longueur_avant_bras` |
| `largeur_bi_auric` | largeur bi-auriculaire | Même variable que dans `_compute_scale` ; réutilisée ici pour le `TOUR_COU` |
| `profil_ok` | profil OK | Booléen : vrai si la vue de profil avait une profondeur exploitable ; décide entre ellipse et ratio simple |

---

# Questions jury anticipées

**Q : "Pourquoi la taille est obligatoire ?"**
R : "MediaPipe estime l'échelle 3D depuis une image unique, ce qui est imprécis. La taille connue est la seule référence fiable. Sans elle, on utilisait une largeur d'épaules moyenne (39 cm), qui ne s'applique pas aux enfants ni aux personnes hors norme."

**Q : "Comment calculez-vous le tour de ceinture ?"**
R : "Deux approches : (1) avec profil → ellipse de Ramanujan à partir de la largeur (face) et profondeur (profil), précision < 0.04% ; (2) sans profil → ratio largeur × 3.20, moins précis mais fonctionnel."

**Q : "Pourquoi 0.62 pour la ceinture ?"**
R : "C'est la position relative de la ceinture entre l'épaule et la hanche, basée sur la norme ISO 8559-1:2017. Le ratio (hauteur taille)/(hauteur épaule→hanche) est d'environ 0.60-0.65 dans la population adulte."

**Q : "Et si la personne est de profil imparfait ?"**
R : "Le `_clamp` limite les valeurs aberrantes. La profondeur minimale est plafonnée à 45% de la largeur pour éviter les ellipses aplaties. Si la photo de profil est inexpoitable, on utilise le fallback par ratio."

**Q : "Comment gérez-vous les hommes vs femmes ?"**
R : "Le filtre `filtrer_par_sexe` exclut 4 codes : longueur sous-seins, tour sous-seins, longueur jupe, longueur robe. Le genre est passé de Laravel → FastAPI dans le payload."

**Q : "Votre solution est-elle fiable ?"**
R : "La calibration par taille connue élimine l'imprécision de l'échelle MediaPipe. Les mesures finales sont cohérentes avec les proportions du corps humain car le même facteur d'échelle est appliqué à toutes les mesures. Les résultats sont validés par fusion de 3 vues (face, dos, profil)."
