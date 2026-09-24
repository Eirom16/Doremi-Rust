"""Shared data loading for Album screen — used by both widget and QML versions."""
from __future__ import annotations

from loguru import logger

from doremi.ui.screens.home_data import _extract_thumbnail
from doremi.utils.time_utils import parse_duration_to_ms


def _artist_names(artists, fallback: str = "") -> str:
    if isinstance(artists, list):
        names = [a.get("name", "") if isinstance(a, dict) else str(a) for a in artists]
        return ", ".join(n for n in names if n) or fallback
    return str(artists) if artists else fallback


def normalize_album_track(track: dict, album_artists: str) -> dict | None:
    video_id = track.get("videoId") or track.get("video_id")
    if not video_id:
        return None
    dur_ms = 0
    for key in ("duration_seconds", "durationSeconds", "lengthSeconds"):
        if track.get(key):
            dur_ms = parse_duration_to_ms(track[key])
            break
    if not dur_ms:
        dur_ms = parse_duration_to_ms(track.get("duration"))
    duration = str(track.get("duration", "") or "")
    if not duration and dur_ms:
        duration = f"{dur_ms // 60000}:{(dur_ms // 1000) % 60:02d}"
    thumb = _extract_thumbnail(track)
    return {
        "videoId": video_id,
        "title": str(track.get("title", "Unknown")),
        "artist": _artist_names(track.get("artists", []), fallback=album_artists),
        "duration": duration,
        "duration_ms": dur_ms,
        "thumbnail_url": thumb,
    }


def is_podcast_id(browse_id: str) -> bool:
    """Los podcasts de YouTube Music usan identificadores MPSP."""
    return browse_id.startswith("MPSP")


async def fetch_album_or_podcast(yt_client, browse_id: str) -> dict:
    """Devuelve álbumes y podcasts con la misma forma para ambas interfaces."""
    if is_podcast_id(browse_id):
        podcast = await yt_client.get_podcast(browse_id)
        if not podcast:
            return {}
        author = podcast.get("author", {})
        author_name = author.get("name", "") if isinstance(author, dict) else str(author or "")
        data = dict(podcast)
        data["type"] = "Podcast"
        data["artists"] = [{"name": author_name}] if author_name else []
        data["tracks"] = []
        for episode in podcast.get("episodes", []):
            normalized = dict(episode)
            normalized.setdefault("artists", data["artists"])
            data["tracks"].append(normalized)
        data["trackCount"] = len(data["tracks"])
        return data
    return await yt_client.get_album(browse_id)


async def gather_album(yt_client, browse_id: str) -> dict:
    """Fetch album data and normalize it for both UI versions."""
    result = {
        "browse_id": browse_id,
        "type": "ÁLBUM",
        "title": "",
        "meta": "",
        "thumbnail_url": "",
        "tracks": [],
        "downloaded_count": 0,
        "track_count": 0,
        "is_fully_downloaded": False,
    }
    if not yt_client or not browse_id:
        return result

    try:
        data = await fetch_album_or_podcast(yt_client, browse_id)
    except Exception as e:
        logger.error(f"Error fetching album {browse_id}: {e}")
        return result

    if not data:
        return result

    album_artists = _artist_names(data.get("artists", []))
    year = str(data.get("year", "") or "")
    result["type"] = str(data.get("type", "ÁLBUM")).upper()
    result["title"] = str(data.get("title", "Unknown"))
    result["thumbnail_url"] = _extract_thumbnail(data)

    liked_ids: set[str] = set()
    downloaded_vids: set[str] = set()
    try:
        from doremi.db.repository import DownloadRepository, SongRepository
        downloads = await DownloadRepository().get_downloads()
        downloaded_vids = {d.video_id for d in downloads}
        liked_ids = await SongRepository().get_liked_video_ids()
    except Exception as e:
        logger.debug(f"Error reading download/like state: {e}")

    raw_tracks = data.get("tracks", [])
    tracks = []
    for t in raw_tracks:
        item = normalize_album_track(t, album_artists)
        if item:
            item["is_liked"] = item["videoId"] in liked_ids
            item["is_downloaded"] = item["videoId"] in downloaded_vids
            tracks.append(item)

    result["tracks"] = tracks
    result["track_count"] = data.get("trackCount", 0) or len(tracks)
    result["downloaded_count"] = sum(1 for t in tracks if t["is_downloaded"])
    result["is_fully_downloaded"] = bool(
        tracks and result["downloaded_count"] == result["track_count"] and result["downloaded_count"] > 0
    )

    meta = album_artists
    if year:
        meta += f" • {year}"
    if result["track_count"]:
        item_name = "episodios" if is_podcast_id(browse_id) else "canciones"
        meta += f" • {result['track_count']} {item_name}"
    result["meta"] = meta
    return result
