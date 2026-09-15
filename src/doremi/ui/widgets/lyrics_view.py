from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class LyricsView(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("lyricsContainer")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        self.scroller = QWidget()
        self.scroller_layout = QVBoxLayout(self.scroller)
        self.scroller_layout.setSpacing(12)
        layout.addWidget(self.scroller)

    def set_lyrics(self, lyrics):
        from PySide6.QtWidgets import QLabel
        while self.scroller_layout.count():
            item = self.scroller_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for line in lyrics:
            label = QLabel(line.text)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFont(QFont("Inter", 14))
            label.setStyleSheet("color: #666688; padding: 8px;")
            label.setProperty("lyricLine", True)
            self.scroller_layout.addWidget(label)

    def highlight_line(self, index):
        for i in range(self.scroller_layout.count()):
            widget = self.scroller_layout.itemAt(i).widget()
            if widget:
                widget.setProperty("active", i == index)
                widget.setStyleSheet(widget.styleSheet())