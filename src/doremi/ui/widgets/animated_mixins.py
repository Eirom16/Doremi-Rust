from PySide6.QtCore import QVariantAnimation, QEvent
from PySide6.QtGui import QColor

class HoverColorAnimationMixin:
    """
    Mixin to add smooth hover color animations to QWidget subclasses.
    Target must implement setStyleSheet or handle color updates.
    """
    def init_hover_animation(self, normal_color: str, hover_color: str, duration: int = 150):
        self._normal_color = QColor(normal_color)
        self._hover_color = QColor(hover_color)
        
        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(duration)
        self._hover_anim.setStartValue(self._normal_color)
        self._hover_anim.setEndValue(self._hover_color)
        self._hover_anim.valueChanged.connect(self._on_hover_color_changed)
        
        self._current_hover_color = self._normal_color

    def _on_hover_color_changed(self, color: QColor):
        self._current_hover_color = color
        self._update_hover_stylesheet()

    def _update_hover_stylesheet(self):
        # Subclasses should override this method to apply the color, for example:
        # self.setStyleSheet(f"background-color: {self._current_hover_color.name(QColor.HexArgb)}; border-radius: 12px;")
        pass

    def enterEvent(self, event):
        self._hover_anim.setDirection(QVariantAnimation.Forward)
        self._hover_anim.start()
        if hasattr(super(), 'enterEvent'):
            super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_anim.setDirection(QVariantAnimation.Backward)
        self._hover_anim.start()
        if hasattr(super(), 'leaveEvent'):
            super().leaveEvent(event)
