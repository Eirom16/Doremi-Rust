from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Property, QEasingCurve, Qt, QPropertyAnimation
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget


class AnimatedProgressBar(QWidget):
    ACCENT_COLOR = "#A78BFA"
    DARK_ACCENT_COLOR = "#8B5CF6"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self._value = 0.0
        self._display_value = 0.0
        self._hover = False
        self._dragging = False
        self._hover_pos = 0.0
        self.on_seek: Callable[[float], None] | None = None

        self._anim = QPropertyAnimation(self, b"display_val", self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_value(self, value: float, animated: bool = True) -> None:
        if self._dragging:
            return
        bounded = max(0.0, min(1.0, value))
        self._value = bounded
        if animated:
            self._anim.stop()
            self._anim.setStartValue(self._display_value)
            self._anim.setEndValue(bounded)
            self._anim.start()
        else:
            self._display_value = bounded
            self.update()

    def _get_display(self) -> float:
        return self._display_value

    def _set_display(self, value: float) -> None:
        self._display_value = value
        self.update()

    display_val = Property(float, _get_display, _set_display)

    def paintEvent(self, event: QPaintEvent) -> None:
        from doremi.ui.design import tokens
        accent = tokens.CURRENT.accent
        accent_bright = tokens.CURRENT.accent_bright

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        bar_h = 6 if self._hover else 4
        bar_y = (h - bar_h) / 2
        radius = bar_h / 2

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(42, 42, 74)))
        painter.drawRoundedRect(0, bar_y, w, bar_h, radius, radius)

        fill_w = int(w * self._display_value)
        if fill_w > 0:
            gradient = QLinearGradient(0, 0, w, 0)
            gradient.setColorAt(0.0, QColor(accent_bright))
            gradient.setColorAt(1.0, QColor(accent))
            painter.setBrush(QBrush(gradient))
            painter.drawRoundedRect(0, bar_y, fill_w, bar_h, radius, radius)

        if self._hover or self._dragging:
            thumb_x = w * (self._hover_pos if self._dragging else self._display_value)
            thumb_r = 7
            painter.setBrush(QBrush(QColor(0, 0, 0, 70)))
            painter.drawEllipse(int(thumb_x - thumb_r + 1), int(h / 2 - thumb_r + 1), thumb_r * 2, thumb_r * 2)
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            painter.drawEllipse(int(thumb_x - thumb_r), int(h / 2 - thumb_r), thumb_r * 2, thumb_r * 2)
        painter.end()

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._dragging = True
        self._seek_from_event(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self._hover_pos = self._pct(event)
        if self._dragging:
            self._seek_from_event(event)
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._dragging = False
        self._seek_from_event(event)

    def _pct(self, event: QMouseEvent) -> float:
        if self.width() <= 0:
            return 0.0
        return max(0.0, min(1.0, event.position().x() / self.width()))

    def _seek_from_event(self, event: QMouseEvent) -> None:
        pct = self._pct(event)
        self._display_value = pct
        self._value = pct
        if self.on_seek:
            self.on_seek(pct)
        self.update()

