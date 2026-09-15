import asyncio
from pathlib import Path
from loguru import logger
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame, QPushButton, QProgressBar, QGridLayout
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QFont, QPixmap

from doremi.config.paths import AppDirs
from doremi.ui.design.icons import Icon
from doremi.ui.widgets.icon_button import IconButton
from doremi.services.download_manager import DownloadManager
from doremi.db.repository import DownloadRepository
from doremi.ui.widgets.skeleton_loader import SkeletonBlock, SkeletonListLoader


class DownloadItemWidget(QFrame):
    like_requested = Signal(str, object)
    delete_requested = Signal(str)
    play_next_requested = Signal(str, str, str, str)  # video_id, title, artist, thumbnail_url
    add_to_queue_requested = Signal(str, str, str, str)  # video_id, title, artist, thumbnail_url
    add_to_playlist_requested = Signal(str, str)  # video_id, title

    def __init__(self, video_id, title, artist, thumbnail_url, parent_playlist_title=None, on_play_local=None, is_liked=False):
        super().__init__()
        self.video_id = video_id
        self.title = title
        self.artist = artist
        self.thumbnail_url = thumbnail_url
        self.parent_playlist_title = parent_playlist_title
        self.on_play_local = on_play_local
        self.file_path = None
        self._build_ui()
        if self.thumbnail_url:
            asyncio.create_task(self._load_thumbnail(self.thumbnail_url))
        
        # Apply initial like state immediately without spawning a database query task
        self.btn_like.setFont(Icon.font(20, filled=is_liked))
        self.btn_like.set_active(is_liked)
        self._update_item_styles()

    def _build_ui(self):
        self.setObjectName("downloadCard")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        accessible = f"{self.title} - {self.artist}" if self.artist else self.title
        if self.parent_playlist_title:
            accessible = f"{accessible} - {self.parent_playlist_title}"
        self.setAccessibleName(accessible)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Checkbox for selection mode
        self.checkbox = QPushButton()
        self.checkbox.setFixedSize(20, 20)
        self.checkbox.setCheckable(True)
        self.checkbox.setChecked(False)
        self.checkbox.setFont(Icon.font(12))
        self.checkbox.setText("")
        self.checkbox.toggled.connect(lambda checked: self.checkbox.setText(Icon.get("check") if checked else ""))
        self.checkbox.hide()
        layout.addWidget(self.checkbox)
        
        self.thumb = QLabel()
        self.thumb.setFixedSize(48, 48)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setText(Icon.get("music_note"))
        self.thumb.setFont(Icon.font(24))
        layout.addWidget(self.thumb)
        
        info = QVBoxLayout()
        self.title_lbl = QLabel(self.title)
        
        artist_text = self.artist
        if self.parent_playlist_title:
            artist_text += f" • {self.parent_playlist_title}"
        self.artist_lbl = QLabel(artist_text)
        
        info.addWidget(self.title_lbl)
        info.addWidget(self.artist_lbl)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        info.addWidget(self.progress_bar)
        
        layout.addLayout(info)
        layout.addStretch()
        
        self.status_lbl = QLabel("")
        layout.addWidget(self.status_lbl)
        
        # Like button
        from doremi.ui.design import tokens
        self.btn_like = IconButton(size=36, active_color=tokens.CURRENT.like_color)
        self.btn_like.setText(Icon.get("favorite"))
        self.btn_like.setFont(Icon.font(20, filled=False))
        self.btn_like.setFixedSize(36, 36)
        self.btn_like.clicked.connect(self._on_like)
        layout.addWidget(self.btn_like)
        
        self.play_btn = IconButton(size=36)
        self.play_btn.setText(Icon.get("play_arrow"))
        self.play_btn.setFont(Icon.font(20))
        self.play_btn.setFixedSize(36, 36)
        self.play_btn.clicked.connect(self._on_play)
        self.play_btn.hide()
        layout.addWidget(self.play_btn)
        
        # Options menu button
        self.menu_btn = QPushButton()
        self.menu_btn.setObjectName("menu_btn")
        self.menu_btn.setText(Icon.get("more_vert"))
        self.menu_btn.setFont(Icon.font(20))
        self.menu_btn.setFixedSize(36, 36)
        self.menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.menu_btn.clicked.connect(self._show_context_menu)
        self.menu_btn.hide()
        layout.addWidget(self.menu_btn)
        
        self._update_item_styles()

    def _update_item_styles(self) -> None:
        from doremi.ui.design import tokens
        from PySide6.QtGui import QColor
        accent = tokens.CURRENT.accent
        accent_c = QColor(accent)
        acc_r, acc_g, acc_b = accent_c.red(), accent_c.green(), accent_c.blue()
        text_primary = tokens.CURRENT.text_primary
        text_secondary = tokens.CURRENT.text_secondary
        bg_surface = tokens.CURRENT.bg_surface
        bg_elevated = tokens.CURRENT.bg_elevated
        bg_high = tokens.CURRENT.bg_high
        border = tokens.CURRENT.border
        text_on_accent = tokens.CURRENT.text_on_accent
        
        like_c = QColor(tokens.CURRENT.like_color)
        like_r, like_g, like_b = like_c.red(), like_c.green(), like_c.blue()
        
        self.setStyleSheet(f"""
            QFrame#downloadCard {{
                background-color: {bg_surface};
                border-radius: 12px;
                border: 1px solid {border};
            }}
            QFrame#downloadCard:hover {{
                background-color: {bg_elevated};
            }}
        """)
        
        if not self.thumb.pixmap():
            self.thumb.setStyleSheet(f"background-color: {bg_high}; color: {text_secondary}; border-radius: 6px;")
        else:
            self.thumb.setStyleSheet("background: transparent; border-radius: 6px;")
            
        self.title_lbl.setStyleSheet(f"color: {text_primary}; font-weight: 600; font-size: 14px; background: transparent; border: none;")
        self.artist_lbl.setStyleSheet(f"color: {text_secondary}; font-size: 12px; background: transparent; border: none;")
        self.status_lbl.setStyleSheet(f"color: {text_secondary}; font-size: 12px; background: transparent; border: none;")
        
        self.checkbox.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 2px solid {border};
                border-radius: 10px;
                color: {text_primary};
                font-family: 'Material Symbols Rounded';
                font-size: 12px;
            }}
            QPushButton:checked {{
                background-color: {accent};
                border-color: {accent};
                color: {text_on_accent};
            }}
        """)
        
        is_liked = getattr(self.btn_like, '_active', False)
        if is_liked:
            self.btn_like.setStyleSheet(f"QPushButton {{ color: {tokens.CURRENT.like_color}; background: transparent; border: none; }}")
        else:
            self.btn_like.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {text_secondary};
                    border: none;
                    border-radius: 18px;
                }}
                QPushButton:hover {{
                    background-color: rgba({like_r},{like_g},{like_b},0.15);
                    color: {tokens.CURRENT.like_color};
                }}
            """)
            
        self.play_btn.setStyleSheet(f"background: transparent; color: {text_primary}; border: none;")
        if hasattr(self, 'menu_btn'):
            self.menu_btn.setStyleSheet(f"""
                QPushButton#menu_btn {{
                    background-color: transparent;
                    color: {text_secondary};
                    border: none;
                    border-radius: 18px;
                    font-family: 'Material Symbols Rounded';
                    font-size: 20px;
                }}
                QPushButton#menu_btn:hover {{
                    background-color: rgba({acc_r}, {acc_g}, {acc_b}, 0.15);
                    color: {accent};
                }}
            """)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{ background: {bg_high}; border-radius: 2px; }}
            QProgressBar::chunk {{ background: {accent}; border-radius: 2px; }}
        """)

    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._update_item_styles()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)

    def _on_like(self):
        self.like_requested.emit(self.video_id, self.btn_like)

    async def _check_like_state(self):
        try:
            from doremi.db.repository import SongRepository
            repo = SongRepository()
            song = await repo.get_song(self.video_id)
            is_liked = song.is_liked if song else False
            
            import shiboken6
            if not shiboken6.isValid(self) or not hasattr(self, 'btn_like') or not shiboken6.isValid(self.btn_like):
                return
                
            # Apply initial style
            self.btn_like.setFont(Icon.font(20, filled=is_liked))
            self.btn_like.set_active(is_liked)
            self._update_item_styles()
        except RuntimeError:
            pass # C++ object deleted during await
        except Exception as e:
            logger.error(f"Error checking like state for {self.video_id}: {e}")

    def set_downloading(self):
        self.progress_bar.show()
        self.status_lbl.setText("Descargando...")
        self.play_btn.hide()
        self.menu_btn.hide()

    def update_progress(self, percent, speed):
        self.progress_bar.setValue(int(percent))
        self.status_lbl.setText(f"{percent}% • {speed}")

    def set_completed(self, filepath):
        self.file_path = filepath
        self.progress_bar.hide()
        self.status_lbl.setText("Completado")
        self.status_lbl.hide()
        self.play_btn.show()
        self.menu_btn.show()

    def set_error(self, msg):
        from doremi.ui.design import tokens
        self.progress_bar.hide()
        self.status_lbl.setText("Error")
        self.status_lbl.setStyleSheet(f"color: {tokens.CURRENT.error}; font-size: 12px; background: transparent; border: none;")
        self.play_btn.hide()
        self.menu_btn.show()

    def _on_play(self):
        if self.file_path and self.on_play_local:
            metadata = {
                "video_id": self.video_id,
                "title": self.title,
                "artist": self.artist,
                "thumbnail_url": self.thumbnail_url
            }
            self.on_play_local(self.file_path, metadata)

    def _on_delete(self):
        self.delete_requested.emit(self.video_id)

    def _on_play_next_clicked(self):
        if self.video_id:
            self.play_next_requested.emit(
                self.video_id, self.title, self.artist, self.thumbnail_url
            )

    def _on_add_to_queue_clicked(self):
        if self.video_id:
            self.add_to_queue_requested.emit(
                self.video_id, self.title, self.artist, self.thumbnail_url
            )

    def _on_add_to_playlist_clicked(self):
        if self.video_id:
            self.add_to_playlist_requested.emit(self.video_id, self.title)

    def _show_context_menu(self):
        from doremi.ui.widgets.song_context_menu import SongContextMenu
        self._current_menu = SongContextMenu(parent=self.window(), is_downloaded=True)
        self._current_menu.play_next.connect(self._on_play_next_clicked)
        self._current_menu.add_to_queue.connect(self._on_add_to_queue_clicked)
        self._current_menu.add_to_playlist.connect(self._on_add_to_playlist_clicked)
        self._current_menu.delete_download.connect(self._on_delete)
        
        self._current_menu._trigger_widget = self.menu_btn
        pos = self.menu_btn.mapToGlobal(self.menu_btn.rect().bottomLeft())
        self._current_menu.popup_at(pos)

    async def _load_thumbnail(self, url: str):
        from doremi.utils.image_cache import ImageCache
        cache = ImageCache()
        path = await cache.download(url)
        import shiboken6
        if not shiboken6.isValid(self):
            return
        if path:
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                pixmap = pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                self.thumb.setPixmap(pixmap)
                self._update_item_styles()

    def set_selection_mode(self, enabled: bool):
        self.selection_mode = enabled
        if enabled:
            self.checkbox.show()
            self.btn_like.hide()
            self.play_btn.hide()
            self.menu_btn.hide()
        else:
            self.checkbox.hide()
            self.checkbox.setChecked(False)
            self.btn_like.show()
            if self.file_path:
                self.play_btn.show()
                self.menu_btn.show()

    def mousePressEvent(self, event) -> None:
        if getattr(self, "selection_mode", False):
            self.checkbox.setChecked(not self.checkbox.isChecked())
            event.accept()
        else:
            super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Delete:
            self._on_delete()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if getattr(self, "selection_mode", False):
                self.checkbox.setChecked(not self.checkbox.isChecked())
            else:
                self._on_play()
            event.accept()
            return
        super().keyPressEvent(event)

class DownloadPlaylistItemWidget(QFrame):
    def __init__(self, playlist_id, title, tracks, on_play_local=None, on_play_local_playlist=None, liked_ids=None):
        super().__init__()
        self.playlist_id = playlist_id
        self.title = title
        self.tracks = tracks
        self.on_play_local = on_play_local
        self.on_play_local_playlist = on_play_local_playlist
        self.liked_ids = liked_ids
        self.is_expanded = False
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("playlistCard")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header Widget (contains thumbnail, title, stats, play and expand buttons)
        self.header = QFrame()
        self.header.setObjectName("playlistHeader")
        self.header.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.header.setAccessibleName(f"Expandir {self.title}")
        
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(12, 12, 12, 12)
        
        # Thumbnail
        self.thumb = QLabel()
        self.thumb.setFixedSize(64, 64)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setText(Icon.get("library_music"))
        self.thumb.setFont(Icon.font(32))
        header_layout.addWidget(self.thumb)
        
        # Metadata Info
        info_layout = QVBoxLayout()
        self.title_lbl = QLabel(self.title)
        
        count = len(self.tracks)
        tracks_text = f"1 canción" if count == 1 else f"{count} canciones"
        self.stats_lbl = QLabel(f"Playlist Offline • {tracks_text}")
        
        info_layout.addWidget(self.title_lbl)
        info_layout.addWidget(self.stats_lbl)
        header_layout.addLayout(info_layout)
        header_layout.addStretch()
        
        # Play Playlist Button
        self.play_btn = IconButton(size=40)
        self.play_btn.setText(Icon.get("play_arrow"))
        self.play_btn.setFont(Icon.font(24))
        self.play_btn.setFixedSize(40, 40)
        self.play_btn.clicked.connect(self._on_play_all)
        header_layout.addWidget(self.play_btn)
        
        # Expand/Collapse Arrow
        self.expand_btn = IconButton(size=40)
        self.expand_btn.setText(Icon.get("chevron_right"))
        self.expand_btn.setFont(Icon.font(24))
        self.expand_btn.setFixedSize(40, 40)
        self.expand_btn.clicked.connect(self.toggle_expand)
        header_layout.addWidget(self.expand_btn)
        
        main_layout.addWidget(self.header)
        
        # Contenedor para las canciones (colapsable)
        self.tracks_container = QFrame()
        self.tracks_container.setObjectName("tracksContainer")
        
        container_layout = QVBoxLayout(self.tracks_container)
        container_layout.setContentsMargins(12, 8, 12, 12)
        container_layout.setSpacing(6)
        
        # Agregar los widgets de canciones individuales dentro de la playlist agrupada
        for t in self.tracks:
            is_liked = False
            if self.liked_ids and t.video_id in self.liked_ids:
                is_liked = True
            widget = DownloadItemWidget(
                video_id=t.video_id,
                title=t.title,
                artist=t.artist,
                thumbnail_url=t.thumbnail_url,
                parent_playlist_title=None,
                on_play_local=self.on_play_local,
                is_liked=is_liked
            )
            widget.set_completed(t.file_path)
            # Make the card style slightly more compact inside the group
            widget.setStyleSheet("QFrame#downloadCard { border-radius: 8px; }")
            container_layout.addWidget(widget)
            
        self.tracks_container.hide()
        main_layout.addWidget(self.tracks_container)
        
        # Permitir expandir haciendo clic en toda la cabecera (excepto si pulsas botones).
        self.header.installEventFilter(self)
        
        self._update_playlist_item_styles()
        
        # Cargar miniatura de la primera canción si está disponible
        if self.tracks and self.tracks[0].thumbnail_url:
            import asyncio
            asyncio.create_task(self._load_thumbnail(self.tracks[0].thumbnail_url))

    def _update_playlist_item_styles(self) -> None:
        from doremi.ui.design import tokens
        accent = tokens.CURRENT.accent
        text_primary = tokens.CURRENT.text_primary
        text_secondary = tokens.CURRENT.text_secondary
        bg_surface = tokens.CURRENT.bg_surface
        bg_elevated = tokens.CURRENT.bg_elevated
        bg_high = tokens.CURRENT.bg_high
        border = tokens.CURRENT.border
        
        self.setStyleSheet(f"""
            QFrame#playlistCard {{
                background-color: {bg_surface};
                border-radius: 12px;
                border: 1px solid {border};
            }}
        """)
        
        radius_style = "border-radius: 12px;" if not self.is_expanded else "border-top-left-radius: 12px; border-top-right-radius: 12px; border-bottom-left-radius: 0px; border-bottom-right-radius: 0px;"
        
        self.header.setStyleSheet(f"""
            QFrame#playlistHeader {{
                background-color: transparent;
                {radius_style}
            }}
            QFrame#playlistHeader:hover {{
                background-color: {bg_elevated};
            }}
        """)
        
        from PySide6.QtGui import QColor
        c = QColor(accent)
        r, g, b = c.red(), c.green(), c.blue()
        
        if not self.thumb.pixmap():
            self.thumb.setStyleSheet(f"background: {bg_high}; border-radius: 8px;")
        else:
            self.thumb.setStyleSheet("background: transparent; border-radius: 8px;")
            
        self.title_lbl.setStyleSheet(f"color: {text_primary}; font-weight: 600; font-size: 16px; background: transparent; border: none;")
        self.stats_lbl.setStyleSheet(f"color: {text_secondary}; font-size: 12px; background: transparent; border: none;")
        
        self.play_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba({r}, {g}, {b}, 0.12); 
                color: {accent}; 
                border: none;
                border-radius: 20px;
            }}
            QPushButton:hover {{
                background: rgba({r}, {g}, {b}, 0.25);
            }}
        """)
        
        self.expand_btn.setStyleSheet(f"background: transparent; color: {text_secondary}; border: none;")
        
        self.tracks_container.setStyleSheet(f"""
            QFrame#tracksContainer {{
                background-color: {bg_elevated};
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
                border-top: 1px solid {border};
            }}
        """)

    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._update_playlist_item_styles()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)

    def eventFilter(self, obj, event) -> bool:
        from PySide6.QtCore import QEvent
        if obj is self.header and event.type() == QEvent.Type.MouseButtonPress:
            return self._handle_header_activation(event.position().toPoint())
        if obj is self.header and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                self.toggle_expand()
                event.accept()
                return True
        return super().eventFilter(obj, event)

    def _handle_header_activation(self, pos) -> bool:
        child = self.header.childAt(pos)
        if child in [self.play_btn, self.expand_btn] or (child and child.parent() in [self.play_btn, self.expand_btn]):
            return False
        self.toggle_expand()
        return True

    def toggle_expand(self):
        self.is_expanded = not self.is_expanded
        if self.is_expanded:
            self.tracks_container.show()
            self.expand_btn.setText(Icon.get("expand_more"))
        else:
            self.tracks_container.hide()
            self.expand_btn.setText(Icon.get("chevron_right"))
        self._update_playlist_item_styles()

    def _on_play_all(self):
        if self.tracks and self.on_play_local_playlist:
            tracks_meta = []
            for t in self.tracks:
                tracks_meta.append({
                    "video_id": t.video_id,
                    "title": t.title,
                    "artist": t.artist,
                    "thumbnail_url": t.thumbnail_url,
                    "file_path": t.file_path,
                    "duration_ms": t.duration_ms
                })
            self.on_play_local_playlist(tracks_meta, 0)

    async def _load_thumbnail(self, url: str):
        from doremi.utils.image_cache import ImageCache
        cache = ImageCache()
        path = await cache.download(url)
        import shiboken6
        if not shiboken6.isValid(self):
            return
        if path:
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                pixmap = pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                self.thumb.setPixmap(pixmap)
                self._update_playlist_item_styles()

class SkeletonGridLoader(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        grid = QGridLayout(self)
        grid.setSpacing(24)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        
        columns = 4
        for i in range(4):
            card = QWidget()
            from doremi.ui.design import tokens
            card.setStyleSheet(f"""
                QWidget {{
                    background-color: {tokens.CURRENT.bg_surface};
                    border-radius: 12px;
                    border: 1px solid {tokens.CURRENT.border};
                }}
            """)
            card.setFixedSize(168, 218)
            lay = QVBoxLayout(card)
            lay.setContentsMargins(10, 10, 10, 10)
            lay.setSpacing(8)
            
            # Thumbnail block
            lay.addWidget(SkeletonBlock(148, 148, 12))
            # Title block
            lay.addWidget(SkeletonBlock(120, 12, 6))
            # Description block
            lay.addWidget(SkeletonBlock(80, 10, 5))
            
            row = i // columns
            col = i % columns
            grid.addWidget(card, row, col)

class DownloadsScreen(QWidget):
    like_requested = Signal(str, object)
    delete_download_requested = Signal(str)
    play_next_requested = Signal(str, str, str, str)  # video_id, title, artist, thumbnail_url
    add_to_queue_requested = Signal(str, str, str, str)  # video_id, title, artist, thumbnail_url
    add_to_playlist_requested = Signal(str, str) # video_id, title

    def __init__(self, extractor, on_play_local, on_play_local_playlist=None, on_navigate=None):
        super().__init__()
        self.extractor = extractor
        self.on_play_local = on_play_local
        self.on_play_local_playlist = on_play_local_playlist
        self.on_navigate = on_navigate
        self._current_tab = "songs"
        self._status_filter = "all"
        self._selection_mode = False
        self._items = {} # video_id -> DownloadItemWidget
        self._playlist_cards = {} # playlist_id -> PlaylistCard
        self._repo = DownloadRepository()
        self._current_load_task = None
        self._build_ui()
        self._connect_manager()


    def _build_ui(self):
        from doremi.ui.design.fonts import AppFont
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(20)

        from doremi.ui.design import tokens
        
        # Header Row
        self.header_row = QWidget()
        self.header_row.setStyleSheet("background: transparent; border: none;")
        header_row_layout = QHBoxLayout(self.header_row)
        header_row_layout.setContentsMargins(0, 0, 0, 0)
        
        self.header = QLabel("Descargas")
        self.header.setFont(QFont("Inter", 24, QFont.Weight.Bold))
        self.header.setStyleSheet(f"")
        header_row_layout.addWidget(self.header)
        header_row_layout.addStretch()
        
        # Action Toolbar (Selection Mode actions)
        self.selection_toolbar = QWidget()
        self.selection_toolbar_layout = QHBoxLayout(self.selection_toolbar)
        self.selection_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self.selection_toolbar_layout.setSpacing(10)
        
        self.btn_select_all = QPushButton("Seleccionar Todo")
        self.btn_select_all.setFont(AppFont.body(12))
        self.btn_select_all.setFixedHeight(34)
        self.btn_select_all.clicked.connect(self._select_all_items)
        self.selection_toolbar_layout.addWidget(self.btn_select_all)
        
        self.btn_delete_selected = QPushButton("Borrar Seleccionados")
        self.btn_delete_selected.setFont(AppFont.body(12))
        self.btn_delete_selected.setFixedHeight(34)
        self.btn_delete_selected.clicked.connect(self._delete_selected_items)
        self.selection_toolbar_layout.addWidget(self.btn_delete_selected)
        
        self.btn_delete_all = QPushButton("Borrar Todo")
        self.btn_delete_all.setFont(AppFont.body(12))
        self.btn_delete_all.setFixedHeight(34)
        self.btn_delete_all.clicked.connect(self._delete_all_items)
        self.selection_toolbar_layout.addWidget(self.btn_delete_all)
        
        self.selection_toolbar.hide()
        header_row_layout.addWidget(self.selection_toolbar)
        
        # Main action button (Enter/Exit selection)
        self.btn_select = QPushButton("Seleccionar")
        self.btn_select.setFont(AppFont.body(12))
        self.btn_select.setFixedHeight(34)
        self.btn_select.clicked.connect(self._toggle_selection_mode)
        header_row_layout.addWidget(self.btn_select)
        
        layout.addWidget(self.header_row)

        # Tabs
        self.tabs = QWidget()
        self.tabs.setStyleSheet("background: transparent; border: none;")
        tabs_layout = QHBoxLayout(self.tabs)
        tabs_layout.setSpacing(16)
        
        tab_names = [
            ("songs", "Canciones"),
            ("albums", "Álbumes"),
            ("playlists", "Playlists Completas")
        ]
        
        self.tab_btns = {}
        for key, name in tab_names:
            btn = QPushButton(name)
            btn.setObjectName(f"tab_{key}")
            btn.setStyleSheet(self._tab_style(key == self._current_tab))
            btn.clicked.connect(lambda _, k=key: self._switch_tab(k))
            tabs_layout.addWidget(btn)
            self.tab_btns[key] = btn
        
        tabs_layout.addStretch()
        layout.addWidget(self.tabs)

        self.status_filters = QWidget()
        self.status_filters.setStyleSheet("background: transparent; border: none;")
        status_layout = QHBoxLayout(self.status_filters)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(8)
        self.status_filter_btns = {}
        for key, label in (
            ("all", "Todas"),
            ("completed", "Completadas"),
            ("active", "En curso"),
            ("error", "Errores"),
        ):
            btn = QPushButton(label)
            btn.setFixedHeight(30)
            btn.clicked.connect(lambda _checked=False, k=key: self._switch_status_filter(k))
            status_layout.addWidget(btn)
            self.status_filter_btns[key] = btn
        status_layout.addStretch()
        layout.addWidget(self.status_filters)
        
        self._update_toolbar_styles()

        self.content_area = QScrollArea()
        self.content_area.setWidgetResizable(True)
        self.content_area.setStyleSheet("background: transparent; border: none;")
        
        self.scroll_content = QWidget()
        self._content_wrapper_layout = QVBoxLayout(self.scroll_content)
        self._content_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(16)
        self.content_layout.setContentsMargins(0, 16, 0, 112)
        
        self._content_wrapper_layout.addLayout(self.content_layout)
        self._content_wrapper_layout.addStretch()
        
        self.content_area.setWidget(self.scroll_content)
        layout.addWidget(self.content_area)

    def _tab_style(self, active: bool):
        from doremi.ui.design import tokens
        accent = tokens.CURRENT.accent
        accent_dim = tokens.CURRENT.accent_dim
        text_primary = tokens.CURRENT.text_primary
        text_secondary = tokens.CURRENT.text_secondary
        bg_elevated = tokens.CURRENT.bg_elevated
        if active:
            return f"""
                QPushButton {{
                    background: {accent_dim};
                    color: {accent};
                    padding: 8px 16px;
                    border-radius: 20px;
                    font-weight: bold;
                    border: none;
                }}
            """
        return f"""
            QPushButton {{
                background: transparent;
                color: {text_secondary};
                padding: 8px 16px;
                border: none;
                border-radius: 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {bg_elevated};
                color: {text_primary};
            }}
        """

    def _switch_tab(self, key):
        if getattr(self, "_selection_mode", False):
            self._toggle_selection_mode()
        self._current_tab = key
        for k, btn in self.tab_btns.items():
            btn.setStyleSheet(self._tab_style(k == key))
        self.status_filters.setVisible(key == "songs")
            
        if self._current_load_task and not self._current_load_task.done():
            self._current_load_task.cancel()
        self._current_load_task = asyncio.create_task(self.load())

    def _switch_status_filter(self, key: str) -> None:
        if key == self._status_filter:
            return
        self._status_filter = key
        self._update_status_filter_styles()
        if getattr(self, "_selection_mode", False):
            self._toggle_selection_mode()
        if self._current_load_task and not self._current_load_task.done():
            self._current_load_task.cancel()
        self._current_load_task = asyncio.create_task(self.load())

    def _task_matches_filter(self, status: str) -> bool:
        if self._status_filter == "all":
            return True
        if self._status_filter == "active":
            return status in {"queued", "downloading", "paused"}
        if self._status_filter == "error":
            return status == "error"
        return False

    def _download_matches_filter(self) -> bool:
        return self._status_filter in {"all", "completed"}

    def _connect_manager(self):
        mgr = DownloadManager.get_instance()
        mgr.download_queued.connect(self._on_download_queued)
        mgr.download_started.connect(self._on_download_started)
        mgr.download_progress.connect(self._on_download_progress)
        mgr.download_completed.connect(self._on_download_completed)
        mgr.download_error.connect(self._on_download_error)

    def _on_download_queued(self, task):
        # Add to UI if matches current tab
        is_playlist = task.parent_playlist_id is not None
        if (
            ((self._current_tab == "playlists" and is_playlist) or (self._current_tab == "songs" and not is_playlist))
            and (self._current_tab != "songs" or self._task_matches_filter(task.status))
        ):
            self._add_item_to_ui(task.video_id, task.title, task.artist, task.thumbnail_url, task.parent_playlist_title)
            self._items[task.video_id].set_downloading()

    def _on_download_started(self, video_id):
        if video_id in self._items:
            self._items[video_id].set_downloading()

    def _on_download_progress(self, video_id, percent, speed):
        if video_id in self._items:
            self._items[video_id].update_progress(percent, speed)

    def _on_download_completed(self, video_id, filepath):
        if video_id in self._items:
            self._items[video_id].set_completed(filepath)

    def _on_download_error(self, video_id, error_msg):
        if video_id in self._items:
            self._items[video_id].set_error(error_msg)

    def _add_item_to_ui(self, vid, title, artist, thumb_url, parent_playlist_title=None, is_liked=False):
        if vid in self._items:
            return
        widget = DownloadItemWidget(vid, title, artist, thumb_url, parent_playlist_title, self.on_play_local, is_liked=is_liked)
        widget.like_requested.connect(self.like_requested.emit)
        widget.delete_requested.connect(self.delete_download_requested.emit)
        widget.play_next_requested.connect(self.play_next_requested.emit)
        widget.add_to_queue_requested.connect(self.add_to_queue_requested.emit)
        widget.add_to_playlist_requested.connect(self.add_to_playlist_requested.emit)
        widget.checkbox.toggled.connect(self._update_selected_count)
        widget.set_selection_mode(getattr(self, "_selection_mode", False))
        self.content_layout.insertWidget(0, widget)
        self._items[vid] = widget

    async def load(self):
        current_task = asyncio.current_task()
        if self._current_load_task and self._current_load_task != current_task and not self._current_load_task.done():
            self._current_load_task.cancel()
        
        self._current_load_task = current_task
        
        try:
            # Clear current content immediately to show loading state
            while self.content_layout.count() > 0:
                item = self.content_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self._items.clear()
            self._playlist_cards.clear()

            # Show skeleton loader instantly
            if self._current_tab == "songs":
                skeleton = SkeletonListLoader(row_count=8)
            else:
                skeleton = SkeletonGridLoader()
            self.content_layout.addWidget(skeleton)

            # Briefly yield to the event loop so the skeleton renders immediately
            await asyncio.sleep(0.01)

            downloads = await self._repo.get_downloads()
            
            from doremi.db.repository import SongRepository
            song_repo = SongRepository()
            liked_ids = await song_repo.get_liked_video_ids()
            
            # Check for cancellation before constructing widgets
            if current_task.cancelled():
                return

            # Remove the skeleton loader
            skeleton.deleteLater()
            while self.content_layout.count() > 0:
                item = self.content_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            if self._current_tab == "playlists" or self._current_tab == "albums":
                # Group downloaded items by parent_playlist_id
                playlist_groups = {}
                for d in downloads:
                    if d.parent_playlist_id:
                        pid = d.parent_playlist_id
                        # Filter by tab type
                        is_album = pid.startswith("album_")
                        if (self._current_tab == "albums" and not is_album) or (self._current_tab == "playlists" and is_album):
                            continue
                        if pid not in playlist_groups:
                            playlist_groups[pid] = {
                                "title": d.parent_playlist_title or ("Album Local" if is_album else "Playlist Local"),
                                "tracks": []
                            }
                        playlist_groups[pid]["tracks"].append(d)
                
                if not playlist_groups:
                    from doremi.ui.design import tokens
                    empty_text = "No hay álbumes descargados." if self._current_tab == "albums" else "No hay playlists descargadas."
                    msg = QLabel(empty_text)
                    msg.setStyleSheet(f" font-size: 16px; padding: 40px;")
                    msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.content_layout.insertWidget(0, msg)
                else:
                    from doremi.ui.widgets.playlist_card import PlaylistCard
                    grid_widget = QWidget()
                    grid_layout = QGridLayout(grid_widget)
                    grid_layout.setSpacing(24)
                    grid_layout.setContentsMargins(0, 0, 0, 0)
                    grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                    
                    columns = 4
                    for index, (pid, info) in enumerate(playlist_groups.items()):
                        row = index // columns
                        col = index % columns
                        
                        tracks = info["tracks"]
                        item_thumb = ""
                        if tracks:
                            item_thumb = getattr(tracks[0], "parent_playlist_thumbnail_url", "") or tracks[0].thumbnail_url
                        
                        card = PlaylistCard(
                            title=info["title"],
                            description=f"{len(tracks)} canciones",
                            thumbnail_url=item_thumb
                        )
                        card.checkbox.toggled.connect(self._update_selected_count)
                        card.set_selection_mode(getattr(self, "_selection_mode", False))
                        self._playlist_cards[pid] = card
                        if self.on_navigate:
                            if pid.startswith("album_"):
                                card.clicked.connect(lambda p=pid: self.on_navigate(f"album?id={p.replace('album_', '')}"))
                            else:
                                card.clicked.connect(lambda p=pid: self.on_navigate(f"playlist?id=local_{p}"))
                                
                        grid_layout.addWidget(card, row, col)
                    
                    self.content_layout.insertWidget(0, grid_widget)
            else:
                # "songs" tab: Show all downloads individually (both completed and active)
                shown_count = 0
                completed_downloads = list(reversed(downloads)) if self._download_matches_filter() else []
                active_tasks = []
                mgr = DownloadManager.get_instance()
                for vid, task in mgr._tasks.items():
                    if self._task_matches_filter(task.status):
                        active_tasks.append((vid, task))

                if not completed_downloads and not active_tasks:
                    from doremi.ui.design import tokens as _t
                    empty_by_filter = {
                        "completed": "No hay descargas completadas.",
                        "active": "No hay descargas en curso.",
                        "error": "No hay descargas con error.",
                    }
                    msg = QLabel(empty_by_filter.get(self._status_filter, "No hay descargas aqui."))
                    msg.setStyleSheet(f"color: {_t.CURRENT.text_secondary}; font-size: 16px; padding: 40px;")
                    msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.content_layout.insertWidget(0, msg)
                
                for i, d in enumerate(completed_downloads):
                    is_liked = d.video_id in liked_ids
                    self._add_item_to_ui(d.video_id, d.title, d.artist, d.thumbnail_url, d.parent_playlist_title, is_liked=is_liked)
                    if d.video_id in self._items:
                        self._items[d.video_id].set_completed(d.file_path)
                        shown_count += 1
                    
                # Add active downloads from manager
                for i, (vid, task) in enumerate(active_tasks):
                    if vid not in self._items:
                        is_liked = vid in liked_ids
                        self._add_item_to_ui(task.video_id, task.title, task.artist, task.thumbnail_url, task.parent_playlist_title, is_liked=is_liked)
                        if task.status == "downloading":
                            self._items[vid].set_downloading()
                        elif task.status == "error":
                            self._items[vid].set_error("Error")
                        else:
                            self._items[vid].set_downloading()
                        shown_count += 1
            
            # Animate content fading in beautifully!
            self._fade_in_content()
            
        except asyncio.CancelledError:
            raise

    def _update_toolbar_styles(self) -> None:
        from doremi.ui.design import tokens
        from PySide6.QtGui import QColor
        accent = tokens.CURRENT.accent
        accent_dim = tokens.CURRENT.accent_dim
        text_primary = tokens.CURRENT.text_primary
        bg_elevated = tokens.CURRENT.bg_elevated
        bg_surface = tokens.CURRENT.bg_surface
        border = tokens.CURRENT.border
        
        err_c = QColor(tokens.CURRENT.error)
        err_r, err_g, err_b = err_c.red(), err_c.green(), err_c.blue()
        
        acc_c = QColor(accent)
        acc_r, acc_g, acc_b = acc_c.red(), acc_c.green(), acc_c.blue()
        
        btn_style = f"""
            QPushButton {{
                background-color: {bg_surface};
                color: {text_primary};
                border: 1px solid {border};
                border-radius: 17px;
                padding: 0 16px;
            }}
            QPushButton:hover {{
                background-color: {bg_elevated};
                border-color: rgba({acc_r}, {acc_g}, {acc_b}, 0.33);
            }}
        """
        
        accent_btn_style = f"""
            QPushButton {{
                background-color: {accent_dim};
                color: {accent};
                border: 1px solid rgba({acc_r}, {acc_g}, {acc_b}, 0.20);
                border-radius: 17px;
                padding: 0 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: rgba({acc_r}, {acc_g}, {acc_b}, 0.13);
            }}
        """
        
        delete_btn_style = f"""
            QPushButton {{
                background-color: rgba({err_r}, {err_g}, {err_b}, 0.1);
                color: {tokens.CURRENT.error};
                border: 1px solid rgba({err_r}, {err_g}, {err_b}, 0.3);
                border-radius: 17px;
                padding: 0 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: rgba({err_r}, {err_g}, {err_b}, 0.2);
            }}
        """
        
        self.btn_select.setStyleSheet(btn_style if not getattr(self, "_selection_mode", False) else accent_btn_style)
        self.btn_select_all.setStyleSheet(btn_style)
        self.btn_delete_selected.setStyleSheet(delete_btn_style)
        self.btn_delete_all.setStyleSheet(delete_btn_style)
        self._update_status_filter_styles()

    def _update_status_filter_styles(self) -> None:
        if not hasattr(self, "status_filter_btns"):
            return
        from doremi.ui.design import tokens
        active_style = f"""
            QPushButton {{
                background: {tokens.CURRENT.accent_dim};
                color: {tokens.CURRENT.accent};
                border: 1px solid {tokens.CURRENT.accent};
                border-radius: 15px;
                padding: 0 12px;
                font-weight: 700;
            }}
        """
        inactive_style = f"""
            QPushButton {{
                background: transparent;
                color: {tokens.CURRENT.text_secondary};
                border: 1px solid {tokens.CURRENT.border};
                border-radius: 15px;
                padding: 0 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {tokens.CURRENT.bg_elevated};
                color: {tokens.CURRENT.text_primary};
            }}
        """
        for key, btn in self.status_filter_btns.items():
            btn.setStyleSheet(active_style if key == self._status_filter else inactive_style)

    def _toggle_selection_mode(self) -> None:
        self._selection_mode = not getattr(self, "_selection_mode", False)
        
        if self._selection_mode:
            self.btn_select.setText("Cancelar")
            self.selection_toolbar.show()
            self._update_selected_count()
        else:
            self.btn_select.setText("Seleccionar")
            self.selection_toolbar.hide()
            
            if self._current_tab == "songs":
                for vid, widget in self._items.items():
                    widget.checkbox.setChecked(False)
            elif self._current_tab == "playlists":
                for pid, card in getattr(self, "_playlist_cards", {}).items():
                    card.checkbox.setChecked(False)
                    
        self._update_toolbar_styles()
        
        if self._current_tab == "songs":
            for vid, widget in self._items.items():
                widget.set_selection_mode(self._selection_mode)
        elif self._current_tab in ("playlists", "albums"):
            for pid, card in getattr(self, "_playlist_cards", {}).items():
                card.set_selection_mode(self._selection_mode)

    def _update_selected_count(self) -> None:
        count = 0
        if self._current_tab == "songs":
            for vid, widget in self._items.items():
                if widget.checkbox.isChecked():
                    count += 1
        elif self._current_tab in ("playlists", "albums"):
            for pid, card in getattr(self, "_playlist_cards", {}).items():
                if card.checkbox.isChecked():
                    count += 1
        
        self.btn_delete_selected.setText(f"Borrar Seleccionados ({count})")

    def _select_all_items(self) -> None:
        all_checked = True
        if self._current_tab == "songs":
            for vid, widget in self._items.items():
                if not widget.checkbox.isChecked():
                    all_checked = False
                    break
            for vid, widget in self._items.items():
                widget.checkbox.setChecked(not all_checked)
        elif self._current_tab in ("playlists", "albums"):
            for pid, card in getattr(self, "_playlist_cards", {}).items():
                if not card.checkbox.isChecked():
                    all_checked = False
                    break
            for pid, card in getattr(self, "_playlist_cards", {}).items():
                card.checkbox.setChecked(not all_checked)

    def _delete_selected_items(self) -> None:
        selected_ids = []
        if self._current_tab == "songs":
            for vid, widget in self._items.items():
                if widget.checkbox.isChecked():
                    selected_ids.append(vid)
        elif self._current_tab in ("playlists", "albums"):
            for pid, card in getattr(self, "_playlist_cards", {}).items():
                if card.checkbox.isChecked():
                    selected_ids.append(pid)
                    
        if not selected_ids:
            return
            
        from PySide6.QtWidgets import QMessageBox
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Confirmar Eliminación")
        if self._current_tab == "songs":
            msg_box.setText(f"¿Estás seguro de que deseas eliminar las {len(selected_ids)} descargas seleccionadas?")
        elif self._current_tab == "albums":
            msg_box.setText(f"¿Estás seguro de que deseas eliminar los {len(selected_ids)} álbumes seleccionados junto con todas sus canciones descargadas?")
        else:
            msg_box.setText(f"¿Estás seguro de que deseas eliminar las {len(selected_ids)} playlists seleccionadas junto con todas sus canciones descargadas?")
            
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        
        from doremi.ui.design import tokens
        msg_box.setStyleSheet(f"""
            QMessageBox {{
                background-color: {tokens.CURRENT.bg_surface};
                
            }}
            QLabel {{
                
            }}
            QPushButton {{
                background-color: {tokens.CURRENT.bg_elevated};
                
                border: 1px solid {tokens.CURRENT.border};
                border-radius: 6px;
                padding: 6px 16px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {tokens.CURRENT.accent_dim};
                color: {tokens.CURRENT.accent};
            }}
        """)
        
        if msg_box.exec() == QMessageBox.StandardButton.Yes:
            asyncio.ensure_future(self._delete_items_async(selected_ids))

    async def _delete_items_async(self, ids: list[str]) -> None:
        self._toggle_selection_mode()

        downloads = await self._repo.get_downloads()
        if self._current_tab == "songs":
            target_ids = set(ids)
        else:
            target_ids = {
                d.video_id
                for d in downloads
                if d.parent_playlist_id in ids
            }

        targets = [d for d in downloads if d.video_id in target_ids]
        for download in targets:
            if not download.file_path:
                continue
            try:
                path = Path(download.file_path)
                if path.exists():
                    path.unlink()
                lrc_path = path.with_suffix(".lrc")
                if lrc_path.exists():
                    lrc_path.unlink()
            except Exception as e:
                logger.error(f"Error deleting file {download.file_path}: {e}")

        await self._repo.remove_downloads([d.video_id for d in targets])
        await self.load()

    def _delete_all_items(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Confirmar Eliminación Masiva")
        if self._current_tab == "songs":
            msg_box.setText("¿Estás seguro de que deseas eliminar TODAS las canciones descargadas?")
        elif self._current_tab == "albums":
            msg_box.setText("¿Estás seguro de que deseas eliminar TODOS los álbumes descargados junto con todas sus canciones?")
        else:
            msg_box.setText("¿Estás seguro de que deseas eliminar TODAS las playlists descargadas junto con todas sus canciones?")
            
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        
        from doremi.ui.design import tokens
        msg_box.setStyleSheet(f"""
            QMessageBox {{
                background-color: {tokens.CURRENT.bg_surface};
                
            }}
            QLabel {{
                
            }}
            QPushButton {{
                background-color: {tokens.CURRENT.bg_elevated};
                
                border: 1px solid {tokens.CURRENT.border};
                border-radius: 6px;
                padding: 6px 16px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {tokens.CURRENT.accent_dim};
                color: {tokens.CURRENT.accent};
            }}
        """)
        
        if msg_box.exec() == QMessageBox.StandardButton.Yes:
            asyncio.ensure_future(self._delete_all_items_async())

    async def _delete_all_items_async(self) -> None:
        if getattr(self, "_selection_mode", False):
            self._toggle_selection_mode()

        downloads = await self._repo.get_downloads()
        if self._current_tab == "songs":
            targets = downloads
        else:
            is_album_tab = self._current_tab == "albums"
            targets = [
                d for d in downloads
                if d.parent_playlist_id
                and d.parent_playlist_id.startswith("album_") == is_album_tab
            ]

        for download in targets:
            if not download.file_path:
                continue
            try:
                path = Path(download.file_path)
                if path.exists():
                    path.unlink()
                lrc_path = path.with_suffix(".lrc")
                if lrc_path.exists():
                    lrc_path.unlink()
            except Exception as e:
                logger.error(f"Error deleting file {download.file_path}: {e}")

        await self._repo.remove_downloads([d.video_id for d in targets])
        await self.load()

    def _apply_theme_styles(self) -> None:
        self._update_toolbar_styles()
        for key, btn in self.tab_btns.items():
            btn.setStyleSheet(self._tab_style(key == self._current_tab))
        self._update_status_filter_styles()

    def _fade_in_content(self) -> None:
        """Smooth fade-in animation when content finishes loading."""
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        effect = QGraphicsOpacityEffect(self.scroll_content)
        self.scroll_content.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(250)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: self.scroll_content.setGraphicsEffect(None))
        anim.start()

    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._apply_theme_styles()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)
