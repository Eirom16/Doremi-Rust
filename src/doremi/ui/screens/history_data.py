"""UI-independent history loading shared by the remaining presentation layers."""

from __future__ import annotations

from loguru import logger


async def gather_history(yt_client) -> tuple[list[dict], set, int]:
    """Fetch and merge local and YouTube Music history by ``videoId``."""
    from doremi.db.repository import HistoryRepository, SongRepository
    from doremi.utils.time_utils import format_duration_short, parse_duration_to_ms

    liked_ids = await SongRepository().get_liked_video_ids()
    local_history = await HistoryRepository().get_history(limit=50)

    yt_history = []
    if yt_client and yt_client.is_authenticated:
        try:
            yt_history = await yt_client.get_history()
        except Exception as exc:
            logger.error(f"Error fetching YouTube history: {exc}")

    items: list[dict] = []
    seen: set[str] = set()
    for entry, thumbnail_url in local_history:
        if entry.video_id in seen:
            continue
        seen.add(entry.video_id)
        items.append({
            "videoId": entry.video_id,
            "title": entry.title,
            "artist": entry.artist,
            "duration": format_duration_short(entry.duration_ms or 0) if entry.duration_ms else "",
            "duration_ms": entry.duration_ms or 0,
            "thumbnail_url": thumbnail_url or "",
        })

    for entry in yt_history:
        video_id = entry.get("videoId", "")
        if not video_id or video_id in seen:
            continue
        seen.add(video_id)
        artists_data = entry.get("artists", [])
        artist_names = ", ".join(artist.get("name", "") for artist in artists_data) if artists_data else ""
        thumbnails = entry.get("thumbnails", [])
        thumb_url = thumbnails[-1].get("url", "") if thumbnails else ""
        duration = entry.get("duration", "")
        items.append({
            "videoId": video_id,
            "title": entry.get("title", "Desconocido"),
            "artist": artist_names,
            "duration": duration,
            "duration_ms": parse_duration_to_ms(duration),
            "thumbnail_url": thumb_url,
        })

    return items, liked_ids, len(local_history)
