"""Shared data loading for Playlist screen — used by both widget and QML versions."""
from __future__ import annotations

from loguru import logger

from doremi.ui.screens.home_data import _extract_thumbnail
from doremi.utils.time_utils import parse_duration_to_ms


def _duration_display(duration: str | None, dur_ms: int) -> str:
    if duration:
        return str(duration)
    if dur_ms:
        return f"{dur_ms // 60000}:{(dur_ms // 1000) % 60:02d}"
    return ""


async def gather_playlist(yt_client, playlist_id: str) -> dict:
    """Fetch playlist data (local o YouTube Music) y normalízala."""
    result = {
        "playlist_id": playlist_id or "",
        "is_local": False,
        "title": "",
        "author": "",
        "track_count": 0,
        "thumbnail_url": "",
        "tracks": [],
        "downloaded_count": 0,
        "is_fully_downloaded": False,
        "local_meta": [],  # metadatos para on_play_local_playlist
    }
    if not playlist_id:
        return result

    if playlist_id.startswith("local_"):
        return await _gather_local_playlist(playlist_id, result)
    return await _gather_remote_playlist(yt_client, playlist_id, result)


async def _gather_local_playlist(playlist_id: str, result: dict) -> dict:
    from doremi.db.repository import DownloadRepository, SongRepository

    actual_pid = playlist_id[len("local_"):]
    result["is_local"] = True

    downloads = await DownloadRepository().get_downloads()
    try:
        liked_ids = await SongRepository().get_liked_video_ids()
    except Exception:
        liked_ids = set()

    tracks = [d for d in downloads if d.parent_playlist_id == actual_pid]
    if not tracks:
        result["title"] = "Playlist Local"
        return result

    first = tracks[0]
    result["title"] = first.parent_playlist_title or "Playlist Local"
    result["author"] = "Biblioteca Local"
    result["track_count"] = len(tracks)
    result["thumbnail_url"] = (
        getattr(first, "parent_playlist_thumbnail_url", "") or first.thumbnail_url or ""
    )
    result["downloaded_count"] = len(tracks)
    result["is_fully_downloaded"] = True

    for t in tracks:
        dur_ms = t.duration_ms or 0
        result["tracks"].append({
            "videoId": t.video_id,
            "title": t.title,
            "artist": t.artist,
            "duration": _duration_display("", dur_ms),
            "duration_ms": dur_ms,
            "thumbnail_url": t.thumbnail_url or "",
            "is_liked": t.video_id in liked_ids,
            "is_downloaded": True,
            "setVideoId": "",
        })
        result["local_meta"].append({
            "video_id": t.video_id,
            "title": t.title,
            "artist": t.artist,
            "thumbnail_url": t.thumbnail_url,
            "file_path": t.file_path,
            "duration_ms": dur_ms,
        })
    return result


async def _gather_remote_playlist(yt_client, playlist_id: str, result: dict) -> dict:
    try:
        data = await yt_client.get_playlist(playlist_id)
    except Exception as e:
        logger.error(f"Error fetching playlist {playlist_id}: {e}")
        return result

    if not data:
        return result

    liked_ids: set[str] = set()
    downloaded_vids: set[str] = set()
    try:
        from doremi.db.repository import DownloadRepository, SongRepository
        downloads = await DownloadRepository().get_downloads()
        downloaded_vids = {d.video_id for d in downloads}
        liked_ids = await SongRepository().get_liked_video_ids()
    except Exception as e:
        logger.debug(f"Error reading download/like state: {e}")

    author = data.get("author", "")
    if isinstance(author, dict):
        author = author.get("name", "")
    result["author"] = str(author or "Unknown")

    result["title"] = str(data.get("title", "Unknown"))
    result["thumbnail_url"] = _extract_thumbnail(data)

    raw_tracks = data.get("tracks", [])
    tracks = []
    for t in raw_tracks:
        video_id = t.get("videoId") or t.get("video_id")
        if not video_id:
            continue
        dur_ms = parse_duration_to_ms(t.get("duration", "") or 0)
        artists = t.get("artists", [])
        if isinstance(artists, list):
            artist = ", ".join(a.get("name", "") for a in artists if isinstance(a, dict))
        else:
            artist = str(artists or "")
        tracks.append({
            "videoId": video_id,
            "title": str(t.get("title", "Unknown")),
            "artist": artist or "Unknown",
            "duration": _duration_display(str(t.get("duration", "") or ""), dur_ms),
            "duration_ms": dur_ms,
            "thumbnail_url": _extract_thumbnail(t),
            "is_liked": video_id in liked_ids,
            "is_downloaded": video_id in downloaded_vids,
            "setVideoId": str(t.get("setVideoId", "") or ""),
        })

    result["tracks"] = tracks
    result["track_count"] = data.get("trackCount", 0) or len(tracks)
    result["downloaded_count"] = sum(1 for t in tracks if t["is_downloaded"])
    result["is_fully_downloaded"] = bool(
        tracks and result["downloaded_count"] == result["track_count"]
    )
    return result
