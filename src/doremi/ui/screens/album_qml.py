from __future__ import annotations

import asyncio
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtWidgets import QApplication
from loguru import logger

from doremi.services.download_manager import DownloadManager
from doremi.ui.viewmodels.album_vm import AlbumViewModel

QML_DIR = Path(__file__).resolve().parent.parent / "qml"


class AlbumScreenQml(QObject):
    """Isla QML: Álbum como QQuickWidget.

    Drop-in replacement de AlbumScreen (QtWidgets): mismas señales,
    mismo constructor, mismo método `load(browse_id)`.
    """

    _qml_island = True  # fade_stack.py: sin cross-fade

    download_requested = Signal(str, str, str, str)
    download_album_requested = Signal(str, str, str)  # browse_id, title, thumbnail_url
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    like_requested = Signal(str, object)
    add_to_playlist_requested = Signal(str, str)
    delete_download_requested = Signal(str)

    def __init__(self, yt_client, on_play_song, on_back=None):
        super().__init__()
        self.yt = yt_client
        self.on_play_song = on_play_song
        self.on_back = on_back
        self._browse_id: str | None = None
        self._load_task: asyncio.Task | None = None

        self._vm = AlbumViewModel(QApplication.instance())

        self.qml_source = QUrl.fromLocalFile(str(QML_DIR / "AlbumScreen.qml"))
        self._load_ok = True

        # Re-emit VM signals as screen signals
        self._vm.download_requested.connect(self.download_requested)
        self._vm.download_album_requested.connect(self.download_album_requested)
        self._vm.play_next_requested.connect(self.play_next_requested)
        self._vm.add_to_queue_requested.connect(self.add_to_queue_requested)
        self._vm.like_requested.connect(self.like_requested)
        self._vm.add_to_playlist_requested.connect(self.add_to_playlist_requested)
        self._vm.delete_download_requested.connect(self.delete_download_requested)
        self._vm.play_queue_requested.connect(self._on_vm_play_queue)
        self._vm.back_requested.connect(self._on_back)

        # Progreso de descarga del álbum (paridad widgets)
        dm = DownloadManager.get_instance()
        dm.download_progress.connect(self._on_dl_progress)
        dm.download_completed.connect(self._on_dl_completed)

    @property
    def is_ok(self) -> bool:
        return self._load_ok

    def _on_back(self) -> None:
        if self.on_back:
            self.on_back()

    def _on_vm_play_queue(self, items: list, index: int) -> None:
        """Construye QueueItem desde los modelos y dispara la reproducción."""
        if not items or not self.on_play_song:
            return
        from doremi.audio.queue import QueueItem
        queue_items = [
            QueueItem(
                video_id=t.get("videoId", ""),
                title=t.get("title", "Unknown"),
                artist=t.get("artist", ""),
                album=self._vm.title or "",
                duration_ms=t.get("duration_ms", 0),
                thumbnail_url=t.get("thumbnail_url", "") or self._vm.thumbnail,
            )
            for t in items
        ]
        index = max(0, min(index, len(queue_items) - 1))
        first = queue_items[index]
        try:
            self.on_play_song(
                first.video_id, first.title, first.artist, first.album,
                first.duration_ms, first.thumbnail_url, queue_items, index,
            )
        except Exception as e:
            logger.error(f"Play error desde isla QML Album: {e}")

    async def load(self, browse_id: str) -> None:
        if not browse_id:
            return
        if self._load_task and not self._load_task.done():
            self._load_task.cancel()
        self._load_task = asyncio.current_task()
        self._browse_id = browse_id
        self._vm.set_loading(True)
        try:
            from doremi.ui.screens.album_data import gather_album
            data = await gather_album(self.yt, browse_id)
            self._vm.set_data(data)
            if self._vm.found:
                self._refresh_download_state()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error loading album (QML): {e}")
            self._vm.set_data({})
        finally:
            self._vm.set_loading(False)

    # ── Estado del botón de descarga ───────────────────────────────────────

    def _album_task_prefix(self) -> str:
        return f"album_{self._browse_id or ''}"

    def _refresh_download_state(self) -> None:
        pct = self._album_tasks_progress()
        if pct is not None:
            self._vm.set_download_state(AlbumViewModel.DL_ACTIVE, pct)
            return
        downloaded = self._vm._downloaded_count
        total = self._vm._track_count
        if total and downloaded >= total:
            self._vm.set_download_state(AlbumViewModel.DL_FULL)
        elif downloaded:
            self._vm.set_download_state(AlbumViewModel.DL_PARTIAL)
        else:
            self._vm.set_download_state(AlbumViewModel.DL_NONE)

    def _album_tasks_progress(self) -> int | None:
        dm = DownloadManager.get_instance()
        tasks = [
            t for t in dm._tasks.values()
            if t.parent_playlist_id == self._album_task_prefix()
        ]
        if not tasks:
            return None
        return int(sum(t.progress for t in tasks) / len(tasks))

    def _on_dl_progress(self, _video_id: str, _progress: float, _speed: str) -> None:
        if not self._browse_id:
            return
        pct = self._album_tasks_progress()
        if pct is not None:
            self._vm.set_download_state(AlbumViewModel.DL_ACTIVE, pct)

    def _on_dl_completed(self, _video_id: str, _filepath: str) -> None:
        if not self._browse_id:
            return
        pct = self._album_tasks_progress()
        if pct is not None:
            self._vm.set_download_state(AlbumViewModel.DL_ACTIVE, pct)
            return
        # Sin tasks vivos: refrescar contadores reales
        asyncio.ensure_future(self._refresh_counts())

    async def _refresh_counts(self) -> None:
        try:
            from doremi.db.repository import DownloadRepository
            downloads = await DownloadRepository().get_downloads()
            downloaded = {d.video_id for d in downloads
                          if d.parent_playlist_id == self._album_task_prefix()}
            fully = len(downloaded) >= self._vm._track_count > 0
            self._vm.refresh_counters(len(downloaded), fully)
        except Exception as e:
            logger.debug(f"Error refreshing album download state: {e}")
