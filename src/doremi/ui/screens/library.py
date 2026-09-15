from functools import partial
import asyncio
from loguru import logger

from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QHBoxLayout, 
    QPushButton, QGridLayout, QGraphicsOpacityEffect, QGraphicsDropShadowEffect,
    QLineEdit, QComboBox
)

from doremi.ui.design.fonts import AppFont
from doremi.ui.widgets.song_card import SongCard
from doremi.ui.widgets.album_card import AlbumCard
from doremi.ui.widgets.artist_card import ArtistCard
from doremi.ui.widgets.playlist_card import PlaylistCard
from doremi.ui.widgets.error_state import ErrorStateWidget
from doremi.ui.widgets.skeleton_loader import SkeletonListLoader
from doremi.ui.widgets.load_more import PaginatorFooter
from doremi.db.repository import DownloadRepository, SongRepository


class LibraryScreen(QWidget):
    download_requested = Signal(str, str, str, str)  # video_id, title, artist, thumb
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    add_to_playlist_requested = Signal(str, str) # video_id, title
    like_requested = Signal(str, object)
    delete_download_requested = Signal(str)
    artist_clicked = Signal(str)
    album_clicked = Signal(str)

    def __init__(self, yt_client, on_play_song, on_navigate=None):
        super().__init__()
        self.yt = yt_client
        self.on_play_song = on_play_song
        self.on_navigate = on_navigate
        self._current_tab = "songs"
        self._current_tab_task = None
        self._currently_rendered_tab = None
        self._library_cache = {}
        self._library_cache_time = {}
        self._library_filter = ""
        self._library_sort = "recent"
        self._build_ui()

    def _connect_card_signals(self, card):
        """Wire up all context-menu signals from a SongCard."""
        card.download_requested.connect(lambda *a: self.download_requested.emit(*a))
        card.play_next_requested.connect(lambda *a: self.play_next_requested.emit(*a))
        card.add_to_queue_requested.connect(lambda *a: self.add_to_queue_requested.emit(*a))
        card.add_to_playlist_requested.connect(lambda *a: self.add_to_playlist_requested.emit(*a))
        card.like_requested.connect(lambda *a: self.like_requested.emit(*a))
        card.delete_download_requested.connect(lambda *a: self.delete_download_requested.emit(*a))
        if hasattr(card, "artist_clicked"):
            card.artist_clicked.connect(lambda *a: self.artist_clicked.emit(*a))
        if hasattr(card, "album_clicked"):
            card.album_clicked.connect(lambda *a: self.album_clicked.emit(*a))

    def _handle_download(self, vid, title, artist, thumb):
        self.download_requested.emit(vid, title, artist, thumb)

    def _handle_play(self, video_id, title, artists, thumbnail_url, duration_ms=0):
        try:
            if self.on_play_song:
                self.on_play_song(video_id, title, artists, "", duration_ms, thumbnail_url)
        except Exception as e:
            logger.error(f"Play error: {e}")

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)

        self.header_label = QLabel("Biblioteca")
        self.header_label.setFont(AppFont.display(24))
        layout.addWidget(self.header_label)

        # Tab container
        self.tabs = QWidget()
        self.tabs.setStyleSheet("background: transparent; border: none;")
        tabs_layout = QHBoxLayout(self.tabs)
        tabs_layout.setContentsMargins(0, 8, 0, 8)
        tabs_layout.setSpacing(12)

        tab_names = [
            ("songs", "Favoritas"),
            ("albums", "Álbumes"),
            ("artists", "Artistas"),
            ("playlists", "Playlists"),
        ]

        for key, name in tab_names:
            btn = QPushButton(name)
            btn.setObjectName(f"tab_{key}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            
            # Apply styling
            self._apply_tab_style(btn, key == self._current_tab)
            
            btn.clicked.connect(lambda _, k=key: self._switch_tab(k))
            tabs_layout.addWidget(btn)

        tabs_layout.addStretch()
        layout.addWidget(self.tabs)

        filters = QWidget()
        filters.setStyleSheet("background: transparent; border: none;")
        filters_layout = QHBoxLayout(filters)
        filters_layout.setContentsMargins(0, 0, 0, 8)
        filters_layout.setSpacing(10)

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Buscar en biblioteca")
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.textChanged.connect(self._on_library_filter_changed)
        filters_layout.addWidget(self.filter_input, stretch=1)

        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Recientes", "recent")
        self.sort_combo.addItem("Título", "title")
        self.sort_combo.addItem("Artista", "artist")
        self.sort_combo.currentIndexChanged.connect(self._on_library_sort_changed)
        filters_layout.addWidget(self.sort_combo)
        layout.addWidget(filters)
        self._update_filter_styles()

        self.content = QScrollArea()
        self.content.setWidgetResizable(True)
        self.content.setStyleSheet("background: transparent; border: none;")

        self.content_widget = QWidget()
        self._content_wrapper_layout = QVBoxLayout(self.content_widget)
        self._content_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(24, 0, 24, 112)
        self.content_layout.setSpacing(16)
        
        self._content_wrapper_layout.addLayout(self.content_layout)
        self._content_wrapper_layout.addStretch()

        self.content.setWidget(self.content_widget)
        layout.addWidget(self.content)

        # Create Floating Action Button (FAB) for playlists
        from doremi.ui.design.icons import Icon
        self.fab = QPushButton(Icon.get("playlist_add"), self)
        self.fab.setFixedSize(56, 56)
        self.fab.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fab.setToolTip("Crear Playlist")
        self.fab.clicked.connect(self._on_create_playlist_clicked)
        
        # Style the FAB
        self._update_fab_style()
        
        # Add elevation/shadow to FAB
        shadow = QGraphicsDropShadowEffect(self.fab)
        shadow.setBlurRadius(16)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.fab.setGraphicsEffect(shadow)
        
        # Hidden by default, shown only when playlists tab is active
        self.fab.hide()
        
        

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "fab"):
            # Position above floating mini player (88px height + 24px padding = 112px from bottom)
            self.fab.move(self.width() - self.fab.width() - 24, self.height() - self.fab.height() - 112)

    def _switch_tab(self, key):
        if key == self._current_tab and getattr(self, "_currently_rendered_tab", None) == key:
            return

        self._current_tab = key

        # Update button styles
        self._update_tab_styles()

        # Toggle FAB visibility depending on selected tab
        if key == "playlists":
            self.fab.show()
            self.fab.raise_()
        else:
            self.fab.hide()

        # Stop any running tab transitions
        if hasattr(self, "_tab_fade_anim") and self._tab_fade_anim:
            self._tab_fade_anim.stop()
        if hasattr(self, "_tab_fade_in_anim") and self._tab_fade_in_anim:
            self._tab_fade_in_anim.stop()

        # Start fade out of the content area
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        
        effect = self.content.graphicsEffect()
        if not effect or not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(self.content)
            self.content.setGraphicsEffect(effect)

        self._tab_fade_anim = QPropertyAnimation(effect, b"opacity", self)
        self._tab_fade_anim.setDuration(120)
        self._tab_fade_anim.setStartValue(effect.opacity())
        self._tab_fade_anim.setEndValue(0.0)
        self._tab_fade_anim.setEasingCurve(QEasingCurve.Type.InCubic)

        def on_fade_out_finished():
            if self._current_tab_task and not self._current_tab_task.done():
                self._current_tab_task.cancel()
            self._current_tab_task = asyncio.create_task(self._load_tab(key))

            # Start fade in
            self._tab_fade_in_anim = QPropertyAnimation(effect, b"opacity", self)
            self._tab_fade_in_anim.setDuration(180)
            self._tab_fade_in_anim.setStartValue(0.0)
            self._tab_fade_in_anim.setEndValue(1.0)
            self._tab_fade_in_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

            def on_fade_in_finished():
                self.content.setGraphicsEffect(None)

            self._tab_fade_in_anim.finished.connect(on_fade_in_finished)
            self._tab_fade_in_anim.start()

        self._tab_fade_anim.finished.connect(on_fade_out_finished)
        self._tab_fade_anim.start()

    def _on_library_filter_changed(self, text: str) -> None:
        self._library_filter = text.strip().lower()
        self._reload_current_tab_for_filters()

    def _on_library_sort_changed(self) -> None:
        self._library_sort = self.sort_combo.currentData() or "recent"
        self._reload_current_tab_for_filters()

    def _reload_current_tab_for_filters(self) -> None:
        self._currently_rendered_tab = None
        if self._current_tab_task and not self._current_tab_task.done():
            self._current_tab_task.cancel()
        self._current_tab_task = asyncio.create_task(self._load_tab(self._current_tab))

    def _matches_library_filter(self, *values) -> bool:
        if not self._library_filter:
            return True
        haystack = " ".join(str(value or "").lower() for value in values)
        return self._library_filter in haystack

    def _sort_items(self, items: list, title_getter, artist_getter=None) -> list:
        if self._library_sort == "title":
            return sorted(items, key=lambda item: str(title_getter(item) or "").lower())
        if self._library_sort == "artist" and artist_getter:
            return sorted(items, key=lambda item: str(artist_getter(item) or "").lower())
        return items

    async def load(self):
        import time
        cache_age = time.time() - self._library_cache_time.get(self._current_tab, 0)
        
        # ── OBTENCIÓN INSTANTÁNEA SI YA ESTÁ PINTADO Y ES RECIENTE ────────────────
        if (
            getattr(self, "_currently_rendered_tab", None) == self._current_tab
            and self._current_tab in self._library_cache
            and cache_age < 300
        ):
            logger.debug(f"El tab '{self._current_tab}' ya está pintado y es reciente (< 300s). Evitando recarga.")
            return

        if self._current_tab_task and not self._current_tab_task.done():
            self._current_tab_task.cancel()
        self._current_tab_task = asyncio.create_task(self._load_tab(self._current_tab))
        try:
            await self._current_tab_task
        except asyncio.CancelledError:
            if self._current_tab_task and not self._current_tab_task.done():
                self._current_tab_task.cancel()
            raise

    async def _load_tab(self, tab):
        import time
        cache_age = time.time() - self._library_cache_time.get(tab, 0)

        # ── OBTENCIÓN INSTANTÁNEA SI YA ESTÁ PINTADO Y ES RECIENTE ────────────────
        if (
            getattr(self, "_currently_rendered_tab", None) == tab
            and tab in self._library_cache
            and cache_age < 300
        ):
            logger.debug(f"El tab '{tab}' ya está renderizado y fresco. Evitando recarga.")
            return

        # 1. Clear content and show the skeleton loader
        self._clear_content()
        self.content_layout.addWidget(SkeletonListLoader(row_count=7))

        try:
            dl_repo = DownloadRepository()
            downloads = await dl_repo.get_downloads()
            self.downloaded_playlist_ids = {d.parent_playlist_id for d in downloads if d.parent_playlist_id}
        except Exception as e:
            logger.debug(f"Error fetching downloads: {e}")
            self.downloaded_playlist_ids = set()

        if not self.yt or not self.yt.is_authenticated:
            self._clear_content()
            from doremi.ui.design import tokens
            msg = QLabel("Inicia sesión para ver tu biblioteca")
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg.setObjectName("libraryEmptyMessage")
            self.content_layout.addWidget(msg)
            self.content_layout.addStretch()
            self._currently_rendered_tab = tab
            return

        try:
            from doremi.ui.design import tokens

            # 2. Perform async fetch or load from cache while skeleton is active
            if tab == "songs":
                liked_songs_data = None
                if self.yt and self.yt.is_authenticated:
                    if tab in self._library_cache and cache_age < 300:
                        liked_songs_data = self._library_cache[tab]
                    else:
                        liked_songs_data = await self.yt.get_liked_songs(limit=50)
                        self._library_cache[tab] = liked_songs_data
                        self._library_cache_time[tab] = time.time()
                
                repo = SongRepository()
                db_songs = await repo.get_liked_songs()
                
                # 3. Fetch completed: clear loader and render real data
                self._clear_content()
                
                tracks = liked_songs_data.get('tracks', []) if liked_songs_data else []
                
                # Combine local database liked songs and YouTube Music liked songs
                seen_video_ids = set()
                combined_tracks = []

                # Add local database liked songs first so they appear instantly
                for song in db_songs:
                    if song.video_id not in seen_video_ids:
                        seen_video_ids.add(song.video_id)
                        combined_tracks.append({
                            'videoId': song.video_id,
                            'title': song.title,
                            'artist': song.artist,
                            'duration': self._format_duration(song.duration_ms),
                            'thumbnail_url': song.thumbnail_url or "",
                            'is_liked': True
                        })

                # Add YouTube Music liked songs
                for track in tracks:
                    vid = track.get('videoId')
                    if vid and vid not in seen_video_ids:
                        seen_video_ids.add(vid)
                        artists = track.get('artists', [])
                        artist_names = ", ".join([a.get('name', '') for a in artists]) if isinstance(artists, list) and artists else 'Unknown'
                        thumbnails = track.get('thumbnails', [])
                        thumbnail_url = thumbnails[-1].get('url', '') if thumbnails else ''
                        combined_tracks.append({
                            'videoId': vid,
                            'title': track.get('title', 'Unknown'),
                            'artist': artist_names,
                            'duration': track.get('duration', ''),
                            'thumbnail_url': thumbnail_url,
                            'is_liked': True
                        })

                combined_tracks = [
                    track for track in combined_tracks
                    if self._matches_library_filter(track.get('title'), track.get('artist'), track.get('album'))
                ]
                combined_tracks = self._sort_items(
                    combined_tracks,
                    lambda track: track.get('title'),
                    lambda track: track.get('artist'),
                )

                if combined_tracks:
                    header = QLabel("Canciones que te gustan")
                    header.setFont(AppFont.heading(16))
                    header.setObjectName("libraryHeader")
                    self.content_layout.addWidget(header)
                    
                    self._library_current_tracks = combined_tracks
                    self._library_render_idx = 0
                    
                    from doremi.ui.widgets.load_more import PaginatorFooter
                    self._songs_paginator = PaginatorFooter()
                    self._songs_paginator.load_requested.connect(self._on_songs_load_more)
                    
                    self._render_songs_chunk(20)
                else:
                    msg = QLabel("No tienes canciones guardadas\n\nLas canciones que reproduzcas aparecerán aquí")
                    msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    msg.setObjectName("libraryEmptyMessage")
                    self.content_layout.addWidget(msg)
            elif tab == "albums":
                if tab in self._library_cache and cache_age < 300:
                    albums = self._library_cache[tab]
                else:
                    albums = await self.yt.get_library_albums()
                    self._library_cache[tab] = albums
                    self._library_cache_time[tab] = time.time()
                self._clear_content()

                if not albums:
                    msg = QLabel("No tienes álbumes guardados")
                    msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    msg.setObjectName("libraryEmptyMessage")
                    self.content_layout.addWidget(msg)
                else:
                    albums = [
                        album for album in albums
                        if self._matches_library_filter(
                            album.get("title"),
                            ", ".join(a.get("name", "") for a in album.get("artists", []) if isinstance(a, dict))
                            if isinstance(album.get("artists", []), list)
                            else album.get("artists", ""),
                            album.get("year", ""),
                        )
                    ]
                    albums = self._sort_items(
                        albums,
                        lambda album: album.get("title"),
                        lambda album: ", ".join(a.get("name", "") for a in album.get("artists", []) if isinstance(a, dict))
                        if isinstance(album.get("artists", []), list)
                        else album.get("artists", ""),
                    )
                    if not albums:
                        msg = QLabel("No hay álbumes que coincidan con la búsqueda")
                        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        msg.setObjectName("libraryEmptyMessage")
                        self.content_layout.addWidget(msg)
                        self._currently_rendered_tab = tab
                        self.content_layout.addStretch()
                        self._fade_in_content()
                        return
                    header = QLabel("Tus Álbumes")
                    header.setFont(QFont("Inter", 16, QFont.Weight.Bold))
                    header.setObjectName("libraryHeader")
                    self.content_layout.addWidget(header)

                    grid = QGridLayout()
                    grid.setSpacing(16)
                    for col in range(4):
                        grid.setColumnMinimumWidth(col, 178)
                    
                    chunk_size = 4
                    for i, album in enumerate(albums):
                        title = album.get("title", "Unknown")
                        artists = album.get("artists", [])
                        artist_names = ", ".join([a.get('name', '') for a in artists]) if isinstance(artists, list) else str(artists)
                        year = album.get("year", "")
                        thumbnails = album.get('thumbnails', [])
                        thumbnail_url = thumbnails[-1].get('url', '') if thumbnails else ''
                        browse_id = album.get('browseId', '')
                        
                        card = AlbumCard(title=title, artist=artist_names, year=year, thumbnail_url=thumbnail_url)
                        if browse_id and self.on_navigate:
                            card.clicked.connect(partial(self.on_navigate, f"album?id={browse_id}"))
                        
                        grid.addWidget(card, i // 4, i % 4, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                        grid.setRowMinimumHeight(i // 4, 228)

                        if (i + 1) % chunk_size == 0:
                            await asyncio.sleep(0)

                    self.content_layout.addLayout(grid)

            elif tab == "artists":
                if not hasattr(self, '_artist_limit'):
                    self._artist_limit = 20

                if tab in self._library_cache and cache_age < 300 and len(self._library_cache[tab]) >= self._artist_limit:
                    artists = self._library_cache[tab][:self._artist_limit]
                else:
                    artists = await self.yt.get_library_artists(limit=self._artist_limit)
                    self._library_cache[tab] = artists
                    self._library_cache_time[tab] = time.time()
                self._clear_content()

                if not artists:
                    msg = QLabel("No sigues a ningún artista")
                    msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    msg.setObjectName("libraryEmptyMessage")
                    self.content_layout.addWidget(msg)
                else:
                    artists = [
                        artist for artist in artists
                        if self._matches_library_filter(artist.get("artist"), artist.get("browseId"))
                    ]
                    artists = self._sort_items(
                        artists,
                        lambda artist: artist.get("artist"),
                        lambda artist: artist.get("artist"),
                    )
                    if not artists:
                        msg = QLabel("No hay artistas que coincidan con la búsqueda")
                        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        msg.setObjectName("libraryEmptyMessage")
                        self.content_layout.addWidget(msg)
                        self._currently_rendered_tab = tab
                        self.content_layout.addStretch()
                        self._fade_in_content()
                        return
                    header = QLabel("Tus Artistas")
                    header.setFont(QFont("Inter", 16, QFont.Weight.Bold))
                    header.setObjectName("libraryHeader")
                    self.content_layout.addWidget(header)

                    grid = QGridLayout()
                    grid.setSpacing(16)
                    for col in range(4):
                        grid.setColumnMinimumWidth(col, 178)

                    chunk_size = 4
                    for i, artist in enumerate(artists):
                        name = artist.get("artist", "Unknown")
                        thumbnails = artist.get('thumbnails', [])
                        thumbnail_url = thumbnails[-1].get('url', '') if thumbnails else ''
                        browse_id = artist.get('browseId', '')
                        
                        card = ArtistCard(name=name, thumbnail_url=thumbnail_url)
                        if browse_id and self.on_navigate:
                            card.clicked.connect(partial(self.on_navigate, f"artist?id={browse_id}"))
                        
                        grid.addWidget(card, i // 4, i % 4, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                        grid.setRowMinimumHeight(i // 4, 220)

                        if (i + 1) % chunk_size == 0:
                            await asyncio.sleep(0)

                    self.content_layout.addLayout(grid)
                    
                    if len(artists) >= self._artist_limit:
                        from doremi.ui.widgets.load_more import PaginatorFooter
                        self._artist_paginator = PaginatorFooter()
                        self._artist_paginator.load_requested.connect(self._on_artists_load_more)
                        self.content_layout.addWidget(self._artist_paginator)
                        self._artist_paginator.set_state("button")

            elif tab == "playlists":
                if tab in self._library_cache and cache_age < 300:
                    playlists = self._library_cache[tab]
                else:
                    playlists = await self.yt.get_library_playlists()
                    self._library_cache[tab] = playlists
                    self._library_cache_time[tab] = time.time()
                self._clear_content()

                header = QLabel("Tus Playlists")
                header.setFont(QFont("Inter", 16, QFont.Weight.Bold))
                header.setObjectName("libraryHeader")
                self.content_layout.addWidget(header)

                if not playlists:
                    msg = QLabel("No tienes playlists")
                    msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    msg.setObjectName("libraryEmptyMessage")
                    self.content_layout.addWidget(msg)
                else:
                    playlists = [
                        playlist for playlist in playlists
                        if self._matches_library_filter(playlist.get("title"), playlist.get("count"))
                    ]
                    playlists = self._sort_items(
                        playlists,
                        lambda playlist: playlist.get("title"),
                    )
                    if not playlists:
                        msg = QLabel("No hay playlists que coincidan con la búsqueda")
                        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        msg.setObjectName("libraryEmptyMessage")
                        self.content_layout.addWidget(msg)
                        self._currently_rendered_tab = tab
                        self.content_layout.addStretch()
                        self._fade_in_content()
                        return
                    grid = QGridLayout()
                    grid.setSpacing(16)
                    for col in range(4):
                        grid.setColumnMinimumWidth(col, 178)

                    chunk_size = 4
                    for i, playlist in enumerate(playlists):
                        title = playlist.get("title", "Unknown")
                        count = playlist.get("count", "")
                        desc = f"{count} canciones" if count else ""
                        thumbnails = playlist.get('thumbnails', [])
                        thumbnail_url = thumbnails[-1].get('url', '') if thumbnails else ''
                        playlist_id = playlist.get('playlistId', '')
                        
                        card = PlaylistCard(
                            title=title,
                            description=desc,
                            thumbnail_url=thumbnail_url,
                            is_downloaded=playlist_id in getattr(self, "downloaded_playlist_ids", set())
                        )
                        if playlist_id and self.on_navigate:
                            card.clicked.connect(partial(self.on_navigate, f"playlist?id={playlist_id}"))
                        
                        grid.addWidget(card, i // 4, i % 4, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                        grid.setRowMinimumHeight(i // 4, 228)

                        if (i + 1) % chunk_size == 0:
                            await asyncio.sleep(0)

                    self.content_layout.addLayout(grid)

        except Exception as e:
            logger.error(f"Error loading {tab}: {e}")
            self._clear_content()
            self.content_layout.addWidget(ErrorStateWidget(
                "No se pudo cargar la biblioteca",
                retry_callback=lambda: asyncio.ensure_future(self.load()),
            ))

        self._currently_rendered_tab = tab
        self.content_layout.addStretch()
        self._fade_in_content()

        # Bring FAB to top after updating layout to prevent overlap issues
        if hasattr(self, "fab") and self.fab.isVisible():
            self.fab.raise_()

    def _on_songs_load_more(self):
        if hasattr(self, '_library_current_tracks') and hasattr(self, '_library_render_idx'):
            self._render_songs_chunk(20)

    def _on_artists_load_more(self):
        if hasattr(self, '_artist_limit'):
            self._artist_limit += 20
        if "artists" in self._library_cache:
            del self._library_cache["artists"]
        if hasattr(self, "_current_tab_task") and self._current_tab_task and not self._current_tab_task.done():
            self._current_tab_task.cancel()
        self._current_tab_task = asyncio.create_task(self._load_tab("artists"))
            
    def _render_songs_chunk(self, chunk_size=20):
        if not hasattr(self, "_library_current_tracks") or not self._library_current_tracks:
            return
            
        if hasattr(self, "_songs_paginator"):
            self.content_layout.removeWidget(self._songs_paginator)
            self._songs_paginator.setParent(None)
            
        tracks = self._library_current_tracks
        start = self._library_render_idx
        end = min(start + chunk_size, len(tracks))
        
        for i in range(start, end):
            track = tracks[i]
            # Parse duration string to ms
            dur_ms = 0
            dur_str = track.get('duration', '')
            if dur_str:
                try:
                    parts = str(dur_str).split(':')
                    if len(parts) == 2:
                        dur_ms = (int(parts[0]) * 60 + int(parts[1])) * 1000
                    elif len(parts) == 3:
                        dur_ms = (int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])) * 1000
                except (ValueError, IndexError):
                    pass
            card = SongCard(
                title=track['title'],
                artist=track['artist'],
                duration=track['duration'],
                thumbnail_url=track['thumbnail_url'],
                on_play=partial(self._handle_play, track['videoId'], track['title'], track['artist'], track['thumbnail_url'], dur_ms),
                video_id=track['videoId'],
                is_liked=track['is_liked'],
                album=track.get('album', ''),
            )
            self._connect_card_signals(card)
            self.content_layout.addWidget(card)
            
        self._library_render_idx = end
        
        if self._library_render_idx < len(tracks):
            self.content_layout.addWidget(self._songs_paginator)
            self._songs_paginator.set_state("button")
        
        if start == 0:
            self._fade_in_content()

    def _on_songs_load_more(self):
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, lambda: self._render_songs_chunk(20))

    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                sub_layout = item.layout()
                self._clear_sub_layout(sub_layout)
                sub_layout.deleteLater()

    def _clear_sub_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    sub_layout = item.layout()
                    self._clear_sub_layout(sub_layout)
                    sub_layout.deleteLater()

    def _fade_in_content(self):
        """Smooth fade-in animation when content finishes loading."""
        effect = QGraphicsOpacityEffect(self.content_widget)
        self.content_widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(300)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: self.content_widget.setGraphicsEffect(None))
        anim.start()

    def _show_no_auth_message(self):
        self.content_layout.addWidget(QLabel(""))
        msg = QLabel("Biblioteca no disponible.\nLa API de YouTube Music requiere autenticación.")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setObjectName("libraryEmptyMessage")
        self.content_layout.addWidget(msg)

    def _format_duration(self, ms):
        if not ms:
            return ""
        seconds = ms // 1000
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}:{secs:02d}"

    def _on_create_playlist_clicked(self):
        from PySide6.QtWidgets import QDialog, QLineEdit, QVBoxLayout, QHBoxLayout
        from PySide6.QtGui import QColor, QLinearGradient, QPainter, QBrush, QPen, QFont
        from PySide6.QtCore import Qt, QRect
        from doremi.ui.design import tokens
        from doremi.ui.design.icons import Icon
        from doremi.ui.design.fonts import AppFont
        from doremi.ui.design.animations import fade_in

        dialog = QDialog(self)
        dialog.setWindowTitle("Crear Nueva Playlist")
        dialog.setFixedSize(420, 340)
        dialog.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        shadow = QGraphicsDropShadowEffect(dialog)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 140))
        dialog.setGraphicsEffect(shadow)

        root = QWidget(dialog)
        root.setFixedSize(420, 340)
        root.setStyleSheet(f"""
            QWidget#createPlaylistRoot {{
                background: {tokens.CURRENT.bg_surface};
                border-radius: 16px;
            }}
        """)
        root.setObjectName("createPlaylistRoot")

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(120)
        header.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {tokens.CURRENT.accent},
                stop:1 {tokens.CURRENT.accent_bright});
            border-radius: 16px 16px 0 0;
        """)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(24, 20, 24, 16)

        icon_lbl = QLabel(Icon.get("playlist_add"))
        icon_lbl.setFont(Icon.font(48, filled=True))
        icon_lbl.setStyleSheet(f"color: {tokens.CURRENT.text_on_accent}; background: transparent;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        header_layout.addWidget(icon_lbl)

        title_lbl = QLabel("Crear Nueva Playlist")
        title_lbl.setFont(AppFont.heading(20))
        title_lbl.setStyleSheet(f"color: {tokens.CURRENT.text_on_accent}; background: transparent;")
        header_layout.addWidget(title_lbl)

        root_layout.addWidget(header)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 24, 24, 20)
        body_layout.setSpacing(16)

        title_input = QLineEdit()
        title_input.setPlaceholderText("Nombre de la playlist")
        title_input.setStyleSheet(f"""
            QLineEdit {{
                background: {tokens.CURRENT.bg_elevated};
                color: {tokens.CURRENT.text_primary};
                border: 1px solid {tokens.CURRENT.border};
                border-radius: 12px;
                padding: 14px 16px;
                font-size: 15px;
            }}
            QLineEdit:focus {{
                border: 2px solid {tokens.CURRENT.accent};
                padding: 13px 15px;
            }}
        """)
        body_layout.addWidget(title_input)

        desc_input = QLineEdit()
        desc_input.setPlaceholderText("Descripción (opcional)")
        desc_input.setStyleSheet(f"""
            QLineEdit {{
                background: {tokens.CURRENT.bg_elevated};
                color: {tokens.CURRENT.text_primary};
                border: 1px solid {tokens.CURRENT.border};
                border-radius: 12px;
                padding: 14px 16px;
                font-size: 15px;
            }}
            QLineEdit:focus {{
                border: 2px solid {tokens.CURRENT.accent};
                padding: 13px 15px;
            }}
        """)
        body_layout.addWidget(desc_input)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setFixedHeight(44)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {tokens.CURRENT.bg_high};
                color: {tokens.CURRENT.text_primary};
                border: none;
                border-radius: 12px;
                font-size: 14px;
                font-weight: bold;
                padding: 0 24px;
            }}
            QPushButton:hover {{
                background: {tokens.CURRENT.bg_elevated};
            }}
        """)
        btn_row.addWidget(cancel_btn)

        create_btn = QPushButton("Crear")
        create_btn.setFixedHeight(44)
        create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        create_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {tokens.CURRENT.accent},
                    stop:1 {tokens.CURRENT.accent_bright});
                color: {tokens.CURRENT.text_on_accent};
                border: none;
                border-radius: 12px;
                font-size: 14px;
                font-weight: bold;
                padding: 0 32px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {tokens.CURRENT.accent_bright},
                    stop:1 {tokens.CURRENT.accent});
            }}
        """)
        btn_row.addWidget(create_btn)
        body_layout.addLayout(btn_row)

        root_layout.addWidget(body)

        cancel_btn.clicked.connect(dialog.reject)
        create_btn.clicked.connect(dialog.accept)
        title_input.returnPressed.connect(dialog.accept)

        fade_in(root, 200)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            title = title_input.text().strip()
            desc = desc_input.text().strip()
            if title:
                asyncio.ensure_future(self._create_playlist_async(title, desc))

    async def _create_playlist_async(self, title: str, description: str):
        try:
            pid = await self.yt.create_playlist(title, description)
            if pid:
                # Reload the playlists tab to show the new one
                self._switch_tab("playlists")
        except Exception as e:
            logger.error(f"Error creating playlist: {e}")

    def _apply_tab_style(self, btn, active: bool) -> None:
        from doremi.ui.design import tokens
        from PySide6.QtGui import QColor
        accent = tokens.CURRENT.accent
        c = QColor(accent)
        r, g, b, _ = c.getRgb()
        if active:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba({r}, {g}, {b}, 0.15);
                    color: {accent};
                    padding: 8px 18px;
                    border: 1px solid rgba({r}, {g}, {b}, 0.3);
                    border-radius: 18px;
                    font-family: 'Inter';
                    font-weight: bold;
                    font-size: 13px;
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    
                    padding: 8px 18px;
                    border: 1px solid transparent;
                    border-radius: 18px;
                    font-family: 'Inter';
                    font-weight: 600;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background: {tokens.CURRENT.bg_elevated};
                    
                }}
            """)

    def _update_tab_styles(self) -> None:
        for btn in self.tabs.findChildren(QPushButton):
            key = btn.objectName().replace("tab_", "")
            self._apply_tab_style(btn, key == self._current_tab)

    def _update_fab_style(self) -> None:
        if not hasattr(self, 'fab'):
            return
        from doremi.ui.design import tokens
        from PySide6.QtGui import QColor
        accent = tokens.CURRENT.accent
        c = QColor(accent)
        bright_hex = c.lighter(125).name()
        dark_hex = c.darker(120).name()
        self.fab.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent};
                color: {tokens.CURRENT.text_on_accent};
                border: none;
                border-radius: 28px;
                font-family: 'Material Symbols Rounded';
                font-size: 26px;
                font-weight: normal;
            }}
            QPushButton:hover {{
                background-color: {bright_hex};
            }}
            QPushButton:pressed {{
                background-color: {dark_hex};
            }}
        """)

    def _update_filter_styles(self) -> None:
        if not hasattr(self, "filter_input"):
            return
        from doremi.ui.design import tokens
        self.filter_input.setStyleSheet(f"""
            QLineEdit {{
                background: {tokens.CURRENT.bg_surface};
                color: {tokens.CURRENT.text_primary};
                border: 1px solid {tokens.CURRENT.border};
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {tokens.CURRENT.accent};
            }}
        """)
        self.sort_combo.setStyleSheet(f"""
            QComboBox {{
                background: {tokens.CURRENT.bg_surface};
                color: {tokens.CURRENT.text_primary};
                border: 1px solid {tokens.CURRENT.border};
                border-radius: 8px;
                padding: 7px 12px;
                min-width: 128px;
            }}
            QComboBox:hover {{
                border-color: {tokens.CURRENT.accent};
            }}
        """)

    def invalidate_songs_cache(self) -> None:
        if hasattr(self, "_library_cache"):
            self._library_cache.pop("songs", None)
            self._library_cache_time.pop("songs", None)
        if getattr(self, "_currently_rendered_tab", None) == "songs":
            self._currently_rendered_tab = None


    def _apply_theme_styles(self) -> None:
        self._update_tab_styles()
        self._update_fab_style()
        self._update_filter_styles()
