from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent, QFont


class ClickableLabel(QLabel):
    clicked = Signal()

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._callback = None

    def set_clicked_callback(self, callback):
        self._callback = callback
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._callback:
            self._callback()
        super().mousePressEvent(event)

    def enterEvent(self, event):
        if self._callback:
            font = self.font()
            font.setUnderline(True)
            self.setFont(font)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._callback:
            font = self.font()
            font.setUnderline(False)
            self.setFont(font)
        super().leaveEvent(event)