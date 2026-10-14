"""Shared data loading for Playlist screen — used by both widget and QML versions.

REC-03C.3 recovery from rescue working tree
(``Doremi-Rust-Rescate`` ``src/doremi/ui/screens/playlist_data.py``,
185 lines). Adaptations vs rescue (no schema/migration changes):

- New ``session:`` / ``local-list:`` / ``smart:`` branches (rescue logic)
  with ``cover_fields`` mosaics and structured ``artists`` credits where the
  source already provides them (remote YT payloads).
- Explicit pagination: ``gather_playlist(..., *, limit=1000, offset=0)``.
  ``local-list:`` forwards to ``LocalLibraryRepository.tracks`` (never
  ``tracks(limit=None)``); ``session:`` forwards to
  ``ListeningPeriods.tracks``; ``smart:`` forwards ``limit`` to
  ``ExperienceRepository.smart_tracks`` (which has no offset, so
  ``limit+offset`` rows are fetched then sliced). ``local_`` slices the
  filtered download list. Remote YT branch returns the full provider
  response (provider owns its pagination).
- No silent truncation: paginated branches return ``limit``/``offset`` and
  ``has_more`` (``len(page) == limit`` heuristic; exact when the store holds
  more than the page). Callers fetch later pages with ``offset+limit``.
- Order and duplicate occurrences preserved (``position`` order; ``append``
  retains duplicates). ``local:`` identities returned as-is, never mapped to
  YouTube IDs. Offline availability comes from ``track_data``/repo
  ``is_file`` checks, so disappeared files are never reported as available;
  offline pages may be short because unavailable items are hidden, not
  counted. Single bounded repo call per branch (no N-plus-1). No Qt widgets;
  ``NetworkMonitor`` imported lazily; no network on import; no remote
  downloads in tests (``yt_client`` is mocked).
"""
from __future__ import annotations

from loguru import logger
from doremi.services.artwork import cover_fields

from doremi.ui.screens.home_data import _extract_thumbnail
from doremi.utils.time_utils import parse_duration_to_ms

_MAX_LIMIT = 1000


def _coerce_limit(value, *, default=_MAX_LIMIT, name="limit"):
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Invalid {name}")
    if value <= 0:
        raise ValueError(f"Invalid {name}")
    return min(value, _MAX_LIMIT)


def _coerce_offset(value, *, name="offset"):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"Invalid {name}")
    return value


def _duration_display(duration: str | None, dur_ms: int) -> str:
    if duration:
        return str(duration)
    if dur_ms:
        return f"{dur_ms // 60000}:{(dur_ms // 1000) % 60:02d}"
    return ""


async def gather_playlist(yt_client, playlist_id: str, *, limit=1000, offset=0) -> dict:
    """Fetch playlist data (local o YouTube Music) y normalízala.

    ``limit``/``offset`` paginate local branches (``session:``,
    ``local-list:``, ``smart:``, ``local_``). Later pages use
    ``offset+limit``; ``has_more`` signals a possibly non-empty next page.
    The remote YT branch ignores pagination and returns the full provider
    payload.
    """
    limit = _coerce_limit(limit, name="limit")
    offset = _coerce_offset(offset)
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
        "limit": limit,
        "offset": offset,
        "has_more": False,
    }
    if not playlist_id:
        return result

    from doremi.system.network import NetworkMonitor
    offline = NetworkMonitor.current_connectivity() is False

    def available_tracks(tracks):
        return [track for track in tracks if track.get("is_downloaded")] if offline else tracks

    if playlist_id.startswith("session:"):
        from doremi.services.listening_periods import ListeningPeriods
        try:
            first, last, cutoff = ListeningPeriods.parse_identity(playlist_id)
            tracks = await ListeningPeriods().tracks(first, last, cutoff, limit=limit, offset=offset)
        except (ValueError, OverflowError):
            tracks = []
        tracks = available_tracks(tracks)
        result.update(title="Sesión musical", author="Tu historial", tracks=tracks,
                      track_count=len(tracks), has_more=len(tracks) == limit,
                      **cover_fields(tracks))
        return result

    if playlist_id.startswith("local-list:"):
        from doremi.db.local_library_repository import LocalLibraryRepository
        title, tracks = await LocalLibraryRepository().tracks(playlist_id, limit=limit, offset=offset)
        tracks = available_tracks(tracks)
        result.update(title=title, author="Doremi · Playlist local", tracks=tracks, track_count=len(tracks),
                      has_more=len(tracks) == limit, **cover_fields(tracks))
        return result

    if playlist_id.startswith("smart:"):
        from doremi.db.experience_repository import ExperienceRepository, SMART_TITLES
        rule = playlist_id.split(":", 1)[1]
        # smart_tracks has limit but no offset: over-fetch then slice.
        fetched = await ExperienceRepository().smart_tracks(rule, limit=min(_MAX_LIMIT, limit + offset) or limit,
                                                            offline_only=offline)
        page = fetched[offset:offset + limit] if offset else fetched[:limit]
        # smart_tracks already applies offline_only in SQL; keep the filter
        # for safety without changing order.
        if offline:
            page = [t for t in page if t.get("is_downloaded")]
        result.update(title=SMART_TITLES[rule], author="Doremi · Colección inteligente",
                      tracks=page, track_count=len(page),
                      has_more=len(fetched) == min(_MAX_LIMIT, limit + offset),
                      **cover_fields(page))
        return result

    if playlist_id.startswith("local_"):
        return await _gather_local_playlist(playlist_id, result, limit=limit, offset=offset)
    return await _gather_remote_playlist(yt_client, playlist_id, result)


async def _gather_local_playlist(playlist_id: str, result: dict, *, limit=1000, offset=0) -> dict:
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

    for t in tracks[offset:offset + limit]:
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
    result["track_count"] = len(result["tracks"])
    result["has_more"] = len(tracks) > offset + limit
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
            "artists": artists,
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
