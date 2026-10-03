import asyncio
from dataclasses import replace

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from doremi.audio.queue import QueueItem
from doremi.utils.i18n import _, _f


class QueueController:
    """Specialized controller for queue-related user actions.

    Owns the queue-manipulation logic previously living in MainWindow's god
    object: play-next / add-to-queue, add-to-playlist (dialog + YT sync), and
    like toggling (with DB + YouTube Music sync and UI updates).

    ``main_window`` is the back-reference to MainWindow. Shared state and UI
    objects (yt client, screens, stack, statusBar, notifications,
    playback_controller) are accessed through ``self.main_window`` rather than
    cached, because MainWindow finishes building them after this controller is
    constructed and ``MainWindow.yt`` is reassigned on login/logout (so the
    current reference must always be read at call time).

    ``queue`` and ``extractor`` are injected directly (already constructed in
    MainWindow.__init__) so the controller can mutate the queue and fetch stream
    info without reaching through MainWindow.

    ``run_async`` is a callable (MainWindow._run_async) used to launch coroutines
    as asyncio tasks.
    """

    def __init__(self, main_window, queue, extractor, run_async):
        self.main_window = main_window
        self.queue = queue
        self.extractor = extractor
        self.run_async = run_async
        self._playlist_dialog = None
        self._like_lock = asyncio.Lock()

    def on_play_next_requested(self, video_id, title, artist, thumb_url):
        from doremi.services.playback_context import playback_context
        from doremi.ui.controllers.track_action_data import capture_track_metadata
        self.run_async(self.add_to_queue_async(
            video_id, title, artist, thumb_url, add_next=True,
            context=playback_context(self.main_window),
            metadata=capture_track_metadata(self.main_window, video_id)))

    def on_add_to_queue_requested(self, video_id, title, artist, thumb_url):
        from doremi.services.playback_context import playback_context
        from doremi.ui.controllers.track_action_data import capture_track_metadata
        self.run_async(self.add_to_queue_async(
            video_id, title, artist, thumb_url, add_next=False,
            context=playback_context(self.main_window),
            metadata=capture_track_metadata(self.main_window, video_id)))

    def requeue_occurrence(self, index: int, add_next: bool) -> None:
        """Copy the selected occurrence, not the first matching video ID."""
        items = self.queue.items
        if not 0 <= index < len(items):
            return
        item = replace(items[index])
        self._insert(item, add_next)

    def _insert(self, item: QueueItem, add_next: bool) -> None:
        if add_next:
            self.queue.add_next(item)
            message = f"Siguiente: {item.title}"
        else:
            self.queue.add_to_end(item)
            message = _f("Añadido a la cola: {title}", title=item.title)
        self.main_window.statusBar().showMessage(message, 2000)
        self.main_window.playback_controller._update_queue_panel()

    async def add_to_queue_async(self, video_id, title, artist, thumb_url, add_next=True, context=None, metadata=None):
        if context and context.get("context_type") == "queue":
            current = self.queue.current
            original = current if current and current.video_id == video_id else next(
                (entry for entry in self.queue.items if entry.video_id == video_id), None)
            if original is not None:
                context = dict(context_type=original.context_type, context_id=original.context_id,
                               context_title=original.context_title)
        item = QueueItem(
            video_id=video_id, title=title, artist=artist,
            album=(metadata or {}).get("album", ""), duration_ms=(metadata or {}).get("duration_ms", 0), thumbnail_url=thumb_url,
            **(context or {"context_type": "queue"}),
        )
        self._insert(item, add_next)
        if item.duration_ms > 0:
            return
        # Queue insertion is immediate; optional metadata must not delay it.
        # Enrich this occurrence only if it has not been removed meanwhile.
        try:
            info = {} if video_id.startswith("local:") else await self.extractor.get_stream_info(video_id)
            if info.get("duration") and any(entry is item for entry in self.queue.items):
                item.duration_ms = max(0, int(info["duration"]) * 1000)
                self.main_window.playback_controller._update_queue_panel()
        except Exception as e:
            logger.debug(f"Could not fetch duration for queue item: {e}")

    def on_add_to_playlist_requested(self, video_id, title):
        from doremi.ui.controllers.track_action_data import capture_track_metadata
        self.run_async(self.show_add_to_playlist_dialog(video_id, title, capture_track_metadata(self.main_window, video_id)))

    async def show_add_to_playlist_dialog(self, video_id, title, metadata=None):
        await self.main_window.desktop_controller.show_picker(video_id, title, metadata)

    async def load_playlist_thumb(self, thumb_label, url):
        from PySide6.QtGui import QPixmap
        from doremi.utils.image_cache import ImageCache
        _image_cache = ImageCache()
        path = await _image_cache.download(url)
        import shiboken6
        if not shiboken6.isValid(thumb_label):
            return
        if path:
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                pixmap = pixmap.scaled(44, 44, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                       Qt.TransformationMode.SmoothTransformation)
                thumb_label.setPixmap(pixmap)
                thumb_label.setStyleSheet("background: transparent; border-radius: 8px;")

    async def add_to_yt_playlist(self, playlist_id: str, video_id: str, playlist_name: str):
        try:
            res = await self.main_window.yt.add_playlist_items(playlist_id, [video_id])
            if res and (res.get('status') == 'STATUS_SUCCEEDED' or 'playlistItemId' in res):
                self.main_window.statusBar().showMessage(f"Añadido a '{playlist_name}'", 3000)
                self.main_window.show_notification(f"Se añadió la canción a '{playlist_name}'", "success")
            else:
                self.main_window.statusBar().showMessage("Error al añadir a playlist", 3000)
                self.main_window.show_notification("Error al añadir a playlist", "error")
        except Exception as e:
            logger.error(f"Failed to add to playlist: {e}")
            self.main_window.statusBar().showMessage("Error al añadir a playlist", 3000)
            self.main_window.show_notification("Error al añadir a playlist", "error")

    def on_like_requested(self, video_id, btn_like):
        from doremi.ui.controllers.track_action_data import capture_track_metadata
        metadata = capture_track_metadata(self.main_window, video_id)
        self.run_async(self.toggle_like_async(video_id, btn_like, metadata))

    async def toggle_like_async(self, video_id, btn_like, metadata=None):
        async with self._like_lock:
            try:
                await self._toggle_like_locked(video_id, btn_like, metadata)
            except Exception as exc:
                logger.error(f"No se pudo actualizar favorito {video_id}: {exc}")
                self.main_window.show_notification(_("No se pudo actualizar el favorito. Puedes reintentarlo."), "error")

    async def _toggle_like_locked(self, video_id, btn_like, metadata=None):
        from doremi.db.repository import SongRepository, DownloadRepository
        repo = SongRepository()

        # Ensure song exists in DB before liking
        song = await repo.get_song(video_id)
        if not song:
            dl_repo = DownloadRepository()
            dl = await dl_repo.get_download(video_id)
            if dl:
                await repo.upsert_song(
                    video_id=video_id,
                    title=dl.title or "Unknown",
                    artist=dl.artist or "Unknown",
                    thumbnail_url=dl.thumbnail_url or ""
                )
            else:
                await repo.upsert_song(video_id=video_id, **(metadata or dict(title="Unknown", artist="Unknown")))

        liked = await repo.toggle_like(video_id)
        from doremi.services.experience_events import events
        events.liked_changed.emit(video_id, liked)
        events.changed.emit()
        current = self.queue.current
        if current and current.video_id == video_id:
            self.main_window.now_playing_screen.set_liked_state(liked)

        # Sync with YouTube Music in the background if authenticated
        if self.main_window.yt.is_authenticated and not video_id.startswith("local:"):
            rating = "LIKE" if liked else "INDIFFERENT"
            try:
                await self.main_window.yt.rate_song(video_id, rating)
            except Exception as exc:
                logger.warning(f"Favorito local guardado; sincronización pendiente: {exc}")
                self.main_window.show_notification(_("Favorito guardado localmente; no se pudo sincronizar con YouTube Music."), "warning")
            self.main_window.library_screen.invalidate_songs_cache()
        else:
            self.main_window.library_screen.invalidate_songs_cache()

        if btn_like is None:
            # Origen QML (sin botón QtWidgets): el toggle ya ocurrió en DB.
            self.main_window.statusBar().showMessage(
                "Añadido a Favoritas" if liked else "Eliminado de Favoritas", 2000
            )
            self.main_window.playback_controller._update_queue_panel()
            library = self.main_window.library_screen
            if getattr(library, "_qml_island", False) and getattr(self.main_window, "_current_route", "") == "library":
                await library.load()
            return

        # If the library screen is currently active and the "songs" tab is active:
        # If unliked, animate it fading out and remove it locally to avoid reloading lag!
        current_screen = self.main_window.stack.currentWidget()
        if (
            current_screen == self.main_window.library_screen
            and self.main_window.library_screen._current_tab == "songs"
            and hasattr(self.main_window.library_screen, "content_layout")
            and not liked
        ):
            card = btn_like.parent()
            if card and isinstance(card, QWidget):
                self.main_window.library_screen.content_layout.removeWidget(card)
                card.deleteLater()

        if btn_like.objectName() == "nowPlayingLikeBtn":
            self.main_window.now_playing_screen.set_liked_state(liked)
            self.main_window.statusBar().showMessage("Añadido a Favoritas" if liked else "Eliminado de Favoritas", 2000)
            self.main_window.playback_controller._update_queue_panel()
            return

        # Update parent SongCard's internal state if applicable
        parent_card = btn_like.parent()
        if parent_card and hasattr(parent_card, "_is_liked"):
            parent_card._is_liked = liked

        from doremi.ui.design import tokens
        from doremi.ui.design.icons import Icon
        from PySide6.QtGui import QColor
        like_c = QColor(tokens.CURRENT.like_color)
        lr, lg, lb = like_c.red(), like_c.green(), like_c.blue()

        btn_like.setText(Icon.get("favorite"))
        if liked:
            btn_like.setStyleSheet(f"QPushButton {{ color: {tokens.CURRENT.like_color}; background: transparent; border: none; }}")
            btn_like.setFont(Icon.font(20, filled=True))
            btn_like.set_active(True)
            self.main_window.statusBar().showMessage("Añadido a Favoritas", 2000)
        else:
            btn_like.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;

                    border: none;
                    border-radius: 18px;
                }}
                QPushButton:hover {{
                    background-color: rgba({lr},{lg},{lb},0.15);
                    color: {tokens.CURRENT.like_color};
                }}
            """)
            btn_like.setFont(Icon.font(20, filled=False))
            btn_like.set_active(False)
            self.main_window.statusBar().showMessage("Eliminado de Favoritas", 2000)

        self.main_window.playback_controller._update_queue_panel()
