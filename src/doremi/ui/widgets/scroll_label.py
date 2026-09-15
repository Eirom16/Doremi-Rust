from PySide6.QtWidgets import QLabel
from PySide6.QtCore import QTimer, Qt


class ScrollLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._original_text = text
        self._offset = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._scroll)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def setText(self, text):
        if not getattr(self, "_scrolling_internal", False):
            self._original_text = text
        super().setText(text)
        self._offset = 0

    def enterEvent(self, event):
        # We compare original text size hint
        if self.width() < self.sizeHint().width():
            self._timer.start(100)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._timer.stop()
        self._offset = 0
        self._scrolling_internal = True
        try:
            self.setText(self._original_text)
        finally:
            self._scrolling_internal = False
        super().leaveEvent(event)

    def _scroll(self):
        if not self._original_text:
            return
        self._offset += 1
        if self._offset > len(self._original_text):
            self._offset = 0
        self._scrolling_internal = True
        try:
            rotated = self._original_text[self._offset:] + " " + self._original_text[:self._offset]
            self.setText(rotated)
        finally:
            self._scrolling_internal = False