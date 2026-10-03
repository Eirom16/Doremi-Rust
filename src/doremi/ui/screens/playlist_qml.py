from __future__ import annotations

import asyncio
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtWidgets import QApplication
from loguru import logger

from doremi.services.download_manager import DownloadManager
from doremi.ui.viewmodels.playlist_vm import PlaylistViewModel

QML_DIR = Path(__file__).resolve().parent.parent / "qml"


class PlaylistScreenQml(QObject):
    """Isla QML: Playlist como QQuickWidget.

    Drop-in replacement de PlaylistScreen (QtWidgets): mismas señales,
    mismo constructor, mismo método `load(playlist_id)`, soporte para
    playlists locales (`local_*`) y remotas de YouTube Music.
    """

    _qml_island = True  # fade_stack.py: sin cross-fade

    download_requested = Signal(str, str, str, str)
    copy_link_requested = Signal(str)
    download_playlist_requested = Signal(str, str, str)  # playlist_id, title, thumbnail_url
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    add_to_playlist_requested = Signal(str, str)
    like_requested = Signal(str, object)
    delete_download_requested = Signal(str)
    notification_requested = Signal(str, str)

    def __init__(self, yt_client, on_play_song, on_play_local_playlist=None, on_back=None):
        super().__init__()
        self.yt = yt_client
        self.on_play_song = on_play_song
        self.on_play_local_playlist = on_play_local_playlist
        self.on_back = on_back
        self._playlist_id: str | None = None  # leído por download_controller (paridad widgets)
        self._load_task: asyncio.Task | None = None
        self._load_generation = 0

        self._vm = PlaylistViewModel(QApplication.instance())

        self.qml_source = QUrl.fromLocalFile(str(QML_DIR / "PlaylistScreen.qml"))
        self._load_ok = True

        # Re-emit VM signals as screen signals
        self._vm.download_requested.connect(self.download_requested)
        self._vm.copy_link_requested.connect(self.copy_link_requested)
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
        self._vm.save_session_requested.connect(self._save_session)
        self._vm.local_edit_requested.connect(self._edit_local)
        self._vm.remove_local_requested.connect(self._remove_local)
        self._vm.notification_requested.connect(self.notification_requested)
        self._vm.collection_copy_link_requested.connect(lambda url: QApplication.clipboard().setText(url))

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

    def _save_session(self, identity, title):
        if self._vm.editing:
            return
        self._vm.set_editing(True)
        async def save():
            from doremi.services.listening_periods import ListeningPeriods
            from doremi.services.experience_events import events
            try:
                first, last, cutoff = ListeningPeriods.parse_identity(identity)
                playlist_id = await ListeningPeriods().save_as_playlist(first, last, title, cutoff)
                events.changed.emit()
                events.collections_changed.emit()
                self.notification_requested.emit("Sesión guardada como playlist", "success")
            except Exception as exc:
                logger.warning(f"Could not save music session: {exc}")
                self.notification_requested.emit("No se pudo guardar la sesión", "error")
            finally:
                self._vm.set_editing(False)
        asyncio.ensure_future(save())

    def _edit_local(self, identity, action, title):
        if self._vm.editing:
            return
        self._vm.set_editing(True)
        async def edit():
            from doremi.db.local_library_repository import LocalLibraryRepository
            from doremi.services.experience_events import events
            try:
                repo = LocalLibraryRepository()
                if action == "rename":
                    await repo.rename_playlist(identity, title)
                else:
                    await repo.delete_playlist(identity)
                events.changed.emit()
                events.collections_changed.emit()
                if identity == self._playlist_id:
                    if action == "delete":
                        self._on_back()
                    else:
                        await self.load(identity)
                self.notification_requested.emit("Playlist actualizada" if action == "rename" else "Playlist eliminada", "success")
            except Exception as exc:
                logger.warning(f"Could not edit local playlist: {exc}")
                self.notification_requested.emit("No se pudo actualizar la playlist", "error")
            finally:
                self._vm.set_editing(False)
        asyncio.ensure_future(edit())

    def _remove_local(self, identity, position, video_id, title):
        if self._vm.editing:
            return
        self._vm.set_editing(True)
        async def remove():
            from doremi.db.local_library_repository import LocalLibraryRepository
            from doremi.services.experience_events import events
            try:
                removed = await LocalLibraryRepository().remove_occurrence(identity, position, video_id)
                if not removed:
                    raise ValueError("La canción ya cambió en esta playlist")
                events.changed.emit()
                events.collections_changed.emit()
                if identity == self._playlist_id:
                    await self.load(identity)
                self.notification_requested.emit(f"Quitada de playlist: {title}", "success")
            except Exception as exc:
                logger.warning(f"Could not remove local occurrence: {exc}")
                self.notification_requested.emit("No se pudo quitar la canción", "error")
            finally:
                self._vm.set_editing(False)
        asyncio.ensure_future(remove())

    def _retry(self) -> None:
        if self._playlist_id:
            asyncio.ensure_future(self.load(self._playlist_id))

    def _on_vm_play_local(self, meta_list: list, start_index: int) -> None:
        if self.on_play_local_playlist and meta_list:
            try:
                self.on_play_local_playlist(meta_list, start_index)
            except Exception as e:
                logger.error(f"Play local playlist error desde isla QML: {e}")

    def _on_vm_play_queue(self, items: list, index: int) -> None:
        if not items or not self.on_play_song:
            return
        from doremi.audio.queue import QueueItem
        queue_items = [
            QueueItem(
                video_id=t.get("videoId", ""),
                title=t.get("title", "Unknown"),
                artist=t.get("artist", ""),
                album="",
                duration_ms=t.get("duration_ms", 0),
                thumbnail_url=t.get("thumbnail_url", "") or self._vm.thumbnail,
                is_local=bool(t.get("local_path")),
                local_path=t.get("local_path"),
                context_type="smart" if (self._playlist_id or "").startswith("smart:") else "playlist",
                context_id=self._playlist_id or "",
                context_title=self._vm.title,
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
            logger.error(f"Play error desde isla QML Playlist: {e}")

    def _on_remove_track(self, video_id: str, set_video_id: str, title: str) -> None:
        asyncio.ensure_future(self._remove_track_async(video_id, set_video_id, title))

    async def _remove_track_async(self, video_id: str, set_video_id: str, title: str) -> None:
        """Remueve el track vía API y recarga (paridad widgets; el confirm lo hace el QML)."""
        identity = self._playlist_id
        try:
            if not self.yt or not self.yt.is_authenticated:
                self.notification_requested.emit("Inicia sesión para editar playlists", "warning")
                return
            response = await self.yt.remove_playlist_items(
                identity, [{"videoId": video_id, "setVideoId": set_video_id}],
            )
            if response:
                self.notification_requested.emit(f"Quitado de playlist: {title}", "success")
                if identity and self._playlist_id == identity:
                    await self.load(identity)
            else:
                self.notification_requested.emit("No se pudo quitar de la playlist", "error")
        except Exception as e:
            logger.error(f"Error quitando track de playlist: {e}")
            self.notification_requested.emit("No se pudo quitar de la playlist", "error")

    # ── Carga ──────────────────────────────────────────────────────────────

    async def load(self, playlist_id: str) -> None:
        if not playlist_id:
            return
        if self._load_task and not self._load_task.done():
            self._load_task.cancel()
        current = asyncio.current_task()
        self._load_task = current
        self._load_generation += 1
        generation = self._load_generation
        self._playlist_id = playlist_id

        def is_current_request() -> bool:
            return generation == self._load_generation and playlist_id == self._playlist_id

        self._vm.set_loading(True)
        self._vm.set_error("")
        try:
            from doremi.ui.screens.playlist_data import gather_playlist
            data = await gather_playlist(self.yt, playlist_id)
            if not is_current_request():
                return
            self._vm.set_data(data)
            from doremi.db.experience_repository import ExperienceRepository
            pinned = await ExperienceRepository().is_pinned(playlist_id)
            if not is_current_request():
                return
            self._vm.set_pin_state(playlist_id, pinned)
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
        try:
            from doremi.db.repository import DownloadRepository
            downloads = await DownloadRepository().get_downloads()
            downloaded = sum(
                1 for d in downloads if d.parent_playlist_id == self._playlist_id
            )
            fully = downloaded >= self._vm._track_count > 0
            self._vm.refresh_counters(downloaded, fully)
        except Exception as e:
            logger.debug(f"Error refreshing playlist download state: {e}")
