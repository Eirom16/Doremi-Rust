from __future__ import annotations

import asyncio
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtWidgets import QApplication
from loguru import logger

from doremi.ui.viewmodels.history_vm import HistoryViewModel

QML_DIR = Path(__file__).resolve().parent.parent / "qml"


class HistoryScreenQml(QObject):
    """Isla QML: Historial de reproducción como QQuickWidget.

    Drop-in replacement de HistoryScreen (QtWidgets): mismas señales,
    mismo constructor, mismo método `load()`. Los datos se cargan con la
    mismo cargador de datos independiente de Widgets.
    """

    _qml_island = True  # fade_stack.py: sin cross-fade (QML anima internamente)
    download_requested = Signal(str, str, str, str)
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    like_requested = Signal(str, object)
    add_to_playlist_requested = Signal(str, str)
    delete_download_requested = Signal(str)
    artist_clicked = Signal(str)
    album_clicked = Signal(str)

    def __init__(self, yt_client, on_play_song):
        super().__init__()
        self.yt = yt_client
        self.on_play_song = on_play_song
        self._load_task: asyncio.Task | None = None
        self._load_generation = 0

        self._vm = HistoryViewModel(QApplication.instance())

        self.qml_source = QUrl.fromLocalFile(str(QML_DIR / "HistoryScreen.qml"))
        self._load_ok = True

        # Re-emit VM signals as screen signals (wiring existente en MainWindow)
        self._vm.download_requested.connect(self.download_requested)
        self._vm.play_next_requested.connect(self.play_next_requested)
        self._vm.add_to_queue_requested.connect(self.add_to_queue_requested)
        self._vm.like_requested.connect(self.like_requested)
        self._vm.add_to_playlist_requested.connect(self.add_to_playlist_requested)
        self._vm.delete_download_requested.connect(self.delete_download_requested)
        self._vm.artist_clicked.connect(self.artist_clicked)
        self._vm.album_clicked.connect(self.album_clicked)
        self._vm.play_requested.connect(self._on_vm_play)
        self._vm.clear_requested.connect(self._on_clear_requested)
        self._vm.retry_requested.connect(self._schedule_load)

    @property
    def is_ok(self) -> bool:
        return self._load_ok

    def _on_vm_play(self, video_id, title, artist, duration_ms, thumb) -> None:
        try:
            if self.on_play_song:
                self.on_play_song(video_id, title, artist, "", duration_ms, thumb)
        except Exception as e:
            logger.error(f"Play error desde isla QML: {e}")

    def _on_clear_requested(self) -> None:
        asyncio.ensure_future(self._clear_history_async())

    async def _clear_history_async(self) -> None:
        try:
            from doremi.db.repository import HistoryRepository
            deleted = await HistoryRepository().clear_history()
            logger.info(f"Cleared {deleted} local history entries")
            await self.load()
        except Exception as e:
            logger.error(f"Error clearing history: {e}")

    def _schedule_load(self) -> None:
        if self._load_task and not self._load_task.done():
            self._load_task.cancel()
        self._load_generation += 1
        self._load_task = asyncio.ensure_future(self._load(self._load_generation))

    async def load(self) -> None:
        current = asyncio.current_task()
        if self._load_task and self._load_task is not current and not self._load_task.done():
            self._load_task.cancel()
        self._load_generation += 1
        self._load_task = current
        try:
            await self._load(self._load_generation)
        finally:
            if self._load_task is current:
                self._load_task = None

    async def _load(self, generation: int) -> None:
        def is_current_request() -> bool:
            return generation == self._load_generation

        try:
            if not is_current_request():
                return
            self._vm.set_loading(True)
            self._vm.set_error("")
            from doremi.ui.screens.history_data import gather_history
            items, _liked, _local_count = await gather_history(self.yt)
            if not is_current_request():
                return
            self._vm.set_items(items)
        except Exception as e:
            logger.error(f"Error loading QML history: {e}")
            if not is_current_request():
                return
            self._vm.set_items([])
            self._vm.set_error("No se pudo cargar el historial. Comprueba tu conexión e inténtalo de nuevo.")
        finally:
            if is_current_request():
                self._vm.set_loading(False)
