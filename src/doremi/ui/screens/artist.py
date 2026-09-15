from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QPushButton, QGridLayout, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap, QColor, QPainterPath, QPainter
from functools import partial
from loguru import logger
import asyncio
from doremi.ui.widgets.song_card import SongCard
from doremi.ui.widgets.album_card import AlbumCard
from doremi.ui.widgets.artist_card import ArtistCard
from doremi.ui.widgets.error_state import ErrorStateWidget
from doremi.ui.widgets.empty_state import EmptyStateWidget
from doremi.ui.design.fonts import AppFont
from doremi.ui.design.icons import Icon
from doremi.ui.design import tokens
from doremi.utils.image_cache import ImageCache

_image_cache = ImageCache()


class ArtistScreen(QWidget):
    download_requested = Signal(str, str, str, str)
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    like_requested = Signal(str, object)
    add_to_playlist_requested = Signal(str, str)
    delete_download_requested = Signal(str)

    def __init__(self, yt_client, on_play_song, on_navigate=None, on_back=None):
        super().__init__()
        self.yt = yt_client
        self.on_play_song = on_play_song
        self.on_navigate = on_navigate
        self.on_back = on_back
        self._channel_id = None
        self._current_load_task = None
        self._data = None
        self._build_ui()

    def _build_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.content_widget = QWidget()
        self._content_wrapper_layout = QVBoxLayout(self.content_widget)
        self._content_wrapper_layout.setContentsMargins(0, 0, 0, 0)

        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(24, 24, 24, 112)
        self.content_layout.setSpacing(16)

        self._content_wrapper_layout.addLayout(self.content_layout)
        self._content_wrapper_layout.addStretch()

        self.scroll.setWidget(self.content_widget)
        self.layout.addWidget(self.scroll)

    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                sub_layout = item.layout()
                self._clear_layout(sub_layout)
                sub_layout.deleteLater()

    def _clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                sub_layout = child.layout()
                self._clear_layout(sub_layout)
                sub_layout.deleteLater()

    async def load(self, channel_id: str):
        if not channel_id:
            return
        if self._current_load_task and not self._current_load_task.done():
            self._current_load_task.cancel()
        self._current_load_task = asyncio.create_task(self._load_async(channel_id))
        try:
            await self._current_load_task
        except asyncio.CancelledError:
            raise

    async def _load_async(self, channel_id: str):
        self._channel_id = channel_id
        self._clear_content()

        from doremi.ui.widgets.skeleton_loader import SkeletonListLoader
        skeleton = SkeletonListLoader(row_count=8)
        self.content_layout.addWidget(skeleton)

        try:
            data = await self.yt.get_artist(channel_id)
            self._data = data
            await self._display_artist(data)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error loading artist: {e}")
            self._clear_content()
            self.content_layout.addWidget(ErrorStateWidget(
                "No se pudo cargar el artista",
                retry_callback=lambda: asyncio.ensure_future(self.load(channel_id)),
            ))

    async def _display_artist(self, data: dict):
        self._clear_content()

        if not data:
            self.content_layout.addWidget(EmptyStateWidget("Artista no encontrado", icon="person"))
            return

        name = data.get('name', 'Unknown')
        subscribers = data.get('subscribers', '')
        thumbnail_url = ""
        thumbnails = data.get('thumbnails', [])
        if thumbnails:
            thumbnail_url = thumbnails[-1].get('url', '')

        # ── Back button ─────────────────────────────────────────────────
        back_row = QHBoxLayout()
        back_row.setContentsMargins(0, 0, 0, 8)
        btn_back = QPushButton()
        btn_back.setIcon(Icon.icon("arrow_back", tokens.CURRENT.text_secondary, 16))
        btn_back.setText("Volver")
        btn_back.setFont(AppFont.label(12))
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                padding: 6px 12px;
                border-radius: 8px;
                color: {tokens.CURRENT.text_secondary};
            }}
            QPushButton:hover {{
                background: {tokens.CURRENT.bg_elevated};
                color: {tokens.CURRENT.text_primary};
            }}
        """)
        btn_back.setFixedHeight(36)
        if self.on_back:
            btn_back.clicked.connect(self.on_back)
        back_row.addWidget(btn_back)
        back_row.addStretch()
        self.content_layout.addLayout(back_row)

        # ── Hero header ─────────────────────────────────────────────────
        header_layout = QHBoxLayout()
        header_layout.setSpacing(28)

        self.cover = QLabel()
        self.cover.setFixedSize(200, 200)
        self.cover.setObjectName("artistCover")
        cover_shadow = QGraphicsDropShadowEffect(self.cover)
        cover_shadow.setBlurRadius(24)
        cover_shadow.setOffset(0, 6)
        cover_shadow.setColor(QColor(0, 0, 0, 80))
        self.cover.setGraphicsEffect(cover_shadow)
        header_layout.addWidget(self.cover)

        if thumbnail_url:
            asyncio.ensure_future(self._load_cover(thumbnail_url))

        info_layout = QVBoxLayout()
        info_layout.setSpacing(8)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)

        type_lbl = QLabel("ARTISTA")
        type_lbl.setFont(AppFont.label(11))
        type_lbl.setStyleSheet(f"color: {tokens.CURRENT.accent}; background: transparent; letter-spacing: 1px;")
        type_lbl.setObjectName("artistType")
        info_layout.addWidget(type_lbl)

        title_lbl = QLabel(name)
        title_lbl.setFont(AppFont.display(32))
        title_lbl.setStyleSheet(f"color: {tokens.CURRENT.text_primary}; background: transparent;")
        title_lbl.setObjectName("artistTitle")
        title_lbl.setWordWrap(True)
        info_layout.addWidget(title_lbl)

        if subscribers:
            meta_lbl = QLabel(subscribers)
            meta_lbl.setFont(AppFont.body(13))
            meta_lbl.setStyleSheet(f"color: {tokens.CURRENT.text_secondary}; background: transparent;")
            meta_lbl.setObjectName("artistMeta")
            info_layout.addWidget(meta_lbl)

        # ── Action buttons ────────────────────────────────────────────
        actions_row = QHBoxLayout()
        actions_row.setSpacing(12)
        actions_row.setContentsMargins(0, 8, 0, 0)

        play_all_btn = QPushButton()
        play_all_btn.setIcon(Icon.icon("play_arrow", tokens.CURRENT.text_on_accent, 20))
        play_all_btn.setText("Reproducir")
        play_all_btn.setFont(AppFont.title(13))
        play_all_btn.setFixedHeight(44)
        play_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        play_all_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {tokens.CURRENT.accent},
                    stop:1 {tokens.CURRENT.accent_bright});
                color: {tokens.CURRENT.text_on_accent};
                border: none;
                border-radius: 22px;
                padding: 0 24px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {tokens.CURRENT.accent_bright},
                    stop:1 {tokens.CURRENT.accent});
            }}
        """)
        play_all_btn.clicked.connect(lambda: self._play_first_song(data))
        actions_row.addWidget(play_all_btn)

        shuffle_btn = QPushButton()
        shuffle_btn.setIcon(Icon.icon("shuffle", tokens.CURRENT.text_primary, 18))
        shuffle_btn.setText("Aleatorio")
        shuffle_btn.setFont(AppFont.title(13))
        shuffle_btn.setFixedHeight(44)
        shuffle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        shuffle_btn.setStyleSheet(f"""
            QPushButton {{
                background: {tokens.CURRENT.bg_elevated};
                color: {tokens.CURRENT.text_primary};
                border: 1px solid {tokens.CURRENT.border};
                border-radius: 22px;
                padding: 0 24px;
            }}
            QPushButton:hover {{
                background: {tokens.CURRENT.bg_high};
                border-color: {tokens.CURRENT.accent};
            }}
        """)
        songs = data.get('songs', {}).get('results', [])
        if songs:
            import random
            shuffle_btn.clicked.connect(lambda: self._play_song(
                random.choice(songs), data.get('name', 'Unknown')
            ))
        actions_row.addWidget(shuffle_btn)
        actions_row.addStretch()
        info_layout.addLayout(actions_row)

        header_layout.addLayout(info_layout)
        header_layout.addStretch()
        self.content_layout.addLayout(header_layout)

        self.content_layout.addSpacing(8)

        # ── Top Songs ──────────────────────────────────────────────────
        if songs:
            songs_header = QLabel("Top Canciones")
            songs_header.setFont(AppFont.heading(18))
            songs_header.setStyleSheet(f"""
                color: {tokens.CURRENT.text_primary}; background: transparent;
                padding: 4px 0 0 0;
            """)
            self.content_layout.addWidget(songs_header)

            for i, track in enumerate(songs[:5]):
                title = track.get('title', 'Unknown')
                video_id = track.get('videoId', '')

                artists = track.get('artists', [])
                artist_names = ", ".join(
                    [a.get('name', '') for a in artists]
                ) if isinstance(artists, list) else str(artists)
                if not artist_names or artist_names == "Unknown":
                    artist_names = name

                duration = track.get('duration', '')
                track_thumbnails = track.get('thumbnails', [])
                track_thumbnail_url = track_thumbnails[-1].get('url', '') if track_thumbnails else ''

                if video_id:
                    # Parse duration string to ms
                    dur_ms = 0
                    if duration:
                        try:
                            parts = str(duration).split(':')
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
                        thumbnail_url=track_thumbnail_url,
                        on_play=partial(self._handle_play, video_id, title, artist_names, track_thumbnail_url, dur_ms)
                    )
                    card.download_requested.connect(self.download_requested.emit)
                    card.play_next_requested.connect(self.play_next_requested.emit)
                    card.add_to_queue_requested.connect(self.add_to_queue_requested.emit)
                    card.like_requested.connect(self.like_requested.emit)
                    card.add_to_playlist_requested.connect(self.add_to_playlist_requested.emit)
                    card.delete_download_requested.connect(self.delete_download_requested.emit)
                    self.content_layout.addWidget(card)

            self.content_layout.addSpacing(8)

        # ── Albums ─────────────────────────────────────────────────────
        albums = data.get('albums', {}).get('results', [])
        if albums:
            albums_header = QLabel("Álbumes")
            albums_header.setFont(AppFont.heading(18))
            albums_header.setStyleSheet(f"""
                color: {tokens.CURRENT.text_primary}; background: transparent;
                padding: 4px 0 0 0;
            """)
            self.content_layout.addWidget(albums_header)

            grid = QGridLayout()
            grid.setSpacing(16)

            for i, album in enumerate(albums):
                a_title = album.get("title", "Unknown")
                year = album.get("year", "")
                browse_id = album.get("browseId", "")
                album_thumbnails = album.get("thumbnails", [])
                album_thumbnail_url = album_thumbnails[-1].get("url", "") if album_thumbnails else ""

                card = AlbumCard(title=a_title, artist=name, year=year,
                                 thumbnail_url=album_thumbnail_url)
                if browse_id and self.on_navigate:
                    card.clicked.connect(partial(self.on_navigate, f"album?id={browse_id}"))
                grid.addWidget(card, i // 4, i % 4)

            self.content_layout.addLayout(grid)
            self.content_layout.addSpacing(8)

        # ── Similar Artists ────────────────────────────────────────────
        related = data.get('related', {}).get('results', [])
        if related:
            related_header = QLabel("Artistas Similares")
            related_header.setFont(AppFont.heading(18))
            related_header.setStyleSheet(f"""
                color: {tokens.CURRENT.text_primary}; background: transparent;
                padding: 4px 0 0 0;
            """)
            self.content_layout.addWidget(related_header)

            scroll_row = QScrollArea()
            scroll_row.setWidgetResizable(False)
            scroll_row.setFixedHeight(230)
            scroll_row.setStyleSheet("background: transparent; border: none;")
            scroll_row.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

            row_content = QWidget()
            row_layout = QHBoxLayout(row_content)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(12)

            for artist in related:
                a_name = artist.get('title', 'Unknown')
                a_id = artist.get('browseId', '')
                a_thumbnails = artist.get('thumbnails', [])
                a_thumbnail_url = a_thumbnails[-1].get('url', '') if a_thumbnails else ''

                card = ArtistCard(name=a_name, thumbnail_url=a_thumbnail_url)
                if a_id and self.on_navigate:
                    card.clicked.connect(partial(self.on_navigate, f"artist?id={a_id}"))
                row_layout.addWidget(card)

            row_layout.addStretch()
            scroll_row.setWidget(row_content)
            self.content_layout.addWidget(scroll_row)

        self.content_layout.addStretch()

    async def _load_cover(self, url: str):
        path = await _image_cache.download(url)
        import shiboken6
        if not shiboken6.isValid(self):
            return
        if path:
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                pixmap = pixmap.scaled(200, 200,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation)
                mask = QPixmap(200, 200)
                mask.fill(Qt.GlobalColor.transparent)
                from PySide6.QtGui import QPainter
                p = QPainter(mask)
                path = QPainterPath()
                path.addEllipse(0, 0, 200, 200)
                p.setClipPath(path)
                p.drawPixmap(0, 0, pixmap)
                p.end()
                self.cover.setPixmap(mask)
                self.cover.setStyleSheet("background: transparent;")

    def _handle_play(self, video_id, title, artists, thumbnail_url, duration_ms=0):
        if self.on_play_song:
            self.on_play_song(video_id, title, artists, "", duration_ms, thumbnail_url)

    def _play_first_song(self, data):
        songs = data.get('songs', {}).get('results', [])
        if songs and self.on_play_song:
            track = songs[0]
            # Extract duration from track
            dur_ms = 0
            track_duration = track.get('duration') or track.get('duration_seconds')
            if track_duration:
                if isinstance(track_duration, (int, float)):
                    dur_ms = int(track_duration) * 1000
                elif isinstance(track_duration, str):
                    try:
                        parts = track_duration.split(':')
                        if len(parts) == 2:
                            dur_ms = (int(parts[0]) * 60 + int(parts[1])) * 1000
                    except (ValueError, IndexError):
                        pass
            self._handle_play(
                track.get('videoId', ''),
                track.get('title', ''),
                data.get('name', ''),
                (track.get('thumbnails') or [{}])[-1].get('url', ''),
                dur_ms
            )

    def _play_song(self, track, artist_name):
        # Extract duration from track
        dur_ms = 0
        track_duration = track.get('duration') or track.get('duration_seconds')
        if track_duration:
            if isinstance(track_duration, (int, float)):
                dur_ms = int(track_duration) * 1000
            elif isinstance(track_duration, str):
                try:
                    parts = track_duration.split(':')
                    if len(parts) == 2:
                        dur_ms = (int(parts[0]) * 60 + int(parts[1])) * 1000
                except (ValueError, IndexError):
                    pass
        self._handle_play(
            track.get('videoId', ''),
            track.get('title', ''),
            artist_name,
            (track.get('thumbnails') or [{}])[-1].get('url', ''),
            dur_ms
        )

    def changeEvent(self, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.PaletteChange:
            if self._data:
                asyncio.ensure_future(self._display_artist(self._data))
        super().changeEvent(event)
