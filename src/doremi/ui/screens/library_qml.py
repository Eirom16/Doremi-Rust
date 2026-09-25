from __future__ import annotations

import asyncio
import time
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtWidgets import QApplication
from loguru import logger

from doremi.ui.viewmodels.library_vm import LibraryViewModel

QML_DIR = Path(__file__).resolve().parent.parent / "qml"

_CACHE_TTL = 300  # segundos (paridad con LibraryScreen widgets)


class LibraryScreenQml(QObject):
    """Isla QML: Biblioteca como QQuickWidget.

    Drop-in replacement de LibraryScreen (QtWidgets): mismas señales,
    mismo constructor, mismos métodos `load()` e `invalidate_songs_cache()`.
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

        self._vm = LibraryViewModel(QApplication.instance())
        self._cache: dict[str, list[dict]] = {}
        self._cache_time: dict[str, float] = {}
        self._load_task: asyncio.Task | None = None

        self.qml_source = QUrl.fromLocalFile(str(QML_DIR / "LibraryScreen.qml"))
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
        self._vm.tab_changed.connect(self._on_tab_changed)
        self._vm.create_playlist_requested.connect(self._on_create_playlist)

    @property
    def is_ok(self) -> bool:
        return self._load_ok

    @property
    def _current_tab(self) -> str:
        """Paridad con LibraryScreen: queue_controller lo consulta."""
        return self._vm.tab

    def _on_vm_play(self, video_id, title, artist, duration_ms, thumb) -> None:
        if self.on_play_song:
            try:
                self.on_play_song(video_id, title, artist, "", duration_ms, thumb)
            except Exception as e:
                logger.error(f"Play error desde isla QML Library: {e}")

    def _on_navigate(self, route: str) -> None:
        if self.on_navigate and route:
            self.on_navigate(route)

    def _on_tab_changed(self) -> None:
        # Conserva el caché por tab; solo entra a la red si está vencido/ausente
        self._schedule_load(force=False)

    def _on_create_playlist(self, title: str, description: str) -> None:
        asyncio.ensure_future(self._create_playlist_async(title, description))

    async def _create_playlist_async(self, title: str, description: str) -> None:
        try:
            pid = await self.yt.create_playlist(title, description)
            if pid:
                self._cache.pop("playlists", None)
                self._cache_time.pop("playlists", None)
                await self._load_tab("playlists")
        except Exception as e:
            logger.error(f"Error creating playlist (QML): {e}")

    def invalidate_songs_cache(self) -> None:
        self._cache.pop("songs", None)
        self._cache_time.pop("songs", None)
        self._vm.clear_tab_data("songs")

    def force_reload(self) -> None:
        self._cache.clear()
        self._cache_time.clear()
        self._schedule_load(force=True)

    async def load(self) -> None:
        await self._load_tab(self._vm.tab)

    def select_tab(self, tab: str) -> None:
        """Abre una pestaña desde navegación externa sin duplicar una vista."""
        self._vm.set_tab(tab)

    def _schedule_load(self, force: bool = False) -> None:
        if self._load_task and not self._load_task.done():
            self._load_task.cancel()
        self._load_task = asyncio.ensure_future(self._load_tab(self._vm.tab, force=force))

    async def _load_tab(self, tab: str, force: bool = False) -> None:
        age = time.time() - self._cache_time.get(tab, 0)
        if not force and tab in self._cache and age < _CACHE_TTL:
            self._vm.set_tab_data(tab, self._cache[tab])
            return

        if not self.yt or not self.yt.is_authenticated:
            # Paridad con LibraryScreen (widgets): sin auth, mensaje en todos los tabs
            self._vm.set_auth_required(True)
            self._vm.set_tab_data(tab, [])
            return

        self._vm.set_auth_required(False)
        self._vm.set_loading(True)
        try:
            from doremi.ui.screens import library_data
            if tab == "songs":
                items = await library_data.gather_liked_songs(self.yt)
            elif tab == "albums":
                items = await library_data.gather_library_albums(self.yt)
            elif tab == "artists":
                items = await library_data.gather_library_artists(self.yt)
            else:
                items = await library_data.gather_library_playlists(self.yt)
            self._cache[tab] = items
            self._cache_time[tab] = time.time()
            self._vm.set_tab_data(tab, items)
        except Exception as e:
            logger.error(f"Error loading library tab '{tab}' (QML): {e}")
            self._vm.set_tab_data(tab, [])
        finally:
            self._vm.set_loading(False)
