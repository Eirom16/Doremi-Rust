import asyncio
import datetime
from functools import partial
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QGridLayout, QPushButton, QGraphicsOpacityEffect, QFrame
from qasync import asyncSlot
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QPixmap
from loguru import logger
from doremi.ui.design.fonts import AppFont
from doremi.ui.design.icons import Icon
from doremi.ui.design import tokens
from doremi.ui.widgets.album_card import AlbumCard
from doremi.ui.widgets.playlist_card import PlaylistCard
from doremi.ui.widgets.song_card import SongCard
from doremi.ui.widgets.artist_card import ArtistCard
from doremi.ui.widgets.error_state import ErrorStateWidget
from doremi.ui.widgets.ripple_button import RippleButton
from doremi.ui.widgets.skeleton_loader import SkeletonListLoader
from doremi.ui.widgets.horizontal_scroll import HorizontalScrollArea
from doremi.utils.image_cache import ImageCache
from doremi.ui.screens.home_data import browse_id_route

_image_cache = ImageCache()

class QuickAccessTile(QWidget):
    clicked = Signal()
    download_requested = Signal(str, str, str, str)  # video_id, title, artist, thumbnail_url
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    add_to_playlist_requested = Signal(str, str)
    like_requested = Signal(str, object)
    delete_download_requested = Signal(str)

    _cached_style: str | None = None
    _cached_theme_id: str | None = None

    def __init__(self, title: str, thumbnail_url: str = "", on_play=None, video_id: str = "", artist: str = "", parent=None):
        super().__init__(parent)
        self._title = title
        self._artist = artist
        self._video_id = video_id
        self._thumbnail_url = thumbnail_url
        self._on_play = on_play
        self.setObjectName("quickAccessTile")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(60)
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
            cache_key = f"{path}_44_44"
            pixmap = QPixmap()
            if QPixmapCache.find(cache_key, pixmap):
                self.thumb.setPixmap(pixmap)
                self.thumb.setStyleSheet("background: transparent; border-radius: 10px;")
            else:
                from doremi.utils.image_cache import load_scaled_async
                def on_loaded(bytes_data):
                    if not shiboken6.isValid(self):
                        return
                    if bytes_data:
                        pix = QPixmap()
                        if pix.loadFromData(bytes_data):
                            QPixmapCache.insert(cache_key, pix)
                            self.thumb.setPixmap(pix)
                            self.thumb.setStyleSheet("background: transparent; border-radius: 10px;")
                load_scaled_async(path, 44, 44, self, on_loaded)

    def _build_ui(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 8, 6)
        lay.setSpacing(12)

        self.thumb = QLabel()
        self.thumb.setFixedSize(44, 44)
        self.thumb.setText(Icon.get("album"))
        self.thumb.setFont(Icon.font(24))
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setStyleSheet(f"background: {tokens.CURRENT.bg_high}; color: {tokens.CURRENT.text_secondary}; border-radius: 10px;")
        lay.addWidget(self.thumb)

        self.title_lbl = QLabel()
        self.title_lbl.setFont(QFont("Inter", 11, QFont.Weight.DemiBold))
        # Elide long title
        metrics = self.title_lbl.fontMetrics()
        elided = metrics.elidedText(self._title, Qt.TextElideMode.ElideRight, 130)
        self.title_lbl.setText(elided)
        lay.addWidget(self.title_lbl, stretch=1)

        # Small hover play button
        self.play_btn = QPushButton()
        self.play_btn.setText(Icon.get("play_arrow"))
        self.play_btn.setFont(Icon.font(16))
        self.play_btn.setFixedSize(32, 32)
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.hide()
        if self._on_play:
            self.play_btn.clicked.connect(self._on_play)
        lay.addWidget(self.play_btn)

        # Small hover three dots button
        self.menu_btn = QPushButton()
        self.menu_btn.setObjectName("menuBtn")
        self.menu_btn.setText(Icon.get("more_vert"))
        self.menu_btn.setFont(Icon.font(16))
        self.menu_btn.setFixedSize(32, 32)
        self.menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.menu_btn.clicked.connect(self._show_context_menu)
        lay.addWidget(self.menu_btn)

        self.menu_btn.setVisible(bool(self._video_id))

        self._apply_style()

    def _apply_style(self):
        t = tokens.CURRENT
        theme_id = t.bg_surface  # usar cualquier token como fingerprint del tema

        if QuickAccessTile._cached_style and QuickAccessTile._cached_theme_id == theme_id:
            self.setStyleSheet(QuickAccessTile._cached_style)
            if hasattr(self, "thumb") and (not self.thumb.pixmap() or self.thumb.pixmap().isNull()):
                self.thumb.setStyleSheet(f"background: {t.bg_high}; color: {t.text_secondary}; border-radius: 10px;")
            return

        style = f"""
            QWidget#quickAccessTile {{
                background-color: {t.bg_surface};
                border: 1px solid {t.border};
                border-radius: 12px;
            }}
            QWidget#quickAccessTile:hover {{
                background-color: {t.bg_elevated};
                border-color: {t.border_focus};
            }}
            QLabel {{
                background: transparent;
                color: {t.text_primary};
            }}
            QPushButton {{
                background-color: {t.accent};
                border: none;
                border-radius: 16px;
                color: {t.text_on_accent};
                font-family: 'Material Symbols Rounded';
            }}
            QPushButton:hover {{
                background-color: {t.accent_bright};
            }}
            QPushButton#menuBtn {{
                background-color: transparent;
                color: {t.text_secondary};
                border-radius: 16px;
            }}
            QPushButton#menuBtn:hover {{
                background-color: rgba(120, 120, 120, 0.15);
                color: {t.accent};
            }}
        """
        QuickAccessTile._cached_style = style
        QuickAccessTile._cached_theme_id = theme_id
        self.setStyleSheet(style)
        if hasattr(self, "thumb") and (not self.thumb.pixmap() or self.thumb.pixmap().isNull()):
            self.thumb.setStyleSheet(f"background: {t.bg_high}; color: {t.text_secondary}; border-radius: 10px;")

    def _on_download_clicked(self):
        if self._video_id:
            self.download_requested.emit(
                self._video_id, self._title, self._artist, self._thumbnail_url
            )

    def _on_play_next_clicked(self):
        if self._video_id:
            self.play_next_requested.emit(
                self._video_id, self._title, self._artist, self._thumbnail_url
            )

    def _on_add_to_queue_clicked(self):
        if self._video_id:
            self.add_to_queue_requested.emit(
                self._video_id, self._title, self._artist, self._thumbnail_url
            )

    def _on_add_to_playlist_clicked(self):
        if self._video_id:
            self.add_to_playlist_requested.emit(self._video_id, self._title)

    def _on_delete_download_clicked(self):
        if self._video_id:
            self.delete_download_requested.emit(self._video_id)

    def _show_context_menu(self):
        asyncio.create_task(self._show_context_menu_async())

    async def _show_context_menu_async(self):
        from doremi.db.repository import DownloadRepository
        repo = DownloadRepository()
        existing = await repo.get_download(self._video_id) if self._video_id else None
        is_downloaded = existing is not None
        
        from doremi.ui.widgets.song_context_menu import SongContextMenu
        self._current_menu = SongContextMenu(parent=self.window(), is_downloaded=is_downloaded)
        self._current_menu.play_next.connect(self._on_play_next_clicked)
        self._current_menu.add_to_queue.connect(self._on_add_to_queue_clicked)
        self._current_menu.add_to_playlist.connect(self._on_add_to_playlist_clicked)
        
        if is_downloaded:
            self._current_menu.delete_download.connect(self._on_delete_download_clicked)
        else:
            self._current_menu.download.connect(self._on_download_clicked)
            
        self._current_menu._trigger_widget = self.menu_btn
        pos = self.menu_btn.mapToGlobal(self.menu_btn.rect().bottomLeft())
        self._current_menu.popup_at(pos)

    def enterEvent(self, event):
        self.play_btn.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.play_btn.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._apply_style()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)


class SpotlightBanner(QFrame):
    _cached_style: str | None = None
    _cached_theme_id: str | None = None

    def __init__(self, title: str, subtitle: str, thumbnail_url: str = "", on_play=None, on_explore=None, parent=None):
        super().__init__(parent)
        self._title = title
        self._subtitle = subtitle
        self._thumbnail_url = thumbnail_url
        self._on_play = on_play
        self._on_explore = on_explore
        self.setFixedHeight(180)
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
            cache_key = f"{path}_140_140"
            pixmap = QPixmap()
            if QPixmapCache.find(cache_key, pixmap):
                self.thumb.setPixmap(pixmap)
                self.thumb.setStyleSheet("background: transparent; border-radius: 12px;")
            else:
                from doremi.utils.image_cache import load_scaled_async
                def on_loaded(bytes_data):
                    if not shiboken6.isValid(self):
                        return
                    if bytes_data:
                        pix = QPixmap()
                        if pix.loadFromData(bytes_data):
                            QPixmapCache.insert(cache_key, pix)
                            self.thumb.setPixmap(pix)
                            self.thumb.setStyleSheet("background: transparent; border-radius: 12px;")
                load_scaled_async(path, 140, 140, self, on_loaded)

    def _build_ui(self):
        self.setObjectName("spotlightBanner")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(20)

        # Left Info column
        info = QVBoxLayout()
        info.setSpacing(6)
        info.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        spot_lbl = QLabel("DESTACADO")
        spot_lbl.setObjectName("spotlightTag")
        spot_lbl.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        info.addWidget(spot_lbl)

        title_lbl = QLabel(self._elide(self._title, 340))
        title_lbl.setObjectName("spotlightTitle")
        title_lbl.setFont(QFont("Inter", 20, QFont.Weight.ExtraBold))
        info.addWidget(title_lbl)

        sub_lbl = QLabel(self._elide(self._subtitle, 340))
        sub_lbl.setObjectName("spotlightSubtitle")
        sub_lbl.setFont(QFont("Inter", 12))
        info.addWidget(sub_lbl)

        info.addSpacing(6)

        # Buttons row
        btns = QHBoxLayout()
        btns.setSpacing(12)

        play_btn = RippleButton("Reproducir", "primary")
        play_btn.setFixedHeight(34)
        if self._on_play:
            play_btn.clicked.connect(self._on_play)
        btns.addWidget(play_btn)

        if self._on_explore:
            exp_btn = RippleButton("Explorar", "secondary")
            exp_btn.setFixedHeight(34)
            exp_btn.clicked.connect(self._on_explore)
            btns.addWidget(exp_btn)

        btns.addStretch()
        info.addLayout(btns)

        lay.addLayout(info, stretch=1)

        # Right thumbnail
        self.thumb = QLabel()
        self.thumb.setFixedSize(140, 140)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setText(Icon.get("featured_play_list"))
        self.thumb.setFont(Icon.font(48))
        lay.addWidget(self.thumb)

        self._apply_style()

    def _elide(self, text: str, width: int) -> str:
        return self.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, width)

    def _apply_style(self):
        t = tokens.CURRENT
        theme_id = t.bg_surface

        if SpotlightBanner._cached_style and SpotlightBanner._cached_theme_id == theme_id:
            self.setStyleSheet(SpotlightBanner._cached_style)
            return

        style = f"""
            #spotlightBanner {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {t.bg_surface}, stop:0.5 {t.bg_elevated}, stop:1 {t.accent_dim});
                border: 1px solid {t.border};
                border-radius: 16px;
            }}
            QLabel {{
                background: transparent;
            }}
            QLabel#spotlightTag {{
                color: {t.accent};
            }}
            QLabel#spotlightTitle {{
                color: {t.text_primary};
            }}
            QLabel#spotlightSubtitle {{
                color: {t.text_secondary};
            }}
        """
        SpotlightBanner._cached_style = style
        SpotlightBanner._cached_theme_id = theme_id
        self.setStyleSheet(style)

    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._apply_style()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)


class GenreButton(RippleButton):
    def __init__(self, name: str, query: str, on_genre_click, parent=None):
        super().__init__(name, "secondary", parent)
        self._query = query
        self._on_genre_click = on_genre_click
        self.setFixedSize(150, 80)
        self.clicked.connect(lambda: self._on_genre_click(self._query))
        self._update_styles()

    def _update_styles(self) -> None:
        from doremi.ui.design import tokens
        t = tokens.CURRENT
        self.setStyleSheet(f"""
            QPushButton {{
                background: {t.bg_elevated};
                color: {t.text_primary};
                border: 1px solid {t.border};
                border-radius: 12px;
                font-size: 14px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: {t.bg_high};
                border-color: {t.accent}55;
            }}
        """)

    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._update_styles()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)


class HomeScreen(QWidget):
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
        self._sections = {}
        self._loaded = False
        self._current_load_task = None
        self._genres = [
            ("Rock", "rock"),
            ("Pop", "pop"),
            ("Reggaeton", "reggaeton"),
            ("Salsa", "salsa"),
            ("Clasica", "classical"),
            ("Electronica", "electronic"),
            ("Jazz", "jazz"),
            ("R&B", "r&b"),
            ("Reggae", "reggae"),
            ("Hip Hop", "hip hop"),
            ("Latina", "latin music"),
            ("Colombia", "colombian music"),
        ]
        self._build_ui()
    
    def _connect_card_signals(self, card):
        """Wire up all context-menu signals from a SongCard."""
        card.download_requested.connect(lambda *a: self.download_requested.emit(*a))
        card.play_next_requested.connect(lambda *a: self.play_next_requested.emit(*a))
        card.add_to_queue_requested.connect(lambda *a: self.add_to_queue_requested.emit(*a))
        card.like_requested.connect(lambda *a: self.like_requested.emit(*a))
        card.add_to_playlist_requested.connect(lambda *a: self.add_to_playlist_requested.emit(*a))
        card.delete_download_requested.connect(lambda *a: self.delete_download_requested.emit(*a))
        if hasattr(card, "artist_clicked"):
            card.artist_clicked.connect(lambda *a: self.artist_clicked.emit(*a))
        if hasattr(card, "album_clicked"):
            card.album_clicked.connect(lambda *a: self.album_clicked.emit(*a))

    def _handle_download(self, vid, title, artist, thumb):
        self.download_requested.emit(vid, title, artist, thumb)
    
    def _handle_play(self, video_id, title, artists, thumbnail_url="", duration_ms=0):
        try:
            artist_str = ", ".join([a.get("name", "") for a in artists]) if isinstance(artists, list) else str(artists)
            if self.on_play_song:
                self.on_play_song(video_id, title, artist_str, "", duration_ms, thumbnail_url)
        except Exception as e:
            logger.error(f"Play error: {e}")

    def _on_genre_click(self, query):
        if self.on_navigate:
            self.on_navigate(f"search?query={query}")

    def _create_genre_card(self, name, query):
        return GenreButton(name, query, self._on_genre_click)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 24, 0)
        layout.setSpacing(12)

        self._header = QLabel("Inicio")
        self._header.setProperty("textRole", "primary")
        self._header.setFont(AppFont.display(30))
        self._header.setStyleSheet("background: transparent;")
        layout.addWidget(self._header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")

        self.content = QWidget()
        self._content_wrapper_layout = QVBoxLayout(self.content)
        self._content_wrapper_layout.setContentsMargins(0, 0, 0, 112)
        
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(22)
        
        self._content_wrapper_layout.addLayout(self.content_layout)
        self._content_wrapper_layout.addStretch()

        self._create_loading_state()

        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll)

    def _create_loading_state(self):
        self.content_layout.addWidget(SkeletonListLoader(row_count=7))

    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _fade_in_content(self):
        """Smooth fade-in animation when content finishes loading."""
        effect = QGraphicsOpacityEffect(self.content)
        self.content.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(300)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: self.content.setGraphicsEffect(None))
        anim.start()

    async def load(self):
        if self._current_load_task and not self._current_load_task.done():
            self._current_load_task.cancel()
        self._current_load_task = asyncio.create_task(self._load_async())
        try:
            await self._current_load_task
        except asyncio.CancelledError:
            if self._current_load_task and not self._current_load_task.done():
                self._current_load_task.cancel()
            raise

    async def _load_async(self):
        if self._loaded:
            return
        self._clear_content()
        self._create_loading_state()

        try:
            from doremi.db.repository import DownloadRepository
            dl_repo = DownloadRepository()
            downloads = await dl_repo.get_downloads()
            self.downloaded_playlist_ids = {d.parent_playlist_id for d in downloads if d.parent_playlist_id}
        except Exception as e:
            logger.debug(f"Error fetching downloaded playlists for badge checks: {e}")
            self.downloaded_playlist_ids = set()

        # Check for cancellation before calling API/rendering

        from loguru import logger
        logger.info(f"Home load: yt={self.yt}, is_auth={getattr(self.yt, 'is_authenticated', False) if self.yt else 'No yt'}")

        if self.yt:
            # Always try YouTube home — get_home/get_charts now work via public client
            logger.info("Loading YouTube home content...")
            await self._load_youtube_home()
        else:
            logger.info("No yt client — loading offline cache")
            self._clear_content()
            await self._load_offline_view()
        
        self._loaded = True

    def force_reload(self):
        """Force a full reload of the home content (e.g. after login)."""
        self._loaded = False
        if self._current_load_task and not self._current_load_task.done():
            self._current_load_task.cancel()
        asyncio.ensure_future(self.load())

    async def _load_youtube_home(self):
        try:
            from loguru import logger
            logger.info("Loading YouTube home recommendations...")
            
            home_data = await self.yt.get_home()
            
            # get_home() returns a list of sections (unauthenticated)
            # or a dict with 'contents' key (authenticated)
            contents = None
            if isinstance(home_data, list) and home_data:
                contents = home_data
            elif isinstance(home_data, dict) and home_data.get('contents'):
                contents = home_data.get('contents', [])

            # Check for cancellation

            if contents:
                self._clear_content()

                # Dynamic Time-based greeting in Spanish
                hour = datetime.datetime.now().hour
                if hour < 12:
                    greeting = "¡Buenos días!"
                elif hour < 18:
                    greeting = "¡Buenas tardes!"
                else:
                    greeting = "¡Buenas noches!"
                
                self._header.setText(greeting)
                
                # Fetch liked video IDs for heart state
                from doremi.db.repository import SongRepository
                liked_ids = await SongRepository().get_liked_video_ids()
                
                # 1. Spotlight Banner (Hero Section)
                spotlight_item = None
                for section in contents:
                    sec_items = section.get('contents', section.get('items', []))
                    for item in sec_items:
                        if isinstance(item, dict) and (item.get('playlistId') or item.get('browseId')):
                            spotlight_item = item
                            break
                    if spotlight_item:
                        break
                
                if spotlight_item:
                    title = spotlight_item.get('title', 'Recomendado')
                    if isinstance(title, dict):
                        title = title.get('text', 'Recomendado')
                    
                    artists = spotlight_item.get('artists', [])
                    if isinstance(artists, list):
                        artist_names = ", ".join([a.get('name', '') for a in artists if isinstance(a, dict)]) or 'YouTube Music'
                    elif isinstance(artists, str):
                        artist_names = artists
                    else:
                        artist_names = 'YouTube Music'
                        
                    thumbnails = spotlight_item.get('thumbnails', [])
                    thumb_url = thumbnails[-1].get('url', '') if thumbnails else ''
                    
                    playlist_id = spotlight_item.get('playlistId')
                    browse_id = spotlight_item.get('browseId')
                    if not playlist_id and browse_id and str(browse_id).startswith("VL"):
                        playlist_id = browse_id
                        browse_id = None
                    
                    on_explore = None
                    if playlist_id and self.on_navigate:
                        route = (
                            browse_id_route(str(playlist_id))
                            if str(playlist_id).startswith("MPSP")
                            else f"playlist?id={playlist_id}"
                        )
                        on_explore = partial(self.on_navigate, route)
                    elif browse_id and self.on_navigate:
                        on_explore = partial(self.on_navigate, browse_id_route(str(browse_id)))
                    
                    banner = SpotlightBanner(str(title), f"De {artist_names}", thumb_url, on_play=on_explore, on_explore=on_explore)
                    self.content_layout.addWidget(banner)
                    self.content_layout.addSpacing(10)

                # 2. Quick Access Grid (Tiles minimalistas 2x3)
                quick_grid = self._render_quick_access_grid(contents, liked_ids)
                if quick_grid:
                    self.content_layout.addWidget(quick_grid)
                    self.content_layout.addSpacing(16)

                # Section Title
                title_lbl = QLabel("Recomendaciones para ti")
                title_lbl.setProperty("textRole", "primary")
                title_lbl.setFont(AppFont.heading(20))
                title_lbl.setStyleSheet("background: transparent; padding-top: 10px;")
                self.content_layout.addWidget(title_lbl)
                
                self._fade_in_content()

                # Yield immediately before heavy rendering
                await asyncio.sleep(0)

                await self._display_home_content(contents, liked_ids)
            else:
                # Fallback to charts
                charts_data = await self.yt.get_charts()
                
                # Check for cancellation

                has_charts = False
                if isinstance(charts_data, dict):
                    has_charts = bool(charts_data.get('items') or charts_data.get('tracks'))
                elif isinstance(charts_data, list):
                    has_charts = bool(charts_data)

                if has_charts:
                    self._clear_content()
                    title = QLabel("Top Charts")
                    title.setProperty("textRole", "primary")
                    title.setFont(AppFont.heading(22))
                    title.setStyleSheet("background: transparent;")
                    self.content_layout.addWidget(title)
                    
                    self._fade_in_content()
                    await asyncio.sleep(0)
                    
                    await self._display_charts(charts_data)
                else:
                    self._clear_content()
                    await self._load_offline_view()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error loading YouTube home: {e}")
            self._clear_content()
            await self._load_offline_view()

    def _render_quick_access_grid(self, sections, liked_ids):
        valid_items = []
        for section in sections:
            sec_items = section.get('contents', section.get('items', []))
            for item in sec_items:
                if len(valid_items) >= 6:
                    break
                if isinstance(item, dict) and item.get('videoId'):
                    # Avoid duplicates
                    v_id = item.get('videoId')
                    if not any(x.get('videoId') == v_id for x in valid_items):
                        valid_items.append(item)
            if len(valid_items) >= 6:
                break
                
        if not valid_items:
            return None

        grid_widget = QWidget()
        grid_lay = QGridLayout(grid_widget)
        grid_lay.setContentsMargins(0, 0, 0, 0)
        grid_lay.setHorizontalSpacing(16)
        grid_lay.setVerticalSpacing(12)
        
        for idx, item in enumerate(valid_items):
            title = item.get('title', 'Unknown')
            if isinstance(title, dict):
                title = title.get('text', 'Unknown')
            
            thumbnails = item.get('thumbnails', [])
            thumb_url = thumbnails[-1].get('url', '') if thumbnails else ''
            
            video_id = item.get('videoId')
            
            artists = item.get('artists', [])
            if isinstance(artists, list):
                artist_names = ", ".join([a.get('name', '') for a in artists if isinstance(a, dict)]) or 'Unknown'
            elif isinstance(artists, str):
                artist_names = artists
            else:
                artist_names = 'Unknown'
            
            # Extract duration from item (duration_seconds or duration string)
            dur_ms = 0
            if item.get('duration_seconds'):
                dur_ms = int(item.get('duration_seconds')) * 1000
            elif item.get('duration'):
                try:
                    dur_str = str(item['duration'])
                    parts = dur_str.split(':')
                    if len(parts) == 2:
                        dur_ms = (int(parts[0]) * 60 + int(parts[1])) * 1000
                    elif len(parts) == 3:
                        dur_ms = (int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])) * 1000
                except (ValueError, IndexError):
                    pass
            
            on_play = None
            if video_id:
                on_play = partial(self._handle_play, video_id, str(title), artist_names, thumb_url, dur_ms)
            
            tile = QuickAccessTile(
                title=str(title),
                thumbnail_url=thumb_url,
                on_play=on_play,
                video_id=video_id or "",
                artist=artist_names
            )
            self._connect_card_signals(tile)
            
            if video_id and on_play:
                tile.clicked.connect(on_play)
                
            grid_lay.addWidget(tile, idx // 3, idx % 3)
            
        return grid_widget

    def _create_card_from_item(self, item, liked_ids):
        title = item.get('title', 'Unknown')
        if isinstance(title, dict):
            title = title.get('text', 'Unknown')

        video_id = item.get('videoId', '')
        playlist_id = item.get('playlistId', '')
        browse_id = item.get('browseId', '')
        if not playlist_id and browse_id and str(browse_id).startswith("VL"):
            playlist_id = browse_id
            browse_id = ''
        
        artists = item.get('artists', [])
        if isinstance(artists, list):
            artist_names = ", ".join([a.get('name', '') for a in artists if isinstance(a, dict)]) or 'Unknown'
        elif isinstance(artists, str):
            artist_names = artists
        else:
            artist_names = 'Unknown'

        duration = item.get('duration', item.get('lengthText', ''))
        thumbnails = item.get('thumbnails', [])
        thumbnail_url = thumbnails[-1].get('url', '') if thumbnails else ''
            
        if video_id:
            # Extract duration_ms from item
            dur_ms = 0
            if item.get('duration_seconds'):
                dur_ms = int(item.get('duration_seconds')) * 1000
            elif duration:
                try:
                    dur_str = str(duration)
                    parts = dur_str.split(':')
                    if len(parts) == 2:
                        dur_ms = (int(parts[0]) * 60 + int(parts[1])) * 1000
                    elif len(parts) == 3:
                        dur_ms = (int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])) * 1000
                except (ValueError, IndexError):
                    pass
            
            card = SongCard(
                title=str(title),
                artist=artist_names,
                duration=str(duration) if duration else '',
                thumbnail_url=thumbnail_url,
                on_play=partial(self._handle_play, video_id, str(title), artist_names, thumbnail_url, dur_ms),
                video_id=video_id,
                is_liked=video_id in liked_ids,
            )
            self._connect_card_signals(card)
            return card
        elif playlist_id:
            author = item.get('author')
            playlist_desc = ""
            if isinstance(author, list):
                playlist_desc = ", ".join([a.get('name', '') for a in author if isinstance(a, dict)])
            elif isinstance(author, dict):
                playlist_desc = author.get('name', '')
            elif isinstance(author, str):
                playlist_desc = author
            
            if not playlist_desc:
                playlist_desc = item.get('description', '')
                
            if not playlist_desc or playlist_desc == 'Unknown':
                playlist_desc = ""

            card = PlaylistCard(
                title=str(title),
                description=playlist_desc,
                thumbnail_url=thumbnail_url,
                is_downloaded=playlist_id in getattr(self, "downloaded_playlist_ids", set())
            )
            if self.on_navigate:
                route = (
                    browse_id_route(str(playlist_id))
                    if str(playlist_id).startswith("MPSP")
                    else f"playlist?id={playlist_id}"
                )
                card.clicked.connect(partial(self.on_navigate, route))
            return card
        elif browse_id:
            if str(browse_id).startswith("UC"):
                card = ArtistCard(name=str(title), thumbnail_url=thumbnail_url)
                if self.on_navigate:
                    card.clicked.connect(partial(self.on_navigate, f"artist?id={browse_id}"))
            else:
                card = AlbumCard(title=str(title), artist=artist_names, thumbnail_url=thumbnail_url)
                if self.on_navigate:
                    card.clicked.connect(partial(self.on_navigate, browse_id_route(str(browse_id))))
            return card
        return None

    async def _display_home_content(self, contents, liked_ids=None):
        if liked_ids is None:
            liked_ids = set()
        for section in contents[:6]:
            if not isinstance(section, dict):
                continue

            section_widget = QWidget()
            section_layout = QVBoxLayout(section_widget)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(12)
            
            section_title = section.get('title', 'Sección')
            if isinstance(section_title, dict):
                section_title = section_title.get('text', 'Sección')
            
            header = QLabel(str(section_title))
            header.setProperty("textRole", "primary")
            header.setFont(AppFont.heading(16))
            header.setStyleSheet("background: transparent; padding-top: 10px;")
            section_layout.addWidget(header)
            
            items = section.get('contents', section.get('items', []))
            if not isinstance(items, list):
                items = []

            has_cards = False
            
            # Determine if this section is mostly songs (videoId)
            has_songs = any('videoId' in item for item in items[:6] if isinstance(item, dict))
            
            if has_songs:
                # Keep QGridLayout for songs
                grid = QGridLayout()
                grid.setContentsMargins(0, 0, 0, 0)
                grid.setHorizontalSpacing(16)
                grid.setVerticalSpacing(12)
                columns = 2
                
                card_index = 0
                for item in items[:8]:
                    if not isinstance(item, dict):
                        continue
                    card = self._create_card_from_item(item, liked_ids)
                    if card:
                        grid.addWidget(card, card_index // columns, card_index % columns)
                        card_index += 1
                        has_cards = True
                if has_cards:
                    section_layout.addLayout(grid)
            else:
                # Use HorizontalScrollArea for albums/playlists/artists!
                scroll = HorizontalScrollArea()
                for item in items[:15]:
                    if not isinstance(item, dict):
                        continue
                    card = self._create_card_from_item(item, liked_ids)
                    if card:
                        scroll.addWidget(card)
                        has_cards = True
                if has_cards:
                    section_layout.addWidget(scroll)
            
            if has_cards:
                self.content_layout.addWidget(section_widget)
            else:
                section_widget.deleteLater()

            # Sleep longer to allow UI updates and image loading between chunks
            await asyncio.sleep(0.01)
        
        self.content_layout.addStretch()

    async def _display_charts(self, charts):
        """Display charts data - handles both list and dict formats."""
        if isinstance(charts, dict):
            section = QWidget()
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(12)

            chart_playlists = charts.get("playlists", [])
            if chart_playlists:
                scroll = HorizontalScrollArea()
                for playlist in chart_playlists[:10]:
                    title = playlist.get("title", "Chart")
                    thumbnails = playlist.get("thumbnails", [])
                    thumbnail_url = thumbnails[-1].get("url", "") if thumbnails else ""
                    playlist_id = playlist.get("playlistId", "")
                    
                    playlist_card = PlaylistCard(
                        title=title,
                        thumbnail_url=thumbnail_url,
                        is_downloaded=playlist_id in getattr(self, "downloaded_playlist_ids", set())
                    )
                    if playlist_id and self.on_navigate:
                        playlist_card.clicked.connect(partial(self.on_navigate, f"playlist?id={playlist_id}"))
                    scroll.addWidget(playlist_card)
                
                playlists_title = QLabel("Playlists Populares")
                playlists_title.setProperty("textRole", "primary")
                playlists_title.setFont(AppFont.heading(16))
                playlists_title.setStyleSheet("background: transparent;")
                section_layout.addWidget(playlists_title)
                section_layout.addWidget(scroll)

            tracks = charts.get("tracks", charts.get("items", []))
            if tracks:
                tracks_title = QLabel("Canciones del Momento")
                tracks_title.setProperty("textRole", "primary")
                tracks_title.setFont(AppFont.heading(16))
                tracks_title.setStyleSheet("background: transparent; padding-top: 10px;")
                section_layout.addWidget(tracks_title)
                
                grid = QGridLayout()
                grid.setContentsMargins(0, 0, 0, 0)
                grid.setHorizontalSpacing(16)
                grid.setVerticalSpacing(12)
                columns = 2
                
                card_index = 0
                for track in tracks[:10]:
                    title = track.get("title", "Unknown")
                    artists = track.get("artists", [])
                    artist_names = ", ".join([a.get("name", "") for a in artists]) if isinstance(artists, list) else str(artists)
                    video_id = track.get("videoId", "")
                    duration = track.get("lengthText", "")
                    thumbnails = track.get('thumbnails', [])
                    thumbnail_url = thumbnails[-1].get('url', '') if thumbnails else ''

                    if video_id:
                        # Parse duration string to ms
                        dur_ms = 0
                        if duration:
                            try:
                                dur_str = str(duration)
                                parts = dur_str.split(':')
                                if len(parts) == 2:
                                    dur_ms = (int(parts[0]) * 60 + int(parts[1])) * 1000
                                elif len(parts) == 3:
                                    dur_ms = (int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])) * 1000
                            except (ValueError, IndexError):
                                pass
                        
                        card = SongCard(
                            title=title,
                            artist=artist_names,
                            duration=duration,
                            thumbnail_url=thumbnail_url,
                            on_play=partial(self._handle_play, video_id, title, artist_names, thumbnail_url, dur_ms),
                            video_id=video_id
                        )
                        card.download_requested.connect(self._handle_download)
                        grid.addWidget(card, card_index // columns, card_index % columns)
                        card_index += 1
                section_layout.addLayout(grid)

            self.content_layout.addWidget(section)

        elif isinstance(charts, list):
            section = QWidget()
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            
            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(16)
            grid.setVerticalSpacing(12)
            columns = 2
            
            card_index = 0
            for item in charts[:12]:
                title = item.get('title', 'Unknown')
                video_id = item.get('videoId', '')
                artists = item.get('artists', [])
                artist_names = ", ".join([a.get('name', '') for a in artists]) if artists else 'Unknown'
                duration = item.get('lengthText', '')
                thumbnails = item.get('thumbnails', [])
                thumbnail_url = thumbnails[-1].get('url', '') if thumbnails else ''

                if video_id:
                    # Parse duration string to ms
                    dur_ms = 0
                    if duration:
                        try:
                            dur_str = str(duration)
                            parts = dur_str.split(':')
                            if len(parts) == 2:
                                dur_ms = (int(parts[0]) * 60 + int(parts[1])) * 1000
                            elif len(parts) == 3:
                                dur_ms = (int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])) * 1000
                        except (ValueError, IndexError):
                            pass
                    
                    card = SongCard(
                        title=title,
                        artist=artist_names,
                        duration=duration,
                        thumbnail_url=thumbnail_url,
                        on_play=partial(self._handle_play, video_id, title, artist_names, thumbnail_url, dur_ms)
                    )
                    grid.addWidget(card, card_index // columns, card_index % columns)
                    card_index += 1
            section_layout.addLayout(grid)
            self.content_layout.addWidget(section)

        self.content_layout.addStretch()


    async def _load_offline_view(self):
        from doremi.services.offline_cache import OfflineCacheManager
        data = OfflineCacheManager.get_instance().load_home()
        title = QLabel("Modo sin conexión")
        title.setProperty("textRole", "primary")
        title.setFont(AppFont.heading(22))
        title.setStyleSheet("background: transparent;")
        self.content_layout.addWidget(title)

        items: list[dict] = []
        seen: set[str] = set()
        for item in [*data.get("tiles", []), *data.get("songs", [])]:
            if item.get("videoId") and item["videoId"] not in seen:
                seen.add(item["videoId"])
                items.append(item)

        if not items:
            hint = QLabel(
                "Aún no hay música disponible. Conéctate una vez para que Doremi "
                "prepare y rote tus recomendaciones."
            )
            hint.setWordWrap(True)
            hint.setProperty("textRole", "secondary")
            self.content_layout.addWidget(hint)
            self.content_layout.addStretch()
            return

        grid = QGridLayout()
        grid.setSpacing(16)
        for index, item in enumerate(items):
            card = SongCard(
                title=item.get("title", ""), artist=item.get("artist", ""),
                duration=item.get("duration", ""),
                thumbnail_url=item.get("thumbnail_url", ""),
                on_play=partial(
                    self._handle_play, item.get("videoId", ""),
                    item.get("title", ""), item.get("artist", ""),
                    item.get("thumbnail_url", ""), item.get("duration_ms", 0),
                ),
            )
            grid.addWidget(card, index // 4, index % 4)
        self.content_layout.addLayout(grid)
        self.content_layout.addStretch()

    async def _load_genres_view(self):
        """Compatibilidad interna: el fallback antiguo ahora usa la caché."""
        await self._load_offline_view()

    def _show_search_prompt(self):
        self._clear_content()
        title = QLabel("Bienvenido a Doremi")
        title.setProperty("textRole", "primary")
        title.setFont(AppFont.heading(22))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("padding: 20px; background: transparent;")
        self.content_layout.addWidget(title)

        search_hint = QLabel("Ve a Buscar y escribe el nombre de una cancion", self.scroll)
        search_hint.setProperty("textRole", "secondary")
        search_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        search_hint.setStyleSheet(f" font-size: 14px; padding: 10px; background: transparent;")
        self.content_layout.addWidget(search_hint)

        self.content_layout.addStretch()

    def _display_explore(self, explore):
        section = QWidget()
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(12)

        header = QLabel("Explorar")
        header.setProperty("textRole", "primary")
        header.setFont(AppFont.heading(17))
        header.setStyleSheet("background: transparent;")
        section_layout.addWidget(header)

        mood_cats = explore.get("moodCategories", [])
        if mood_cats:
            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(12)

            for i, cat in enumerate(mood_cats[:6]):
                title = cat.get("title", "Moods")
                playlist_card = PlaylistCard(title=title)
                grid.addWidget(playlist_card, i // 3, i % 3)

            section_layout.addLayout(grid)

        self.content_layout.addWidget(section)

    def _display_home(self, home):
        for item in home:
            section = QWidget()
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(12)

            title = item.get("title", {}).get("text", "Sección")
            header = QLabel(title)
            header.setProperty("textRole", "primary")
            header.setFont(AppFont.heading(17))
            header.setStyleSheet("background: transparent;")
            section_layout.addWidget(header)

            contents = item.get("contents", [])
            if contents:
                grid = QGridLayout()
                grid.setContentsMargins(0, 0, 0, 0)
                grid.setSpacing(12)

                for i, content in enumerate(contents[:6]):
                    content_type = content.get("contentType", "")

                    if "album" in content_type.lower():
                        album = content.get("album", {})
                        title_text = album.get("title", "Album")
                        artist_text = album.get("artist", {}).get("name", "Artist")
                        card = AlbumCard(title=title_text, artist=artist_text)
                        grid.addWidget(card, i // 3, i % 3)

                    elif "playlist" in content_type.lower():
                        playlist = content.get("playlist", {})
                        title_text = playlist.get("title", "Playlist")
                        playlist_id = playlist.get("playlistId", "")
                        card = PlaylistCard(
                            title=title_text,
                            is_downloaded=playlist_id in getattr(self, "downloaded_playlist_ids", set())
                        )
                        if playlist_id and self.on_navigate:
                            card.clicked.connect(partial(self.on_navigate, f"playlist?id={playlist_id}"))
                        grid.addWidget(card, i // 3, i % 3)

                    elif "song" in content_type.lower() or "video" in content_type.lower():
                        video = content.get("video", {}) or content.get("musicVideo", {})
                        title_text = video.get("title", {}).get("text", "Title")
                        artists = video.get("artist", {})
                        if isinstance(artists, list):
                            artists_text = ", ".join([a.get("name", "") for a in artists])
                        else:
                            artists_text = artists.get("name", "Artist") if artists else "Artist"
                        video_id = video.get("videoId", "")

                        if video_id:
                            # Extract duration from video data if available
                            dur_ms = 0
                            video_duration = video.get("lengthText") or video.get("duration")
                            if video_duration:
                                try:
                                    dur_str = str(video_duration)
                                    parts = dur_str.split(':')
                                    if len(parts) == 2:
                                        dur_ms = (int(parts[0]) * 60 + int(parts[1])) * 1000
                                    elif len(parts) == 3:
                                        dur_ms = (int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])) * 1000
                                except (ValueError, IndexError):
                                    pass
                            
                            card = SongCard(
                                title=title_text,
                                artist=artists_text,
                                duration=video_duration or "",
                                on_play=partial(self._handle_play, video_id, title_text, artists_text, "", dur_ms)
                            )
                            section_layout.addWidget(card)

                if grid.count() > 0:
                    section_layout.addLayout(grid)

            self.content_layout.addWidget(section)
