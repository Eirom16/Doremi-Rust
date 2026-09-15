from __future__ import annotations

import asyncio

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontMetrics, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget, QPushButton

from doremi.ui.design.fonts import AppFont
from doremi.ui.design.icons import Icon
from doremi.utils.image_cache import ImageCache

_image_cache = ImageCache()


from doremi.ui.widgets.animated_mixins import HoverColorAnimationMixin

class PlaylistCard(QWidget, HoverColorAnimationMixin):
    clicked = Signal()

    def __init__(self, title: str, description: str = "", thumbnail_url: str = "", is_downloaded: bool = False):
        super().__init__()
        self.init_hover_animation(normal_color="#10101E", hover_color="#16162A")
        self._title = title
        self._description = description
        self._thumbnail_url = thumbnail_url
        
        # Selection mode checkbox (absolutely positioned inside top-left corner)
        self.checkbox = QPushButton(self)
        self.checkbox.setFixedSize(24, 24)
        self.checkbox.setCheckable(True)
        self.checkbox.setChecked(False)
        self.checkbox.setFont(Icon.font(14))
        self.checkbox.setText("")
        self.checkbox.toggled.connect(lambda checked: self.checkbox.setText(Icon.get("check") if checked else ""))
        self.checkbox.hide()
        self.checkbox.move(10, 10)

        # Offline download badge (absolutely positioned inside top-right corner over thumbnail)
        self.offline_badge = QLabel(self)
        self.offline_badge.setFixedSize(20, 20)
        self.offline_badge.setFont(Icon.font(11))
        self.offline_badge.setText(Icon.get("download_done"))
        self.offline_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.offline_badge.setStyleSheet("""
            QLabel {
                background-color: #1DB954;
                color: #FFFFFF;
                border-radius: 10px;
                border: 1px solid rgba(0, 0, 0, 0.2);
                font-family: 'Material Symbols Rounded';
                font-size: 11px;
            }
        """)
        self.offline_badge.move(138, 10)
        if is_downloaded:
            self.offline_badge.show()
        else:
            self.offline_badge.hide()
        
        self._build_ui()
        
        if self._thumbnail_url:
            asyncio.ensure_future(self._load_thumbnail())

    def set_downloaded(self, is_downloaded: bool) -> None:
        if is_downloaded:
            self.offline_badge.show()
        else:
            self.offline_badge.hide()

    async def _load_thumbnail(self) -> None:
        path = await _image_cache.download(self._thumbnail_url)
        import shiboken6
        if not shiboken6.isValid(self):
            return
            
        if path:
            from PySide6.QtGui import QPixmapCache
            cache_key = f"{path}_148_148"
            pixmap = QPixmap()
            if QPixmapCache.find(cache_key, pixmap):
                self.thumbnail.setPixmap(pixmap)
                self.thumbnail.setStyleSheet("background: transparent; border-radius: 12px;")
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
                            self.thumbnail.setStyleSheet("background: transparent; border-radius: 12px;")
                load_scaled_async(path, 148, 148, self, on_loaded)

    def _build_ui(self) -> None:
        self.setObjectName("playlistCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        accessible = f"{self._title} - {self._description}" if self._description else self._title
        self.setAccessibleName(accessible)
        self.setFixedSize(168, 218)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.thumbnail = QLabel(Icon.get("playlist_play"))
        self.thumbnail.setFixedSize(148, 148)
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setFont(Icon.font(56))
        layout.addWidget(self.thumbnail)

        self.title_label = QLabel(self._elide(self._title, 148))
        self.title_label.setFont(AppFont.title(11))
        self.title_label.setToolTip(self._title)
        layout.addWidget(self.title_label)

        if self._description:
            self.desc_label = QLabel(self._elide(self._description, 148))
            self.desc_label.setFont(AppFont.label(10))
            self.desc_label.setToolTip(self._description)
            layout.addWidget(self.desc_label)
        self._update_card_styles()

    def _update_card_styles(self) -> None:
        from doremi.ui.design import tokens
        accent = tokens.CURRENT.accent
        text_primary = tokens.CURRENT.text_primary
        text_secondary = tokens.CURRENT.text_secondary
        bg_surface = tokens.CURRENT.bg_surface
        bg_elevated = tokens.CURRENT.bg_elevated
        bg_high = tokens.CURRENT.bg_high
        border_color = tokens.CURRENT.border
        
        from PySide6.QtGui import QColor
        acc_c = QColor(accent)
        acc_r, acc_g, acc_b = acc_c.red(), acc_c.green(), acc_c.blue()

        self.setStyleSheet(f"""
            #playlistCard {{
                background-color: {bg_surface};
                border-radius: 12px;
                border: 1px solid {border_color};
            }}
            #playlistCard:hover {{
                background-color: {bg_elevated};
                border-color: rgba({acc_r}, {acc_g}, {acc_b}, 0.33);
            }}
            #playlistCard:focus {{
                background-color: {bg_elevated};
                border: 2px solid {accent};
            }}
        """)
        
        if not self.thumbnail.pixmap():
            self.thumbnail.setStyleSheet(f"""
                background: {bg_high};
                color: {text_secondary};
                border-radius: 12px;
            """)
        else:
            self.thumbnail.setStyleSheet("background: transparent; border-radius: 12px;")
            
        self.title_label.setStyleSheet(f"color: {text_primary}; background: transparent;")
        if hasattr(self, 'desc_label'):
            self.desc_label.setStyleSheet(f"color: {text_secondary}; background: transparent;")
            
        self.checkbox.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(30, 30, 40, 0.8);
                border: 2px solid {border_color};
                border-radius: 12px;
                color: #FFFFFF;
                font-family: 'Material Symbols Rounded';
                font-size: 14px;
            }}
            QPushButton:checked {{
                background-color: {accent};
                border-color: {accent};
                color: #FFFFFF;
            }}
        """)

    def _elide(self, text: str, width: int) -> str:
        return QFontMetrics(AppFont.label(10)).elidedText(text, Qt.TextElideMode.ElideRight, width)

    def set_selection_mode(self, enabled: bool) -> None:
        self.selection_mode = enabled
        if enabled:
            self.checkbox.show()
        else:
            self.checkbox.hide()
            self.checkbox.setChecked(False)

    def enterEvent(self, event):
        self.checkbox.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.checkbox.isChecked():
            self.checkbox.hide()
        super().leaveEvent(event)

    def _update_hover_stylesheet(self):
        from PySide6.QtGui import QColor
        bg = self._current_hover_color.name(QColor.HexArgb)
        self.setStyleSheet(f"#playlistCard {{ background-color: {bg}; border-radius: 12px; border: 1px solid rgba(167,139,250,0.12); }}")

    def mousePressEvent(self, event) -> None:
        if getattr(self, "selection_mode", False):
            self.checkbox.setChecked(not self.checkbox.isChecked())
        else:
            if event.button() == Qt.MouseButton.LeftButton:
                self.clicked.emit()
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() not in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            super().keyPressEvent(event)
            return
        if getattr(self, "selection_mode", False):
            self.checkbox.setChecked(not self.checkbox.isChecked())
        else:
            self.clicked.emit()
        event.accept()

    def paintEvent(self, event) -> None:
        from PySide6.QtWidgets import QStyle, QStyleOption
        from PySide6.QtGui import QPainter
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)
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
