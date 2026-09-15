import io
import httpx
from PIL import Image
from loguru import logger

from doremi.native_rs import average_center_zone, adjust_hsv

EQ_PRESETS: dict[str, tuple[float, list[float]]] = {
    "Flat":         (0.0,  [0.0]*10),
    "Bass Boost":   (2.0,  [6.0, 5.0, 4.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
    "Treble Boost": (0.0,  [0.0, 0.0, 0.0, 0.0, 0.0, 2.0, 4.0, 5.0, 6.0, 6.0]),
    "Vocal":        (0.0,  [-2.0,-1.0, 0.0, 2.0, 4.0, 4.0, 3.0, 2.0, 1.0, 0.0]),
    "Classical":    (0.0,  [4.0, 3.0, 2.0, 0.0, 0.0, 0.0, 0.0, 2.0, 3.0, 4.0]),
    "Electronic":   (2.0,  [4.0, 3.0, 0.0, 2.0, 0.0, 0.0, 2.0, 3.0, 4.0, 4.0]),
    "Hip-Hop":      (2.0,  [5.0, 4.0, 2.0, 3.0, 0.0, 0.0, 1.0, 2.0, 3.0, 4.0]),
    "Rock":         (1.0,  [4.0, 3.0, 2.0, 0.0,-1.0,-1.0, 0.0, 2.0, 3.0, 4.0]),
    "Jazz":         (0.0,  [3.0, 2.0, 1.0, 2.0, 0.0, 0.0, 1.0, 2.0, 3.0, 3.0]),
    "Pop":          (0.0,  [-1.0, 0.0, 2.0, 3.0, 4.0, 3.0, 2.0, 0.0,-1.0,-1.0]),
}

EQ_BAND_LABELS = [
    "60Hz", "170Hz", "310Hz", "600Hz", "1kHz",
    "3kHz", "6kHz", "12kHz", "14kHz", "16kHz"
]


async def extract_dominant_color(image_url: str) -> str | None:
    """
    Extrae el color dominante de un artwork para usarlo como acento de tema.
    Usa el módulo nativo Rust (`doremi.native_rs`), requerido por el proyecto.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(image_url)

        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        img = img.resize((50, 50), Image.LANCZOS)
        w, h = img.size
        rgb = average_center_zone(list(img.tobytes()), w, h)
        if rgb:
            adjusted = adjust_hsv(rgb[0], rgb[1], rgb[2],
                                  min_saturation=0.5, min_value=0.6)
            return f"#{adjusted[0]:02x}{adjusted[1]:02x}{adjusted[2]:02x}"
        return None

    except Exception as e:
        logger.debug(f"Color extraction failed: {e}")
        return None
