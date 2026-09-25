from __future__ import annotations

import asyncio
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtWidgets import QApplication
from loguru import logger

from doremi.utils.i18n import _
from doremi.ui.viewmodels.search_vm import SearchViewModel

QML_DIR = Path(__file__).resolve().parent.parent / "qml"


class SearchScreenQml(QObject):
    """Isla QML: Búsqueda como QQuickWidget.

    Drop-in replacement de SearchScreen (QtWidgets): mismas señales,
    mismo constructor, mismo método `search(query)`. Caché por categoría
    como la versión widgets.
    """

    _qml_island = True  # fade_stack.py: sin cross-fade

    download_requested = Signal(str, str, str, str)
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    like_requested = Signal(str, object)
    add_to_playlist_requested = Signal(str, str)
    delete_download_requested = Signal(str)

    def __init__(self, yt_client, on_play_song, on_navigate=None):
        super().__init__()
        self.yt = yt_client
        self.on_play_song = on_play_song
        self.on_navigate = on_navigate

        self._vm = SearchViewModel(QApplication.instance())
        self._current_query = ""
        self._results_by_cat: dict[str, list[dict]] = {}
        self._fetch_task: asyncio.Task | None = None

        self.qml_source = QUrl.fromLocalFile(str(QML_DIR / "SearchScreen.qml"))
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
        self._vm.category_changed.connect(self._on_category_changed)
        self._vm.retry_requested.connect(self._on_retry)

    @property
    def is_ok(self) -> bool:
        return self._load_ok

    def close(self) -> None:
        """Compatibility cleanup for callers from the former widget surface."""
        if self._fetch_task and not self._fetch_task.done():
            self._fetch_task.cancel()

    def _on_vm_play(self, video_id, title, artist, duration_ms, thumb) -> None:
        if self.on_play_song:
            try:
                self.on_play_song(video_id, title, artist, "", duration_ms, thumb)
            except Exception as e:
                logger.error(f"Play error desde isla QML Search: {e}")

    def _on_navigate(self, route: str) -> None:
        if self.on_navigate and route:
            self.on_navigate(route)

    def _on_category_changed(self) -> None:
        if self._current_query:
            self._schedule_fetch(self._current_query, self._vm.category)
        else:
            self._apply_results(self._vm.category, [])

    def _on_retry(self) -> None:
        if self._current_query:
            self._results_by_cat.pop(self._vm.category, None)
            self._schedule_fetch(self._current_query, self._vm.category)

    # ── API pública (paridad con SearchScreen) ─────────────────────────────

    async def search(self, query: str) -> None:
        """Disparada por NavigationController cuando el usuario envía el buscador."""
        if not query:
            self._current_query = ""
            self._vm.set_query("")
            self._results_by_cat = {}
            self._apply_results(self._vm.category, [])
            return
        if query == self._current_query and self._vm.category in self._results_by_cat:
            return
        self._current_query = query
        self._vm.set_query(query)
        self._results_by_cat = {}
        await self._fetch(query, self._vm.category)

    async def load(self) -> None:
        pass  # paridad con SearchScreen (no-op; la búsqueda la dispara `search()`)

    def update_liked_state(self, video_id: str, liked: bool) -> None:
        items = self._results_by_cat.get("song", [])
        for item in items:
            if item.get("videoId") == video_id:
                item["is_liked"] = liked
        if self._vm.category == "song":
            self._vm.set_songs(items)

    # ── Fetch con caché por categoría ──────────────────────────────────────

    def _schedule_fetch(self, query: str, category: str) -> None:
        if self._fetch_task and not self._fetch_task.done():
            self._fetch_task.cancel()
        self._fetch_task = asyncio.ensure_future(self._fetch(query, category))

    async def _fetch(self, query: str, category: str) -> None:
        if category in self._results_by_cat:
            self._apply_results(category, self._results_by_cat[category])
            return

        self._vm.set_loading(True)
        self._vm.set_error("")
        try:
            from doremi.ui.screens.search_data import gather_search
            items = await gather_search(self.yt, query, category)
            # El usuario pudo cambiar de categoría/query mientras tanto
            if query != self._current_query:
                return
            self._results_by_cat[category] = items
            if category == self._vm.category:
                self._apply_results(category, items)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error en búsqueda QML ({category}): {e}")
            if category == self._vm.category and query == self._current_query:
                self._vm.set_error(_("No se pudieron cargar los resultados"))
        finally:
            if category == self._vm.category and query == self._current_query:
                self._vm.set_loading(False)

    def _apply_results(self, category: str, items: list[dict]) -> None:
        self._vm.set_loading(False)
        self._vm.set_error("")
        if category == "song":
            self._vm.set_songs(items)
        elif category in {"album", "podcast"}:
            self._vm.set_albums(items)
        elif category == "playlist":
            self._vm.set_playlists(items)
