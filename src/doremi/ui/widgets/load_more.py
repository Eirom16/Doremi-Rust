from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt, Signal
from doremi.ui.design.icons import Icon
from doremi.ui.design.fonts import AppFont
from doremi.ui.design import tokens
from doremi.ui.widgets.animated_mixins import HoverColorAnimationMixin

class LoadMoreButton(QPushButton, HoverColorAnimationMixin):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.init_hover_animation(normal_color="transparent", hover_color="#2A2A40")
        self.setFont(AppFont.title(14))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(48)
        self._apply_style()

    def _apply_style(self):
        c = tokens.CURRENT.text_secondary
        self.setStyleSheet(f"""
            QPushButton {{
                color: {c};
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 24px;
                background: transparent;
            }}
        """)

    def _update_hover_stylesheet(self):
        from PySide6.QtGui import QColor
        bg = self._current_hover_color.name(QColor.HexArgb)
        c = tokens.CURRENT.text_primary
        self.setStyleSheet(f"""
            QPushButton {{
                color: {c};
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 24px;
                background: {bg};
            }}
        """)


class LoadingSpinnerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(48, 48)
        self._angle = 0
        from PySide6.QtCore import QTimer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        
    def start(self):
        self._timer.start(30)
        self.show()
        
    def stop(self):
        self._timer.stop()
        self.hide()
        
    def _rotate(self):
        self._angle = (self._angle + 12) % 360
        self.update()
        
    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QColor, QPen
        from PySide6.QtCore import QRectF, Qt
        painter = QPainter(self)
        if not painter.isActive():
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        pen = QPen(QColor(tokens.CURRENT.accent))
        pen.setWidth(3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        rect = QRectF(self.width() / 2 - 12, self.height() / 2 - 12, 24, 24)
        painter.drawArc(rect, -self._angle * 16, 280 * 16)


class PaginatorFooter(QWidget):
    load_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.set_state("hidden") # hidden, button, loading

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn = LoadMoreButton("Mostrar más")
        self.btn.setFixedWidth(160)
        self.btn.clicked.connect(self._on_click)
        
        self.spinner = LoadingSpinnerWidget()
        
        layout.addWidget(self.btn)
        layout.addWidget(self.spinner)

    def _on_click(self):
        self.set_state("loading")
        self.load_requested.emit()

    def set_state(self, state: str):
        if state == "hidden":
            self.btn.hide()
            self.spinner.stop()
            self.hide()
        elif state == "button":
            self.show()
            self.spinner.stop()
            self.btn.show()
        elif state == "loading":
            self.show()
            self.btn.hide()
            self.spinner.start()
