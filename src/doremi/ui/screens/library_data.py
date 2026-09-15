"""Shared data loading for Library screen — used by both widget and QML versions."""
from __future__ import annotations

from typing import Any

from loguru import logger

from doremi.ui.screens.home_data import (
    _extract_artist_names,
    _extract_thumbnail,
    _parse_duration_ms,
)


def _format_duration(ms: int) -> str:
    if not ms:
        return ""
    seconds = ms // 1000
    return f"{seconds // 60}:{seconds % 60:02d}"


async def gather_liked_songs(yt_client) -> list[dict]:
    """Canciones favoritas: DB local primero (instantáneo) + YouTube Music."""
    combined: list[dict] = []
    seen: set[str] = set()

    try:
        from doremi.db.repository import SongRepository
        for song in await SongRepository().get_liked_songs():
            if song.video_id in seen:
                continue
            seen.add(song.video_id)
            combined.append({
                "videoId": song.video_id,
                "title": song.title,
                "artist": song.artist,
                "duration": _format_duration(song.duration_ms or 0),
                "duration_ms": song.duration_ms or 0,
                "thumbnail_url": song.thumbnail_url or "",
                "is_liked": True,
            })
    except Exception as e:
        logger.debug(f"Error reading local liked songs: {e}")

    if yt_client and yt_client.is_authenticated:
        try:
            data = await yt_client.get_liked_songs(limit=50)
            for track in (data or {}).get("tracks", []):
                vid = track.get("videoId")
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                combined.append({
                    "videoId": vid,
                    "title": track.get("title", "Unknown"),
                    "artist": _extract_artist_names(track.get("artists", [])),
                    "duration": str(track.get("duration", "")),
                    "duration_ms": _parse_duration_ms(track),
                    "thumbnail_url": _extract_thumbnail(track),
                    "is_liked": True,
                })
        except Exception as e:
            logger.error(f"Error fetching YT liked songs: {e}")

    return combined


async def gather_library_albums(yt_client) -> list[dict]:
    if not yt_client or not yt_client.is_authenticated:
        return []
    try:
        albums = await yt_client.get_library_albums()
    except Exception as e:
        logger.error(f"Error fetching library albums: {e}")
        return []
    return [
        {
            "title": str(album.get("title", "Unknown")),
            "artist": _extract_artist_names(album.get("artists", [])),
            "year": str(album.get("year", "")),
            "thumbnail_url": _extract_thumbnail(album),
            "navigate": f"album?id={album['browseId']}" if album.get("browseId") else "",
        }
        for album in (albums or [])
        if isinstance(album, dict)
    ]


async def gather_library_artists(yt_client, limit: int = 50) -> list[dict]:
    if not yt_client or not yt_client.is_authenticated:
        return []
    try:
        artists = await yt_client.get_library_artists(limit=limit)
    except Exception as e:
        logger.error(f"Error fetching library artists: {e}")
        return []
    return [
        {
            "name": str(artist.get("artist", "Unknown")),
            "thumbnail_url": _extract_thumbnail(artist),
            "navigate": f"artist?id={artist['browseId']}" if artist.get("browseId") else "",
        }
        for artist in (artists or [])
        if isinstance(artist, dict)
    ]


async def gather_library_playlists(yt_client) -> list[dict]:
    if not yt_client or not yt_client.is_authenticated:
        return []
    try:
        playlists = await yt_client.get_library_playlists()
    except Exception as e:
        logger.error(f"Error fetching library playlists: {e}")
        return []

    downloaded_ids: set[str] = set()
    try:
        from doremi.db.repository import DownloadRepository
        downloads = await DownloadRepository().get_downloads()
        downloaded_ids = {d.parent_playlist_id for d in downloads if d.parent_playlist_id}
    except Exception as e:
        logger.debug(f"Error fetching downloads for badges: {e}")

    result: list[dict] = []
    for pl in playlists or []:
        if not isinstance(pl, dict):
            continue
        count = pl.get("count", "")
        playlist_id = pl.get("playlistId", "")
        result.append({
            "title": str(pl.get("title", "Unknown")),
            "subtitle": f"{count} canciones" if count else "",
            "count": str(count or ""),
            "thumbnail_url": _extract_thumbnail(pl),
            "is_downloaded": playlist_id in downloaded_ids,
            "navigate": f"playlist?id={playlist_id}" if playlist_id else "",
        })
    return result
