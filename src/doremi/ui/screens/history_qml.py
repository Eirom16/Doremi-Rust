from __future__ import annotations

import asyncio
from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
from loguru import logger

from doremi.ui.theme_bridge import theme_bridge
from doremi.ui.viewmodels.history_vm import HistoryViewModel

QML_DIR = Path(__file__).resolve().parent.parent / "qml"


class HistoryScreenQml(QWidget):
    """Isla QML: Historial de reproducción como QQuickWidget.

    Drop-in replacement de HistoryScreen (QtWidgets): mismas señales,
    mismo constructor, mismo método `load()`. Los datos se cargan con la
    misma función compartida `gather_history()`.
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
        self.setAutoFillBackground(False)

        self._vm = HistoryViewModel(QApplication.instance())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._quick = QQuickWidget(self)
        self._quick.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self._quick.setAutoFillBackground(False)
        from PySide6.QtGui import QColor
        self._quick.setClearColor(QColor(0, 0, 0, 0))

        engine = self._quick.engine()
        engine.addImportPath(str(QML_DIR))

        ctx = self._quick.rootContext()
        ctx.setContextProperty("themeBridge", theme_bridge())
        ctx.setContextProperty("vm", self._vm)

        self._quick.setSource(QUrl.fromLocalFile(str(QML_DIR / "HistoryScreen.qml")))

        self._load_ok = self._quick.status() == QQuickWidget.Status.Ready
        if not self._load_ok:
            for err in self._quick.errors():
                logger.error(f"QML HistoryScreen: {err.toString()}")

        layout.addWidget(self._quick)

        import os
        if os.environ.get("DOREMI_FPS") == "1":
            self._quick.rootObject() and self._quick.rootObject().setProperty("showFps", True)

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

    async def load(self) -> None:
        try:
            self._vm.set_loading(True)
            from doremi.ui.screens.history import gather_history
            items, _liked, _local_count = await gather_history(self.yt)
            self._vm.set_items(items)
        except Exception as e:
            logger.error(f"Error loading QML history: {e}")
            self._vm.set_items([])
        finally:
            self._vm.set_loading(False)
