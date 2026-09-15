import io
import httpx
from PIL import Image
from loguru import logger
from doremi.config.paths import AppDirs
from doremi.config.themes import extract_dominant_color
from pathlib import Path
import hashlib


async def get_dominant_color_from_url(image_url: str) -> str | None:
    return await extract_dominant_color(image_url)


async def get_artwork_color(artwork_url: str) -> str | None:
    try:
        return await get_dominant_color_from_url(artwork_url)
    except Exception as e:
        logger.debug(f"Failed to extract color: {e}")
        return None