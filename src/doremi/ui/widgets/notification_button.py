from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QBrush, QColor, QFont

from doremi.ui.design import tokens
from doremi.ui.design.icons import Icon


class NotificationButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.has_unread = False
        self._update_styles()

    def set_unread(self, has_unread: bool):
        if self.has_unread != has_unread:
            self.has_unread = has_unread
            self.update() # Trigger repaint to draw/remove dot

    def set_panel_open(self, is_open: bool):
        if is_open:
            self.setText(Icon.get("close"))
        else:
            self.setText(Icon.get("notifications"))

    def _update_styles(self):
        from PySide6.QtGui import QColor
        text_primary = tokens.CURRENT.text_primary
        c = QColor(text_primary)
        
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 18px;
                color: {text_primary};
                font-family: "{Icon.font().family()}";
                font-size: 20px;
            }}
            QPushButton:hover {{
                background: rgba({c.red()},{c.green()},{c.blue()},0.08);
            }}
        """)
        self.setText(Icon.get("notifications"))
        self.setFont(Icon.font(20))

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

    def paintEvent(self, event):
        # Draw base text and hover background
        super().paintEvent(event)
        
        if self.has_unread:
            # Draw beautiful unread notification dot on the top right
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Use active theme's accent color for the dot
            dot_color = QColor(tokens.CURRENT.accent)
            painter.setBrush(QBrush(dot_color))
            painter.setPen(Qt.PenStyle.NoPen)
            
            # Position dot at (width - 10, 8) with diameter 8
            painter.drawEllipse(self.width() - 10, 8, 8, 8)
            painter.end()
