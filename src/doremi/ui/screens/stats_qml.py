from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtWidgets import QApplication
from loguru import logger

from doremi.ui.viewmodels.stats_vm import StatsViewModel

QML_DIR = Path(__file__).resolve().parent.parent / "qml"


class StatsScreenQml(QObject):
    """Isla QML: Estadísticas como QQuickWidget.

    Drop-in replacement de StatsScreen (QtWidgets): mismas señales,
    mismo constructor, mismo método `load()`.
    """

    _qml_island = True  # fade_stack.py: sin cross-fade

    download_requested = Signal(str, str, str, str)
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    like_requested = Signal(str, object)
    add_to_playlist_requested = Signal(str, str)
    delete_download_requested = Signal(str)
    artist_clicked = Signal(str)
    album_clicked = Signal(str)  # paridad con StatsScreen

    def __init__(self, yt_client, on_play_song):
        super().__init__()
        self.yt = yt_client
        self.on_play_song = on_play_song

        self._vm = StatsViewModel(QApplication.instance())

        self.qml_source = QUrl.fromLocalFile(str(QML_DIR / "StatsScreen.qml"))
        self._load_ok = True

        # Re-emit VM signals as screen signals
        self._vm.download_requested.connect(self.download_requested)
        self._vm.play_next_requested.connect(self.play_next_requested)
        self._vm.add_to_queue_requested.connect(self.add_to_queue_requested)
        self._vm.like_requested.connect(self.like_requested)
        self._vm.add_to_playlist_requested.connect(self.add_to_playlist_requested)
        self._vm.delete_download_requested.connect(self.delete_download_requested)
        self._vm.artist_clicked.connect(self.artist_clicked)
        self._vm.play_requested.connect(self._on_vm_play)

    @property
    def is_ok(self) -> bool:
        return self._load_ok

    def _on_vm_play(self, video_id, title, artist, duration_ms, thumb) -> None:
        if self.on_play_song:
            try:
                self.on_play_song(video_id, title, artist, "", duration_ms, thumb)
            except Exception as e:
                logger.error(f"Play error desde isla QML Stats: {e}")

    async def load(self) -> None:
        self._vm.set_loading(True)
        try:
            from doremi.ui.screens.stats_data import gather_stats
            data = await gather_stats()
            self._vm.set_data(data)
        except Exception as e:
            logger.error(f"Error loading stats (QML): {e}")
            self._vm.set_data({})
        finally:
            self._vm.set_loading(False)
