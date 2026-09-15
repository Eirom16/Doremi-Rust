from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QScrollArea, QPushButton, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtCore import Qt, Signal, QSize, QPropertyAnimation, Property, QEasingCurve
from PySide6.QtGui import QFont, QPixmap, QPainter, QColor
import asyncio
from doremi.utils.image_cache import ImageCache
from doremi.audio.player import PlayerState
from doremi.utils.time_utils import format_duration_short
from doremi.ui.design.icons import Icon
from doremi.ui.design.fonts import AppFont
from doremi.ui.widgets.icon_button import IconButton
from doremi.ui.widgets.animated_progress import AnimatedProgressBar

_image_cache = ImageCache()

class LyricLabel(QLabel):
    def __init__(self, text, align_flag, base_font_size=18):
        super().__init__(text)
        self.setAlignment(align_flag)
        self.setWordWrap(True)
        self.base_font_size = base_font_size
        self._progress = 0.0
        
        # Force dynamic point size via setFont AND setStyleSheet inline to bypass QSS stylesheet overrides
        self.setFont(QFont("Inter", base_font_size + 8, QFont.Weight.Black))
        self.setStyleSheet(f"background: transparent; font-size: {base_font_size + 8}pt; font-family: 'Inter';")
        self.setContentsMargins(16, 8, 16, 8)
        
        self.anim = QPropertyAnimation(self, b"progress")
        self.anim.setDuration(450)
        self.anim.setEasingCurve(QEasingCurve.Type.OutBack)
        
    def get_progress(self):
        return self._progress
        
    def set_progress(self, p):
        self._progress = p
        self.update()
        
    progress = Property(float, get_progress, set_progress)
    
    def set_active(self, active: bool):
        self.anim.stop()
        self.anim.setEndValue(1.0 if active else 0.0)
        self.anim.start()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        # Clamp progress to strictly [0.0, 1.0] to prevent OutBack easing curve overshooting color calculations
        p = max(0.0, min(1.0, self._progress))
        
        # Always white text for premium dynamic legibility
        alpha = int(140 + (255 - 140) * p) # 140 is more readable for inactive floating text
        text_color = QColor(255, 255, 255, alpha)
        
        # Soft dark outline only for active/activating text, preventing muddy overlap on inactive text
        shadow_alpha = int(170 * p)
        shadow_color = QColor(0, 0, 0, shadow_alpha)
        
        # Setup scale transformation
        scale = 0.88 + (0.12 * p) # Scale transitions from 0.88 to 1.0
        cx = self.width() / 2
        cy = self.height() / 2
        
        painter.save()
        painter.translate(cx, cy)
        painter.scale(scale, scale)
        painter.translate(-cx, -cy)
        
        flags = int(self.alignment()) | Qt.TextFlag.TextWordWrap
        font = self.font()
        font.setFamily("Inter")
        # Explicitly enforce size in point size inside the painter to bypass QSS
        current_size = self.base_font_size + (8 * p)
        font.setPointSize(int(current_size))
        font.setWeight(QFont.Weight.Black if p > 0.5 else QFont.Weight.Bold)
        painter.setFont(font)
        
        # Draw soft 8-directional shadow outline for robust contrast
        painter.setPen(shadow_color)
        offsets = [
            (-1, -1), (1, -1), (-1, 1), (1, 1),
            (0, -1.5), (0, 1.5), (-1.5, 0), (1.5, 0)
        ]
        rect = self.contentsRect()
        for dx, dy in offsets:
            painter.drawText(rect.translated(dx, dy), flags, self.text())
            
        # Draw main text
        painter.setPen(text_color)
        painter.drawText(rect, flags, self.text())
        
        painter.restore()

class NowPlayingScreen(QWidget):
    download_requested = Signal(str, str, str, str)
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    artist_clicked = Signal(str)
    album_clicked = Signal(str)
    like_requested = Signal(str, object)
    add_to_playlist_requested = Signal(str, str)
    delete_download_requested = Signal(str)

    def __init__(self, player, queue, yt_client, play_queue_item_cb, settings=None, on_back=None):
        super().__init__()
        self.player = player
        self.queue = queue
        self.yt = yt_client
        self.play_queue_item_cb = play_queue_item_cb
        self.settings = settings
        self.on_back = on_back
        self._is_playing = False
        self._ui_ready = False
        self.setObjectName("nowPlayingScreen")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        from doremi.ui.widgets.ambient_background import AmbientBackgroundWidget
        self.ambient_bg = AmbientBackgroundWidget(self)
        self.ambient_bg.lower()
        
        self._build_ui()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.ambient_bg.setGeometry(self.rect())
        if hasattr(self, "artwork"):
            target_size = 240 if self.height() < 700 else 280
            if self.artwork.width() != target_size:
                self.artwork.setFixedSize(target_size, target_size)

    def _make_btn(self, icon_name, size=24, color="#FFFFFF", btn_size=40, primary=False):
        if primary:
            btn = QPushButton()
            btn.setText(Icon.get(icon_name))
            btn.setFont(Icon.font(size))
            btn.setFixedSize(btn_size, btn_size)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            radius = btn_size // 2
            btn.setObjectName("primaryPlayBtn")
            btn.setStyleSheet(f"QPushButton#primaryPlayBtn {{ border-radius: {radius}px; font-family: 'Material Symbols Rounded'; font-size: {size}px; }}")
            return btn

        btn = IconButton(size=btn_size, active_color="rgba(255,255,255,0.2)")
        btn.setText(Icon.get(icon_name))
        btn.setFont(Icon.font(size))
        btn.setFixedSize(btn_size, btn_size)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # Style border and background cleanly without inline color hardcoding
        btn.setStyleSheet("QPushButton { border: none; background: transparent; }")
        return btn

    def _build_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        self.setStyleSheet("#nowPlayingScreen { background: transparent; }")

        # Top bar with collapse/back button
        from doremi.ui.design import tokens
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(24, 16, 24, 0)
        self.btn_collapse = QPushButton()
        self.btn_collapse.setText("Minimizar")
        self.btn_collapse.setIcon(Icon.icon("expand_more", tokens.CURRENT.text_secondary, 18))
        self.btn_collapse.setIconSize(QSize(18, 18))
        self.btn_collapse.setFont(QFont("Inter", 12, QFont.Weight.Medium))
        self.btn_collapse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_collapse.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                
                border: none;
                padding: 6px 16px;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background: {tokens.CURRENT.bg_elevated};
                
            }}
        """)
        self.btn_collapse.setFixedHeight(36)
        if self.on_back:
            self.btn_collapse.clicked.connect(self.on_back)
        top_bar.addWidget(self.btn_collapse)
        top_bar.addStretch()
        outer_layout.addLayout(top_bar)

        layout = QHBoxLayout()
        # The mini player floats above this screen, so keeping a large reserved
        # bottom margin here compresses the left column and can make playback
        # controls overlap the album artwork on shorter windows.
        layout.setContentsMargins(40, 16, 40, 24)
        layout.setSpacing(40)

        # Left Side (Artwork & Details + Controls)
        left_panel = QWidget()
        left_panel.setObjectName("nowPlayingLeftPanel")
        left_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        left_panel.setStyleSheet("#nowPlayingLeftPanel { background: transparent; }")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.artwork = QLabel()
        self.artwork.setFixedSize(280, 280)
        self.artwork.setScaledContents(True)
        self.artwork.setObjectName("nowPlayingArtwork")
        self.artwork.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.artwork.setText(Icon.get("library_music"))
        self.artwork.setFont(Icon.font(120))
        self.artwork.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        left_layout.addWidget(self.artwork, alignment=Qt.AlignmentFlag.AlignCenter)

        left_layout.addSpacing(24)

        # ── Song info row ──
        info_layout = QHBoxLayout()
        
        text_info = QVBoxLayout()
        self.title = QLabel("No hay canción")
        self.title.setFont(QFont("Inter", 22, QFont.Weight.Bold))
        self.title.setObjectName("nowPlayingTitle")
        self.title.setWordWrap(True)
        text_info.addWidget(self.title)

        from doremi.ui.widgets.clickable_label import ClickableLabel
        self.artist = ClickableLabel("")
        self.artist.setFont(QFont("Inter", 14))
        self.artist.setObjectName("nowPlayingArtist")
        self.artist.set_clicked_callback(self._on_artist_clicked)
        text_info.addWidget(self.artist)
        
        info_layout.addLayout(text_info)
        info_layout.addStretch()

        # Like button
        self.btn_like = IconButton(size=48, active_color="#F472B6")
        self.btn_like.setText(Icon.get("favorite"))
        self.btn_like.setFont(Icon.font(28, filled=False))
        self.btn_like.setObjectName("nowPlayingLikeBtn")
        self.btn_like.setAccessibleName("Me gusta")
        self.btn_like.clicked.connect(self._on_like_clicked)
        info_layout.addWidget(self.btn_like)

        left_layout.addLayout(info_layout)
        left_layout.addSpacing(16)

        # ── Progress bar with time labels ──
        progress_row = QHBoxLayout()
        progress_row.setSpacing(10)

        self.time_current = QLabel("0:00")
        self.time_current.setFont(AppFont.mono(11))
        self.time_current.setObjectName("nowPlayingTimeCurrent")
        self.time_current.setFixedWidth(40)
        self.time_current.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        progress_row.addWidget(self.time_current)

        self.progress = AnimatedProgressBar()
        self.progress.setEnabled(False)
        self.progress.on_seek = self._on_seek
        progress_row.addWidget(self.progress, stretch=1)

        self.time_total = QLabel("0:00")
        self.time_total.setFont(AppFont.mono(11))
        self.time_total.setObjectName("nowPlayingTimeTotal")
        self.time_total.setFixedWidth(40)
        self.time_total.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        progress_row.addWidget(self.time_total)

        left_layout.addLayout(progress_row)
        left_layout.addSpacing(12)

        # ── Playback controls ──
        controls = QHBoxLayout()
        controls.setSpacing(16)
        controls.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_shuffle = self._make_btn("shuffle", 24, "#6B6B9B", 42)
        self.btn_shuffle.setObjectName("nowPlayingShuffleBtn")
        self.btn_shuffle.setAccessibleName("Reproducción aleatoria")
        self.btn_shuffle.clicked.connect(self._on_shuffle)
        controls.addWidget(self.btn_shuffle)

        self.btn_prev = self._make_btn("skip_previous", 32, "#F1F0FF", 50)
        self.btn_prev.setObjectName("nowPlayingPrevBtn")
        self.btn_prev.setAccessibleName("Pista anterior")
        self.btn_prev.clicked.connect(self._on_prev)
        controls.addWidget(self.btn_prev)

        self.btn_play = self._make_btn("play_arrow", 40, "#0A0A14", 64, primary=True)
        self.btn_play.setAccessibleName("Reproducir o Pausar")
        self.btn_play.clicked.connect(self._on_play_pause)
        controls.addWidget(self.btn_play)

        self.btn_next = self._make_btn("skip_next", 32, "#F1F0FF", 50)
        self.btn_next.setObjectName("nowPlayingNextBtn")
        self.btn_next.setAccessibleName("Pista siguiente")
        self.btn_next.clicked.connect(self._on_next)
        controls.addWidget(self.btn_next)

        self.btn_repeat = self._make_btn("repeat", 24, "#6B6B9B", 42)
        self.btn_repeat.setObjectName("nowPlayingRepeatBtn")
        self.btn_repeat.setAccessibleName("Repetir")
        self.btn_repeat.clicked.connect(self._on_repeat)
        controls.addWidget(self.btn_repeat)

        self.btn_more = self._make_btn("more_vert", 24, "#6B6B9B", 42)
        self.btn_more.setObjectName("nowPlayingMoreBtn")
        self.btn_more.setAccessibleName("Más opciones de la canción actual")
        self.btn_more.clicked.connect(self._show_current_track_menu)
        controls.addWidget(self.btn_more)

        left_layout.addLayout(controls)
        left_layout.addStretch()

        # Right Side (Tabs: Queue, Lyrics, Related)
        right_panel = QWidget()
        right_panel.setObjectName("nowPlayingRightPanel")
        right_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        right_panel.setStyleSheet("#nowPlayingRightPanel { background: transparent; }")
        right_panel.setMinimumWidth(560)
        right_panel.setMaximumWidth(700)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("nowPlayingTabs")


        # Tab: Queue (A CONTINUACIÓN)
        from doremi.ui.widgets.queue_panel import QueuePanel
        self.queue_tab = QueuePanel(self.play_queue_item_cb)
        self.queue_tab.like_requested.connect(lambda *a: self.like_requested.emit(*a))
        self.queue_tab.download_requested.connect(lambda *a: self.download_requested.emit(*a))
        self.queue_tab.play_next_requested.connect(lambda *a: self.play_next_requested.emit(*a))
        self.queue_tab.add_to_queue_requested.connect(lambda *a: self.add_to_queue_requested.emit(*a))
        self.queue_tab.add_to_playlist_requested.connect(lambda *a: self.add_to_playlist_requested.emit(*a))
        self.queue_tab.delete_download_requested.connect(lambda *a: self.delete_download_requested.emit(*a))
        self.queue_tab.artist_clicked.connect(lambda *a: self.artist_clicked.emit(*a))
        self.tabs.addTab(self.queue_tab, "A CONTINUACIÓN")

        self.lyrics_scroll = QScrollArea()
        self.lyrics_scroll.setWidgetResizable(True)
        self.lyrics_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lyrics_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; } QScrollArea > QWidget > QWidget { background: transparent; }")
        
        self.lyrics_container = QWidget()
        self.lyrics_container.setObjectName("lyricsContainer")
        self.lyrics_container.setStyleSheet("#lyricsContainer { background: transparent; }")
        self.lyrics_layout = QVBoxLayout(self.lyrics_container)
        self.lyrics_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.lyrics_layout.setContentsMargins(16, 16, 16, 112)
        self.lyrics_scroll.setWidget(self.lyrics_container)
        
        self._lyric_lines = []
        self._current_lyric_index = -1
        
        # Initial message
        msg = QLabel("Reproduce una canción para ver las letras")
        msg.setFont(QFont("Inter", 14))
        msg.setStyleSheet("color: rgba(255, 255, 255, 0.7);")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lyrics_layout.addWidget(msg)
        
        self.tabs.addTab(self.lyrics_scroll, "LETRA")
        
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # Tab: Related (SIMILARES)
        self.related_scroll = QScrollArea()
        self.related_scroll.setWidgetResizable(True)
        self.related_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.related_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; } QScrollArea > QWidget > QWidget { background: transparent; }")
        self.related_container = QWidget()
        self.related_container.setObjectName("relatedContainer")
        self.related_container.setStyleSheet("#relatedContainer { background: transparent; }")
        self.related_layout = QVBoxLayout(self.related_container)
        self.related_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.related_layout.setContentsMargins(0, 0, 0, 112)
        self.related_scroll.setWidget(self.related_container)
        
        self.tabs.addTab(self.related_scroll, "SIMILARES")

        right_layout.addWidget(self.tabs)

        layout.addWidget(left_panel)
        layout.addWidget(right_panel)
        outer_layout.addLayout(layout)
        self._ui_ready = True
        self._update_styles()

    def _on_artist_clicked(self):
        text = self.artist.text()
        if text and text != "Unknown Artist":
            self.artist_clicked.emit(text)

    def _on_like_clicked(self):
        """Toggle like for the currently playing song."""
        video_id = self.player.status.current_video_id
        if video_id:
            main = self._find_main_window()
            if main:
                main._on_like_requested(video_id, self.btn_like)

    # ── Playback control handlers ──
    def _on_play_pause(self):
        main = self._find_main_window()
        if main:
            main._on_play_pause()

    def _on_prev(self):
        main = self._find_main_window()
        if main:
            main._on_prev()

    def _on_next(self):
        main = self._find_main_window()
        if main:
            main._on_next()

    def _on_seek(self, pct: float):
        main = self._find_main_window()
        if main and self.player.status.duration_ms > 0:
            ms = int(pct * self.player.status.duration_ms)
            main._on_seek(ms)

    def _on_shuffle(self):
        is_shuffled = self.queue.toggle_shuffle()
        self.update_shuffle_repeat_state()
        
        main = self._find_main_window()
        if main:
            main.playback_controller._update_queue_panel()
            if hasattr(main, "_persist_queue_playback_settings"):
                main._persist_queue_playback_settings()
            if main.mpris:
                main.mpris.update_shuffle(is_shuffled)

    def _on_repeat(self):
        self.queue.toggle_repeat()
        self.update_shuffle_repeat_state()
        main = self._find_main_window()
        if main and hasattr(main, "_persist_queue_playback_settings"):
            main._persist_queue_playback_settings()
        if main and getattr(main, "mpris", None):
            main.mpris.update_loop_status()

    def _show_current_track_menu(self):
        asyncio.ensure_future(self._show_current_track_menu_async())

    async def _show_current_track_menu_async(self):
        item = self.queue.current
        if not item or not getattr(item, "video_id", ""):
            return

        is_downloaded = False
        try:
            from doremi.db.repository import DownloadRepository
            is_downloaded = await DownloadRepository().get_download(item.video_id) is not None
        except Exception:
            is_downloaded = False

        from doremi.ui.widgets.song_context_menu import SongContextMenu
        menu_parent = self.window()
        menu = SongContextMenu(
            parent=menu_parent,
            is_downloaded=is_downloaded,
            has_album=bool(getattr(item, "album", "")),
        )
        self._current_menu = menu

        thumb_url = getattr(item, "thumbnail_url", "") or ""
        menu.play_next.connect(lambda: self.play_next_requested.emit(item.video_id, item.title, item.artist, thumb_url))
        menu.add_to_queue.connect(lambda: self.add_to_queue_requested.emit(item.video_id, item.title, item.artist, thumb_url))
        menu.add_to_playlist.connect(lambda: self.add_to_playlist_requested.emit(item.video_id, item.title))
        menu.go_to_artist.connect(lambda: self.artist_clicked.emit(item.artist))
        menu.go_to_album.connect(lambda: self.album_clicked.emit(item.album))
        menu.download.connect(lambda: self.download_requested.emit(item.video_id, item.title, item.artist, thumb_url))
        menu.delete_download.connect(lambda: self.delete_download_requested.emit(item.video_id))
        menu.copy_link.connect(lambda: self._copy_current_track_link(item.video_id))
        setattr(menu, "_trigger_widget", self.btn_more)

        pos = self.btn_more.rect().bottomLeft()
        if menu_parent and hasattr(self.btn_more, "mapTo"):
            pos = self.btn_more.mapTo(menu_parent, pos)
        menu.popup_at(pos)

    def _copy_current_track_link(self, video_id: str):
        if not video_id:
            return
        from PySide6.QtWidgets import QApplication
        from doremi.ui.widgets.toast import ToastNotification
        QApplication.clipboard().setText(f"https://music.youtube.com/watch?v={video_id}")
        ToastNotification.show(self.window(), "Enlace copiado", "success")

    def update_shuffle_repeat_state(self):
        """Sync button visuals with current queue state."""
        from doremi.ui.design import tokens
        from doremi.audio.queue import RepeatMode
        from PySide6.QtGui import QColor
        
        is_light = QColor(tokens.CURRENT.bg_base).lightness() > 128
        inactive_color = "rgba(18, 18, 36, 0.55)" if is_light else "rgba(255, 255, 255, 0.5)"
        
        # Shuffle
        color = tokens.CURRENT.accent if self.queue.shuffle_enabled else inactive_color
        self.btn_shuffle.setStyleSheet(f"QPushButton {{ color: {color}; border: none; background: transparent; }}")
        
        # Repeat
        mode = self.queue.repeat_mode
        if mode == RepeatMode.OFF:
            self.btn_repeat.setText(Icon.get("repeat"))
            self.btn_repeat.setStyleSheet(f"QPushButton {{ color: {inactive_color}; border: none; background: transparent; }}")
            self.btn_repeat.setFont(Icon.font(24))
        elif mode == RepeatMode.ALL:
            self.btn_repeat.setText(Icon.get("repeat"))
            self.btn_repeat.setStyleSheet(f"QPushButton {{ color: {tokens.CURRENT.accent}; border: none; background: transparent; }}")
            self.btn_repeat.setFont(Icon.font(24))
        elif mode == RepeatMode.ONE:
            self.btn_repeat.setText(Icon.get("repeat_one"))
            self.btn_repeat.setStyleSheet(f"QPushButton {{ color: {tokens.CURRENT.accent}; border: none; background: transparent; }}")
            self.btn_repeat.setFont(Icon.font(24))

    def _find_main_window(self):
        w = self.parent()
        while w:
            if hasattr(w, '_on_play_pause'):
                return w
            w = w.parent() if hasattr(w, 'parent') and callable(w.parent) else None
        return None

    def update_track_info(self, title: str, artist: str, thumbnail_url: str):
        self.title.setText(title)
        self.artist.setText(artist)
        self.progress.setEnabled(True)
        
        if thumbnail_url:
            asyncio.ensure_future(self._load_thumbnail(thumbnail_url))
        else:
            self.artwork.setPixmap(QPixmap())
            self.artwork.setText(Icon.get("library_music"))
            self.artwork.setFont(Icon.font(120))
            from doremi.ui.design import tokens
            from PySide6.QtGui import QColor
            is_light = QColor(tokens.CURRENT.bg_base).lightness() > 128
            bg = "rgba(0, 0, 0, 0.05)" if is_light else "rgba(255, 255, 255, 0.08)"
            fg = "#121224" if is_light else "#FFFFFF"
            self.artwork.setStyleSheet(f"background: {bg}; color: {fg}; border-radius: 24px;")
            self.ambient_bg.set_image(None)

    def update_state(self, status):
        self._is_playing = status.state == PlayerState.PLAYING
        self.btn_play.setText(Icon.get("pause" if self._is_playing else "play_arrow"))

    def update_position(self, position_ms: int, duration_ms: int):
        if duration_ms > 0:
            self.progress.set_value(position_ms / duration_ms)
        self.time_current.setText(format_duration_short(position_ms))
        self.time_total.setText(format_duration_short(duration_ms))
        self._highlight_lyric(position_ms)
        
    def set_lyrics_loading(self):
        self.lyrics_scroll.verticalScrollBar().setValue(0)
        while self.lyrics_layout.count():
            item = self.lyrics_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        self._lyric_lines.clear()
        self._current_lyric_index = -1
        
        from doremi.ui.design import tokens
        loading_lbl = QLabel("Buscando letras...")
        loading_lbl.setFont(QFont("Inter", 14))
        loading_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_lbl.setStyleSheet(f"color: {tokens.CURRENT.text_secondary}; margin-top: 32px;")
        self.lyrics_layout.addWidget(loading_lbl)

    def set_lyrics(self, lyrics):
        self.lyrics_scroll.verticalScrollBar().setValue(0)
        while self.lyrics_layout.count():
            item = self.lyrics_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        self._lyric_lines.clear()
        self._current_lyric_index = -1
        
        if not lyrics:
            from doremi.ui.design import tokens
            no_lyrics = QLabel("No hay letras disponibles")
            no_lyrics.setFont(QFont("Inter", 14))
            no_lyrics.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_lyrics.setStyleSheet(f"color: {tokens.CURRENT.text_secondary};")
            self.lyrics_layout.addWidget(no_lyrics)
            return

        import re
        if isinstance(lyrics, str):
            lines = lyrics.strip().split('\n')
        elif isinstance(lyrics, list):
            lines = lyrics
        else:
            lines = [str(lyrics)]
            
        font_size = 18
        alignment = "center"
        line_spacing = 1.5
        if self.settings:
            font_size = self.settings.subtitles.font_size
            alignment = self.settings.subtitles.alignment
            line_spacing = self.settings.subtitles.line_spacing
            
        align_flag = Qt.AlignmentFlag.AlignCenter
        if alignment == "left":
            align_flag = Qt.AlignmentFlag.AlignLeft
        elif alignment == "right":
            align_flag = Qt.AlignmentFlag.AlignRight
            
        padding = int(line_spacing * 4)

        for line_text in lines:
            clean = line_text.strip()
            if not clean:
                spacer = QLabel("")
                spacer.setFixedHeight(16)
                self.lyrics_layout.addWidget(spacer)
                self._lyric_lines.append((-1, spacer))
                continue
            
            timestamp_ms = -1
            match = re.match(r'^((?:\[\d{1,}:\d{2}(?:\.\d+)?\])+)(.*)', clean)
            if match:
                tags_str = match.group(1)
                clean = match.group(2).strip()
                first_tag = re.search(r'\[(\d{1,}):(\d{2}(?:\.\d+)?)\]', tags_str)
                if first_tag:
                    mins = int(first_tag.group(1))
                    secs = float(first_tag.group(2))
                    timestamp_ms = int((mins * 60 + secs) * 1000)
            
            if not clean:
                if timestamp_ms != -1:
                    clean = "🎶"
                else:
                    continue
            
            lbl = LyricLabel(clean, align_flag, font_size)
            # Set vertical spacing dynamically based on settings line_spacing
            lbl.setContentsMargins(16, int(line_spacing * 6), 16, int(line_spacing * 6))
            self.lyrics_layout.addWidget(lbl)
            self._lyric_lines.append((timestamp_ms, lbl))
            
        has_timestamps = any(ts != -1 for ts, lbl in self._lyric_lines)
        if not has_timestamps and len(self._lyric_lines) > 0:
            from doremi.ui.design import tokens
            notice = QLabel("Sincronización no disponible para esta pista")
            notice.setFont(QFont("Inter", 11, QFont.Weight.Medium))
            notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
            notice.setStyleSheet(f"color: {tokens.CURRENT.text_secondary}; padding-bottom: 24px; padding-top: 12px; opacity: 0.75;")
            self.lyrics_layout.insertWidget(0, notice)
            
            for _, lbl in self._lyric_lines:
                if isinstance(lbl, LyricLabel):
                    lbl.set_active(True)
                    
        self.lyrics_layout.addStretch()
        # Force layout to compute geometries immediately
        self.lyrics_container.updateGeometry()

    def _highlight_lyric(self, position_ms: int):
        if not hasattr(self, '_lyric_lines') or not self._lyric_lines:
            return

        adjusted_position = position_ms + 400
        if self.settings:
            adjusted_position += self.settings.subtitles.delay_ms

        active_idx = -1
        for i, (ts, lbl) in enumerate(self._lyric_lines):
            if ts != -1 and adjusted_position >= ts:
                active_idx = i

        if active_idx != -1 and active_idx != self._current_lyric_index:
            from doremi.ui.design import tokens
            
            font_size = 18
            line_spacing = 1.5
            glow = True
            auto_scroll = True
            animation_style = "glow"
            if self.settings:
                font_size = self.settings.subtitles.font_size
                line_spacing = self.settings.subtitles.line_spacing
                glow = self.settings.subtitles.glow_effect
                auto_scroll = self.settings.subtitles.auto_scroll
                animation_style = self.settings.subtitles.animation_style
                
            padding = int(line_spacing * 4)

            if self._current_lyric_index != -1:
                old_ts, old_lbl = self._lyric_lines[self._current_lyric_index]
                if isinstance(old_lbl, LyricLabel):
                    old_lbl.set_active(False)
            
            new_ts, new_lbl = self._lyric_lines[active_idx]
            if isinstance(new_lbl, LyricLabel):
                new_lbl.set_active(True)
            
            self._current_lyric_index = active_idx
            
            if auto_scroll:
                scroll_bar = self.lyrics_scroll.verticalScrollBar()
                target_y = new_lbl.y() - (self.lyrics_scroll.height() / 2) + (new_lbl.height() / 2)
                
                if animation_style == "none":
                    scroll_bar.setValue(int(max(0, target_y)))
                else:
                    from PySide6.QtCore import QPropertyAnimation, QEasingCurve
                    self._scroll_anim = QPropertyAnimation(scroll_bar, b"value")
                    self._scroll_anim.setDuration(450)
                    self._scroll_anim.setStartValue(scroll_bar.value())
                    self._scroll_anim.setEndValue(int(max(0, target_y)))
                    self._scroll_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
                    self._scroll_anim.start()

    def _on_tab_changed(self, index):
        if self.tabs.tabText(index) == "LETRA" and self._current_lyric_index != -1:
            ts, lbl = self._lyric_lines[self._current_lyric_index]
            if isinstance(lbl, LyricLabel) and lbl.y() > 0:
                target_y = lbl.y() - (self.lyrics_scroll.height() / 2) + (lbl.height() / 2)
                self.lyrics_scroll.verticalScrollBar().setValue(int(max(0, target_y)))

    def update_lyrics_style(self):
        if not hasattr(self, '_lyric_lines') or not self._lyric_lines:
            return
            
        font_size = 22
        alignment = "center"
        line_spacing = 1.5
        if self.settings:
            font_size = self.settings.subtitles.font_size
            alignment = self.settings.subtitles.alignment
            line_spacing = self.settings.subtitles.line_spacing
            
        align_flag = Qt.AlignmentFlag.AlignCenter
        if alignment == "left":
            align_flag = Qt.AlignmentFlag.AlignLeft
        elif alignment == "right":
            align_flag = Qt.AlignmentFlag.AlignRight
            
        # Update spacing and font sizes dynamically in real-time
        vertical_padding = int(line_spacing * 6)
        
        for idx, (ts, lbl) in enumerate(self._lyric_lines):
            if isinstance(lbl, LyricLabel):
                lbl.setAlignment(align_flag)
                lbl.base_font_size = font_size
                # Instantly apply the new font size via setFont AND setStyleSheet inline to bypass QSS
                lbl.setFont(QFont("Inter", font_size + 8, QFont.Weight.Black))
                lbl.setStyleSheet(f"background: transparent; font-size: {font_size + 8}pt; font-family: 'Inter';")
                lbl.setContentsMargins(16, vertical_padding, 16, vertical_padding)
                lbl.update()
            elif isinstance(lbl, QLabel) and ts == -1:
                # Dynamically resize blank spacers based on line_spacing
                lbl.setFixedHeight(int(line_spacing * 10))
                
        # Force the layout to compute geometries and resize the scroll container immediately
        self.lyrics_container.updateGeometry()

    def _thumbnail_candidates(self, url: str) -> list[str]:
        """Return best-effort high-resolution artwork URLs before falling back.

        YouTube Music often returns tiny thumbnails (w120/w226, hqdefault, etc.).
        The large now-playing artwork makes that very visible, so try known higher
        resolution variants first while preserving the original URL as fallback.
        """
        import re
        candidates: list[str] = []

        def add(candidate: str):
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        if not url:
            return candidates

        # YouTube video thumbnails.
        video_match = re.search(r"/vi(?:_webp)?/([^/?]+)/", url)
        video_id = video_match.group(1) if video_match else self.player.status.current_video_id
        if video_id and ("ytimg.com" in url or "youtube" in url):
            base = "https://i.ytimg.com/vi"
            add(f"{base}/{video_id}/maxresdefault.jpg")
            add(f"{base}/{video_id}/sddefault.jpg")
            add(f"{base}/{video_id}/hqdefault.jpg")
            add(f"{base}/{video_id}/mqdefault.jpg")

        # Googleusercontent/YT Music album art size params.
        add(re.sub(r"=w\d+-h\d+[^&?]*", "=w1200-h1200-l90-rj", url))
        add(re.sub(r"=s\d+[^&?]*", "=s1200", url))

        # Generic direct replacements seen in API responses.
        high_res_url = url
        for small, large in (("w120", "w1200"), ("h120", "h1200"), ("w226", "w1200"), ("h226", "h1200"), ("w544", "w1200"), ("h544", "h1200")):
            high_res_url = high_res_url.replace(small, large)
        add(high_res_url)
        add(url)
        return candidates

    async def _load_thumbnail(self, url: str):
        from loguru import logger
        logger.debug(f"NowPlaying._load_thumbnail called with url={url[:80]}")
        import shiboken6

        path = None
        for candidate in self._thumbnail_candidates(url):
            path = await _image_cache.download(candidate)
            if not shiboken6.isValid(self):
                return
            if path:
                break

        if path:
            logger.debug(f"NowPlaying: image downloaded to {path}")
            try:
                with open(path, "rb") as f:
                    self.ambient_bg.set_image(f.read())
            except Exception:
                pass
            
            pixmap = QPixmap(str(path))
            logger.debug(f"NowPlaying: QPixmap null={pixmap.isNull()}, size={pixmap.width()}x{pixmap.height()}")
            if not pixmap.isNull():
                size = max(220, self.artwork.width() or 280)
                radius = 24 if size >= 270 else 20
                pixmap = pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                # Center crop
                x = (pixmap.width() - size) // 2
                y = (pixmap.height() - size) // 2
                pixmap = pixmap.copy(x, y, size, size)
                # Apply rounded rect clip
                from PySide6.QtGui import QPainter, QPainterPath
                from PySide6.QtCore import QRectF
                rounded = QPixmap(size, size)
                rounded.fill(Qt.GlobalColor.transparent)
                painter = QPainter(rounded)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                clip_path = QPainterPath()
                clip_path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
                painter.setClipPath(clip_path)
                painter.drawPixmap(0, 0, pixmap)
                painter.end()
                
                # Stop any existing artwork fade animations
                if hasattr(self, "_artwork_fade") and self._artwork_fade:
                    self._artwork_fade.stop()
                if hasattr(self, "_artwork_fade_in") and self._artwork_fade_in:
                    self._artwork_fade_in.stop()
                    
                # Animate transition
                from PySide6.QtWidgets import QGraphicsOpacityEffect
                from PySide6.QtCore import QPropertyAnimation, QEasingCurve
                
                effect = self.artwork.graphicsEffect()
                if not effect or not isinstance(effect, QGraphicsOpacityEffect):
                    effect = QGraphicsOpacityEffect(self.artwork)
                    self.artwork.setGraphicsEffect(effect)
                    
                self._artwork_fade = QPropertyAnimation(effect, b"opacity", self)
                self._artwork_fade.setDuration(120)
                self._artwork_fade.setStartValue(effect.opacity())
                self._artwork_fade.setEndValue(0.0)
                self._artwork_fade.setEasingCurve(QEasingCurve.Type.InCubic)
                
                def on_fade_out_done():
                    self.artwork.setPixmap(rounded)
                    self.artwork.setText("")
                    self.artwork.setStyleSheet("background: transparent;")
                    
                    self._artwork_fade_in = QPropertyAnimation(effect, b"opacity", self)
                    self._artwork_fade_in.setDuration(180)
                    self._artwork_fade_in.setStartValue(0.0)
                    self._artwork_fade_in.setEndValue(1.0)
                    self._artwork_fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
                    
                    def on_fade_in_done():
                        self.artwork.setGraphicsEffect(None)
                        
                    self._artwork_fade_in.finished.connect(on_fade_in_done)
                    self._artwork_fade_in.start()
                    
                self._artwork_fade.finished.connect(on_fade_out_done)
                self._artwork_fade.start()
                logger.debug(f"NowPlaying: artwork pixmap SET animation started")
        else:
            logger.warning(f"NowPlaying: image download failed for url={url[:80]}")
            self.ambient_bg.set_image(None)

    def set_related(self, tracks, play_callback):
        """Populate the SIMILARES tab with related songs."""
        from functools import partial
        from doremi.ui.widgets.song_card import SongCard
        
        self.related_scroll.verticalScrollBar().setValue(0)
        while self.related_layout.count():
            item = self.related_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not tracks:
            msg = QLabel("No hay canciones similares")
            msg.setFont(QFont("Inter", 14))
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            from doremi.ui.design import tokens
            msg.setStyleSheet(f"")
            self.related_layout.addWidget(msg)
            return

        for track in tracks[:12]:
            video_id = track.get('videoId', '')
            title = track.get('title', 'Unknown')
            artists = track.get('artists', [])
            if isinstance(artists, list):
                artist_names = ", ".join(a.get('name', '') for a in artists if isinstance(a, dict)) or 'Unknown'
            else:
                artist_names = str(artists) if artists else 'Unknown'
            
            duration = track.get('duration', track.get('length', ''))
            thumbnails = track.get('thumbnail', track.get('thumbnails', []))
            if isinstance(thumbnails, list):
                thumb_url = thumbnails[-1].get('url', '') if thumbnails else ''
            elif isinstance(thumbnails, dict):
                thumb_url = thumbnails.get('url', '')
            else:
                thumb_url = ''

            if video_id:
                on_play = None
                if play_callback:
                    on_play = partial(play_callback, video_id, title, artist_names, '', 0, thumb_url)
                
                card = SongCard(
                    title=title,
                    artist=artist_names,
                    duration=str(duration) if duration else '',
                    thumbnail_url=thumb_url,
                    on_play=on_play,
                    video_id=video_id,
                )
                card.download_requested.connect(lambda *a: self.download_requested.emit(*a))
                card.play_next_requested.connect(lambda *a: self.play_next_requested.emit(*a))
                card.add_to_queue_requested.connect(lambda *a: self.add_to_queue_requested.emit(*a))
                card.like_requested.connect(lambda *a: self.like_requested.emit(*a))
                card.add_to_playlist_requested.connect(lambda *a: self.add_to_playlist_requested.emit(*a))
                card.delete_download_requested.connect(lambda *a: self.delete_download_requested.emit(*a))
                card.artist_clicked.connect(lambda *a: self.artist_clicked.emit(*a))
                self.related_layout.addWidget(card)

        self.related_layout.addStretch()

    def set_liked_state(self, liked: bool) -> None:
        """Dynamically style the like button based on the liked state and active theme colors."""
        from doremi.ui.design import tokens
        from doremi.ui.design.icons import Icon
        from PySide6.QtGui import QColor
        
        like_c = QColor(tokens.CURRENT.like_color)
        lr, lg, lb = like_c.red(), like_c.green(), like_c.blue()
        
        is_light = QColor(tokens.CURRENT.bg_base).lightness() > 128
        inactive_color = "rgba(18, 18, 36, 0.55)" if is_light else "rgba(255, 255, 255, 0.5)"
        
        self.btn_like.setText(Icon.get("favorite"))
        if liked:
            self.btn_like.setStyleSheet(f"QPushButton {{ color: {tokens.CURRENT.like_color}; background: transparent; border: none; }}")
            self.btn_like.setFont(Icon.font(28, filled=True))
            self.btn_like.set_active(True)
        else:
            self.btn_like.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {inactive_color};
                    border: none;
                    border-radius: 24px;
                }}
                QPushButton:hover {{
                    background-color: rgba({lr},{lg},{lb},0.15);
                    color: {tokens.CURRENT.like_color};
                }}
            """)
            self.btn_like.setFont(Icon.font(28, filled=False))
            self.btn_like.set_active(False)

    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if self._ui_ready and event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            self._update_styles()
        super().changeEvent(event)

    def _update_styles(self) -> None:
        if not getattr(self, "_ui_ready", False):
            return
        from doremi.ui.design import tokens
        from doremi.ui.design.icons import Icon
        from PySide6.QtGui import QColor, QPixmap
        
        # Determine theme mode (light vs dark)
        is_light = QColor(tokens.CURRENT.bg_base).lightness() > 128
        
        # 1. Update collapse button
        icon_color = "#121224" if is_light else "#FFFFFF"
        hover_bg = "rgba(0, 0, 0, 0.06)" if is_light else "rgba(255, 255, 255, 0.1)"
        self.btn_collapse.setIcon(Icon.icon("expand_more", icon_color, 24))
        self.btn_collapse.setText("")
        self.btn_collapse.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                padding: 6px 16px;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background: {hover_bg};
            }}
        """)
        
        # 2. Update control buttons styling dynamically based on the theme
        text_primary = tokens.CURRENT.text_primary
        text_secondary = tokens.CURRENT.text_secondary
        
        self.title.setStyleSheet(f"color: {text_primary};")
        self.artist.setStyleSheet(f"color: {text_secondary};")
        self.time_current.setStyleSheet(f"color: {text_secondary};")
        self.time_total.setStyleSheet(f"color: {text_secondary};")
        
        self.btn_prev.setStyleSheet(f"QPushButton {{ color: {text_primary}; border: none; background: transparent; }}")
        self.btn_next.setStyleSheet(f"QPushButton {{ color: {text_primary}; border: none; background: transparent; }}")
        if hasattr(self, "btn_more"):
            self.btn_more.setStyleSheet(f"QPushButton {{ color: {text_secondary}; border: none; background: transparent; }}")
        
        self.tabs.setStyleSheet(f"""
            QTabWidget {{
                background: transparent;
                border: none;
            }}
            QTabWidget::pane {{
                background: transparent;
                border: none;
            }}
            QTabWidget QWidget {{
                background: transparent;
            }}
            QTabBar {{
                background: transparent;
            }}
            QTabBar::tab {{
                color: {text_secondary};
                background: transparent;
                padding: 10px 16px;
                border: none;
                font-family: Inter;
                font-size: 13px;
                font-weight: bold;
            }}
            QTabBar::tab:selected {{
                color: {tokens.CURRENT.accent};
                border-bottom: 2px solid {tokens.CURRENT.accent};
            }}
        """)
        
        # 3. Update shuffle and repeat states
        self.update_shuffle_repeat_state()
        
        # 4. Update lyrics style
        self.update_lyrics_style()
        
        # 5. If artwork is a placeholder, refresh its background/foreground color
        if not hasattr(self, "artwork") or not self.artwork.pixmap() or self.artwork.pixmap().isNull():
            bg = "rgba(0, 0, 0, 0.05)" if is_light else "rgba(255, 255, 255, 0.08)"
            fg = "#121224" if is_light else "#FFFFFF"
            self.artwork.setStyleSheet(f"background: {bg}; color: {fg}; border-radius: 24px;")
        else:
            self.artwork.setStyleSheet("background: transparent;")
 
        # 6. Update the like button state dynamically
        video_id = self.player.status.current_video_id
        if video_id:
            self.set_liked_state(self.btn_like._is_active)
            
        # 7. Propagate theme styles to the ambient background
        if hasattr(self, "ambient_bg"):
            self.ambient_bg.update_theme_styles()
