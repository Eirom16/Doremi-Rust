from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPointF, Qt, QPropertyAnimation
from PySide6.QtGui import QBrush, QColor, QMouseEvent, QPainter, QPaintEvent, QRadialGradient
from PySide6.QtWidgets import QPushButton


class RippleButton(QPushButton):
    def __init__(self, text: str = "", variant: str = "primary", icon_name: str = "", parent=None):
        super().__init__(text, parent)
        self.variant = variant
        self.icon_name = icon_name
        self._ripple_pos = QPointF(0, 0)
        self._ripple_opacity = 0.0
        self._ripple_radius = 0.0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(40)

        self._ripple_anim = QPropertyAnimation(self, b"ripple_opacity", self)
        self._ripple_anim.setDuration(500)
        self._ripple_anim.setStartValue(0.35)
        self._ripple_anim.setEndValue(0.0)
        self._ripple_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._radius_anim = QPropertyAnimation(self, b"ripple_rad", self)
        self._radius_anim.setDuration(500)
        self._radius_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._apply_style()

    def _apply_style(self) -> None:
        from doremi.ui.design import tokens
        from PySide6.QtGui import QColor
        accent = tokens.CURRENT.accent
        c = QColor(accent)
        r, g, b, _ = c.getRgb()
        
        # Calculate variants dynamically
        bright_hex = c.lighter(125).name()
        dark_hex = c.darker(120).name()

        err_c = QColor(tokens.CURRENT.error)
        err_r, err_g, err_b = err_c.red(), err_c.green(), err_c.blue()

        styles = {
            "primary": f"""
                QPushButton {{
                    background-color: {accent};
                    color: {tokens.CURRENT.text_on_accent};
                    border: none;
                    border-radius: 20px;
                    padding: 10px 26px;
                    font-family: 'Inter';
                    font-size: 14px;
                    font-weight: 700;
                }}
                QPushButton:hover {{ background-color: {bright_hex}; }}
                QPushButton:pressed {{ background-color: {dark_hex}; }}
                QPushButton:disabled {{ background-color: {tokens.CURRENT.bg_high};  }}
            """,
            "secondary": f"""
                QPushButton {{
                    background-color: rgba({r},{g},{b},0.12);
                    color: {accent};
                    border: 1px solid rgba({r},{g},{b},0.3);
                    border-radius: 20px;
                    padding: 10px 24px;
                    font-family: 'Inter';
                    font-size: 14px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: rgba({r},{g},{b},0.2);
                    border-color: rgba({r},{g},{b},0.6);
                }}
            """,
            "ghost": f"""
                QPushButton {{
                    background-color: transparent;
                    
                    border: none;
                    border-radius: 20px;
                    padding: 10px 20px;
                    font-family: 'Inter';
                    font-size: 14px;
                }}
                QPushButton:hover {{ background-color: {tokens.CURRENT.bg_elevated};  }}
            """,
            "danger": f"""
                QPushButton {{
                    background-color: rgba({err_r},{err_g},{err_b},0.12);
                    color: {tokens.CURRENT.error};
                    border: 1px solid rgba({err_r},{err_g},{err_b},0.3);
                    border-radius: 20px;
                    padding: 10px 24px;
                    font-family: 'Inter';
                    font-size: 14px;
                    font-weight: 600;
                }}
                QPushButton:hover {{ background-color: rgba({err_r},{err_g},{err_b},0.2); }}
            """,
        }
        self.setStyleSheet(styles.get(self.variant, styles["primary"]))

    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._apply_style()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)

    def _get_opacity(self) -> float:
        return self._ripple_opacity

    def _set_opacity(self, value: float) -> None:
        self._ripple_opacity = value
        self.update()

    ripple_opacity = Property(float, _get_opacity, _set_opacity)

    def _get_rad(self) -> float:
        return self._ripple_radius

    def _set_rad(self, value: float) -> None:
        self._ripple_radius = value
        self.update()

    ripple_rad = Property(float, _get_rad, _set_rad)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._ripple_pos = QPointF(event.position())
        self._radius_anim.stop()
        self._radius_anim.setStartValue(10.0)
        self._radius_anim.setEndValue(max(self.width(), self.height()) * 1.5)
        self._radius_anim.start()
        self._ripple_anim.stop()
        self._ripple_anim.start()
        super().mousePressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        if self._ripple_opacity <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipRect(self.rect())
        color = QColor(255, 255, 255)
        color.setAlphaF(self._ripple_opacity)
        gradient = QRadialGradient(self._ripple_pos, self._ripple_radius)
        gradient.setColorAt(0, color)
        gradient.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(self._ripple_pos, self._ripple_radius, self._ripple_radius)
        painter.end()

