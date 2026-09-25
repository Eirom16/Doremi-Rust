from __future__ import annotations

import asyncio
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtWidgets import QApplication
from loguru import logger

from doremi.services.download_manager import DownloadManager
from doremi.ui.viewmodels.downloads_vm import DownloadsViewModel

QML_DIR = Path(__file__).resolve().parent.parent / "qml"


class DownloadsScreenQml(QObject):
    """Isla QML: Descargas como QQuickWidget.

    Drop-in replacement de DownloadsScreen (QtWidgets): mismas señales,
    mismo constructor, mismo método `load()`.
    """

    _qml_island = True  # fade_stack.py: sin cross-fade

    like_requested = Signal(str, object)
    delete_download_requested = Signal(str)
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    add_to_playlist_requested = Signal(str, str)

    def __init__(self, extractor, on_play_local, on_play_local_playlist=None, on_navigate=None):
        super().__init__()
        self.extractor = extractor
        self.on_play_local = on_play_local
        self.on_play_local_playlist = on_play_local_playlist
        self.on_navigate = on_navigate

        self._vm = DownloadsViewModel(QApplication.instance())
        self._load_task: asyncio.Task | None = None

        self.qml_source = QUrl.fromLocalFile(str(QML_DIR / "DownloadsScreen.qml"))
        self._load_ok = True

        # Re-emit VM signals as screen signals
        self._vm.like_requested.connect(self.like_requested)
        self._vm.delete_download_requested.connect(self.delete_download_requested)
        self._vm.play_next_requested.connect(self.play_next_requested)
        self._vm.add_to_queue_requested.connect(self.add_to_queue_requested)
        self._vm.add_to_playlist_requested.connect(self.add_to_playlist_requested)
        self._vm.play_local_requested.connect(self._on_vm_play_local)
        self._vm.navigate_requested.connect(self._on_navigate)
        self._vm.batch_delete_requested.connect(self._on_batch_delete)
        self._vm.tab_changed.connect(self._schedule_load)
        self._vm.status_filter_changed.connect(self._schedule_load)

        self._connect_manager()

    @property
    def is_ok(self) -> bool:
        return self._load_ok

    @property
    def _current_tab(self) -> str:
        """Paridad con DownloadsScreen (widgets)."""
        return self._vm.tab

    # ── Handlers VM → mundo exterior ───────────────────────────────────────

    def _on_vm_play_local(self, path: str, metadata: dict) -> None:
        if self.on_play_local and path:
            try:
                self.on_play_local(path, metadata)
            except Exception as e:
                logger.error(f"Play local error desde isla QML Downloads: {e}")

    def _on_navigate(self, route: str) -> None:
        if self.on_navigate and route:
            self.on_navigate(route)

    def _on_batch_delete(self, ids: list, is_group: bool) -> None:
        asyncio.ensure_future(self._batch_delete_async(ids, is_group))

    async def _batch_delete_async(self, ids: list, is_group: bool) -> None:
        from doremi.ui.screens import downloads_data
        try:
            if self._vm.selectionMode:
                self._vm.toggle_selection_mode()
            if ids:
                if is_group:
                    await downloads_data.delete_group_downloads(ids)
                else:
                    await downloads_data.delete_download_files(ids)
            else:
                # delete_all: todos los del tab actual
                if is_group:
                    all_ids = [
                        self._vm.groups.get(i)["playlist_id"]
                        for i in range(self._vm.groups.rowCount())
                    ]
                    await downloads_data.delete_group_downloads(all_ids)
                else:
                    all_ids = [
                        self._vm.songs.get(i)["videoId"]
                        for i in range(self._vm.songs.rowCount())
                        if self._vm.songs.get(i).get("status") == "completed"
                    ]
                    await downloads_data.delete_download_files(all_ids)
            await self.load()
        except Exception as e:
            logger.error(f"Error en borrado batch (QML Downloads): {e}")
            from doremi.ui.widgets.toast import ToastNotification
            from doremi.utils.i18n import _
            ToastNotification.show(self, _("No se pudieron eliminar todos los archivos. Puedes reintentarlo."), "error")
            await self.load()

    # ── Carga ──────────────────────────────────────────────────────────────

    def _schedule_load(self) -> None:
        if self._vm.selectionMode:
            self._vm.toggle_selection_mode()
        if self._load_task and not self._load_task.done():
            self._load_task.cancel()
        self._load_task = asyncio.ensure_future(self.load())

    async def load(self) -> None:
        self._vm.set_loading(True)
        try:
            from doremi.ui.screens import downloads_data
            if self._vm.tab == "songs":
                items = await downloads_data.gather_downloaded_songs(self._vm.statusFilter)
                self._vm.set_songs(items)
            else:
                items = await downloads_data.gather_download_groups(self._vm.tab)
                self._vm.set_groups(items)
        except Exception as e:
            logger.error(f"Error loading downloads (QML): {e}")
            if self._vm.tab == "songs":
                self._vm.set_songs([])
            else:
                self._vm.set_groups([])
        finally:
            self._vm.set_loading(False)

    # ── Live updates del DownloadManager ───────────────────────────────────

    def _connect_manager(self) -> None:
        mgr = DownloadManager.get_instance()
        mgr.tasks_changed.connect(self._schedule_load)
        mgr.download_queued.connect(self._on_download_queued)
        mgr.download_started.connect(self._on_download_started)
        mgr.download_progress.connect(self._on_download_progress)
        mgr.download_completed.connect(self._on_download_completed)
        mgr.download_error.connect(self._on_download_error)

    def _on_download_queued(self, task) -> None:
        if self._vm.tab != "songs":
            return
        from doremi.ui.screens.downloads_data import task_matches_filter
        if not task_matches_filter(task.status, self._vm.statusFilter):
            return
        self._vm.upsert_task({
            "videoId": task.video_id,
            "title": task.title,
            "artist": task.artist,
            "playlist_title": task.parent_playlist_title or "",
            "thumbnail_url": task.thumbnail_url or "",
            "status": task.status,
            "progress": float(task.progress or 0.0),
            "speed": task.speed or "",
            "file_path": "",
            "is_liked": False,
        })

    def _on_download_started(self, video_id: str) -> None:
        self._vm.update_status(video_id, "downloading")

    def _on_download_progress(self, video_id: str, percent: float, speed: str) -> None:
        self._vm.update_progress(video_id, percent, speed or "")

    def _on_download_completed(self, video_id: str, filepath: str) -> None:
        self._vm.songs.update_item(video_id, status="completed", progress=100.0,
                                   speed="", file_path=filepath)
        # El item completado pasa a ser reproducible; recarga para ordenarlo arriba
        if self._vm.statusFilter == "completed":
            self._schedule_load()

    def _on_download_error(self, video_id: str, _error_msg: str) -> None:
        self._vm.update_status(video_id, "error")
