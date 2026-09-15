from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QStackedWidget


class FadeStackedWidget(QStackedWidget):
    DURATION = 260

    def __init__(self, parent=None):
        super().__init__(parent)
        self._animating = False
        self._running_animations: list[QPropertyAnimation] = []

    def setCurrentIndexAnimated(self, index: int) -> None:
        if self._animating or index == self.currentIndex():
            return
        current = self.currentWidget()
        next_widget = self.widget(index)
        if current is None or next_widget is None:
            self.setCurrentIndex(index)
            return

        # QQuickWidget + QGraphicsOpacityEffect = parpadeo/render roto.
        # Las islas QML cambian sin cross-fade (la animación va dentro del QML).
        def _is_qml_island(w) -> bool:
            try:
                if getattr(w, "_qml_island", False):
                    return True
                from PySide6.QtQuickWidgets import QQuickWidget
                return bool(w.findChildren(QQuickWidget))
            except Exception:
                return False

        if _is_qml_island(current) or _is_qml_island(next_widget):
            self.setCurrentIndex(index)
            return

        self._animating = True
        out_effect = QGraphicsOpacityEffect(current)
        current.setGraphicsEffect(out_effect)
        fade_out = QPropertyAnimation(out_effect, b"opacity", self)
        fade_out.setDuration(self.DURATION // 2)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InExpo)

        def switch() -> None:
            current.setGraphicsEffect(None)
            self.setCurrentIndex(index)
            in_effect = QGraphicsOpacityEffect(next_widget)
            next_widget.setGraphicsEffect(in_effect)
            fade_in = QPropertyAnimation(in_effect, b"opacity", self)
            fade_in.setDuration(self.DURATION // 2)
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)
            fade_in.setEasingCurve(QEasingCurve.Type.OutExpo)

            def done() -> None:
                next_widget.setGraphicsEffect(None)
                self._animating = False
                self._running_animations.clear()

            fade_in.finished.connect(done)
            self._running_animations.append(fade_in)
            fade_in.start()

        fade_out.finished.connect(switch)
        self._running_animations = [fade_out]
        fade_out.start()

