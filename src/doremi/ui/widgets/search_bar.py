from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit
from PySide6.QtCore import Signal


class SearchBar(QWidget):
    textChanged = Signal(str)
    returnPressed = Signal(str)

    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)

        self.input = QLineEdit()
        self.input.setObjectName("searchBar")
        self.input.setPlaceholderText("Buscar canciones, álbumes, artistas...")
        self.input.textChanged.connect(self.textChanged.emit)
        self.input.returnPressed.connect(self._on_return_pressed)
        layout.addWidget(self.input)

    def _on_return_pressed(self):
        self.returnPressed.emit(self.input.text())

    def text(self):
        return self.input.text()

    def clear(self):
        self.input.clear()