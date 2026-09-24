import asyncio

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
        self.run_async(self.add_to_queue_async(video_id, title, artist, thumb_url, add_next=True))

    def on_add_to_queue_requested(self, video_id, title, artist, thumb_url):
        self.run_async(self.add_to_queue_async(video_id, title, artist, thumb_url, add_next=False))

    async def add_to_queue_async(self, video_id, title, artist, thumb_url, add_next=True):
        # Try to get duration from stream info
        dur_ms = 0
        try:
            info = await self.extractor.get_stream_info(video_id)
            if info.get("duration"):
                dur_ms = int(info["duration"]) * 1000
        except Exception as e:
            logger.debug(f"Could not fetch duration for queue item: {e}")

        item = QueueItem(
            video_id=video_id, title=title, artist=artist,
            album="", duration_ms=dur_ms, thumbnail_url=thumb_url,
        )
        if add_next:
            self.queue.add_next(item)
            self.main_window.statusBar().showMessage(f"Siguiente: {title}", 2000)
        else:
            self.queue.add_to_end(item)
            self.main_window.statusBar().showMessage(_f("Añadido a la cola: {title}", title=title), 2000)
        self.main_window.playback_controller._update_queue_panel()

    def on_add_to_playlist_requested(self, video_id, title):
        self.run_async(self.show_add_to_playlist_dialog(video_id, title))

    async def show_add_to_playlist_dialog(self, video_id, title):
        if not self.main_window.yt.is_authenticated:
            self.main_window.statusBar().showMessage("Inicia sesión para añadir a playlists", 3000)
            return

        playlists = await self.main_window.yt.get_library_playlists()
        if not playlists:
            self.main_window.statusBar().showMessage("No tienes playlists creadas", 3000)
            return

        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
            QWidget, QLineEdit, QPushButton, QGraphicsDropShadowEffect
        )
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtGui import QColor, QPixmap
        from doremi.ui.design.fonts import AppFont
        from doremi.ui.design.icons import Icon
        from doremi.ui.design import tokens
        from doremi.ui.design.animations import fade_in

        dialog = QDialog(self.main_window)
        dialog.setWindowTitle("Añadir a Playlist")
        dialog.setFixedSize(440, 480)
        dialog.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        shadow = QGraphicsDropShadowEffect(dialog)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 140))
        dialog.setGraphicsEffect(shadow)

        root = QWidget(dialog)
        root.setFixedSize(440, 480)
        root.setObjectName("addToPlaylistRoot")
        root.setStyleSheet(f"""
            QWidget#addToPlaylistRoot {{
                background: {tokens.CURRENT.bg_surface};
                border-radius: 16px;
            }}
        """)

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(80)
        header.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {tokens.CURRENT.accent},
                stop:1 {tokens.CURRENT.accent_bright});
            border-radius: 16px 16px 0 0;
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)

        icon_lbl = QLabel(Icon.get("playlist_add"))
        icon_lbl.setFont(Icon.font(28, filled=True))
        icon_lbl.setStyleSheet(f"color: {tokens.CURRENT.text_on_accent}; background: transparent;")
        header_layout.addWidget(icon_lbl)

        header_text = QLabel(f"Añadir a playlist")
        header_text.setFont(AppFont.heading(17))
        header_text.setStyleSheet(f"color: {tokens.CURRENT.text_on_accent}; background: transparent;")
        header_layout.addWidget(header_text)
        header_layout.addStretch()

        close_btn = QPushButton(Icon.get("close"))
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.15);
                color: {tokens.CURRENT.text_on_accent};
                border: none;
                border-radius: 16px;
                font-family: 'Material Symbols Rounded';
                font-size: 20px;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.25); }}
        """)
        close_btn.clicked.connect(dialog.reject)
        header_layout.addWidget(close_btn)

        root_layout.addWidget(header)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 12, 16, 16)
        body_layout.setSpacing(8)

        search_input = QLineEdit()
        search_input.setPlaceholderText("Buscar playlist...")
        search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {tokens.CURRENT.bg_elevated};
                color: {tokens.CURRENT.text_primary};
                border: 1px solid {tokens.CURRENT.border};
                border-radius: 10px;
                padding: 10px 14px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 2px solid {tokens.CURRENT.accent};
                padding: 9px 13px;
            }}
        """)
        body_layout.addWidget(search_input)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)

        for pl in playlists:
            pid = pl.get('playlistId')
            p_title = pl.get('title', 'Unknown')
            p_count = pl.get('count', '')
            p_thumbnails = pl.get('thumbnails', [])
            p_thumbnail_url = p_thumbnails[-1].get('url', '') if p_thumbnails else ''
            subtitle = f"{p_count} canciones" if p_count else ""

            row = QPushButton()
            row.setFixedHeight(60)
            row.setCursor(Qt.CursorShape.PointingHandCursor)
            row.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    border-radius: 8px;
                    text-align: left;
                    padding: 0;
                }}
                QPushButton:hover {{
                    background: {tokens.CURRENT.accent_dim};
                }}
            """)

            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(10, 8, 10, 8)
            row_layout.setSpacing(12)

            thumb = QLabel()
            thumb.setFixedSize(44, 44)
            if p_thumbnail_url:
                thumb.setStyleSheet("background: transparent; border-radius: 8px;")
                asyncio.ensure_future(self.load_playlist_thumb(thumb, p_thumbnail_url))
            else:
                thumb.setFont(Icon.font(22))
                thumb.setText(Icon.get("playlist_play"))
                thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
                thumb.setStyleSheet(f"""
                    background: {tokens.CURRENT.bg_high};
                    color: {tokens.CURRENT.text_disabled};
                    border-radius: 8px;
                """)
            row_layout.addWidget(thumb)

            text_col = QVBoxLayout()
            text_col.setSpacing(2)
            name_lbl = QLabel(p_title)
            name_lbl.setFont(AppFont.title(13))
            name_lbl.setStyleSheet(f"color: {tokens.CURRENT.text_primary}; background: transparent;")
            text_col.addWidget(name_lbl)

            if subtitle:
                sub_lbl = QLabel(subtitle)
                sub_lbl.setFont(AppFont.caption(11))
                sub_lbl.setStyleSheet(f"color: {tokens.CURRENT.text_secondary}; background: transparent;")
                text_col.addWidget(sub_lbl)

            row_layout.addLayout(text_col)
            row_layout.addStretch()

            add_icon = QLabel(Icon.get("add"))
            add_icon.setFont(Icon.font(18))
            add_icon.setStyleSheet(f"color: {tokens.CURRENT.text_disabled}; background: transparent;")
            add_icon.setFixedSize(28, 28)
            add_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row_layout.addWidget(add_icon)

            row.clicked.connect(lambda _, pid=pid, p_title=p_title: (
                dialog.accept(),
                self.run_async(self.add_to_yt_playlist(pid, video_id, p_title))
            ))
            content_layout.addWidget(row)

        content_layout.addStretch()
        scroll.setWidget(content)
        body_layout.addWidget(scroll)

        root_layout.addWidget(body)

        def filter_playlists(text: str):
            for i in range(content_layout.count()):
                item = content_layout.itemAt(i)
                if item and item.widget():
                    widget = item.widget()
                    lbl = widget.findChildren(QLabel)
                    match = False
                    for l in lbl:
                        if text.lower() in l.text().lower():
                            match = True
                            break
                    widget.setVisible(match)

        search_input.textChanged.connect(filter_playlists)

        fade_in(root, 200)
        self._playlist_dialog = dialog
        dialog.open()

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
        self.run_async(self.toggle_like_async(video_id, btn_like))

    async def toggle_like_async(self, video_id, btn_like):
        async with self._like_lock:
            try:
                await self._toggle_like_locked(video_id, btn_like)
            except Exception as exc:
                logger.error(f"No se pudo actualizar favorito {video_id}: {exc}")
                self.main_window.show_notification(_("No se pudo actualizar el favorito. Puedes reintentarlo."), "error")

    async def _toggle_like_locked(self, video_id, btn_like):
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
                await repo.upsert_song(video_id=video_id, title="Unknown", artist="Unknown")

        liked = await repo.toggle_like(video_id)
        current = self.queue.current
        if current and current.video_id == video_id:
            self.main_window.now_playing_screen.set_liked_state(liked)
        search = getattr(self.main_window, "search_screen", None)
        if search is not None and hasattr(search, "update_liked_state"):
            search.update_liked_state(video_id, liked)

        # Sync with YouTube Music in the background if authenticated
        if self.main_window.yt.is_authenticated:
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
            if getattr(library, "_qml_island", False) and library.isVisible():
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
