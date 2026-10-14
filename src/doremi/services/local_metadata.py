"""Read embedded covers and tags without changing the user's audio files.

Synchronous by design: decoding and thumbnailing run on the calling thread,
so future consumers (Qt controllers, repositories) must offload
:func:`read_metadata` with ``asyncio.to_thread`` or a worker thread instead
of calling it on the Qt main thread. No ``asyncio`` is introduced here and
no network I/O is performed.
"""
import base64
import hashlib
import io
import tempfile
from pathlib import Path

from PIL import Image, ImageOps
from loguru import logger
from mutagen import File, MutagenError
from mutagen.flac import Picture
from mutagen.id3 import ID3, ID3NoHeaderError

from doremi.config.paths import AppDirs


def _first(tags, *keys):
    for key in keys:
        value = tags.get(key)
        if hasattr(value, "text"):
            value = value.text
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ""
        if value:
            return str(value).strip()[:500]
    return ""


def _picture(tags, audio):
    pictures = list(getattr(audio, "pictures", []))
    if hasattr(tags, "getall"):
        pictures += tags.getall("APIC")
    for value in tags.get("metadata_block_picture", []):
        try:
            pictures.append(Picture(base64.b64decode(value)))
        except (ValueError, MutagenError):
            continue
    pictures.sort(key=lambda picture: getattr(picture, "type", 0) != 3)
    if pictures:
        return pictures[0].data
    covers = tags.get("covr", [])
    if covers:
        return bytes(covers[0])
    covers = tags.get("coverart", [])
    return base64.b64decode(covers[0]) if covers else None


def read_metadata(path):
    """Return ``{title, artist, album, duration_ms, thumbnail_url}`` for *path*.

    Read-only against the user's library: the audio file is never modified.
    The only write is a content-addressed JPEG thumbnail under
    ``AppDirs.artwork_cache`` (``embedded-<sha256>.jpg``), created atomically
    via a temporary file + ``Path.replace`` and skipped when the embedded
    picture exceeds 16 MiB (checked before any Pillow decode).
    """
    path = Path(path)
    result = dict(title=path.stem, artist="", album="", duration_ms=0, thumbnail_url="")
    try:
        audio = File(path)
        tags = audio.tags if audio is not None and audio.tags is not None else {}
        if audio is None and path.suffix.lower() == ".mp3":
            # Also accept an ID3-only file; malformed audio must not prevent import.
            try:
                tags = ID3(path)
            except ID3NoHeaderError:
                pass
        result.update(title=_first(tags, "title", "TIT2", "\xa9nam") or path.stem,
                      artist=_first(tags, "artist", "TPE1", "\xa9ART"),
                      album=_first(tags, "album", "TALB", "\xa9alb"),
                      duration_ms=int(getattr(getattr(audio, "info", None), "length", 0) * 1000))
        data = _picture(tags, audio)
        if data and len(data) <= 16 * 1024 * 1024:
            destination = AppDirs.artwork_cache / ("embedded-" + hashlib.sha256(data).hexdigest() + ".jpg")
            if not destination.is_file():
                with Image.open(io.BytesIO(data)) as image:
                    image = ImageOps.exif_transpose(image).convert("RGB")
                    image.thumbnail((1024, 1024))
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".jpg", delete=False) as file:
                        temporary = Path(file.name)
                    try:
                        image.save(temporary, format="JPEG", quality=90)
                        temporary.replace(destination)
                    finally:
                        temporary.unlink(missing_ok=True)
            result["thumbnail_url"] = destination.as_uri()
    except (MutagenError, OSError, ValueError, TypeError, Image.DecompressionBombError) as exc:
        logger.debug("Could not read local metadata for {}: {}", path.name, exc)
    return result
