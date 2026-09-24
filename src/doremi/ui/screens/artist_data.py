"""Shared data loading for Artist screen — used by both widget and QML versions."""
from __future__ import annotations

from loguru import logger

from doremi.ui.screens.home_data import (
    _extract_artist_names,
    _extract_thumbnail,
    _parse_duration_ms,
)


async def gather_artist(yt_client, channel_id: str) -> dict:
    """Fetch artist data and normalize it for both UI versions."""
    result = {
        "name": "",
        "subscribers": "",
        "thumbnail_url": "",
        "songs": [],
        "albums": [],
        "related": [],
    }

    if not yt_client or not channel_id:
        return result

    try:
        data = await yt_client.get_artist(channel_id)
    except Exception as e:
        logger.error(f"Error fetching artist {channel_id}: {e}")
        return result

    if not data:
        return result

    result["name"] = str(data.get("name", "Unknown"))
    result["subscribers"] = str(data.get("subscribers", "") or "")
    result["thumbnail_url"] = _extract_thumbnail(data)

    try:
        from doremi.db.repository import SongRepository
        liked_ids = await SongRepository().get_liked_video_ids()
    except Exception:
        liked_ids = set()

    # YouTube Music ya entrega el conjunto de canciones disponible para este
    # artista. No truncarlo: la vista debe permitir descubrir su catálogo.
    for track in data.get("songs", {}).get("results", []):
        vid = track.get("videoId", "")
        if not vid:
            continue
        artist = _extract_artist_names(track.get("artists", []))
        if artist == "Unknown":
            artist = result["name"]
        result["songs"].append({
            "videoId": vid,
            "title": str(track.get("title", "Unknown")),
            "artist": artist,
            "duration": str(track.get("duration", "") or ""),
            "duration_ms": _parse_duration_ms(track),
            "thumbnail_url": _extract_thumbnail(track),
            "is_liked": vid in liked_ids,
        })

    for album in data.get("albums", {}).get("results", []):
        browse_id = album.get("browseId", "")
        result["albums"].append({
            "title": str(album.get("title", "Unknown")),
            "artist": result["name"],
            "year": str(album.get("year", "") or ""),
            "thumbnail_url": _extract_thumbnail(album),
            "navigate": f"album?id={browse_id}" if browse_id else "",
        })

    for rel in data.get("related", {}).get("results", []):
        browse_id = rel.get("browseId", "")
        result["related"].append({
            "name": str(rel.get("title", "Unknown")),
            "thumbnail_url": _extract_thumbnail(rel),
            "navigate": f"artist?id={browse_id}" if browse_id else "",
        })

    return result
