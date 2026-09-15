from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Signal, Qt, Property, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QPixmap
import asyncio
from doremi.utils.image_cache import ImageCache
from doremi.ui.design.icons import Icon
from doremi.ui.widgets.icon_button import IconButton
from doremi.ui.widgets.song_context_menu import SongContextMenu
from doremi.ui.design import tokens

_image_cache = ImageCache()

class SongCard(QWidget):
    clicked = Signal()
    artist_clicked = Signal(str)
    album_clicked = Signal(str)
    download_requested = Signal(str, str, str, str)  # video_id, title, artist, thumbnail_url
    play_next_requested = Signal(str, str, str, str)  # video_id, title, artist, thumbnail_url
    add_to_queue_requested = Signal(str, str, str, str)  # video_id, title, artist, thumbnail_url
    add_to_playlist_requested = Signal(str, str) # video_id, title
    like_requested = Signal(str, object)  # video_id, button_instance
    delete_download_requested = Signal(str)  # video_id
    remove_from_playlist_requested = Signal(str, str, str, str)  # playlist_id, video_id, set_video_id, title

    def __init__(
        self,
        title,
        artist,
        duration,
        thumbnail_url="",
        on_play=None,
        video_id="",
        is_liked=False,
        album="",
        playlist_id="",
        set_video_id="",
    ):
        super().__init__()
        self._title = title
        self._artist = artist
        self._album = album
        self._duration = duration
        self._thumbnail_url = thumbnail_url
        self._on_play = on_play
        self._video_id = video_id
        self._is_liked = is_liked
        self._playlist_id = playlist_id
        self._set_video_id = set_video_id
        
        self._bg_opacity = 0.0
        self._bg_anim = QPropertyAnimation(self, b"bg_opacity", self)
        self._bg_anim.setDuration(150)
        self._bg_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        self._build_ui()
        if self._thumbnail_url:
            asyncio.ensure_future(self._load_thumbnail())

    async def _load_thumbnail(self):
        path = await _image_cache.download(self._thumbnail_url)
        import shiboken6
        if not shiboken6.isValid(self):
            return
            
        if path:
            from PySide6.QtGui import QPixmapCache
            cache_key = f"{path}_50_50"
            pixmap = QPixmap()
            if QPixmapCache.find(cache_key, pixmap):
                self.thumbnail.setPixmap(pixmap)
                self.thumbnail.setObjectName("thumbnail_image")
            else:
                from doremi.utils.image_cache import load_scaled_async
                def on_loaded(bytes_data):
                    if not shiboken6.isValid(self):
                        return
                    if bytes_data:
                        pix = QPixmap()
                        if pix.loadFromData(bytes_data):
                            QPixmapCache.insert(cache_key, pix)
                            self.thumbnail.setPixmap(pix)
                            self.thumbnail.setObjectName("thumbnail_image")
                load_scaled_async(path, 50, 50, self, on_loaded)

    def _build_ui(self):
        self.setObjectName("songCard")
        self.setFixedHeight(68)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        accessible = f"{self._title} - {self._artist}" if self._artist else self._title
        self.setAccessibleName(accessible)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(10)

        self.thumbnail = QLabel()
        self.thumbnail.setFixedSize(50, 50)
        self.thumbnail.setText(Icon.get("music_note"))
        self.thumbnail.setFont(Icon.font(24))
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.thumbnail)

        info = QVBoxLayout()
        info.setSpacing(2)
        info.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.title_label = QLabel(self._title)
        self.title_label.setFont(QFont("Inter", 13, QFont.Weight.DemiBold))
        
        # Elide long text
        metrics = self.title_label.fontMetrics()
        elided_title = metrics.elidedText(self._title, Qt.TextElideMode.ElideRight, 240)
        self.title_label.setText(elided_title)
        info.addWidget(self.title_label)

        from doremi.ui.widgets.clickable_label import ClickableLabel
        self.artist_label = ClickableLabel(self._artist)
        self.artist_label.set_clicked_callback(self._on_artist_clicked)
        self.artist_label.setFont(QFont("Inter", 11))
        self.artist_label.setStyleSheet(f"color: {tokens.CURRENT.text_secondary}; background: transparent;")
        
        # Elide long text (we do this manually since we can't easily elide a clickable label dynamically on resize without custom paint)
        artist_metrics = self.artist_label.fontMetrics()
        elided_artist = artist_metrics.elidedText(self._artist, Qt.TextElideMode.ElideRight, 260)
        self.artist_label.setText(elided_artist)
        info.addWidget(self.artist_label)

        layout.addLayout(info)
        layout.addStretch()

        self.duration_label = QLabel(self._duration)
        self.duration_label.setFont(QFont("Inter", 10))
        self.duration_label.setFixedWidth(46)
        self.duration_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.duration_label)

        # Like button
        self.btn_like = IconButton(size=40, active_color=tokens.CURRENT.like_color)
        self.btn_like.setObjectName("btn_like")
        self.btn_like.setText(Icon.get("favorite"))
        self.btn_like.setFont(Icon.font(25, filled=self._is_liked))
        self.btn_like.setFixedSize(40, 40)
        if self._is_liked:
            self.btn_like.set_active(True)
        self.btn_like.clicked.connect(self._on_like_clicked)
        layout.addWidget(self.btn_like)

        # Play button
        self.btn_play = IconButton(size=40)
        self.btn_play.setObjectName("btn_play")
        self.btn_play.setText(Icon.get("play_arrow"))
        self.btn_play.setFont(Icon.font(27))
        self.btn_play.setFixedSize(40, 40)
        if self._on_play:
            self.btn_play.clicked.connect(self._on_play)
        self.btn_play.setVisible(self._on_play is not None)
        layout.addWidget(self.btn_play)

        # Context menu trigger
        self.menu_btn = QPushButton()
        self.menu_btn.setObjectName("menu_btn")
        self.menu_btn.setText(Icon.get("more_vert"))
        self.menu_btn.setFont(Icon.font(26))
        self.menu_btn.setFixedSize(40, 40)
        self.menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.menu_btn.clicked.connect(self._show_context_menu)
        layout.addWidget(self.menu_btn)

        self._update_card_styles()

    def _update_card_styles(self) -> None:
        if not self.thumbnail.pixmap():
            self.thumbnail.setObjectName("thumbnail_placeholder")
        else:
            self.thumbnail.setObjectName("thumbnail_image")
            
        self.title_label.setProperty("textRole", "primary")
        self.artist_label.setProperty("textRole", "secondary")
        
        if hasattr(self, "duration_label"):
            self.duration_label.setProperty("textRole", "secondary")
        
        self.btn_like.setProperty("liked", "true" if self._is_liked else "false")
        
    def _activate(self) -> None:
        if self._on_play:
            self._on_play()
        self.clicked.emit()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not isinstance(self.childAt(event.pos()), type(self.artist_label)):
                self._activate()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._activate()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Delete and self._video_id:
            self.delete_download_requested.emit(self._video_id)
            event.accept()
            return
        super().keyPressEvent(event)

    def _on_artist_clicked(self):
        # We handle this manually and prevent row selection logic
        self.artist_clicked.emit(self._artist)

    def _on_album_clicked(self):
        if self._album:
            self.album_clicked.emit(self._album)

    def _on_download_clicked(self):
        if self._video_id:
            self.download_requested.emit(
                self._video_id, self._title, self._artist, self._thumbnail_url
            )

    def _on_like_clicked(self):
        if self._video_id:
            self.like_requested.emit(self._video_id, self.btn_like)
        self._is_liked = not self._is_liked

    def _on_play_next_clicked(self):
        if self._video_id:
            self.play_next_requested.emit(
                self._video_id, self._title, self._artist, self._thumbnail_url
            )
            from doremi.ui.widgets.toast import ToastNotification
            ToastNotification.show(self.window(), f"Reproduciendo a continuación: {self._title}", "info")

    def _on_add_to_queue_clicked(self):
        if self._video_id:
            self.add_to_queue_requested.emit(
                self._video_id, self._title, self._artist, self._thumbnail_url
            )
            from doremi.ui.widgets.toast import ToastNotification
            ToastNotification.show(self.window(), f"Añadido a la cola: {self._title}", "info")

    def _on_add_to_playlist_clicked(self):
        if self._video_id:
            self.add_to_playlist_requested.emit(self._video_id, self._title)

    def _on_copy_link_clicked(self):
        if not self._video_id:
            return
        from PySide6.QtWidgets import QApplication
        from doremi.ui.widgets.toast import ToastNotification
        QApplication.clipboard().setText(f"https://music.youtube.com/watch?v={self._video_id}")
        ToastNotification.show(self.window(), "Enlace copiado", "success")

    def _on_delete_download_clicked(self):
        if self._video_id:
            self.delete_download_requested.emit(self._video_id)
            from doremi.ui.widgets.toast import ToastNotification
            ToastNotification.show(self.window(), f"Descarga borrada: {self._title}", "success")

    def _on_remove_from_playlist_clicked(self):
        if self._playlist_id and self._video_id and self._set_video_id:
            self.remove_from_playlist_requested.emit(
                self._playlist_id, self._video_id, self._set_video_id, self._title
            )

    def _show_context_menu(self):
        asyncio.create_task(self._show_context_menu_async())

    async def _show_context_menu_async(self):
        from doremi.db.repository import DownloadRepository
        repo = DownloadRepository()
        existing = await repo.get_download(self._video_id) if self._video_id else None
        is_downloaded = existing is not None
        
        self._current_menu = SongContextMenu(
            parent=self.window(),
            is_downloaded=is_downloaded,
            has_album=bool(self._album),
            can_remove_from_playlist=bool(
                self._playlist_id and self._video_id and self._set_video_id
            ),
        )
        self._current_menu.play_next.connect(self._on_play_next_clicked)
        self._current_menu.add_to_queue.connect(self._on_add_to_queue_clicked)
        self._current_menu.add_to_playlist.connect(self._on_add_to_playlist_clicked)
        self._current_menu.go_to_artist.connect(self._on_artist_clicked)
        self._current_menu.go_to_album.connect(self._on_album_clicked)
        self._current_menu.copy_link.connect(self._on_copy_link_clicked)
        self._current_menu.remove_from_playlist.connect(self._on_remove_from_playlist_clicked)
        
        if is_downloaded:
            self._current_menu.delete_download.connect(self._on_delete_download_clicked)
        else:
            self._current_menu.download.connect(self._on_download_clicked)
            
        self._current_menu._trigger_widget = self.menu_btn
        pos = self.menu_btn.mapToGlobal(self.menu_btn.rect().bottomLeft())
        self._current_menu.popup_at(pos)

    def _get_bg_opacity(self) -> float:
        return self._bg_opacity

    def _set_bg_opacity(self, value: float) -> None:
        self._bg_opacity = value
        self.update()

    bg_opacity = Property(float, _get_bg_opacity, _set_bg_opacity)

    def paintEvent(self, event) -> None:
        from PySide6.QtGui import QPainter, QColor
        from PySide6.QtCore import Qt
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if self._bg_opacity > 0.0:
            accent = tokens.CURRENT.accent
            c = QColor(accent)
            c.setAlphaF(self._bg_opacity * 0.08)
            painter.setBrush(c)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.rect(), 12, 12)
            
        painter.end()
        super().paintEvent(event)

    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._update_card_styles()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)

    def enterEvent(self, event) -> None:
        self._bg_anim.stop()
        self._bg_anim.setStartValue(self._bg_opacity)
        self._bg_anim.setEndValue(1.0)
        self._bg_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._bg_anim.stop()
        self._bg_anim.setStartValue(self._bg_opacity)
        self._bg_anim.setEndValue(0.0)
        self._bg_anim.start()
        super().leaveEvent(event)
