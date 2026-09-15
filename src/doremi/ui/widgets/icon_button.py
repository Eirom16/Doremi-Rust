from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QSize, Qt, QPropertyAnimation, QSequentialAnimationGroup
from PySide6.QtGui import QBrush, QColor, QEnterEvent, QIcon, QPainter, QPaintEvent
from PySide6.QtWidgets import QPushButton


class IconButton(QPushButton):
    def __init__(
        self,
        icon: QIcon | None = None,
        size: int = 40,
        active_color: str = "#A78BFA",
        parent=None,
    ):
        super().__init__(parent)
        self.setFixedSize(QSize(size, size))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._active_color = QColor(active_color)
        self._is_active = False
        self._bg_opacity = 0.0
        if icon:
            self.setIcon(icon)
            self.setIconSize(QSize(size - 12, size - 12))
        
        self._user_stylesheet = ""
        self._icon_size = size // 2 + 4
        self.setStyleSheet("QPushButton { border: none; background: transparent; }")

        self._scale = 1.0
        
        self._bg_anim = QPropertyAnimation(self, b"bg_opacity", self)
        self._bg_anim.setDuration(150)
        self._bg_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._scale_anim = QPropertyAnimation(self, b"icon_scale", self)
        self._scale_anim.setDuration(250)
        
    def setFont(self, font):
        super().setFont(font)
        sz = font.pixelSize() if font.pixelSize() > 0 else font.pointSize()
        if sz > 0:
            self._icon_size = sz
        self._update_full_stylesheet()

    def setStyleSheet(self, stylesheet: str) -> None:
        self._user_stylesheet = stylesheet
        self._update_full_stylesheet()

    def _update_full_stylesheet(self) -> None:
        stylesheet = self._user_stylesheet or ""
        sz = getattr(self, "_icon_size", 0)
        if sz <= 0:
            font = self.font()
            sz = font.pixelSize() if font.pixelSize() > 0 else font.pointSize()
            if sz <= 0:
                sz = self.width() // 2 + 4 if self.width() > 0 else 18
            self._icon_size = sz
            
        fam = "Material Symbols Rounded"
        
        font_rules = []
        if "font-family" not in stylesheet:
            font_rules.append(f"font-family: '{fam}';")
        if "font-size" not in stylesheet:
            font_rules.append(f"font-size: {sz}px;")
            
        if font_rules:
            rules_str = " ".join(font_rules)
            stylesheet = stylesheet + f"\nQPushButton, IconButton {{ {rules_str} }}"
            
        super().setStyleSheet(stylesheet)

    def set_active(self, active: bool) -> None:
        was_active = self._is_active
        self._is_active = active
        self.update()
        if active and not was_active and self.isVisible():
            self.pulse()

    def pulse(self) -> None:
        if hasattr(self, "_scale_anim"):
            self._scale_anim.stop()
        if hasattr(self, "_pulse_anim"):
            self._pulse_anim.stop()
            
        group = QSequentialAnimationGroup(self)
        
        # First heartbeat peak
        a1 = QPropertyAnimation(self, b"icon_scale", self)
        a1.setDuration(120)
        a1.setStartValue(1.0)
        a1.setEndValue(1.3)
        a1.setEasingCurve(QEasingCurve.Type.OutQuad)
        
        # Intermediate release
        a2 = QPropertyAnimation(self, b"icon_scale", self)
        a2.setDuration(90)
        a2.setStartValue(1.3)
        a2.setEndValue(1.05)
        a2.setEasingCurve(QEasingCurve.Type.InQuad)
        
        # Second heartbeat peak
        a3 = QPropertyAnimation(self, b"icon_scale", self)
        a3.setDuration(90)
        a3.setStartValue(1.05)
        a3.setEndValue(1.18)
        a3.setEasingCurve(QEasingCurve.Type.OutQuad)
        
        # Return to baseline
        a4 = QPropertyAnimation(self, b"icon_scale", self)
        a4.setDuration(140)
        a4.setStartValue(1.18)
        a4.setEndValue(1.0)
        a4.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        group.addAnimation(a1)
        group.addAnimation(a2)
        group.addAnimation(a3)
        group.addAnimation(a4)
        
        self._pulse_anim = group
        group.start()

    def _get_bg(self) -> float:
        return self._bg_opacity

    def _set_bg(self, value: float) -> None:
        self._bg_opacity = value
        self.update()

    bg_opacity = Property(float, _get_bg, _set_bg)

    def _get_scale(self) -> float:
        return self._scale

    def _set_scale(self, value: float) -> None:
        self._scale = value
        self.update()

    icon_scale = Property(float, _get_scale, _set_scale)

    def enterEvent(self, event: QEnterEvent) -> None:
        self._bg_anim.stop()
        self._bg_anim.setStartValue(self._bg_opacity)
        self._bg_anim.setEndValue(1.0)
        self._bg_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._bg_anim.stop()
        self._bg_anim.setStartValue(self._bg_opacity)
        self._bg_anim.setEndValue(0.0)
        self._bg_anim.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._scale_anim.stop()
        self._scale_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scale_anim.setEndValue(0.75)
        self._scale_anim.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._scale_anim.stop()
        self._scale_anim.setEasingCurve(QEasingCurve.Type.OutElastic)
        self._scale_anim.setEndValue(1.0)
        self._scale_anim.start()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        from doremi.ui.design import tokens
        active_color = QColor(tokens.CURRENT.accent)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Apply scaling from center
        w, h = self.width(), self.height()
        painter.translate(w / 2, h / 2)
        painter.scale(self._scale, self._scale)
        painter.translate(-w / 2, -h / 2)

        if self._bg_opacity > 0:
            color = QColor(active_color if self._is_active else QColor(tokens.CURRENT.text_primary))
            color.setAlphaF(self._bg_opacity * 0.12)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(self.rect())
            
        if self.text():
            painter.setFont(self.font())
            text_color = self.palette().color(self.foregroundRole())
            # For specific elements that force color via stylesheet, we might need to parse it,
            # but usually foregroundRole is correct or text_primary
            painter.setPen(text_color)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        elif not self.icon().isNull():
            # Fallback for QIcon if set
            icon_size = self.iconSize()
            x = (w - icon_size.width()) // 2
            y = (h - icon_size.height()) // 2
            self.icon().paint(painter, x, y, icon_size.width(), icon_size.height())
            
        painter.end()

