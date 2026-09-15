from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import QTimer, Qt


class LoadingSpinner(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.label = QLabel("⏳")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("font-size: 32px;")
        layout.addWidget(self.label)

        self.text = QLabel("Cargando...")
        self.text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text.setStyleSheet("color: #888899;")
        layout.addWidget(self.text)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self._angle = 0

    def start(self, message="Cargando..."):
        self.text.setText(message)
        self._timer.start(100)
        self.show()

    def stop(self):
        self._timer.stop()
        self.hide()

    def _rotate(self):
        self._angle = (self._angle + 10) % 360
        self.label.setText("⏳")