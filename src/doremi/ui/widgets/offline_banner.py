from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget


class OfflineBannerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._applying_style = False  # Guard against recursive changeEvent
        from doremi.ui.design import tokens
        from doremi.ui.design.icons import Icon
        from doremi.ui.design.fonts import AppFont
        
        # Margins: left/right matching the main window content
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 18, 0)
        layout.setSpacing(12)
        
        self.icon = Icon.label("wifi_off", size=18, color=tokens.CURRENT.warning)
        layout.addWidget(self.icon)
        
        self.label = QLabel("Sin conexión: reproduciendo descargas locales")
        self.label.setFont(AppFont.body(13))
        self.label.setStyleSheet("color: #FFFFFF; font-weight: 500; border: none; background: transparent;")
        layout.addWidget(self.label)
        
        layout.addStretch()
        
        # Add badge
        self.badge = QLabel("MODO OFFLINE")
        self.badge.setFont(AppFont.label(9))
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setFixedSize(96, 20)
        layout.addWidget(self.badge)
        
        self.setFixedHeight(0)
        self.setVisible(False)
        self._apply_style()

    def _apply_style(self) -> None:
        if self._applying_style:
            return
        self._applying_style = True
        try:
            from doremi.ui.design import tokens
            from PySide6.QtGui import QColor
            warn_c = QColor(tokens.CURRENT.warning)
            r, g, b = warn_c.red(), warn_c.green(), warn_c.blue()
            
            # Glassmorphic warning border, bg and floating margin
            self.setStyleSheet(f"""
                OfflineBannerWidget {{
                    background-color: rgba({r},{g},{b},0.08);
                    border: 1px solid rgba({r},{g},{b},0.25);
                    border-radius: 12px;
                    margin: 4px 18px 8px 18px;
                }}
            """)
            
            self.label.setStyleSheet(f" font-weight: 500; border: none; background: transparent;")
            
            self.badge.setStyleSheet(f"""
                QLabel {{
                    background-color: rgba({r},{g},{b},0.15);
                    color: {tokens.CURRENT.warning};
                    border: 1px solid rgba({r},{g},{b},0.4);
                    border-radius: 6px;
                    font-weight: 700;
                }}
            """)
        finally:
            self._applying_style = False
 
    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange) and not self._applying_style:
            self._apply_style()
        super().changeEvent(event)

    def show_banner(self) -> None:
        if self.isVisible() and self.height() > 0:
            return
            
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        
        self.setVisible(True)
        self.setFixedHeight(54)
        
        # Setup opacity animation
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.anim = QPropertyAnimation(self.effect, b"opacity", self)
        self.anim.setDuration(350)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.start()
        
    def hide_banner(self) -> None:
        if not self.isVisible() or self.height() == 0:
            return
            
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.anim = QPropertyAnimation(self.effect, b"opacity", self)
        self.anim.setDuration(300)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self.anim.finished.connect(self._on_hide_finished)
        self.anim.start()

    def _on_hide_finished(self) -> None:
        self.setVisible(False)
        self.setFixedHeight(0)
