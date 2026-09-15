"""Shared data loading for Downloads screen — used by both widget and QML versions."""
from __future__ import annotations

from pathlib import Path

from loguru import logger

ACTIVE_STATUSES = {"queued", "downloading", "paused"}


def task_matches_filter(status: str, status_filter: str) -> bool:
    """Filtro de estado para los items del tab de canciones."""
    if status_filter == "all":
        return True
    if status_filter == "active":
        return status in ACTIVE_STATUSES
    if status_filter == "error":
        return status == "error"
    return False


async def gather_downloaded_songs(status_filter: str = "all") -> list[dict]:
    """Descargas completadas (repo) + tareas activas del DownloadManager."""
    from doremi.db.repository import DownloadRepository, SongRepository

    items: list[dict] = []
    seen: set[str] = set()

    try:
        downloads = await DownloadRepository().get_downloads()
    except Exception as e:
        logger.error(f"Error fetching downloads: {e}")
        downloads = []

    try:
        liked_ids = await SongRepository().get_liked_video_ids()
    except Exception:
        liked_ids = set()

    # Completadas (más recientes primero — paridad con widgets: reversed())
    if status_filter in {"all", "completed"}:
        for d in reversed(downloads):
            seen.add(d.video_id)
            items.append({
                "videoId": d.video_id,
                "title": d.title,
                "artist": d.artist,
                "playlist_title": d.parent_playlist_title or "",
                "thumbnail_url": d.thumbnail_url or "",
                "status": "completed",
                "progress": 100.0,
                "speed": "",
                "file_path": d.file_path or "",
                "is_liked": d.video_id in liked_ids,
            })

    # Tareas activas del manager
    try:
        from doremi.services.download_manager import DownloadManager
        mgr = DownloadManager.get_instance()
        for vid, task in mgr._tasks.items():
            if vid in seen or not task_matches_filter(task.status, status_filter):
                continue
            items.append({
                "videoId": vid,
                "title": task.title,
                "artist": task.artist,
                "playlist_title": task.parent_playlist_title or "",
                "thumbnail_url": task.thumbnail_url or "",
                "status": task.status,
                "progress": float(task.progress or 0.0),
                "speed": task.speed or "",
                "file_path": "",
                "is_liked": vid in liked_ids,
            })
    except Exception as e:
        logger.debug(f"Error reading active download tasks: {e}")

    return items


async def gather_download_groups(kind: str) -> list[dict]:
    """Agrupa descargas por playlist/álbum. kind: 'playlists' | 'albums'."""
    from doremi.db.repository import DownloadRepository

    try:
        downloads = await DownloadRepository().get_downloads()
    except Exception as e:
        logger.error(f"Error fetching downloads: {e}")
        return []

    groups: dict[str, dict] = {}
    for d in downloads:
        pid = d.parent_playlist_id
        if not pid:
            continue
        is_album = pid.startswith("album_")
        if (kind == "albums") != is_album:
            continue
        if pid not in groups:
            thumb = getattr(d, "parent_playlist_thumbnail_url", "") or d.thumbnail_url or ""
            groups[pid] = {
                "playlist_id": pid,
                "title": d.parent_playlist_title or ("Álbum Local" if is_album else "Playlist Local"),
                "count": 0,
                "thumbnail_url": thumb,
                "navigate": f"album?id={pid[6:]}" if is_album else f"playlist?id=local_{pid}",
            }
        groups[pid]["count"] += 1

    for g in groups.values():
        g["subtitle"] = f"{g['count']} canciones"

    return list(groups.values())


async def delete_download_files(video_ids: list[str]) -> int:
    """Borra archivos físicos + entradas del repo. Devuelve cuántos quedaron registrados para borrado."""
    from doremi.db.repository import DownloadRepository

    repo = DownloadRepository()
    downloads = await repo.get_downloads()
    targets = [d for d in downloads if d.video_id in set(video_ids)]

    for download in targets:
        if not download.file_path:
            continue
        try:
            path = Path(download.file_path)
            if path.exists():
                path.unlink()
            lrc_path = path.with_suffix(".lrc")
            if lrc_path.exists():
                lrc_path.unlink()
        except Exception as e:
            logger.error(f"Error borrando archivo {download.file_path}: {e}")

    await repo.remove_downloads([d.video_id for d in targets])
    return len(targets)


async def delete_group_downloads(playlist_ids: list[str]) -> int:
    """Borra todas las descargas cuyas playlists/álbumes estén en la lista."""
    from doremi.db.repository import DownloadRepository

    downloads = await DownloadRepository().get_downloads()
    ids = {d.video_id for d in downloads if d.parent_playlist_id in set(playlist_ids)}
    return await delete_download_files(list(ids))
