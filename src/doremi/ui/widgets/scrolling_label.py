from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, Qt, QTimer, QPropertyAnimation
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget


class ScrollingLabel(QWidget):
    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._text = text
        self._offset = 0.0
        from doremi.ui.design import tokens
        from doremi.ui.design.fonts import AppFont
        self._color = QColor(tokens.CURRENT.text_primary)
        self._font = AppFont.title(14)
        self._scrolling = False
        self.setFixedHeight(24)
        self._anim = QPropertyAnimation(self, b"scroll_offset", self)
        self._anim.setEasingCurve(QEasingCurve.Type.Linear)
        self._anim.finished.connect(self._on_anim_finished)
        self._pause_timer = QTimer(self)
        self._pause_timer.setSingleShot(True)
        self._pause_timer.timeout.connect(self._start_scroll)

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float) -> None:
        self._offset = value
        self.update()

    scroll_offset = Property(float, _get_offset, _set_offset)

    def setText(self, text: str) -> None:
        self._text = text
        self._offset = 0.0
        self._anim.stop()
        self._check_overflow()
        self.update()

    def text(self) -> str:
        return self._text

    def setColor(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def setFont(self, font: QFont) -> None:
        self._font = font
        self._check_overflow()
        self.update()

    def resizeEvent(self, event) -> None:
        self._check_overflow()
        super().resizeEvent(event)

    def _check_overflow(self) -> None:
        fm = QFontMetrics(self._font)
        self._scrolling = fm.horizontalAdvance(self._text) > self.width() and self.width() > 0
        if self._scrolling:
            self._pause_timer.start(1500)

    def _start_scroll(self) -> None:
        fm = QFontMetrics(self._font)
        distance = max(0, fm.horizontalAdvance(self._text) - self.width() + 28)
        if distance <= 0:
            return
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(float(distance))
        self._anim.setDuration(max(1200, int(distance * 18)))
        self._anim.start()

    def _on_anim_finished(self) -> None:
        self._offset = 0.0
        self._pause_timer.start(1200)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self._font)
        painter.setPen(self._color)
        painter.setClipRect(self.rect())
        painter.drawText(
            int(-self._offset),
            0,
            self.width() + int(self._offset) + 220,
            self.height(),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._text,
        )
        if self._scrolling:
            from doremi.ui.design import tokens
            fade = QLinearGradient(self.width() - 30, 0, self.width(), 0)
            fade.setColorAt(0, QColor(0, 0, 0, 0))
            fade.setColorAt(1, QColor(tokens.CURRENT.bg_elevated))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(fade))
            painter.drawRect(self.width() - 30, 0, 30, self.height())
        painter.end()

