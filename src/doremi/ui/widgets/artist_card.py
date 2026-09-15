from __future__ import annotations

import asyncio

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontMetrics, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from doremi.ui.design.fonts import AppFont
from doremi.ui.design.icons import Icon
from doremi.utils.image_cache import ImageCache

_image_cache = ImageCache()


class ArtistCard(QWidget):
    clicked = Signal()

    def __init__(self, name: str, thumbnail_url: str = ""):
        super().__init__()
        self._name = name
        self._thumbnail_url = thumbnail_url
        self._build_ui()
        if self._thumbnail_url:
            asyncio.ensure_future(self._load_thumbnail())

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
                self.thumbnail.setStyleSheet("background: transparent; border-radius: 74px;")
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
                            self.thumbnail.setStyleSheet("background: transparent; border-radius: 74px;")
                load_scaled_async(path, 148, 148, self, on_loaded)

    def _build_ui(self) -> None:
        self.setObjectName("artistCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(self._name)
        self.setFixedSize(168, 210)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.thumbnail = QLabel(Icon.get("person"))
        self.thumbnail.setFixedSize(148, 148)
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setFont(Icon.font(58))
        layout.addWidget(self.thumbnail, alignment=Qt.AlignmentFlag.AlignCenter)

        self.name_label = QLabel(self._elide(self._name, 148))
        self.name_label.setFont(AppFont.title(11))
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setToolTip(self._name)
        layout.addWidget(self.name_label)
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
            #artistCard {{
                background-color: {bg_surface};
                border-radius: 12px;
                border: 1px solid {border_color};
            }}
            #artistCard:hover {{
                background-color: {bg_elevated};
                border-color: rgba({acc_r}, {acc_g}, {acc_b}, 0.33);
            }}
            #artistCard:focus {{
                background-color: {bg_elevated};
                border: 2px solid {accent};
            }}
        """)
        
        if not self.thumbnail.pixmap():
            self.thumbnail.setStyleSheet(f"""
                background: {bg_high};
                color: {text_secondary};
                border-radius: 74px;
            """)
        else:
            self.thumbnail.setStyleSheet("background: transparent; border-radius: 74px;")
            
        self.name_label.setStyleSheet(f"color: {text_primary}; background: transparent;")

    def _elide(self, text: str, width: int) -> str:
        return QFontMetrics(AppFont.title(11)).elidedText(text, Qt.TextElideMode.ElideRight, width)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)

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
