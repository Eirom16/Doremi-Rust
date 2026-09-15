"""Shared data loading for Home screen — used by both widget and QML versions."""
from __future__ import annotations

import datetime
from typing import Any

from loguru import logger


def _parse_duration_ms(item: dict) -> int:
    """Extract duration in ms from a YouTube Music item."""
    if item.get("duration_seconds"):
        return int(item["duration_seconds"]) * 1000
    duration = item.get("duration") or item.get("lengthText", "")
    if duration:
        try:
            parts = str(duration).split(":")
            if len(parts) == 2:
                return (int(parts[0]) * 60 + int(parts[1])) * 1000
            elif len(parts) == 3:
                return (int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])) * 1000
        except (ValueError, IndexError):
            pass
    return 0


def _extract_artist_names(artists: Any) -> str:
    """Extract comma-separated artist names from various YouTube Music formats."""
    if isinstance(artists, list):
        return ", ".join(a.get("name", "") for a in artists if isinstance(a, dict)) or "Unknown"
    if isinstance(artists, str):
        return artists
    return "Unknown"


def _extract_title(item: dict) -> str:
    """Extract title from various YouTube Music item formats."""
    title = item.get("title", "Unknown")
    if isinstance(title, dict):
        return title.get("text", "Unknown")
    return str(title)


def _extract_thumbnail(item: dict) -> str:
    """Extract thumbnail URL from a YouTube Music item."""
    thumbnails = item.get("thumbnails", [])
    return thumbnails[-1].get("url", "") if thumbnails else ""


def _extract_navigate(item: dict) -> str:
    """Extract navigation route from a YouTube Music item."""
    video_id = item.get("videoId", "")
    playlist_id = item.get("playlistId", "")
    browse_id = item.get("browseId", "")

    if not playlist_id and browse_id and str(browse_id).startswith("VL"):
        playlist_id = browse_id
        browse_id = ""

    if video_id:
        return f"play:{video_id}"
    if playlist_id:
        return f"playlist?id={playlist_id}"
    if browse_id:
        if str(browse_id).startswith("UC"):
            return f"artist?id={browse_id}"
        return f"album?id={browse_id}"
    return ""


async def gather_home(yt_client) -> dict:
    """Fetch home data from YouTube Music and return normalized structures.

    Returns dict with keys: greeting, spotlight, tiles, horizontal, songs.
    """
    result = {
        "greeting": "",
        "spotlight": [],
        "tiles": [],
        "horizontal": [],     # flat (compat)
        "sections": [],       # agrupado por sección para las islas QML
        "songs": [],
    }

    # Time-based greeting
    hour = datetime.datetime.now().hour
    if hour < 12:
        result["greeting"] = "¡Buenos días!"
    elif hour < 18:
        result["greeting"] = "¡Buenas tardes!"
    else:
        result["greeting"] = "¡Buenas noches!"

    if not yt_client:
        return result

    try:
        home_data = await yt_client.get_home()
    except Exception as e:
        logger.error(f"Error fetching home: {e}")
        return result

    contents = None
    if isinstance(home_data, list) and home_data:
        contents = home_data
    elif isinstance(home_data, dict) and home_data.get("contents"):
        contents = home_data.get("contents", [])

    if not contents:
        try:
            charts_data = await yt_client.get_charts()
            if isinstance(charts_data, dict):
                tracks = charts_data.get("tracks", charts_data.get("items", []))
                playlists = charts_data.get("playlists", [])
                for pl in playlists[:10]:
                    result["horizontal"].append({
                        "section_title": "Playlists Populares",
                        "type": "playlist",
                        "item_title": pl.get("title", "Chart"),
                        "subtitle": "",
                        "thumbnail_url": _extract_thumbnail(pl),
                        "navigate": f"playlist?id={pl.get('playlistId', '')}",
                        "is_downloaded": False,
                    })
                for track in tracks[:12]:
                    result["songs"].append({
                        "title": track.get("title", "Unknown"),
                        "artist": _extract_artist_names(track.get("artists", [])),
                        "duration": str(track.get("lengthText", "")),
                        "duration_ms": _parse_duration_ms(track),
                        "thumbnail_url": _extract_thumbnail(track),
                        "videoId": track.get("videoId", ""),
                        "is_liked": False,
                    })
            elif isinstance(charts_data, list):
                for item in charts_data[:12]:
                    result["songs"].append({
                        "title": item.get("title", "Unknown"),
                        "artist": _extract_artist_names(item.get("artists", [])),
                        "duration": str(item.get("lengthText", "")),
                        "duration_ms": _parse_duration_ms(item),
                        "thumbnail_url": _extract_thumbnail(item),
                        "videoId": item.get("videoId", ""),
                        "is_liked": False,
                    })
        except Exception as e:
            logger.error(f"Error fetching charts fallback: {e}")
        return result

    # Fetch liked IDs
    liked_ids: set[str] = set()
    try:
        from doremi.db.repository import SongRepository
        liked_ids = await SongRepository().get_liked_video_ids()
    except Exception:
        pass

    # 1. Spotlight — first item with playlistId or browseId
    spotlight_item = None
    for section in contents:
        sec_items = section.get("contents", section.get("items", []))
        for item in sec_items:
            if isinstance(item, dict) and (item.get("playlistId") or item.get("browseId")):
                spotlight_item = item
                break
        if spotlight_item:
            break

    if spotlight_item:
        title = _extract_title(spotlight_item)
        artists = spotlight_item.get("artists", [])
        artist_names = _extract_artist_names(artists)
        thumb = _extract_thumbnail(spotlight_item)
        navigate = _extract_navigate(spotlight_item)
        result["spotlight"].append({
            "title": title,
            "subtitle": f"De {artist_names}",
            "thumbnail_url": thumb,
            "navigate": navigate,
        })

    # 2. Quick Access tiles (first 6 unique videoIds)
    seen_vids: set[str] = set()
    for section in contents:
        sec_items = section.get("contents", section.get("items", []))
        for item in sec_items:
            if len(result["tiles"]) >= 6:
                break
            if not isinstance(item, dict):
                continue
            vid = item.get("videoId")
            if not vid or vid in seen_vids:
                continue
            seen_vids.add(vid)
            result["tiles"].append({
                "title": _extract_title(item),
                "artist": _extract_artist_names(item.get("artists", [])),
                "thumbnail_url": _extract_thumbnail(item),
                "videoId": vid,
                "duration_ms": _parse_duration_ms(item),
            })
        if len(result["tiles"]) >= 6:
            break

    # 3. Sections → horizontal or song grid
    for section in contents[:6]:
        if not isinstance(section, dict):
            continue
        sec_items = section.get("contents", section.get("items", []))
        if not isinstance(sec_items, list):
            continue

        sec_title = section.get("title", "Sección")
        if isinstance(sec_title, dict):
            sec_title = sec_title.get("text", "Sección")

        has_songs = any("videoId" in it for it in sec_items[:6] if isinstance(it, dict))

        if has_songs:
            for it in sec_items[:8]:
                if not isinstance(it, dict) or not it.get("videoId"):
                    continue
                result["songs"].append({
                    "title": _extract_title(it),
                    "artist": _extract_artist_names(it.get("artists", [])),
                    "duration": str(it.get("duration", "")),
                    "duration_ms": _parse_duration_ms(it),
                    "thumbnail_url": _extract_thumbnail(it),
                    "videoId": it.get("videoId", ""),
                    "is_liked": it.get("videoId", "") in liked_ids,
                })
        else:
            for it in sec_items[:15]:
                if not isinstance(it, dict):
                    continue
                vid = it.get("videoId", "")
                pl_id = it.get("playlistId", "")
                br_id = it.get("browseId", "")
                if not pl_id and br_id and str(br_id).startswith("VL"):
                    pl_id = br_id
                    br_id = ""

                if pl_id:
                    item_type = "playlist"
                    navigate = f"playlist?id={pl_id}"
                elif br_id:
                    if str(br_id).startswith("UC"):
                        item_type = "artist"
                        navigate = f"artist?id={br_id}"
                    else:
                        item_type = "album"
                        navigate = f"album?id={br_id}"
                elif vid:
                    item_type = "song"
                    navigate = f"play:{vid}"
                else:
                    continue

                author = it.get("author")
                subtitle = ""
                if isinstance(author, list):
                    subtitle = ", ".join(a.get("name", "") for a in author if isinstance(a, dict))
                elif isinstance(author, dict):
                    subtitle = author.get("name", "")
                elif isinstance(author, str):
                    subtitle = author
                if not subtitle:
                    subtitle = it.get("description", "")

                result["horizontal"].append({
                "section_title": str(sec_title),
                "type": item_type,
                "item_title": _extract_title(it),
                "subtitle": subtitle,
                "thumbnail_url": _extract_thumbnail(it),
                "navigate": navigate,
                "is_downloaded": False,
            })

    # Agrupar horizontal en secciones ordenadas (las islas renderizan rails)
    _sections: dict[str, list] = {}
    for item in result["horizontal"]:
        _sections.setdefault(item.get("section_title", ""), []).append(item)
    result["sections"] = [
        {"title": title, "items": items} for title, items in _sections.items() if title
    ]

    return result
