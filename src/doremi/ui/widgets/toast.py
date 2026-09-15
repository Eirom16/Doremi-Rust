from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QTimer, Qt, QPropertyAnimation
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget, QGraphicsOpacityEffect

from doremi.ui.design.fonts import AppFont
from doremi.ui.design.icons import Icon


class ToastNotification(QWidget):
    _ICONS = {
        "success": "check_circle",
        "error": "error",
        "info": "info",
        "warning": "warning",
    }

    def __init__(self, parent: QWidget, message: str, kind: str = "info", action_text: str = None, action_callback = None):
        super().__init__(parent, Qt.WindowType.SubWindow)
        from doremi.ui.design import tokens
        from PySide6.QtGui import QColor
        
        icon_name = self._ICONS.get(kind, "info")
        accent_hex = getattr(tokens.CURRENT, kind, tokens.CURRENT.info)
        accent_c = QColor(accent_hex)
        r, g, b = accent_c.red(), accent_c.green(), accent_c.blue()
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 20, 12)
        layout.setSpacing(10)
        layout.addWidget(Icon.label(icon_name, 20, accent_hex))
        msg = QLabel(message)
        msg.setFont(AppFont.body(13))
        msg.setWordWrap(True)
        msg.setMaximumWidth(280)
        msg.setStyleSheet(f" background: transparent;")
        layout.addWidget(msg)
        
        if action_text and action_callback:
            from PySide6.QtWidgets import QPushButton
            btn = QPushButton(action_text)
            btn.setFont(AppFont.title(13))
            btn.setStyleSheet(f"color: {accent_hex}; background: transparent; border: none; font-weight: bold;")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            
            def on_action():
                action_callback()
                self._dismiss()
                
            btn.clicked.connect(on_action)
            layout.addWidget(btn)
            
        self.setStyleSheet(f"ToastNotification {{ background-color: {tokens.CURRENT.bg_surface}; border: 1px solid rgba({r},{g},{b},0.40); border-radius: 14px; }}")
        self.adjustSize()
        parent_rect = parent.rect()
        self.move(max(20, parent_rect.width() - self.width() - 20), max(20, parent_rect.height() - self.height() - 96))
        
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)
        
        super().show()
        self.raise_()

        self._in_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._in_anim.setDuration(260)
        self._in_anim.setStartValue(0.0)
        self._in_anim.setEndValue(1.0)
        self._in_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._in_anim.start()
        QTimer.singleShot(3500, self._dismiss)

    def _dismiss(self) -> None:
        self._out_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._out_anim.setDuration(320)
        self._out_anim.setStartValue(self._opacity_effect.opacity())
        self._out_anim.setEndValue(0.0)
        self._out_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._out_anim.finished.connect(self.deleteLater)
        self._out_anim.start()

    @staticmethod
    def show(parent: QWidget, message: str, kind: str = "info", action_text: str = None, action_callback = None) -> "ToastNotification":
        return ToastNotification(parent, message, kind, action_text, action_callback)


