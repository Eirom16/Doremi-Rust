"""Shared data loading for Downloads screen — used by both widget and QML versions."""
from __future__ import annotations

import asyncio
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
            # A file can disappear outside Doremi.  Do not leave a completed
            # row that later fails in the player; repair the stale DB record
            # while loading the offline library.
            path = Path(d.file_path or "")
            if not d.file_path or not path.is_file():
                logger.warning(f"Removing stale download record for {d.video_id}: {d.file_path!r}")
                try:
                    await DownloadRepository().remove_download(d.video_id)
                except Exception as exc:
                    logger.error(f"Could not remove stale download record {d.video_id}: {exc}")
                continue
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
        # La vista de canciones ya reconcilia estos registros.  Los grupos
        # deben respetar la misma fuente de verdad: de otro modo un archivo
        # borrado fuera de Doremi deja una tarjeta de álbum/playlist local que
        # promete contenido que ya no existe.
        path = Path(d.file_path or "")
        if not d.file_path or not path.is_file():
            logger.warning(f"Removing stale download record for {d.video_id}: {d.file_path!r}")
            try:
                await DownloadRepository().remove_download(d.video_id)
            except Exception as exc:
                logger.error(f"Could not remove stale download record {d.video_id}: {exc}")
            continue
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


def delete_audio_file(file_path: str) -> bool:
    """Borra el audio o propaga el fallo; devuelve si también se borró la letra."""
    if not file_path:
        return True
    path = Path(file_path)
    path.unlink(missing_ok=True)
    try:
        path.with_suffix(".lrc").unlink(missing_ok=True)
    except OSError as exc:
        logger.warning(f"No se pudo borrar la letra de {file_path}: {exc}")
        return False
    return True


class DownloadDeletionError(Exception):
    def __init__(self, deleted: int, failed: int):
        self.deleted = deleted
        self.failed = failed
        super().__init__(f"{deleted} deleted, {failed} failed")


class DownloadClearError(Exception):
    """The all-downloads operation could not reach a safe finished state."""


async def clear_all_downloads(manager=None, *, cancel_timeout: float = 5.0) -> int:
    """Clear downloads from both the database and download directory.

    Active worker tasks are cancelled first and must actually leave the manager
    before files are touched.  This prevents a downloader from recreating a
    file after its database row was removed.  Orphan files are removed too, so
    a previous crash cannot make Settings report a successful clear while disk
    space remains occupied.
    """
    if manager is not None:
        active_ids = list(getattr(manager, "_tasks", {}).keys())
        for video_id in active_ids:
            manager.cancel_download(video_id)

        if active_ids:
            deadline = asyncio.get_running_loop().time() + cancel_timeout
            while any(video_id in getattr(manager, "_tasks", {}) for video_id in active_ids):
                if asyncio.get_running_loop().time() >= deadline:
                    raise DownloadClearError(
                        "No se pudieron cancelar todas las descargas activas. Inténtalo de nuevo."
                    )
                await asyncio.sleep(0.05)

    from doremi.config.paths import AppDirs
    from doremi.db.repository import DownloadRepository

    downloads = await DownloadRepository().get_downloads()
    deleted = await delete_download_files([download.video_id for download in downloads])

    # A managed download can live in a playlist subdirectory.  Delete any
    # remaining orphan payloads inside the configured root, never following a
    # directory symlink outside that root.
    root = AppDirs.downloads
    if not root.exists():
        return deleted
    orphan_deleted = 0
    failures = 0
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        try:
            if path.is_symlink() or path.is_file():
                path.unlink()
                orphan_deleted += 1
            elif path.is_dir():
                path.rmdir()
        except OSError as exc:
            failures += 1
            logger.error(f"No se pudo borrar {path}: {exc}")
    if failures:
        raise DownloadDeletionError(deleted + orphan_deleted, failures)
    return deleted + orphan_deleted


async def delete_download_files(video_ids: list[str]) -> int:
    """Borra archivos físicos + entradas del repo. Devuelve cuántos quedaron registrados para borrado."""
    from doremi.db.repository import DownloadRepository

    repo = DownloadRepository()
    downloads = await repo.get_downloads()
    targets = [d for d in downloads if d.video_id in set(video_ids)]

    deleted, failed = 0, 0
    for download in targets:
        try:
            lyrics_deleted = delete_audio_file(download.file_path)
            await repo.remove_download(download.video_id)
            deleted += 1
            if not lyrics_deleted:
                failed += 1
        except Exception as e:
            failed += 1
            logger.error(f"Error borrando archivo {download.file_path}: {e}")
    if failed:
        raise DownloadDeletionError(deleted, failed)
    return deleted


async def delete_group_downloads(playlist_ids: list[str]) -> int:
    """Borra todas las descargas cuyas playlists/álbumes estén en la lista."""
    from doremi.db.repository import DownloadRepository

    downloads = await DownloadRepository().get_downloads()
    ids = {d.video_id for d in downloads if d.parent_playlist_id in set(playlist_ids)}
    return await delete_download_files(list(ids))
