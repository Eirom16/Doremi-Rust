from __future__ import annotations

import asyncio
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtWidgets import QApplication
from loguru import logger

from doremi.ui.viewmodels.artist_vm import ArtistViewModel

QML_DIR = Path(__file__).resolve().parent.parent / "qml"


class ArtistScreenQml(QObject):
    """Isla QML: Artista como QQuickWidget.

    Drop-in replacement de ArtistScreen (QtWidgets): mismas señales,
    mismo constructor, mismo método `load(channel_id)`.
    """

    _qml_island = True  # fade_stack.py: sin cross-fade

    download_requested = Signal(str, str, str, str)
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    like_requested = Signal(str, object)
    add_to_playlist_requested = Signal(str, str)
    delete_download_requested = Signal(str)

    def __init__(self, yt_client, on_play_song, on_navigate=None, on_back=None):
        super().__init__()
        self.yt = yt_client
        self.on_play_song = on_play_song
        self.on_navigate = on_navigate
        self.on_back = on_back
        self._channel_id = None
        self._load_task: asyncio.Task | None = None

        self._vm = ArtistViewModel(QApplication.instance())

        self.qml_source = QUrl.fromLocalFile(str(QML_DIR / "ArtistScreen.qml"))
        self._load_ok = True

        # Re-emit VM signals as screen signals
        self._vm.download_requested.connect(self.download_requested)
        self._vm.play_next_requested.connect(self.play_next_requested)
        self._vm.add_to_queue_requested.connect(self.add_to_queue_requested)
        self._vm.like_requested.connect(self.like_requested)
        self._vm.add_to_playlist_requested.connect(self.add_to_playlist_requested)
        self._vm.delete_download_requested.connect(self.delete_download_requested)
        self._vm.play_requested.connect(self._on_vm_play)
        self._vm.navigate_requested.connect(self._on_navigate)
        self._vm.back_requested.connect(self._on_back)

    @property
    def is_ok(self) -> bool:
        return self._load_ok

    def _on_vm_play(self, video_id, title, artist, duration_ms, thumb) -> None:
        if self.on_play_song:
            try:
                self.on_play_song(video_id, title, artist, "", duration_ms, thumb)
            except Exception as e:
                logger.error(f"Play error desde isla QML Artist: {e}")

    def _on_navigate(self, route: str) -> None:
        if self.on_navigate and route:
            self.on_navigate(route)

    def _on_back(self) -> None:
        if self.on_back:
            self.on_back()

    async def load(self, channel_id: str) -> None:
        if not channel_id:
            return
        if self._load_task and not self._load_task.done():
            self._load_task.cancel()
        self._load_task = asyncio.current_task()
        self._channel_id = channel_id
        self._vm.set_loading(True)
        try:
            from doremi.ui.screens.artist_data import gather_artist
            data = await gather_artist(self.yt, channel_id)
            self._vm.set_data(data)
        except Exception as e:
            logger.error(f"Error loading artist (QML): {e}")
            self._vm.set_data({})
        finally:
            self._vm.set_loading(False)
