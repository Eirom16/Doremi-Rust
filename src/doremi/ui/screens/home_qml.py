from __future__ import annotations

import asyncio
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtWidgets import QApplication
from loguru import logger

from doremi.ui.viewmodels.home_vm import HomeViewModel

QML_DIR = Path(__file__).resolve().parent.parent / "qml"


class HomeScreenQml(QObject):
    """Isla QML: Pantalla Inicio como QQuickWidget.

    Drop-in replacement de HomeScreen (QtWidgets): mismas señales,
    mismo constructor, mismo método `load()`. Los datos se cargan con la
    misma función compartida `gather_home()`.
    """

    _qml_island = True  # fade_stack.py: sin cross-fade
    download_requested = Signal(str, str, str, str)
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    like_requested = Signal(str, object)
    add_to_playlist_requested = Signal(str, str)
    delete_download_requested = Signal(str)
    artist_clicked = Signal(str)
    album_clicked = Signal(str)

    def __init__(self, yt_client, on_play_song, on_navigate=None):
        super().__init__()
        self.yt = yt_client
        self.on_play_song = on_play_song
        self.on_navigate = on_navigate
        self._loaded = False
        self._load_task: asyncio.Task | None = None
        self._load_generation = 0

        self._vm = HomeViewModel(QApplication.instance())

        self.qml_source = QUrl.fromLocalFile(str(QML_DIR / "HomeScreen.qml"))
        self._load_ok = True

        # Re-emit VM signals as screen signals
        self._vm.download_requested.connect(self.download_requested)
        self._vm.play_next_requested.connect(self.play_next_requested)
        self._vm.add_to_queue_requested.connect(self.add_to_queue_requested)
        self._vm.like_requested.connect(self.like_requested)
        self._vm.add_to_playlist_requested.connect(self.add_to_playlist_requested)
        self._vm.delete_download_requested.connect(self.delete_download_requested)
        self._vm.artist_clicked.connect(self.artist_clicked)
        self._vm.album_clicked.connect(self.album_clicked)
        self._vm.play_requested.connect(self._on_vm_play)
        self._vm.navigate_requested.connect(self._on_navigate)
        self._vm.search_navigate.connect(self._on_search_navigate)
        self._vm.retry_requested.connect(self.force_reload)

    @property
    def is_ok(self) -> bool:
        return self._load_ok

    def _on_navigate(self, route: str) -> None:
        if not route:
            return
        if route.startswith("play:"):
            self._play_by_video_id(route[5:])
            return
        if self.on_navigate:
            self.on_navigate(route)

    def _play_by_video_id(self, video_id: str) -> None:
        """Fallback para cards horizontales tipo 'song' (navigate=play:<id>)."""
        for model in (self._vm.tiles, self._vm.songs):
            for i in range(model.rowCount()):
                item = model.get(i)
                if item and item.get("videoId") == video_id:
                    self._on_vm_play(
                        video_id, item.get("title", ""), item.get("artist", ""),
                        item.get("duration_ms", 0), item.get("thumbnail_url", ""),
                    )
                    return
        self._on_vm_play(video_id, "", "", 0, "")

    def _on_search_navigate(self, route: str) -> None:
        if self.on_navigate:
            self.on_navigate(route)

    def _on_vm_play(self, video_id, title, artist, duration_ms, thumb) -> None:
        if self.on_play_song:
            try:
                self.on_play_song(video_id, title, artist, "", duration_ms, thumb)
            except Exception as e:
                logger.error(f"Play error desde isla QML Home: {e}")

    def force_reload(self) -> None:
        self._loaded = False
        if self._load_task and not self._load_task.done():
            self._load_task.cancel()
        self._load_generation += 1
        self._load_task = asyncio.ensure_future(self._load(self._load_generation))

    async def load(self) -> None:
        """Load Home once, replacing an older in-flight public load safely."""
        if self._loaded:
            return
        current = asyncio.current_task()
        if self._load_task and self._load_task is not current and not self._load_task.done():
            self._load_task.cancel()
        self._load_generation += 1
        self._load_task = current
        try:
            await self._load(self._load_generation)
        finally:
            # ``load`` can be awaited by a navigation callback. Never retain
            # that caller task after it has finished, or a future retry would
            # cancel the unrelated callback itself.
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
            from doremi.ui.screens.home_data import gather_home
            data = await gather_home(self.yt)
            if not is_current_request():
                return
            self._vm.set_greeting(data["greeting"])
            self._vm.set_spotlight(data["spotlight"])
            self._vm.set_tiles(data["tiles"])
            self._vm.set_horizontal(data["horizontal"])
            self._vm.set_songs(data["songs"])
            if data.get("_source") == "online":
                from doremi.services.offline_cache import OfflineCacheManager
                settings = getattr(self.yt, "settings", None)
                if settings is not None:
                    OfflineCacheManager.get_instance().schedule_sync(data, settings)
            self._loaded = True
        except Exception as e:
            logger.error(f"Error loading QML home: {e}")
            if not is_current_request():
                return
            self._loaded = False
            self._vm.set_greeting("")
            self._vm.set_spotlight([])
            self._vm.set_tiles([])
            self._vm.set_horizontal([])
            self._vm.set_songs([])
            self._vm.set_error("No se pudo cargar Inicio. Comprueba tu conexión e inténtalo de nuevo.")
        finally:
            if is_current_request():
                self._vm.set_loading(False)
