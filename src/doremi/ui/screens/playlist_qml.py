from __future__ import annotations

import asyncio
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtWidgets import QApplication
from loguru import logger

from doremi.services.download_manager import DownloadManager
from doremi.services.collection_identity import has_local_playlist_namespace
from doremi.ui.viewmodels.playlist_vm import PlaylistViewModel

from doremi.ui.qml_paths import qml_dir

QML_DIR = qml_dir()


class PlaylistScreenQml(QObject):
    """Isla QML: Playlist como QQuickWidget.

    Drop-in replacement de PlaylistScreen (QtWidgets): mismas señales,
    mismo constructor, mismo método `load(playlist_id)`, soporte para
    playlists locales (`local_*`) y remotas de YouTube Music.
    """

    _qml_island = True  # fade_stack.py: sin cross-fade

    download_requested = Signal(str, str, str, str)
    download_playlist_requested = Signal(str, str, str)  # playlist_id, title, thumbnail_url
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    add_to_playlist_requested = Signal(str, str)
    like_requested = Signal(str, object)
    delete_download_requested = Signal(str)

    def __init__(self, yt_client, on_play_song, on_play_local_playlist=None, on_back=None):
        super().__init__()
        self.yt = yt_client
        self.on_play_song = on_play_song
        self.on_play_local_playlist = on_play_local_playlist
        self.on_back = on_back
        self._playlist_id: str | None = None  # leído por download_controller (paridad widgets)
        self._load_task: asyncio.Task | None = None
        self._load_generation = 0
        self._page_task: asyncio.Task | None = None

        self._vm = PlaylistViewModel(QApplication.instance())

        self.qml_source = QUrl.fromLocalFile(str(QML_DIR / "PlaylistScreen.qml"))
        self._load_ok = True

        # Re-emit VM signals as screen signals
        self._vm.download_requested.connect(self.download_requested)
        self._vm.download_playlist_requested.connect(self.download_playlist_requested)
        self._vm.play_next_requested.connect(self.play_next_requested)
        self._vm.add_to_queue_requested.connect(self.add_to_queue_requested)
        self._vm.add_to_playlist_requested.connect(self.add_to_playlist_requested)
        self._vm.like_requested.connect(self.like_requested)
        self._vm.delete_download_requested.connect(self.delete_download_requested)
        self._vm.play_queue_requested.connect(self._on_vm_play_queue)
        self._vm.play_local_requested.connect(self._on_vm_play_local)
        self._vm.remove_track_requested.connect(self._on_remove_track)
        self._vm.back_requested.connect(self._on_back)
        self._vm.retry_requested.connect(self._retry)
        self._vm.load_more_requested.connect(self._request_load_more)

        # Progreso de descarga de la playlist (paridad widgets)
        dm = DownloadManager.get_instance()
        dm.download_progress.connect(self._on_dl_progress)
        dm.download_completed.connect(self._on_dl_completed)

    @property
    def is_ok(self) -> bool:
        return self._load_ok

    def _on_back(self) -> None:
        if self.on_back:
            self.on_back()

    def _retry(self) -> None:
        if self._playlist_id:
            limit, offset = getattr(self, "_initial_page", (1000, 0))
            asyncio.ensure_future(self.load(self._playlist_id, limit=limit, offset=offset))

    def _on_vm_play_local(self, meta_list: list, start_index: int) -> None:
        if ((self._load_task and not self._load_task.done())
                or (self._playlist_id and self._vm._playlist_id != self._playlist_id)):
            return
        if self.on_play_local_playlist and meta_list:
            try:
                if self._playlist_id:
                    context = dict(
                        context_type="smart" if self._playlist_id.startswith("smart:") else "playlist",
                        context_id=self._playlist_id, context_title=self._vm.title,
                    )
                    # Metadata already accepts this REC-04.1.1 field. Stamp
                    # at the producer boundary, before the next route's fade.
                    meta_list = [dict(m, playback_context=m.get("playback_context") or context)
                                 for m in meta_list]
                self.on_play_local_playlist(meta_list, start_index)
            except Exception as e:
                logger.error(f"Play local playlist error desde isla QML: {e}")

    def _on_vm_play_queue(self, items: list, index: int) -> None:
        if ((self._load_task and not self._load_task.done())
                or (self._playlist_id and self._vm._playlist_id != self._playlist_id)):
            return
        if not items or not self.on_play_song:
            return
        from doremi.audio.queue import QueueItem
        from doremi.services.local_playback import available_local_path
        context_type = ("smart" if (self._playlist_id or "").startswith("smart:")
                        else "playlist")
        queue_items = [
            QueueItem(
                video_id=t.get("videoId", ""),
                title=t.get("title", "Unknown"),
                artist=t.get("artist", ""),
                album="",
                duration_ms=t.get("duration_ms", 0),
                thumbnail_url=t.get("thumbnail_url", "") or self._vm.thumbnail,
                context_type=context_type,
                context_id=self._playlist_id or "",
                context_title=self._vm.title,
                local_path=path,
                is_local=bool(path),
            )
            for t in items
            for path in [available_local_path(t.get("local_path"))]
        ]
        index = max(0, min(index, len(queue_items) - 1))
        first = queue_items[index]
        try:
            self.on_play_song(
                first.video_id, first.title, first.artist, first.album,
                first.duration_ms, first.thumbnail_url, queue_items, index,
            )
        except Exception as e:
            logger.error(f"Play error desde isla QML Playlist: {e}")

    def _on_remove_track(self, video_id: str, set_video_id: str, title: str) -> None:
        asyncio.ensure_future(self._remove_track_async(video_id, set_video_id, title))

    async def _remove_track_async(self, video_id: str, set_video_id: str, title: str) -> None:
        """Remueve el track vía API y recarga (paridad widgets; el confirm lo hace el QML)."""
        try:
            if not self.yt or not self.yt.is_authenticated:
                from doremi.ui.widgets.toast import ToastNotification
                ToastNotification.show(self.window(), "Inicia sesión para editar playlists", "warning")
                return
            response = await self.yt.remove_playlist_items(
                self._playlist_id, [{"videoId": video_id, "setVideoId": set_video_id}],
            )
            from doremi.ui.widgets.toast import ToastNotification
            if response:
                ToastNotification.show(self.window(), f"Quitado de playlist: {title}", "success")
                if self._playlist_id:
                    await self.load(self._playlist_id)
            else:
                ToastNotification.show(self.window(), "No se pudo quitar de la playlist", "error")
        except Exception as e:
            logger.error(f"Error quitando track de playlist: {e}")

    # ── Carga ──────────────────────────────────────────────────────────────

    async def load(self, playlist_id: str, *, limit: int = 1000, offset: int = 0) -> None:
        """Replace a visible range; load_more() appends subsequent local pages.

        Explicit reloads invalidate both first-page and incremental requests,
        including reloads of the same identity. The old one-argument call
        retains its initial range of up to 1000 local occurrences.
        """
        if not playlist_id:
            return
        from doremi.ui.screens.playlist_data import _coerce_limit, _coerce_offset
        limit, offset = _coerce_limit(limit), _coerce_offset(offset)
        self._initial_page = (limit, offset)
        current = asyncio.current_task()
        self._load_generation += 1
        generation = self._load_generation
        for task in (self._load_task, getattr(self, "_page_task", None)):
            if task and task is not current and not task.done():
                task.cancel()
        self._page_task = None
        self._load_task = current
        self._playlist_id = playlist_id

        def is_current_request() -> bool:
            return generation == self._load_generation and playlist_id == self._playlist_id

        self._vm.set_loading(True)
        self._vm.set_error("")
        self._vm.set_loading_more(False)
        self._vm.set_load_more_error("")
        try:
            from doremi.ui.screens.playlist_data import gather_playlist
            # Keep the historical default call shape for existing hosts.
            data = (await gather_playlist(self.yt, playlist_id) if limit == 1000 and offset == 0
                    else await gather_playlist(self.yt, playlist_id, limit=limit, offset=offset))
            if not is_current_request():
                return
            if data.get("playlist_id") != playlist_id:
                raise ValueError("Playlist response identity mismatch")
            self._vm.set_data(data)
            if self._vm.found and not self._vm.isLocal:
                self._refresh_download_state()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error loading playlist (QML): {e}")
            if not is_current_request():
                return
            self._vm.set_data({"playlist_id": playlist_id})
            self._vm.set_error("No se pudo cargar la playlist. Comprueba tu conexión e inténtalo de nuevo.")
        finally:
            if is_current_request():
                self._vm.set_loading(False)
            if self._load_task is current:
                self._load_task = None

    def _request_load_more(self) -> None:
        """Claim the UI request synchronously before scheduling its page task."""
        if (self._vm.loading or self._vm.loadingMore or not self._vm.hasMore
                or self._vm._playlist_id != self._playlist_id
                or not has_local_playlist_namespace(self._playlist_id)):
            return
        self._vm.set_loading_more(True)
        self._page_task = asyncio.ensure_future(self.load_more())

    async def load_more(self) -> bool:
        """Append one local page. Remote provider pagination remains untouched."""
        playlist_id = self._playlist_id
        if (not has_local_playlist_namespace(playlist_id)
                or self._vm.loading or not self._vm.hasMore
                or (self._page_task and self._page_task is not asyncio.current_task()
                    and not self._page_task.done())):
            return False
        current = asyncio.current_task()
        self._page_task = current
        generation = self._load_generation
        limit = self._vm.pageLimit
        offset = self._vm.pageOffset + limit

        def is_current_request():
            return generation == self._load_generation and playlist_id == self._playlist_id

        self._vm.set_loading_more(True)
        self._vm.set_load_more_error("")
        try:
            from doremi.ui.screens.playlist_data import gather_playlist
            data = await gather_playlist(self.yt, playlist_id, limit=limit, offset=offset)
            if not is_current_request():
                return False
            if not self._vm.append_page(data):
                raise ValueError("Playlist page identity or offset mismatch")
            if not self._vm.isLocal:
                self._refresh_download_state()
            return True
        except asyncio.CancelledError:
            raise
        except Exception as e:
            if is_current_request():
                logger.warning(f"Error loading playlist page: {e}")
                self._vm.set_load_more_error("No se pudo cargar la siguiente página. Puedes reintentarlo.")
            return False
        finally:
            if is_current_request():
                self._vm.set_loading_more(False)
            if self._page_task is current:
                self._page_task = None

    # ── Estado del botón de descarga ───────────────────────────────────────

    def _tasks_progress(self) -> int | None:
        dm = DownloadManager.get_instance()
        tasks = [t for t in dm._tasks.values() if t.parent_playlist_id == self._playlist_id]
        if not tasks:
            return None
        return int(sum(t.progress for t in tasks) / len(tasks))

    def _refresh_download_state(self) -> None:
        if self._vm.isLocal:
            return
        pct = self._tasks_progress()
        if pct is not None:
            self._vm.set_download_state(PlaylistViewModel.DL_ACTIVE, pct)
            return
        if self._vm._is_fully:
            self._vm.set_download_state(PlaylistViewModel.DL_FULL)
        elif self._vm._downloaded_count:
            self._vm.set_download_state(PlaylistViewModel.DL_PARTIAL)
        else:
            self._vm.set_download_state(PlaylistViewModel.DL_NONE)

    def _on_dl_progress(self, _video_id: str, _progress: float, _speed: str) -> None:
        if not self._playlist_id or self._vm.isLocal:
            return
        pct = self._tasks_progress()
        if pct is not None:
            self._vm.set_download_state(PlaylistViewModel.DL_ACTIVE, pct)

    def _on_dl_completed(self, _video_id: str, _filepath: str) -> None:
        if not self._playlist_id or self._vm.isLocal:
            return
        if self._tasks_progress() is not None:
            return  # aún hay tareas activas
        asyncio.ensure_future(self._refresh_counts())

    async def _refresh_counts(self) -> None:
        if not self._playlist_id:
            return
        playlist_id, generation = self._playlist_id, self._load_generation
        try:
            from doremi.db.repository import DownloadRepository
            downloads = await DownloadRepository().get_downloads()
            if playlist_id != self._playlist_id or generation != self._load_generation:
                return
            downloaded = sum(
                1 for d in downloads if d.parent_playlist_id == self._playlist_id
            )
            fully = downloaded >= self._vm._track_count > 0
            self._vm.refresh_counters(downloaded, fully)
        except Exception as e:
            logger.debug(f"Error refreshing playlist download state: {e}")
