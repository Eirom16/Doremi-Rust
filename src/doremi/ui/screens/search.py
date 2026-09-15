"""
Search results screen with category filter chips (Canciones, Artistas,
Álbumes, Playlists) — inspired by YT Music's results layout.

Receives a query from GlobalSearchBar, fetches *all* result types once,
then lets the user filter by category using the chip bar.
"""

from functools import partial
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QPushButton, QGridLayout, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from qasync import asyncSlot
from loguru import logger
import asyncio

from doremi.ui.widgets.song_card import SongCard
from doremi.ui.widgets.album_card import AlbumCard
from doremi.ui.widgets.artist_card import ArtistCard
from doremi.ui.widgets.playlist_card import PlaylistCard
from doremi.ui.widgets.error_state import ErrorStateWidget
from doremi.ui.widgets.ripple_button import RippleButton
from doremi.ui.widgets.skeleton_loader import SkeletonListLoader
from doremi.ui.design.icons import Icon


# ---------------------------------------------------------------------------
# Filter chip widget
# ---------------------------------------------------------------------------
class _FilterChip(QPushButton):
    """A rounded toggle chip for category filtering."""

    def __init__(self, text: str, category: str):
        super().__init__(text)
        self.category = category
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(34)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self._apply_style()

    def _apply_style(self):
        from doremi.ui.design import tokens
        accent = tokens.CURRENT.accent
        self.setStyleSheet(f"""
            QPushButton {{
                background: {tokens.CURRENT.bg_surface};
                
                border: 1px solid {tokens.CURRENT.border};
                border-radius: 17px;
                padding: 0 20px;
                font-size: 13px;
                font-family: Inter;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {tokens.CURRENT.bg_elevated};
                
            }}
            QPushButton:checked {{
                background: {accent};
                
                border: 1px solid {accent};
            }}
        """)

    def changeEvent(self, event):
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange,):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._apply_style()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)


# ---------------------------------------------------------------------------
# Top Result card (the prominent first result)
# ---------------------------------------------------------------------------
class _TopResultCard(QWidget):
    """A prominent, beautiful square card shown for the top search result."""
    clicked = Signal()
    download_requested = Signal(str, str, str, str)  # video_id, title, artist, thumbnail_url
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    add_to_playlist_requested = Signal(str, str)
    delete_download_requested = Signal(str)

    def __init__(self, title, artist, result_type, thumbnail_url="", on_play=None, video_id=""):
        super().__init__()
        self._title = title
        self._artist = artist
        self._video_id = video_id
        self._thumbnail_url = thumbnail_url
        self._on_play = on_play
        self._has_thumbnail = bool(thumbnail_url)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Set size for the premium square top result card
        self.setFixedSize(320, 220)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)

        # Top row: Large Thumbnail + Round Play Button + Three Dots Menu Button
        top_row = QHBoxLayout()
        
        self.thumb = QLabel()
        self.thumb.setFixedSize(92, 92)
        self.thumb.setScaledContents(True)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setText(Icon.get("library_music"))
        self.thumb.setFont(Icon.font(40))
        top_row.addWidget(self.thumb)

        top_row.addStretch()

        # Side-by-side action buttons layout
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)
        actions_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.play_btn = QPushButton(self)
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.setText(Icon.get("play_arrow"))
        self.play_btn.setFixedSize(48, 48)
        if on_play:
            self.play_btn.clicked.connect(on_play)
        actions_layout.addWidget(self.play_btn)

        self.menu_btn = QPushButton(self)
        self.menu_btn.setObjectName("menuBtn")
        self.menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.menu_btn.setText(Icon.get("more_vert"))
        self.menu_btn.setFixedSize(48, 48)
        self.menu_btn.setVisible(bool(video_id))
        self.menu_btn.clicked.connect(self._show_context_menu)
        actions_layout.addWidget(self.menu_btn)

        top_row.addLayout(actions_layout)
        lay.addLayout(top_row)
        lay.addStretch()

        # Bottom row: Title, Artist, and Type Badge
        info = QVBoxLayout()
        info.setSpacing(4)

        self.title_lbl = QLabel(self._elide(title, 280))
        self.title_lbl.setFont(QFont("Inter", 20, QFont.Weight.ExtraBold))
        info.addWidget(self.title_lbl)

        # Sub-row for type badge and artist name
        sub_row = QHBoxLayout()
        sub_row.setSpacing(8)
        sub_row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        self.type_lbl = QLabel(result_type.upper())
        self.type_lbl.setObjectName("typeLabel")
        self.type_lbl.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        self.type_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.type_lbl.setFixedHeight(18)
        sub_row.addWidget(self.type_lbl)

        self.artist_lbl = QLabel(self._elide(artist, 180))
        self.artist_lbl.setFont(QFont("Inter", 12))
        self.artist_lbl.setObjectName("artistLabel")
        sub_row.addWidget(self.artist_lbl, stretch=1)
        
        info.addLayout(sub_row)
        lay.addLayout(info)

        if thumbnail_url:
            asyncio.ensure_future(self._load_thumb(thumbnail_url))

        self._apply_style()
        self._update_child_styles()

    def _elide(self, text: str, width: int) -> str:
        return self.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, width)

    def _apply_style(self):
        from doremi.ui.design import tokens
        accent = tokens.CURRENT.accent
        self.setStyleSheet(f"""
            _TopResultCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {tokens.CURRENT.bg_surface}, stop:1 {tokens.CURRENT.bg_elevated});
                border-radius: 16px;
                border: 1px solid {tokens.CURRENT.border};
            }}
            _TopResultCard:hover {{
                border: 1px solid {accent};
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {tokens.CURRENT.bg_elevated}, stop:1 {tokens.CURRENT.bg_high});
            }}
            QLabel#typeLabel {{
                color: {tokens.CURRENT.text_on_accent};
                background-color: {tokens.CURRENT.accent};
                border-radius: 4px;
                padding: 1px 6px;
            }}
        """)

        # Style the play button directly to show the Material symbol properly
        self.play_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {tokens.CURRENT.accent};
                color: {tokens.CURRENT.text_on_accent};
                border: none;
                border-radius: 24px;
                font-family: 'Material Symbols Rounded';
                font-size: 24px;
                font-weight: normal;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {tokens.CURRENT.accent_bright};
            }}
        """)

        # Style the menu button directly to show the Material symbol properly
        self.menu_btn.setStyleSheet(f"""
            QPushButton#menuBtn {{
                background: transparent;
                color: {tokens.CURRENT.text_secondary};
                border: none;
                border-radius: 24px;
                font-family: 'Material Symbols Rounded';
                font-size: 28px;
                padding: 0px;
            }}
            QPushButton#menuBtn:hover {{
                background-color: rgba(120, 120, 120, 0.15);
                color: {tokens.CURRENT.accent};
            }}
        """)

    def _update_child_styles(self):
        from doremi.ui.design import tokens
        if not self._has_thumbnail:
            self.thumb.setStyleSheet(f"background: {tokens.CURRENT.bg_surface};  border-radius: 12px;")
        else:
            self.thumb.setStyleSheet(f"border-radius: 12px; background: transparent;")
        self.title_lbl.setStyleSheet(f" background: transparent; color: {tokens.CURRENT.text_primary};")
        self.artist_lbl.setStyleSheet(f" background: transparent; color: {tokens.CURRENT.text_secondary};")

    def changeEvent(self, event):
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange,):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._apply_style()
                    self._update_child_styles()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)

    async def _load_thumb(self, url):
        from doremi.utils.image_cache import ImageCache
        cache = ImageCache()
        path = await cache.download(url)
        import shiboken6
        if not shiboken6.isValid(self):
            return
        if path:
            pix = QPixmap(str(path))
            if not pix.isNull():
                self.thumb.setPixmap(pix)
                self.thumb.setText("")
                self._has_thumbnail = True
                self._update_child_styles()

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

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._on_play:
            self._on_play()
        super().mousePressEvent(e)


# ---------------------------------------------------------------------------
# SearchScreen
# ---------------------------------------------------------------------------
class SearchScreen(QWidget):
    CATEGORIES = [
        ("Canciones", "song"),
        ("Álbumes", "album"),
        ("Playlists", "playlist"),
    ]

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
        self._current_query = ""
        self._all_results: list = []       # raw API results
        self._results_by_cat: dict[str, list] = {}  # category-specific search results cache
        self._active_category = "song"     # default filter
        self._current_columns = 0
        self._category_widgets = {}
        self._category_grid_layouts = {}
        self._category_cards = {}
        self._category_columns = {}
        self._build_ui()

    def _handle_download(self, vid, title, artist, thumb):
        self.download_requested.emit(vid, title, artist, thumb)

    # ------------------------------------------------------------------
    # Play handler
    # ------------------------------------------------------------------
    def _handle_play(self, video_id, title, artists, thumbnail_url, duration_ms=0):
        logger.info(f"_handle_play: video_id={repr(video_id)}, title={title[:30]}")
        try:
            if not video_id:
                logger.error("Empty video_id!")
                return
            artist_str = (
                ", ".join([a.get("name", "") for a in artists])
                if isinstance(artists, list)
                else str(artists)
            )
            if self.on_play_song:
                self.on_play_song(video_id, title, artist_str, "", duration_ms, thumbnail_url)
        except Exception as e:
            logger.error(f"Play error: {e}")

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -- Header area (query label + chip bar) --
        self.header_widget = QWidget()
        header_lay = QVBoxLayout(self.header_widget)
        header_lay.setContentsMargins(24, 16, 24, 12)
        header_lay.setSpacing(12)

        self._query_label = QLabel("")
        self._query_label.setFont(QFont("Inter", 20, QFont.Weight.Bold))
        self._query_label.setVisible(False)
        header_lay.addWidget(self._query_label)

        # Chip row
        chip_row = QHBoxLayout()
        chip_row.setSpacing(8)
        self._chips: dict[str, _FilterChip] = {}

        for label, cat in self.CATEGORIES:
            chip = _FilterChip(label, cat)
            chip.toggled.connect(partial(self._on_chip_toggled, cat))
            chip_row.addWidget(chip)
            self._chips[cat] = chip

        chip_row.addStretch()
        header_lay.addLayout(chip_row)

        root.addWidget(self.header_widget)

        # -- Scrollable results area (must be created BEFORE chips are checked) --
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("background: transparent; border: none;")

        self._results_widget = QWidget()
        self._content_wrapper_layout = QVBoxLayout(self._results_widget)
        self._content_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        
        self._results_layout = QVBoxLayout()
        self._results_layout.setSpacing(16)
        self._results_layout.setContentsMargins(0, 16, 0, 112)
        
        self._content_wrapper_layout.addLayout(self._results_layout)
        self._content_wrapper_layout.addStretch()

        self._scroll.setWidget(self._results_widget)
        root.addWidget(self._scroll)

        # Default check (after results_layout exists)
        self._chips["song"].setChecked(True)
        self._update_search_screen_styles()

    def _update_search_screen_styles(self) -> None:
        from doremi.ui.design import tokens
        if hasattr(self, 'header_widget') and self.header_widget:
            self.header_widget.setStyleSheet(f"""
                background-color: {tokens.CURRENT.bg_base};
                border-bottom: 1px solid {tokens.CURRENT.border};
            """)
        if hasattr(self, '_query_label') and self._query_label:
            self._query_label.setStyleSheet(f" background: transparent;")

    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange,):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._update_search_screen_styles()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)

    # ------------------------------------------------------------------
    # Chip toggling
    # ------------------------------------------------------------------
    def _on_chip_toggled(self, category: str, checked: bool):
        if not checked:
            # Don't allow un-checking the only active chip
            self._chips[category].blockSignals(True)
            self._chips[category].setChecked(True)
            self._chips[category].blockSignals(False)
            return

        # Un-check all others
        for cat, chip in self._chips.items():
            if cat != category:
                chip.blockSignals(True)
                chip.setChecked(False)
                chip.blockSignals(False)

        self._active_category = category
        if self._current_query:
            asyncio.ensure_future(self._fetch_category_results(self._current_query, category))
        else:
            self._render_filtered()

    # ------------------------------------------------------------------
    # Public entry point — called from MainWindow
    # ------------------------------------------------------------------
    async def search(self, query: str):
        """Trigger a search.  Called by MainWindow when user submits."""
        if not query:
            self._clear_results()
            self._query_label.setVisible(False)
            return
        if query == self._current_query:
            return

        self._current_query = query
        self._query_label.setText(f"Resultados para \"{query}\"")
        self._query_label.setVisible(True)
        await self._do_search(query)

    @asyncSlot()
    async def _do_search(self, query: str):
        if not self.yt:
            return
        try:
            self._clear_results()
            self._results_layout.addWidget(SkeletonListLoader(row_count=6))
            
            try:
                from doremi.db.repository import DownloadRepository
                dl_repo = DownloadRepository()
                downloads = await dl_repo.get_downloads()
                self.downloaded_playlist_ids = {d.parent_playlist_id for d in downloads if d.parent_playlist_id}
            except Exception as e:
                logger.debug(f"Error fetching downloads: {e}")
                self.downloaded_playlist_ids = set()

            self._results_by_cat = {}
            await self._fetch_category_results(query, self._active_category)
        except Exception as e:
            logger.error(f"Search error: {e}")
            self._clear_results()
            self._results_layout.addWidget(ErrorStateWidget(
                "No se pudo realizar la búsqueda",
                retry_callback=lambda: asyncio.ensure_future(self._do_search(query)),
            ))

    async def _fetch_category_results(self, query: str, category: str):
        # Fetch liked ids to display the correct liked state
        try:
            from doremi.db.repository import SongRepository
            repo = SongRepository()
            self.liked_video_ids = await repo.get_liked_video_ids()
        except Exception as e:
            logger.debug(f"Error fetching liked video ids: {e}")
            self.liked_video_ids = set()

        if category in self._results_by_cat:
            self._render_filtered()
            return

        self._clear_results()
        self._results_layout.addWidget(SkeletonListLoader(row_count=6))

        try:
            yt_filter = {
                "song": "songs",
                "album": "albums",
                "playlist": "playlists"
            }.get(category, None)

            results = await self.yt.search(query, filter=yt_filter, limit=40)
            import shiboken6
            if not shiboken6.isValid(self):
                return
            self._results_by_cat[category] = results or []
            self._render_filtered()
        except Exception as e:
            import shiboken6
            if not shiboken6.isValid(self):
                return
            logger.error(f"Error fetching results for {category}: {e}")
            self._clear_results()
            self._results_layout.addWidget(ErrorStateWidget(
                "No se pudieron cargar los resultados",
                retry_callback=lambda: asyncio.ensure_future(self._fetch_category_results(query, category)),
            ))

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _clear_results(self):
        if hasattr(self, '_category_widgets'):
            for widget in self._category_widgets.values():
                widget.deleteLater()
            self._category_widgets.clear()
            
        self._category_grid_layouts.clear()
        self._category_cards.clear()
        self._category_columns.clear()
        
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _render_filtered(self):
        # Remove any SkeletonListLoader from layout
        for i in range(self._results_layout.count()):
            item = self._results_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), SkeletonListLoader):
                w = item.widget()
                self._results_layout.removeWidget(w)
                w.deleteLater()
                break

        cat = self._active_category

        # Hide all other category widgets
        for c, widget in self._category_widgets.items():
            if c != cat:
                widget.hide()

        # If already created, just show it and return
        if cat in self._category_widgets:
            self._category_widgets[cat].show()
            if cat != "song":
                self._recalculate_grid()
            return

        # Otherwise, create it!
        cat_widget = QWidget()
        cat_widget.setStyleSheet("background: transparent;")
        cat_layout = QVBoxLayout(cat_widget)
        cat_layout.setContentsMargins(0, 0, 0, 0)
        cat_layout.setSpacing(16)

        filtered = self._results_by_cat.get(cat, [])

        if not filtered:
            from doremi.ui.design import tokens
            empty = QLabel("No se encontraron resultados en esta categoría")
            empty.setFont(QFont("Inter", 13))
            empty.setStyleSheet(f" padding: 32px; background: transparent;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cat_layout.addWidget(empty)
            cat_layout.addStretch()
        elif cat == "song":
            # Main Split Screen Widget
            split_widget = QWidget()
            split_layout = QHBoxLayout(split_widget)
            split_layout.setContentsMargins(24, 0, 24, 0)
            split_layout.setSpacing(24)

            # Left Column (Resultado Principal)
            left_col = QVBoxLayout()
            left_col.setSpacing(12)
            left_col.setContentsMargins(0, 0, 0, 0)
            
            from doremi.ui.design import tokens
            lbl_top = QLabel("Resultado principal")
            lbl_top.setFont(QFont("Inter", 14, QFont.Weight.Bold))
            lbl_top.setStyleSheet(f"color: {tokens.CURRENT.text_primary}; background: transparent;")
            left_col.addWidget(lbl_top)

            top = filtered[0]
            video_id = top.get("videoId", "")
            title = top.get("title", "Unknown")
            artists = top.get("artists", [])
            artist_str = (
                ", ".join([a.get("name", "") for a in artists])
                if isinstance(artists, list)
                else str(artists)
            )
            thumbnails = top.get("thumbnails", [])
            thumb_url = thumbnails[-1].get("url", "") if thumbnails else ""
            rt = top.get("resultType", "song")
            type_label = {"song": "Canción", "video": "Video", "": "Canción"}.get(rt, "Canción")

            top_card = _TopResultCard(
                title=title,
                artist=artist_str,
                result_type=type_label,
                thumbnail_url=thumb_url,
                on_play=lambda: self._handle_play(video_id, title, artists, thumb_url, 
                    int(top.get("duration", 0)) * 1000 if isinstance(top.get("duration"), (int, float)) else
                    (lambda d: (lambda p: (int(p[0])*60+int(p[1]))*1000 if len(p)==2 else 0)(d.split(":")) if isinstance(d,str) else 0)(top.get("duration"))) if video_id else None,
                video_id=video_id
            )
            top_card.download_requested.connect(lambda *a: self.download_requested.emit(*a))
            top_card.play_next_requested.connect(lambda *a: self.play_next_requested.emit(*a))
            top_card.add_to_queue_requested.connect(lambda *a: self.add_to_queue_requested.emit(*a))
            top_card.add_to_playlist_requested.connect(lambda *a: self.add_to_playlist_requested.emit(*a))
            top_card.delete_download_requested.connect(lambda *a: self.delete_download_requested.emit(*a))
            left_col.addWidget(top_card)
            left_col.addStretch()
            split_layout.addLayout(left_col)

            # Right Column (Canciones)
            right_col = QVBoxLayout()
            right_col.setSpacing(8)
            right_col.setContentsMargins(0, 0, 0, 0)

            lbl_songs = QLabel("Canciones principales")
            lbl_songs.setFont(QFont("Inter", 14, QFont.Weight.Bold))
            lbl_songs.setStyleSheet(f"color: {tokens.CURRENT.text_primary}; background: transparent;")
            right_col.addWidget(lbl_songs)

            songs_to_render = filtered[1:5] if len(filtered) > 1 else []
            for item in songs_to_render:
                card = self._make_card(item, "song")
                if card:
                    right_col.addWidget(card)
            right_col.addStretch()
            split_layout.addLayout(right_col, stretch=1)

            cat_layout.addWidget(split_widget)

            # Rest of the songs listed below in normal list
            remaining = filtered[5:]
            if remaining:
                lbl_others = QLabel("Más canciones")
                lbl_others.setFont(QFont("Inter", 14, QFont.Weight.Bold))
                lbl_others.setStyleSheet(f"color: {tokens.CURRENT.text_primary}; background: transparent; padding-left: 24px; padding-top: 24px;")
                cat_layout.addWidget(lbl_others)
                
                for item in remaining:
                    card = self._make_card(item, "song")
                    if card:
                        # Extra margin for clean visual alignment
                        card_wrapper = QWidget()
                        card_wrapper.setStyleSheet("background: transparent;")
                        card_lay = QHBoxLayout(card_wrapper)
                        card_lay.setContentsMargins(16, 0, 16, 0)
                        card_lay.addWidget(card)
                        cat_layout.addWidget(card_wrapper)
            
            cat_layout.addStretch()
        else:
            # Multi-column grid layout for album/artist/playlist
            grid_widget = QWidget()
            grid_widget.setContentsMargins(24, 0, 24, 0)
            grid_layout = QGridLayout(grid_widget)
            grid_layout.setContentsMargins(0, 0, 0, 0)
            grid_layout.setHorizontalSpacing(16)
            grid_layout.setVerticalSpacing(16)
            
            cat_layout.addWidget(grid_widget)
            
            # Pre-create all cards exactly once for this category results fetch
            category_cards = []
            for item in filtered:
                card = self._make_card(item, cat)
                if card:
                    category_cards.append(card)

            self._category_grid_layouts[cat] = grid_layout
            self._category_cards[cat] = category_cards
            self._category_columns[cat] = 0

            # Recalculate and arrange the cards
            self._recalculate_grid()
            cat_layout.addStretch()

        self._results_layout.addWidget(cat_widget)
        self._category_widgets[cat] = cat_widget

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._recalculate_grid()

    def _recalculate_grid(self):
        cat = self._active_category
        if cat == "song":
            return
            
        grid_layout = self._category_grid_layouts.get(cat)
        cards = self._category_cards.get(cat)
        if not grid_layout or not cards:
            return
            
        width = self.width() or 800
        # Card width is 168px + 16px spacing = ~184px
        columns = max(2, width // 184)
        
        # Performance optimization: only rebuild the grid if column count actually changed!
        if self._category_columns.get(cat, 0) == columns:
            return
        self._category_columns[cat] = columns

        # Remove widgets from grid without deleting/destroying them
        while grid_layout.count():
            grid_layout.takeAt(0)

        # Re-add existing widgets to layout at new row and column positions
        for idx, card in enumerate(cards):
            grid_layout.addWidget(card, idx // columns, idx % columns)

    def _make_card(self, item: dict, cat: str) -> QWidget | None:
        thumbnails = item.get("thumbnails", [])
        thumb_url = thumbnails[-1].get("url", "") if thumbnails else ""

        if cat == "song":
            video_id = item.get("videoId", "")
            if not video_id:
                return None
            title = item.get("title", "Unknown")
            artists = item.get("artists", [])
            artist_names = (
                ", ".join([a.get("name", "") for a in artists])
                if isinstance(artists, list)
                else str(artists)
            )
            duration = item.get("duration", 0)
            if isinstance(duration, (int, float)) and duration > 0:
                minutes = int(duration) // 60
                seconds = int(duration) % 60
                duration_str = f"{minutes}:{seconds:02d}"
            elif isinstance(duration, str):
                duration_str = duration
            else:
                duration_str = ""
            
            # Extract duration_ms for queue
            dur_ms = 0
            if isinstance(duration, (int, float)) and duration > 0:
                dur_ms = int(duration) * 1000
            elif isinstance(duration, str):
                try:
                    dur_str = str(duration)
                    parts = dur_str.split(':')
                    if len(parts) == 2:
                        dur_ms = (int(parts[0]) * 60 + int(parts[1])) * 1000
                    elif len(parts) == 3:
                        dur_ms = (int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])) * 1000
                except (ValueError, IndexError):
                    pass

            liked_ids = getattr(self, "liked_video_ids", set())
            is_liked = video_id in liked_ids
            card = SongCard(
                title=title,
                artist=artist_names,
                duration=duration_str,
                thumbnail_url=thumb_url,
                on_play=lambda: self._handle_play(video_id, title, artists, thumb_url, dur_ms),
                video_id=video_id,
                is_liked=is_liked
            )
            card.download_requested.connect(lambda *a: self.download_requested.emit(*a))
            card.play_next_requested.connect(lambda *a: self.play_next_requested.emit(*a))
            card.add_to_queue_requested.connect(lambda *a: self.add_to_queue_requested.emit(*a))
            card.like_requested.connect(lambda *a: self.like_requested.emit(*a))
            card.add_to_playlist_requested.connect(lambda *a: self.add_to_playlist_requested.emit(*a))
            card.delete_download_requested.connect(lambda *a: self.delete_download_requested.emit(*a))
            return card

        elif cat == "album":
            title = item.get("title", "Unknown")
            artists = item.get("artists", [])
            artist_names = (
                ", ".join([a.get("name", "") for a in artists])
                if isinstance(artists, list)
                else str(artists)
            )
            card = AlbumCard(title=title, artist=artist_names, thumbnail_url=thumb_url)
            browse_id = item.get("browseId", "")
            if browse_id and self.on_navigate:
                card.clicked.connect(partial(self.on_navigate, f"album?id={browse_id}"))
            return card

        elif cat == "artist":
            name = item.get("title", item.get("artist", item.get("name", "Unknown")))
            card = ArtistCard(name=name, thumbnail_url=thumb_url)
            browse_id = item.get("browseId", "")
            if browse_id and self.on_navigate:
                card.clicked.connect(partial(self.on_navigate, f"artist?id={browse_id}"))
            return card

        elif cat == "playlist":
            title = item.get("title", "Unknown")
            playlist_id = item.get("playlistId", "")
            card = PlaylistCard(
                title=title,
                thumbnail_url=thumb_url,
                is_downloaded=playlist_id in getattr(self, "downloaded_playlist_ids", set())
            )
            if playlist_id and self.on_navigate:
                card.clicked.connect(partial(self.on_navigate, f"playlist?id={playlist_id}"))
            return card

        return None

    async def load(self):
        pass
