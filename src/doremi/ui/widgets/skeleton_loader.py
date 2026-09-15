from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, Qt, QPropertyAnimation
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPaintEvent
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget


class SkeletonBlock(QWidget):
    def __init__(self, width: int, height: int, radius: int = 8, parent=None):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self._radius = radius
        self._shimmer_pos = -0.3
        self._anim = QPropertyAnimation(self, b"shimmer", self)
        self._anim.setStartValue(-0.3)
        self._anim.setEndValue(1.3)
        self._anim.setDuration(1500)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._anim.setLoopCount(-1)
        self._anim.start()

    def _get_shimmer(self) -> float:
        return self._shimmer_pos

    def _is_ancestor_animating(self) -> bool:
        p = self.parentWidget()
        while p:
            if p.graphicsEffect() is not None:
                return True
            if hasattr(p, "_animating") and p._animating:
                return True
            p = p.parentWidget()
        return False

    def _set_shimmer(self, value: float) -> None:
        self._shimmer_pos = value
        if self.isVisible() and not self._is_ancestor_animating():
            self.update()

    shimmer = Property(float, _get_shimmer, _set_shimmer)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if hasattr(self, "_anim") and self._anim.state() != QPropertyAnimation.State.Running:
            self._anim.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        if hasattr(self, "_anim"):
            self._anim.stop()

    def paintEvent(self, event: QPaintEvent) -> None:
        if self._is_ancestor_animating():
            return
        from doremi.ui.design import tokens
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        
        base_color = QColor(tokens.CURRENT.bg_high)
        painter.setBrush(QBrush(base_color))
        painter.drawRoundedRect(self.rect(), self._radius, self._radius)
        
        w = self.width()
        shimmer_w = w * 0.4
        x = self._shimmer_pos * (w + shimmer_w) - shimmer_w
        gradient = QLinearGradient(x, 0, x + shimmer_w, 0)
        gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        
        accent_color = QColor(tokens.CURRENT.accent)
        shimmer_color = QColor(accent_color.red(), accent_color.green(), accent_color.blue(), 32)
        gradient.setColorAt(0.5, shimmer_color)
        gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(self.rect(), self._radius, self._radius)
        painter.end()


def make_song_skeleton(parent=None) -> QWidget:
    widget = QWidget(parent)
    row = QHBoxLayout(widget)
    row.setContentsMargins(12, 8, 12, 8)
    row.setSpacing(12)
    row.addWidget(SkeletonBlock(48, 48, 8))
    info = QVBoxLayout()
    info.setSpacing(6)
    info.addWidget(SkeletonBlock(180, 14, 7))
    info.addWidget(SkeletonBlock(110, 11, 7))
    row.addLayout(info)
    row.addStretch()
    row.addWidget(SkeletonBlock(50, 11, 7))
    return widget


class SkeletonListLoader(QWidget):
    def __init__(self, row_count: int = 6, skeleton_factory=None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)
        factory = skeleton_factory or make_song_skeleton
        for _ in range(row_count):
            layout.addWidget(factory(self))
        layout.addStretch()

