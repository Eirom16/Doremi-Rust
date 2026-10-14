"""Shared artwork selection using the existing disk caches, without network I/O."""
import hashlib
from pathlib import Path
from urllib.parse import unquote, urlsplit

from doremi.config.paths import AppDirs


def resolve_artwork(url, video_id=""):
    url = str(url or "")
    if url.startswith("file:"):
        return url if Path(unquote(urlsplit(url).path)).is_file() else ""
    if url and not url.startswith(("http://", "https://")):
        path = Path(url)
        return path.resolve().as_uri() if path.is_file() else ""
    if url:
        path = AppDirs.artwork_cache / (hashlib.md5(url.encode()).hexdigest() + ".jpg")
        if path.is_file():
            return path.as_uri()
    if video_id and all(c.isalnum() or c in "_-" for c in video_id):
        path = AppDirs.cache / "offline" / "artwork" / (video_id + ".jpg")
        if path.is_file():
            return path.as_uri()
    return url


def cover_fields(tracks, explicit=""):
    """First available cover and up to four distinct sources in collection order."""
    sources = []
    if explicit:
        url = resolve_artwork(explicit)
        if url:
            return dict(thumbnail_url=url, artwork_sources=[url])
    for track in tracks:
        url = resolve_artwork(track.get("thumbnail_url", ""), track.get("videoId", ""))
        if url and url not in sources:
            sources.append(url)
            if len(sources) == 4:
                break
    return dict(thumbnail_url=sources[0] if sources else "", artwork_sources=sources)
