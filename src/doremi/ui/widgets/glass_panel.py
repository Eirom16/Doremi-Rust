from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPoint, Qt, QPropertyAnimation
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QVBoxLayout, QWidget


class GlassPanel(QWidget):
    def __init__(self, parent=None, blur_radius: int = 20):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.SubWindow | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self._opacity = 0.0
        self._blur_radius = blur_radius
        self._trigger_widget = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self._opacity_anim = QPropertyAnimation(self, b"panel_opacity", self)
        self._opacity_anim.setDuration(200)
        self._opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._pos_anim = QPropertyAnimation(self, b"pos", self)
        self._pos_anim.setDuration(200)
        self._pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _get_opacity(self) -> float:
        return self._opacity

    def _set_opacity(self, value: float) -> None:
        self._opacity = value
        self.update()

    panel_opacity = Property(float, _get_opacity, _set_opacity)

    def popup_at(self, pos: QPoint) -> None:
        from PySide6.QtCore import QTimer, QPoint
        from PySide6.QtWidgets import QApplication
        
        self._just_opened = True
        QTimer.singleShot(100, lambda: setattr(self, "_just_opened", False))

        self.adjustSize()
        target_x = pos.x()
        target_y = pos.y() + 10
        
        # Prevent cutoff on the right and bottom edges of the parent window or screen
        if self.parentWidget():
            parent_width = self.parentWidget().width()
            parent_height = self.parentWidget().height()
            
            if target_x + self.width() > parent_width:
                target_x = parent_width - self.width() - 8
            
            if target_y + self.height() > parent_height:
                target_y = pos.y() - self.height() - 10
        else:
            screen = QApplication.screenAt(pos) or QApplication.primaryScreen()
            if screen:
                if target_x + self.width() > screen.geometry().right():
                    target_x = pos.x() - self.width() + 32
                if target_y + self.height() > screen.geometry().bottom():
                    target_y = pos.y() - self.height() - 10

        # Check if already visible and not in the process of closing
        is_closing = False
        if self._opacity_anim.state() == QPropertyAnimation.State.Running and self._opacity_anim.endValue() == 0.0:
            is_closing = True

        if self.isVisible() and not is_closing:
            # Already visible and not closing, just smoothly transition to the new position if it changed
            if self._opacity_anim.state() != QPropertyAnimation.State.Running:
                self._opacity = 1.0
                self.update()
            
            target_pos = QPoint(target_x, target_y)
            if self.pos() != target_pos:
                self._pos_anim.stop()
                self._pos_anim.setStartValue(self.pos())
                self._pos_anim.setEndValue(target_pos)
                self._pos_anim.start()
            return

        self.move(target_x, target_y)
        self.raise_()
        self.show()
        
        self._opacity_anim.stop()
        self._opacity_anim.setStartValue(0.0)
        self._opacity_anim.setEndValue(1.0)
        self._opacity_anim.start()
        
        self._pos_anim.stop()
        self._pos_anim.setStartValue(QPoint(target_x, target_y - 10))
        self._pos_anim.setEndValue(QPoint(target_x, target_y))
        self._pos_anim.start()

    def dismiss(self) -> None:
        try:
            self._opacity_anim.finished.disconnect()
        except RuntimeError:
            pass
        self._opacity_anim.stop()
        self._opacity_anim.setStartValue(self._opacity)
        self._opacity_anim.setEndValue(0.0)
        self._opacity_anim.finished.connect(self.close)
        self._opacity_anim.start()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        from PySide6.QtWidgets import QApplication
        QApplication.instance().installEventFilter(self)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        from PySide6.QtWidgets import QApplication
        QApplication.instance().removeEventFilter(self)

    def mousePressEvent(self, event):
        # Accept the event so clicks inside the panel don't fall through to the parent window
        event.accept()

    def eventFilter(self, watched, event) -> bool:
        if not getattr(self, "auto_dismiss", True):
            return super().eventFilter(watched, event)
            
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QWidget, QAbstractButton, QApplication
        
        if event.type() == QEvent.Type.WindowDeactivate:
            # Only dismiss if the active window is not the GlassPanel or its children
            active = QApplication.activeWindow()
            if active is not None and active != self and not self.isAncestorOf(active):
                self.dismiss()
            return False
            
        if event.type() == QEvent.Type.MouseButtonPress:
            if getattr(self, "_just_opened", False):
                return False
                
            if not isinstance(watched, QWidget):
                return False
            
            is_inside = False
            if watched == self or self.isAncestorOf(watched):
                is_inside = True
            
            if not is_inside:
                trigger = getattr(self, "_trigger_widget", None)
                if trigger and isinstance(trigger, QWidget):
                    if watched == trigger or (isinstance(watched, QWidget) and trigger.isAncestorOf(watched)):
                        self.dismiss()
                        if isinstance(trigger, QAbstractButton):
                            return True
                        return False
                self.dismiss()
        return super().eventFilter(watched, event)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self._opacity)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(Qt.PenStyle.NoPen)
        
        # Query tokens.CURRENT dynamically for elevated background
        from doremi.ui.design import tokens
        bg_col = QColor(tokens.CURRENT.bg_elevated)
        bg_col.setAlpha(230)
        
        painter.setBrush(QBrush(bg_col))
        painter.drawRoundedRect(rect, 16, 16)
        
        # Build gradient borders with the dynamic accent color
        accent_col = QColor(tokens.CURRENT.accent)
        border = QLinearGradient(0, 0, 0, self.height())
        border.setColorAt(0, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 80))
        border.setColorAt(0.6, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 22))
        border.setColorAt(1, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 10))
        
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QBrush(border), 1.0))
        painter.drawRoundedRect(rect, 16, 16)
        painter.end()


