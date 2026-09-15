"""Shared data loading for Search screen — used by both widget and QML versions."""
from __future__ import annotations

from loguru import logger

from doremi.ui.screens.home_data import (
    _extract_artist_names,
    _extract_thumbnail,
    _parse_duration_ms,
)

YT_FILTERS = {"song": "songs", "album": "albums", "playlist": "playlists"}


async def gather_search(yt_client, query: str, category: str, limit: int = 40) -> list[dict]:
    """Busca en YouTube Music y normaliza resultados de una categoría."""
    if not yt_client or not query:
        return []

    try:
        results = await yt_client.search(query, filter=YT_FILTERS.get(category), limit=limit)
    except Exception as e:
        logger.error(f"Error searching '{category}' for '{query}': {e}")
        return []

    results = results or []

    if category == "song":
        liked_ids: set[str] = set()
        try:
            from doremi.db.repository import SongRepository
            liked_ids = await SongRepository().get_liked_video_ids()
        except Exception:
            pass
        return [_normalize_song(it, liked_ids) for it in results if it.get("videoId")]

    if category == "album":
        return [
            {
                "title": str(it.get("title", "Unknown")),
                "artist": _extract_artist_names(it.get("artists", [])),
                "thumbnail_url": _extract_thumbnail(it),
                "navigate": f"album?id={it['browseId']}" if it.get("browseId") else "",
            }
            for it in results
        ]

    if category == "playlist":
        downloaded: set[str] = set()
        try:
            from doremi.db.repository import DownloadRepository
            downloads = await DownloadRepository().get_downloads()
            downloaded = {d.parent_playlist_id for d in downloads if d.parent_playlist_id}
        except Exception:
            pass
        return [
            {
                "title": str(it.get("title", "Unknown")),
                "subtitle": str(it.get("count", "")) and f"{it['count']} canciones" or "",
                "thumbnail_url": _extract_thumbnail(it),
                "is_downloaded": it.get("playlistId", "") in downloaded,
                "navigate": f"playlist?id={it['playlistId']}" if it.get("playlistId") else "",
            }
            for it in results
        ]

    return []


def _normalize_song(item: dict, liked_ids: set[str]) -> dict:
    duration = item.get("duration", "")
    if isinstance(duration, (int, float)) and duration > 0:
        # yt a veces devuelve segundos como número
        dur_ms = int(duration) * 1000
        dur_str = f"{int(duration) // 60}:{int(duration) % 60:02d}"
    else:
        dur_str = str(duration or "")
        dur_ms = _parse_duration_ms(item)
    return {
        "videoId": item.get("videoId", ""),
        "title": str(item.get("title", "Unknown")),
        "artist": _extract_artist_names(item.get("artists", [])),
        "duration": dur_str,
        "duration_ms": dur_ms,
        "thumbnail_url": _extract_thumbnail(item),
        "is_liked": item.get("videoId", "") in liked_ids,
        "result_type": item.get("resultType", "song"),
    }
