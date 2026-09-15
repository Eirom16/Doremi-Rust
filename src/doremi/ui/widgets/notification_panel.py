from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QProgressBar, QFrame
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QFont, QColor

from doremi.ui.design import tokens
from doremi.ui.design.icons import Icon
from doremi.services.download_manager import DownloadManager


class DownloadProgressRow(QWidget):
    cancel_requested = Signal(str)

    def __init__(self, video_id: str, title: str, artist: str, parent=None):
        super().__init__(parent)
        self.video_id = video_id
        self.title = title
        self.artist = artist
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # Header row: Title + Cancel Button
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self.title_lbl = QLabel(f"{self.artist} - {self.title}")
        self.title_lbl.setFont(QFont("Inter", 11, QFont.Weight.Medium))
        self.title_lbl.setStyleSheet(f"")
        header_layout.addWidget(self.title_lbl, stretch=1)

        self.cancel_btn = QPushButton()
        self.cancel_btn.setFixedSize(20, 20)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(lambda: self.cancel_requested.emit(self.video_id))
        header_layout.addWidget(self.cancel_btn)

        layout.addLayout(header_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        # Subtext row (percentage + speed)
        self.sub_lbl = QLabel("En cola...")
        self.sub_lbl.setFont(QFont("Inter", 9))
        self.sub_lbl.setStyleSheet(f"")
        layout.addWidget(self.sub_lbl)

        self._update_styles()

    def set_progress(self, progress: float, speed: str):
        self.progress_bar.setValue(int(progress))
        speed_str = f" • {speed}" if speed else ""
        self.sub_lbl.setText(f"{int(progress)}%{speed_str}")

    def _update_styles(self):
        if not hasattr(self, "title_lbl") or not hasattr(self, "sub_lbl") or not hasattr(self, "cancel_btn") or not hasattr(self, "progress_bar"):
            return
        text_primary = tokens.CURRENT.text_primary
        text_secondary = tokens.CURRENT.text_secondary
        accent = tokens.CURRENT.accent
        bg_high = tokens.CURRENT.bg_high
        c = QColor(text_primary)

        self.title_lbl.setStyleSheet(f"color: {text_primary}; background: transparent;")
        self.sub_lbl.setStyleSheet(f"color: {text_secondary}; background: transparent;")
        
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {text_secondary};
                border: none;
                border-radius: 10px;
                font-family: "{Icon.font().family()}";
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: rgba({c.red()},{c.green()},{c.blue()},0.08);
                color: {tokens.CURRENT.error};
            }}
        """)
        self.cancel_btn.setText(Icon.get("close"))

        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {bg_high};
                border: none;
                border-radius: 2.5px;
            }}
            QProgressBar::chunk {{
                background-color: {accent};
                border-radius: 2.5px;
            }}
        """)

    def changeEvent(self, event):
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._update_styles()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)

class ReleaseNotificationRow(QWidget):
    artist_clicked = Signal(str, str) # artist_name, artist_id
    song_clicked = Signal(str, str, str, str)

    def __init__(self, video_id: str, title: str, artist: str, artist_id: str, thumb_url: str, created_at, parent=None):
        super().__init__(parent)
        self.video_id = video_id
        self.title = title
        self.artist = artist
        self.artist_id = artist_id
        self.thumb_url = thumb_url
        self.created_at = created_at
        
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._build_ui()

    def _build_ui(self):
        from doremi.ui.widgets.clickable_label import ClickableLabel
        self.setMinimumHeight(68)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(12)

        # Left Avatar (Circular)
        self.avatar_img = ClickableLabel()
        self.avatar_img.set_clicked_callback(lambda: self.artist_clicked.emit(self.artist, self.artist_id or ""))
        self.avatar_img.setFixedSize(42, 42)
        self.avatar_img.setStyleSheet(f"background: {tokens.CURRENT.bg_high}; border-radius: 21px;")
        layout.addWidget(self.avatar_img)

        # Middle Content
        mid_layout = QVBoxLayout()
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.setSpacing(4)
        
        self.msg_lbl = ClickableLabel(f"<b>{self.artist}</b> subió: {self.title}")
        self.msg_lbl.set_clicked_callback(lambda: self.song_clicked.emit(self.video_id, self.title, self.artist, self.thumb_url))
        self.msg_lbl.setFont(QFont("Inter", 11))
        self.msg_lbl.setWordWrap(True)
        mid_layout.addWidget(self.msg_lbl)
        
        # Time ago string
        time_ago = self._get_time_ago(self.created_at)
        self.time_lbl = QLabel(time_ago)
        self.time_lbl.setFont(QFont("Inter", 10))
        self.time_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        mid_layout.addWidget(self.time_lbl)
        
        layout.addLayout(mid_layout, stretch=1)
        
        # Right Video Thumbnail (Rectangular)
        self.video_img = ClickableLabel()
        self.video_img.set_clicked_callback(lambda: self.song_clicked.emit(self.video_id, self.title, self.artist, self.thumb_url))
        self.video_img.setFixedSize(56, 40)
        self.video_img.setStyleSheet(f"background: {tokens.CURRENT.bg_high}; border-radius: 8px;")
        layout.addWidget(self.video_img)
        
        self._update_styles()
        
        if self.thumb_url:
            import asyncio
            asyncio.ensure_future(self._load_images())

    async def _load_images(self):
        from doremi.utils.image_cache import ImageCache
        cache = ImageCache()
        path = await cache.download(self.thumb_url)
        
        import shiboken6
        if not shiboken6.isValid(self):
            return
            
        if path:
            from PySide6.QtGui import QPixmap, QPainter, QPainterPath
            from PySide6.QtCore import Qt, QRectF
            
            pixmap = QPixmap()
            if pixmap.load(str(path)):
                # Rectangular for video
                video_pix = pixmap.scaled(56, 40, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                self.video_img.setPixmap(video_pix)
                self.video_img.setStyleSheet("background: transparent; border-radius: 8px;")
                
                # Circular for avatar
                scaled = pixmap.scaled(42, 42, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                out_pix = QPixmap(42, 42)
                out_pix.fill(Qt.GlobalColor.transparent)
                
                painter = QPainter(out_pix)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                path_obj = QPainterPath()
                path_obj.addEllipse(QRectF(0, 0, 42, 42))
                painter.setClipPath(path_obj)
                painter.drawPixmap(0, 0, scaled)
                painter.end()
                
                self.avatar_img.setPixmap(out_pix)
                self.avatar_img.setStyleSheet("background: transparent;")

    def _get_time_ago(self, created_at) -> str:
        if not created_at:
            return ""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        
        # Make created_at timezone-aware if it's naive
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
            
        diff = now - created_at
        hours = int(diff.total_seconds() / 3600)
        if hours < 1:
            mins = int(diff.total_seconds() / 60)
            return f"hace {mins} minutos"
        elif hours < 24:
            return f"hace {hours} horas"
        else:
            days = hours // 24
            return f"hace {days} días"

    def _update_styles(self):
        text_primary = tokens.CURRENT.text_primary
        text_secondary = tokens.CURRENT.text_secondary
        c = QColor(text_primary)
        
        self.msg_lbl.setStyleSheet(f"color: {text_primary}; background: transparent;")
        self.time_lbl.setStyleSheet(f"color: {text_secondary}; background: transparent;")
        
        self.setStyleSheet(f"""
            ReleaseNotificationRow {{
                background: transparent;
                border-radius: 12px;
            }}
            ReleaseNotificationRow:hover {{
                background: rgba({c.red()}, {c.green()}, {c.blue()}, 0.08);
            }}
        """)

    def changeEvent(self, event):
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._update_styles()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)


class NotificationHistoryRow(QWidget):
    def __init__(self, message: str, kind: str = "success", parent=None):
        super().__init__(parent)
        self.message = message
        self.kind = kind
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)

        # Kind icon (success, error, info)
        icon_name = "check_circle"
        if self.kind == "error":
            icon_name = "error"
        elif self.kind == "info":
            icon_name = "info"

        self.icon_lbl = QLabel(Icon.get(icon_name))
        self.icon_lbl.setFont(Icon.font(16))
        self.icon_lbl.setFixedSize(20, 20)
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_lbl)

        # Message text
        self.msg_lbl = QLabel(self.message)
        self.msg_lbl.setFont(QFont("Inter", 10))
        self.msg_lbl.setWordWrap(True)
        layout.addWidget(self.msg_lbl, stretch=1)

        self._update_styles()

    def _update_styles(self):
        if not hasattr(self, "icon_lbl") or not hasattr(self, "msg_lbl"):
            return
        text_primary = tokens.CURRENT.text_primary
        color_map = {
            "success": tokens.CURRENT.success,
            "error": tokens.CURRENT.error,
            "info": tokens.CURRENT.info
        }
        accent = color_map.get(self.kind, tokens.CURRENT.accent)
        
        self.icon_lbl.setStyleSheet(f"color: {accent}; background: transparent;")
        self.msg_lbl.setStyleSheet(f"color: {text_primary}; background: transparent;")

    def changeEvent(self, event):
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._update_styles()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)


class NotificationPanel(QWidget):
    unread_changed = Signal(bool) # Emits has_unread status
    panel_toggled = Signal(bool) # Emits whether panel is open or closed
    artist_clicked = Signal(str, str) # artist_name, artist_id
    song_clicked = Signal(str, str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("notificationPanel")
        self.setMinimumWidth(0)
        
        self._tasks_metadata = {} # video_id -> {"title": str, "artist": str}
        self._active_widgets = {} # video_id -> DownloadProgressRow
        self._history_items = []  # List of {"message": str, "kind": str}
        self.has_unread = False

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._build_ui()
        self._connect_download_manager()

    def _build_ui(self):
        root_layout = self.layout()
        if not root_layout:
            root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        
        self.container = QWidget()
        self.container.setObjectName("notificationPanelContainer")
        self.container.setFixedWidth(360)
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        root_layout.addWidget(self.container)

        # Header
        header_widget = QWidget()
        header_widget.setFixedHeight(64)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(16, 12, 16, 8)
        header_layout.setSpacing(8)

        self.title_lbl = QLabel("Notificaciones")
        self.title_lbl.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        self.title_lbl.setStyleSheet(f"color: {tokens.CURRENT.text_primary};")
        header_layout.addWidget(self.title_lbl, stretch=1)

        self.clear_btn = QPushButton("Limpiar")
        self.clear_btn.setFont(QFont("Inter", 10, QFont.Weight.Medium))
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self.clear_history)
        header_layout.addWidget(self.clear_btn)

        container_layout.addWidget(header_widget)

        # Horizontal Separator
        self.sep = QFrame()
        self.sep.setFrameShape(QFrame.Shape.HLine)
        self.sep.setFrameShadow(QFrame.Shadow.Plain)
        self.sep.setFixedHeight(1)
        container_layout.addWidget(self.sep)

        # Scroll Area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._inner = QWidget()
        self._inner.setObjectName("notificationScrollInner")
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(8, 8, 8, 12)
        self._inner_layout.setSpacing(6)
        
        # Sections inside inner layout
        # A. Empty State
        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setContentsMargins(16, 32, 16, 32)
        empty_layout.setSpacing(8)
        self.empty_icon = QLabel(Icon.get("notifications"))
        self.empty_icon.setFont(Icon.font(36))
        self.empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.empty_icon)
        self.empty_lbl = QLabel("No tienes notificaciones")
        self.empty_lbl.setFont(QFont("Inter", 11))
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.empty_lbl)
        self._inner_layout.addWidget(self.empty_widget)

        # B. Active downloads group
        self.active_container = QWidget()
        self.active_layout = QVBoxLayout(self.active_container)
        self.active_layout.setContentsMargins(0, 0, 0, 0)
        self.active_layout.setSpacing(4)
        
        self.active_hdr = QLabel("Descargas en curso")
        self.active_hdr.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.active_layout.addWidget(self.active_hdr)
        self._inner_layout.addWidget(self.active_container)
        self.active_container.hide()

        # C. History group
        self.history_container = QWidget()
        self.history_layout = QVBoxLayout(self.history_container)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.setSpacing(4)

        self.history_hdr = QLabel("Historial")
        self.history_hdr.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.history_layout.addWidget(self.history_hdr)
        self._inner_layout.addWidget(self.history_container)
        self.history_container.hide()

        # D. Releases group (New Database Notifications)
        self.releases_container = QWidget()
        self.releases_layout = QVBoxLayout(self.releases_container)
        self.releases_layout.setContentsMargins(0, 0, 0, 0)
        self.releases_layout.setSpacing(0)
        
        self.releases_hdr = QLabel("Nuevos lanzamientos")
        self.releases_hdr.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.releases_layout.addWidget(self.releases_hdr)
        self._inner_layout.addWidget(self.releases_container)
        self.releases_container.hide()

        # D. Spacer to push everything up
        self._inner_layout.addStretch(1)

        self._scroll.setWidget(self._inner)
        container_layout.addWidget(self._scroll)

        self._update_styles()

    def _update_styles(self):
        if not hasattr(self, "sep") or not hasattr(self, "clear_btn"):
            return
        text_primary = tokens.CURRENT.text_primary
        text_secondary = tokens.CURRENT.text_secondary
        bg_overlay = tokens.CURRENT.bg_overlay
        border_color = tokens.CURRENT.border
        accent = tokens.CURRENT.accent
        c = QColor(text_primary)

        self.setStyleSheet(f"""
            #notificationPanel {{
                background: transparent;
                border: none;
            }}
            #notificationPanelContainer {{
                background: {bg_overlay};
                border-left: 1px solid {border_color};
            }}
            #notificationScrollInner {{
                background: transparent;
            }}
        """)

        self.sep.setStyleSheet(f"background-color: {border_color}; border: none;")

        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {text_secondary};
                border: none;
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                color: {accent};
            }}
        """)

        if hasattr(self, "title_lbl") and self.title_lbl:
            self.title_lbl.setStyleSheet(f"color: {text_primary}; background: transparent;")
        if hasattr(self, "empty_icon") and self.empty_icon:
            self.empty_icon.setStyleSheet(f" background: transparent;")
        if hasattr(self, "empty_lbl") and self.empty_lbl:
            self.empty_lbl.setStyleSheet(f"color: {text_secondary}; background: transparent;")
        section_style = f"color: {text_secondary}; background: transparent; padding: 4px 6px 6px 6px;"
        if hasattr(self, "active_hdr") and self.active_hdr:
            self.active_hdr.setStyleSheet(section_style)
        if hasattr(self, "history_hdr") and self.history_hdr:
            self.history_hdr.setStyleSheet(section_style)
        if hasattr(self, "releases_hdr") and self.releases_hdr:
            self.releases_hdr.setStyleSheet(section_style)

        self._scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 8px 2px 8px 0;
            }}
            QScrollBar::handle:vertical {{
                background: rgba({c.red()},{c.green()},{c.blue()},0.12);
                border-radius: 3px;
                min-height: 36px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba({QColor(accent).red()},{QColor(accent).green()},{QColor(accent).blue()},0.42);
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: transparent;
                height: 0;
            }}
        """)

    def changeEvent(self, event):
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._update_styles()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)

    def _connect_download_manager(self):
        mgr = DownloadManager.get_instance()
        mgr.download_queued.connect(self._on_download_queued)
        mgr.download_started.connect(self._on_download_started)
        mgr.download_progress.connect(self._on_download_progress)
        mgr.download_completed.connect(self._on_download_completed)
        mgr.download_error.connect(self._on_download_error)

    def add_custom_notification(self, message: str, kind: str = "info"):
        """Interface for other systems (like playlist download starts) to send notifications."""
        self._history_items.append({"message": message, "kind": kind})
        
        row = NotificationHistoryRow(message, kind)
        self.history_layout.addWidget(row)
        
        # Trigger unread dot if dropdown is not currently open
        if not self.isVisible():
            self.has_unread = True
            self.unread_changed.emit(True)
            
        self._update_visibility()

    def clear_history(self):
        self._history_items.clear()
        # Remove widgets from history layout except index 0 (the header)
        while self.history_layout.count() > 1:
            item = self.history_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        self._update_visibility()

    def _update_visibility(self):
        has_active = len(self._active_widgets) > 0
        has_history = len(self._history_items) > 0
        has_releases = self.releases_layout.count() > 1

        self.active_container.setVisible(has_active)
        self.history_container.setVisible(has_history)
        self.releases_container.setVisible(has_releases)
        self.empty_widget.setVisible(not has_active and not has_history and not has_releases)
        self.clear_btn.setVisible(has_history)

        # Recalcular altura no es necesario ya que usará todo el alto
        pass

    # --- Loading from DB ---
    from qasync import asyncSlot
    
    @asyncSlot()
    async def load_db_notifications(self):
        from doremi.db.repository import NotificationRepository
        
        try:
            repo = NotificationRepository()
            releases = await repo.get_recent(limit=20)
                
            # Clear old release rows
            while self.releases_layout.count() > 1:
                item = self.releases_layout.takeAt(1)
                if item.widget():
                    item.widget().deleteLater()
                    
            # Releases
            for notif in releases:
                row = ReleaseNotificationRow(notif.video_id, notif.title, notif.artist, notif.artist_id, notif.thumbnail_url, notif.created_at)
                row.artist_clicked.connect(self.artist_clicked.emit)
                row.song_clicked.connect(self.song_clicked.emit)
                self.releases_layout.addWidget(row)
                
            self.releases_container.show()
            
            self._update_visibility()
            await repo.mark_all_read()
        except Exception as e:
            from loguru import logger
            logger.error(f"Error loading notifications for dropdown: {e}")

    def toggle_panel(self):
        if self.isVisible():
            self._close_anim()
        else:
            self.has_unread = False
            self.unread_changed.emit(False)
            self.load_db_notifications()
            self._open_anim()

    def _open_anim(self):
        self.show()
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        self.anim = QPropertyAnimation(self, b"maximumWidth")
        self.anim.setDuration(250)
        self.anim.setStartValue(0)
        self.anim.setEndValue(360)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.valueChanged.connect(self._on_anim_step)
        self.anim.finished.connect(lambda: self.panel_toggled.emit(True))
        self.anim.start()

    def _close_anim(self):
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        self.anim = QPropertyAnimation(self, b"maximumWidth")
        self.anim.setDuration(250)
        self.anim.setStartValue(self.width())
        self.anim.setEndValue(0)
        self.anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self.anim.valueChanged.connect(self._on_anim_step)
        def _on_close_finished():
            self.hide()
            self.panel_toggled.emit(False)
        self.anim.finished.connect(_on_close_finished)
        self.anim.start()

    def _on_anim_step(self, value):
        win = self.window()
        if hasattr(win, "_position_mini_player"):
            win._position_mini_player()

    # --- Slot Listeners ---
    @Slot(object)
    def _on_download_queued(self, task):
        self._tasks_metadata[task.video_id] = {
            "title": task.title,
            "artist": task.artist
        }
        
        row = DownloadProgressRow(task.video_id, task.title, task.artist)
        row.cancel_requested.connect(lambda vid: DownloadManager.get_instance().cancel_download(vid))
        
        self.active_layout.addWidget(row)
        self._active_widgets[task.video_id] = row
        
        if not self.isVisible():
            self.has_unread = True
            self.unread_changed.emit(True)
            
        self._update_visibility()

    @Slot(str)
    def _on_download_started(self, video_id):
        # Optional styling update or just let it update with progress
        pass

    @Slot(str, float, str)
    def _on_download_progress(self, video_id, progress, speed):
        if video_id in self._active_widgets:
            self._active_widgets[video_id].set_progress(progress, speed)

    @Slot(str, str)
    def _on_download_completed(self, video_id, filepath):
        # Move from active to history
        meta = self._tasks_metadata.get(video_id, {"title": video_id, "artist": "Canción"})
        title = meta["title"]
        artist = meta["artist"]

        # Clean active widget
        if video_id in self._active_widgets:
            widget = self._active_widgets.pop(video_id)
            self.active_layout.removeWidget(widget)
            widget.deleteLater()

        # Add history entry
        msg = f"Descarga finalizada: {artist} - {title}"
        self.add_custom_notification(msg, "success")

    @Slot(str, str)
    def _on_download_error(self, video_id, error_msg):
        # Move from active to history
        meta = self._tasks_metadata.get(video_id, {"title": video_id, "artist": "Canción"})
        title = meta["title"]

        # Clean active widget
        if video_id in self._active_widgets:
            widget = self._active_widgets.pop(video_id)
            self.active_layout.removeWidget(widget)
            widget.deleteLater()

        # Add history entry
        msg = f"Error al descargar '{title}': {error_msg}"
        self.add_custom_notification(msg, "error")
