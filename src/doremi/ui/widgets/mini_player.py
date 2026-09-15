from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QSizePolicy, QGraphicsOpacityEffect, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, Signal, QSize, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPixmap, QFont
from doremi.audio.player import PlayerState
from doremi.utils.time_utils import format_duration_short
import asyncio
from doremi.utils.image_cache import ImageCache
from doremi.ui.design.fonts import AppFont
from doremi.ui.design.icons import Icon
from doremi.ui.design import tokens
from doremi.ui.widgets.animated_progress import AnimatedProgressBar
from doremi.ui.widgets.icon_button import IconButton
from doremi.ui.widgets.scrolling_label import ScrollingLabel

_image_cache = ImageCache()


class ArtworkLoadingOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._angle = 0
        from PySide6.QtCore import QTimer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self.hide()
        
    def start(self):
        self._timer.start(30)
        self.show()
        
    def stop(self):
        self._timer.stop()
        self.hide()
        
    def _rotate(self):
        self._angle = (self._angle + 12) % 360
        self.update()
        
    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QColor, QPen
        from PySide6.QtCore import QRectF
        painter = QPainter(self)
        if not painter.isActive():
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Dark overlay
        painter.fillRect(self.rect(), QColor(0, 0, 0, 150))
        
        # Spinner
        pen = QPen(QColor(tokens.CURRENT.accent))
        pen.setWidth(3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        rect = QRectF(self.width() / 2 - 12, self.height() / 2 - 12, 24, 24)
        painter.drawArc(rect, -self._angle * 16, 120 * 16)
        painter.end()


class MiniPlayerWidget(QWidget):
    on_expand = Signal()
    on_prev = Signal()
    on_play_pause = Signal()
    on_next = Signal()
    on_seek = Signal(int)
    artist_clicked = Signal(str)

    def __init__(self, player, queue, on_expand, on_prev, on_play_pause, on_next, on_seek, parent=None):
        super().__init__(parent)
        self.player = player
        self.queue = queue
        self._is_playing = False
        
        # Connect signals to the passed callbacks
        self.on_expand.connect(on_expand)
        self.on_prev.connect(on_prev)
        self.on_play_pause.connect(on_play_pause)
        self.on_next.connect(on_next)
        self.on_seek.connect(on_seek)
            
        self._build_ui()

    def _get_player_height(self) -> int:
        return self.height()

    def _set_player_height(self, value: int):
        self.setFixedHeight(value)
        positioner = getattr(self.window(), "_position_mini_player", None)
        if callable(positioner):
            positioner()

    player_height = Property(int, _get_player_height, _set_player_height)

    def show_animated(self):
        if self._is_visible:
            return
        self._is_visible = True
        
        self._pop_anim = QPropertyAnimation(self, b"player_height", self)
        self._pop_anim.setDuration(600)
        self._pop_anim.setStartValue(0)
        self._pop_anim.setEndValue(88)
        self._pop_anim.setEasingCurve(QEasingCurve.Type.OutExpo)
        self._pop_anim.start()

    def _build_ui(self):
        self.setObjectName("miniPlayer")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(0) # Initially hidden
        self._is_visible = False

        self.setStyleSheet("""
            #miniPlayer {
                background: transparent;
            }
        """)

        # Outer layout with margins so the player keeps its floating capsule shape.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 4, 12, 4)
        outer.setSpacing(0)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Inner card
        self.card = QWidget()
        self.card.setObjectName("playerCard")
        self.card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        card_layout = QHBoxLayout(self.card)
        card_layout.setContentsMargins(12, 9, 16, 9)
        card_layout.setSpacing(14)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # ── Artwork ──
        self.artwork = QLabel()
        self.artwork.setFixedSize(60, 60)
        self.artwork.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.artwork.setText(Icon.get("library_music"))
        self.artwork.setFont(Icon.font(28))
        self.artwork.setStyleSheet("background: transparent;")
        
        self.artwork_overlay = ArtworkLoadingOverlay(self.artwork)
        self.artwork_overlay.setFixedSize(60, 60)
        
        card_layout.addWidget(self.artwork)

        # ── Song info ──
        info_widget = QWidget()
        info_widget.setObjectName("miniPlayerInfo")
        info_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        info_widget.setStyleSheet("#miniPlayerInfo { background: transparent; }")
        info_widget.setFixedWidth(220)
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.title = ScrollingLabel("Sin reproduccion")
        self.title.setFont(AppFont.title(13))
        self.title.setColor(tokens.CURRENT.text_primary)
        self.title.setFixedWidth(220)
        info_layout.addWidget(self.title)

        from doremi.ui.widgets.clickable_label import ClickableLabel
        self.artist = ClickableLabel("")
        self.artist.set_clicked_callback(self._on_artist_clicked)
        self.artist.setFont(AppFont.label(10))
        self.artist.setMaximumWidth(220)
        info_layout.addWidget(self.artist)

        card_layout.addWidget(info_widget)

        # ── Progress section (time + slider + time) ──
        progress_widget = QWidget()
        progress_widget.setObjectName("miniPlayerProgress")
        progress_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        progress_widget.setStyleSheet("#miniPlayerProgress { background: transparent; }")
        progress_layout = QHBoxLayout(progress_widget)
        progress_layout.setContentsMargins(4, 0, 4, 0)
        progress_layout.setSpacing(10)
        progress_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.time_current = QLabel("0:00")
        self.time_current.setFont(AppFont.mono(10))
        self.time_current.setStyleSheet(f"")
        self.time_current.setFixedWidth(36)
        self.time_current.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        progress_layout.addWidget(self.time_current)

        self.progress = AnimatedProgressBar()
        self.progress.setEnabled(False)
        self.progress.on_seek = self._on_progress_seek
        progress_layout.addWidget(self.progress, stretch=1)

        self.time_total = QLabel("0:00")
        self.time_total.setFont(AppFont.mono(10))
        self.time_total.setStyleSheet(f"")
        self.time_total.setFixedWidth(36)
        self.time_total.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        progress_layout.addWidget(self.time_total)

        card_layout.addWidget(progress_widget, stretch=1)

        # ── Playback controls ── (larger icons, better spacing)
        controls = QHBoxLayout()
        controls.setSpacing(4)
        controls.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.btn_prev = self._make_control_btn("skip_previous", size=28, color=tokens.CURRENT.text_primary, btn_size=42)
        self.btn_prev.setAccessibleName("Pista anterior")
        self.btn_prev.clicked.connect(lambda: self.on_prev.emit())
        controls.addWidget(self.btn_prev)

        self.btn_play = self._make_control_btn("play_arrow", size=36, color=tokens.CURRENT.text_on_accent, btn_size=52, primary=True)
        self.btn_play.setAccessibleName("Reproducir o Pausar")
        self.btn_play.clicked.connect(lambda: self.on_play_pause.emit())
        controls.addWidget(self.btn_play)

        self.btn_next = self._make_control_btn("skip_next", size=28, color=tokens.CURRENT.text_primary, btn_size=42)
        self.btn_next.setAccessibleName("Pista siguiente")
        self.btn_next.clicked.connect(lambda: self.on_next.emit())
        controls.addWidget(self.btn_next)

        controls.addSpacing(8)

        self.btn_expand = self._make_control_btn("expand_less", size=24, color=tokens.CURRENT.text_secondary, btn_size=38)
        self.btn_expand.setAccessibleName("Expandir reproductor")
        self.btn_expand.clicked.connect(lambda: self.on_expand.emit())
        controls.addWidget(self.btn_expand)

        card_layout.addLayout(controls)

        outer.addWidget(self.card)
        self._update_mini_player_styles()

    def _on_artist_clicked(self):
        text = self.artist.text()
        if text:
            self.artist_clicked.emit(text)

    @staticmethod
    def _make_control_btn(icon_name, size=24, color="#FFFFFF", btn_size=40, primary=False):
        from PySide6.QtWidgets import QPushButton
        from doremi.ui.design import tokens
        if primary:
            btn = QPushButton()
            btn.setText(Icon.get(icon_name))
            btn.setFont(Icon.font(size))
            btn.setFixedSize(btn_size, btn_size)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            radius = btn_size // 2
            btn.setObjectName("primaryPlayBtn")
            btn.setStyleSheet(f"QPushButton#primaryPlayBtn {{ border-radius: {radius}px; }}")
            return btn
            
        btn = IconButton(size=btn_size, active_color=tokens.CURRENT.accent_dim)
        btn.setText(Icon.get(icon_name))
        btn.setFont(Icon.font(size))
        btn.setFixedSize(btn_size, btn_size)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # We rely on IconButton's paintEvent for the hover background.
        btn.setStyleSheet(f"QPushButton {{ color: {color}; border: none; background: transparent; }}")
        return btn

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _on_progress_seek(self, pct: float):
        if self.player.status.duration_ms > 0:
            ms = int(pct * self.player.status.duration_ms)
            self.on_seek.emit(ms)

    def update_track_info(self, title: str, artist: str, thumbnail_url: str):
        self.show_animated()
        self.title.setText(title)
        self.artist.setText(artist)
        self.progress.setEnabled(True)

        if thumbnail_url:
            asyncio.ensure_future(self._load_thumbnail(thumbnail_url))
        else:
            self.artwork.setPixmap(QPixmap())
            self.artwork.setText(Icon.get("library_music"))
            self.artwork.setFont(Icon.font(28))
            self._update_mini_player_styles()

    async def _load_thumbnail(self, url: str):
        path = await _image_cache.download(url)
        import shiboken6
        if not shiboken6.isValid(self):
            return
        if path:
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                # Clip artwork to rounded rect
                size = 60
                radius = 10
                from PySide6.QtGui import QPainter, QPainterPath
                from PySide6.QtCore import QRectF
                scaled = pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                x = (scaled.width() - size) // 2
                y = (scaled.height() - size) // 2
                cropped = scaled.copy(x, y, size, size)
                rounded = QPixmap(size, size)
                rounded.fill(Qt.GlobalColor.transparent)
                painter = QPainter(rounded)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                clip_path = QPainterPath()
                clip_path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
                painter.setClipPath(clip_path)
                painter.drawPixmap(0, 0, cropped)
                painter.end()

                # Remove any previous graphics effect to avoid QPainter conflicts
                if self.artwork.graphicsEffect():
                    self.artwork.setGraphicsEffect(None)
                if hasattr(self, '_fade_anim') and self._fade_anim:
                    self._fade_anim.stop()

                # Fade-in transition for the new artwork
                effect = QGraphicsOpacityEffect(self.artwork)
                self.artwork.setGraphicsEffect(effect)
                
                self.artwork.setPixmap(rounded)
                self.artwork.setText("")
                self.artwork.setStyleSheet("background: transparent;")
                
                self._fade_anim = QPropertyAnimation(effect, b"opacity", self)
                self._fade_anim.setDuration(250)
                self._fade_anim.setStartValue(0.0)
                self._fade_anim.setEndValue(1.0)
                self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                self._fade_anim.finished.connect(lambda: self.artwork.setGraphicsEffect(None))
                self._fade_anim.start()

    def update_state(self, status):
        """Update play/pause icon dynamically based on player state."""
        if status.state == PlayerState.LOADING:
            self.artwork_overlay.start()
        else:
            self.artwork_overlay.stop()
            
        if status.state == PlayerState.PLAYING:
            self._is_playing = True
            self.btn_play.setText(Icon.get("pause"))
        else:
            self._is_playing = False
            self.btn_play.setText(Icon.get("play_arrow"))

    def update_position(self, position_ms: int, duration_ms: int):
        if duration_ms > 0:
            self.progress.set_value(position_ms / duration_ms)
        self.time_current.setText(format_duration_short(position_ms))
        self.time_total.setText(format_duration_short(duration_ms))

    def _update_mini_player_styles(self) -> None:
        if not hasattr(self, 'card') or not self.card:
            return
        from doremi.ui.design import tokens
        from PySide6.QtGui import QColor
        surface = QColor(tokens.CURRENT.bg_surface)
        base = QColor(tokens.CURRENT.bg_base)
        accent = QColor(tokens.CURRENT.accent)
        is_light = base.lightness() > 150
        surface_alpha = 0.94 if is_light else 0.86
        border_alpha = 0.18 if is_light else 0.22
        hover_alpha = 0.10 if is_light else 0.14
        placeholder_bg = "rgba(0,0,0,0.08)" if is_light else "rgba(255,255,255,0.10)"
        
        if not hasattr(self, "_card_shadow"):
            self._card_shadow = QGraphicsDropShadowEffect(self.card)
            self.card.setGraphicsEffect(self._card_shadow)
        self._card_shadow.setBlurRadius(30 if is_light else 34)
        self._card_shadow.setOffset(0, 6 if is_light else 8)
        self._card_shadow.setColor(QColor(8, 10, 20, 48 if is_light else 150))

        # 1. Floating capsule: adaptive frosted material, no nested black panels.
        self.card.setStyleSheet(f"""
            #playerCard {{
                background: rgba({surface.red()},{surface.green()},{surface.blue()},{surface_alpha});
                border-radius: 16px;
                border: 1px solid rgba({accent.red()},{accent.green()},{accent.blue()},{border_alpha});
            }}
        """)
        
        # 2. Artwork styling
        if not self.artwork.pixmap() or self.artwork.pixmap().isNull():
            self.artwork.setStyleSheet(f"""
                background: {placeholder_bg};
                border-radius: 10px;
            """)
        else:
            self.artwork.setStyleSheet("background: transparent; border-radius: 10px;")

        # 3. Label text styling
        self.title.setColor(tokens.CURRENT.text_primary)
        from doremi.ui.widgets.clickable_label import ClickableLabel
        if hasattr(self, "artist") and isinstance(self.artist, ClickableLabel):
            self.artist.setStyleSheet(f"color: {tokens.CURRENT.text_secondary}; background: transparent;")
        self.time_current.setStyleSheet(f"color: {tokens.CURRENT.text_secondary}; background: transparent;")
        self.time_total.setStyleSheet(f"color: {tokens.CURRENT.text_secondary}; background: transparent;")

        # 4. Button styles
        control_style = f"""
            QPushButton {{
                color: {tokens.CURRENT.text_secondary};
                border: none;
                background: transparent;
            }}
            QPushButton:hover {{
                color: {tokens.CURRENT.text_primary};
                background: rgba({accent.red()},{accent.green()},{accent.blue()},{hover_alpha});
            }}
        """
        self.btn_prev.setStyleSheet(control_style)
        self.btn_next.setStyleSheet(control_style)
        self.btn_expand.setStyleSheet(control_style)
        self.btn_play.setStyleSheet(f"""
            QPushButton#primaryPlayBtn {{
                background: {tokens.CURRENT.accent};
                color: {tokens.CURRENT.text_on_accent};
                border: 1px solid rgba(255,255,255,{0.48 if not is_light else 0.70});
                border-radius: 26px;
                font-family: 'Material Symbols Rounded';
                font-size: 36px;
            }}
            QPushButton#primaryPlayBtn:hover {{
                background: {tokens.CURRENT.accent_bright};
            }}
        """)

    def changeEvent(self, event):
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange, QEvent.Type.ApplicationPaletteChange):
            if not getattr(self, "_in_style_change", False):
                self._in_style_change = True
                try:
                    self._update_mini_player_styles()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)
