"""Capture displayed metadata at the action boundary, without network requests."""
from PySide6.QtCore import QAbstractItemModel
from math import isfinite

from doremi.audio.queue import QueueItem


def song_fields(item):
    """Only persistence fields; never forward arbitrary QML payload keys."""
    duration = item.get("duration_ms", 0)
    return dict(title=str(item.get("title", "") or ""),
                artist=str(item.get("artist", "") or ""),
                album=str(item.get("album", "") or ""),
                duration_ms=max(0, int(duration)) if isinstance(duration, (int, float)) and isfinite(duration) else 0,
                thumbnail_url=str(item.get("thumbnail_url", item.get("thumbnail", "")) or ""))


def capture_track_metadata(window, video_id):
    current = getattr(getattr(window, "queue", None), "current", None)
    if isinstance(current, QueueItem) and current.video_id == video_id:
        return song_fields(vars(current))
    route = getattr(window, "_current_route", "")
    if not isinstance(route, str):
        return {}
    vm = getattr(getattr(window, route + "_screen", None), "_vm", None)
    lookup = getattr(vm, "track_metadata", None)
    if callable(lookup):
        item = lookup(video_id)
        if isinstance(item, dict):
            return song_fields(item)
    for name in ("tracks", "songs", "featured", "rest", "tiles", "topSongs", "model", "related", "queueModel"):
        model = getattr(vm, name, None)
        if not isinstance(model, QAbstractItemModel) or not callable(getattr(model, "get", None)):
            continue
        for row in range(model.rowCount()):
            item = model.get(row)
            if isinstance(item, dict) and item.get("videoId") == video_id:
                return song_fields(item)
    return {}
