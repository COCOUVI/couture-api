# ── Service de téléchargement et prétraitement des images ────────────
import io

import httpx
import numpy as np
from PIL import Image, ImageOps


async def download_image_as_rgb(url: str) -> np.ndarray:
    """
    Telecharge une image depuis Cloudinary et retourne
    un numpy array RVB avec l'orientation EXIF corrigee.
    """
    # Redimensionnement côté Cloudinary pour accélérer le download
    optimized_url = _cloudinary_resize(url, width=800)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(optimized_url)
        response.raise_for_status()

    img_pil = Image.open(io.BytesIO(response.content))
    img_pil = ImageOps.exif_transpose(img_pil)   # Corrige l'orientation EXIF
    img_pil = img_pil.convert("RGB")              # Supprime le canal alpha si présent
    return np.array(img_pil)


def _cloudinary_resize(url: str, width: int) -> str:
    """Insere un redimensionnement Cloudinary dans l'URL pour réduire le poids."""
    if "cloudinary.com" in url and "/upload/" in url:
        return url.replace("/upload/", f"/upload/w_{width},c_limit/")
    return url
