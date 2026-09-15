"""Shared data loading for Stats screen — used by both widget and QML versions."""
from __future__ import annotations

import datetime
from collections import Counter

from loguru import logger


async def gather_stats() -> dict:
    """Calcula métricas de escucha desde el historial local."""
    result = {
        "time_listened": "0m",
        "total_plays": 0,
        "unique_artists": 0,
        "top_songs": [],   # [{videoId, title, artist, plays, thumbnail_url, is_liked}]
        "chart": [],       # [{day, count}] — últimos 7 días
    }

    try:
        from doremi.db.repository import HistoryRepository, SongRepository, DownloadRepository
        history_repo = HistoryRepository()
        raw = await history_repo.get_history(limit=500)
        all_history = [entry for entry, _ in raw]
        liked_ids = await SongRepository().get_liked_video_ids()
    except Exception as e:
        logger.error(f"Error gathering stats: {e}")
        return result

    if not all_history:
        return result

    # Tarjetas
    total_ms = sum(entry.duration_ms or 0 for entry in all_history)
    total_mins = total_ms // 60000
    result["time_listened"] = (
        f"{total_mins // 60}h {total_mins % 60}m" if total_mins >= 60 else f"{total_mins}m"
    )
    result["total_plays"] = len(all_history)
    result["unique_artists"] = len({e.artist for e in all_history if e.artist})

    # Top 5 canciones
    song_repo = SongRepository()
    dl_repo = DownloadRepository()
    counter = Counter((e.video_id, e.title, e.artist) for e in all_history)
    for (video_id, title, artist), plays in counter.most_common(5):
        thumbnail_url = ""
        try:
            db_song = await song_repo.get_song(video_id)
            if db_song and db_song.thumbnail_url:
                thumbnail_url = db_song.thumbnail_url
            else:
                db_download = await dl_repo.get_download(video_id)
                if db_download and db_download.thumbnail_url:
                    thumbnail_url = db_download.thumbnail_url
        except Exception:
            pass
        result["top_songs"].append({
            "videoId": video_id,
            "title": title,
            "artist": artist,
            "plays": plays,
            "thumbnail_url": thumbnail_url,
            "is_liked": video_id in liked_ids,
        })

    # Actividad últimos 7 días
    weekday_map = {0: "Lun", 1: "Mar", 2: "Mié", 3: "Jue", 4: "Vie", 5: "Sáb", 6: "Dom"}
    today = datetime.date.today()
    days: dict[datetime.date, int] = {
        today - datetime.timedelta(days=i): 0 for i in range(6, -1, -1)
    }
    for entry in all_history:
        if entry.played_at and entry.played_at.date() in days:
            days[entry.played_at.date()] += 1
    result["chart"] = [
        {"day": weekday_map[d.weekday()], "count": count}
        for d, count in sorted(days.items())
    ]

    return result
