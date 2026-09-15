from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPointF, QRectF, QSize, Slot, Qt, QPropertyAnimation
from PySide6.QtGui import QBrush, QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QCheckBox


class AnimatedToggle(QCheckBox):
    def __init__(
        self,
        parent=None,
        track_color: str = "#4A4A6A",
        active_color: str = "#A78BFA",
        thumb_color: str = "#FFFFFF",
        pulse_color: str = "#A78BFA",
    ):
        super().__init__(parent)
        self._track_color = QColor(track_color)
        self._active_color = QColor(active_color)
        self._thumb_color = QColor(thumb_color)
        self._pulse_color = QColor(pulse_color)
        self._thumb_pos = 0.0
        self._pulse_radius = 0.0
        self.setFixedSize(52, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setText("")

        self._thumb_anim = QPropertyAnimation(self, b"thumb_position", self)
        self._thumb_anim.setDuration(220)
        self._thumb_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self._pulse_anim = QPropertyAnimation(self, b"pulse_radius", self)
        self._pulse_anim.setDuration(300)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Connect directly to toggled instead of stateChanged for flawless boolean trigger
        self.toggled.connect(self._animate_toggled)

    def hitButton(self, pos) -> bool:
        """Make the entire widget boundary interactive and clickable."""
        return self.rect().contains(pos)

    def _get_thumb_pos(self) -> float:
        return self._thumb_pos

    def _set_thumb_pos(self, pos: float) -> None:
        self._thumb_pos = pos
        self.update()

    thumb_position = Property(float, _get_thumb_pos, _set_thumb_pos)

    def _get_pulse(self) -> float:
        return self._pulse_radius

    def _set_pulse(self, radius: float) -> None:
        self._pulse_radius = radius
        self.update()

    pulse_radius = Property(float, _get_pulse, _set_pulse)

    @Slot(bool)
    def _animate_toggled(self, checked: bool) -> None:
        self._thumb_anim.stop()
        self._thumb_anim.setStartValue(self._thumb_pos)
        self._thumb_anim.setEndValue(1.0 if checked else 0.0)
        self._thumb_anim.start()

        self._pulse_anim.stop()
        self._pulse_anim.setStartValue(0.0)
        self._pulse_anim.setEndValue(1.0)
        self._pulse_anim.start()

    def setChecked(self, checked: bool) -> None:
        super().setChecked(checked)
        # Instantly update position without animating if we are initializing (not visible yet)
        if not self.isVisible():
            self._thumb_pos = 1.0 if checked else 0.0
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        from doremi.ui.design import tokens
        self._active_color = QColor(tokens.CURRENT.accent)
        self._pulse_color = QColor(tokens.CURRENT.accent)
        # Adapt inactive track color to the active theme's disabled color token
        self._track_color = QColor(tokens.CURRENT.text_disabled)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        thumb_r = h / 2 - 3
        thumb_x = 4 + self._thumb_pos * (w - thumb_r * 2 - 8)
        thumb_y = h / 2

        t = self._thumb_pos
        track = QColor(
            int(self._track_color.red() + t * (self._active_color.red() - self._track_color.red())),
            int(self._track_color.green() + t * (self._active_color.green() - self._track_color.green())),
            int(self._track_color.blue() + t * (self._active_color.blue() - self._track_color.blue())),
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(track))
        painter.drawRoundedRect(QRectF(0, 0, w, h), h / 2, h / 2)

        if self._pulse_radius > 0:
            pulse = QColor(self._pulse_color)
            pulse.setAlpha(int(130 * (1 - self._pulse_radius)))
            painter.setBrush(QBrush(pulse))
            painter.drawEllipse(
                QPointF(thumb_x + thumb_r, thumb_y),
                thumb_r * 1.9 * self._pulse_radius,
                thumb_r * 1.9 * self._pulse_radius,
            )

        # Subtle shadow under the thumb for a premium depth aesthetic
        painter.setBrush(QColor(0, 0, 0, 45))
        painter.drawEllipse(QPointF(thumb_x + thumb_r + 0.5, thumb_y + 1), thumb_r, thumb_r)
        painter.setBrush(QBrush(self._thumb_color))
        painter.drawEllipse(QPointF(thumb_x + thumb_r, thumb_y), thumb_r, thumb_r)
        painter.end()

    def sizeHint(self) -> QSize:
        return QSize(52, 28)
