import logging
import re
from urllib.parse import urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_CLOUDINARY_PATTERN = re.compile(
    r"/image/upload/(?:v\d+/)?(.+)"
)


def _extract_public_id(url: str) -> str | None:
    path = urlparse(url).path
    match = _CLOUDINARY_PATTERN.search(path)
    if not match:
        return None
    full = match.group(1)
    public_id = re.sub(r"\.\w+$", "", full)
    return public_id


async def delete_cloudinary_image(url: str) -> bool:
    if not settings.CLOUDINARY_API_KEY or not settings.CLOUDINARY_API_SECRET:
        logger.warning("CLOUDINARY_API_KEY/CLOUDINARY_API_SECRET non configurés")
        return False

    public_id = _extract_public_id(url)
    if not public_id:
        logger.warning("Impossible d'extraire public_id de l'URL: %s", url)
        return False

    destroy_url = (
        f"https://api.cloudinary.com/v1_1/"
        f"{settings.CLOUDINARY_CLOUD_NAME}/image/destroy"
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                destroy_url,
                data={
                    "public_id": public_id,
                    "api_key": settings.CLOUDINARY_API_KEY,
                },
                auth=(settings.CLOUDINARY_API_KEY, settings.CLOUDINARY_API_SECRET),
            )
        data = response.json()
        if data.get("result") == "ok":
            logger.info("Image supprimée de Cloudinary: %s", public_id)
            return True
        logger.warning(
            "Échec suppression Cloudinary %s: %s", public_id, data.get("result")
        )
        return False
    except Exception as e:
        logger.error("Erreur suppression Cloudinary %s: %s", public_id, e)
        return False


async def cleanup_cloudinary_images(urls: list[str]) -> None:
    for url in urls:
        await delete_cloudinary_image(url)
