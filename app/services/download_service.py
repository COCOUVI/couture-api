import io
import cv2
import httpx
import numpy as np
from PIL import Image


async def download_image_as_rgb(url: str) -> np.ndarray:
    """
    Télécharge une image depuis une URL (Cloudinary) et
    retourne un numpy array RGB prêt pour MediaPipe.
    On demande à Cloudinary de limiter la largeur à 800px
    pour réduire le temps de téléchargement.
    """
    # Optimisation Cloudinary : redimensionner à 800px de large
    optimized_url = _cloudinary_resize(url, width=800)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(optimized_url)
        response.raise_for_status()

    img_pil = Image.open(io.BytesIO(response.content)).convert("RGB")
    return np.array(img_pil)


def _cloudinary_resize(url: str, width: int) -> str:
    """
    Insère un paramètre de transformation Cloudinary dans l'URL.
    Ex: .../upload/image.jpg → .../upload/w_800/image.jpg
    Ne modifie pas les URLs non-Cloudinary.
    """
    if "cloudinary.com" in url and "/upload/" in url:
        return url.replace("/upload/", f"/upload/w_{width},c_limit/")
    return url
