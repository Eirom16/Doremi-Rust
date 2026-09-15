from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from doremi.ui.design.fonts import AppFont
from doremi.ui.design.icons import Icon


class ErrorStateWidget(QWidget):
    def __init__(
        self,
        message: str = "No se pudo cargar el contenido",
        retry_callback: Callable[[], None] | None = None,
        action_text: str = "Reintentar",
        parent=None,
    ):
        super().__init__(parent)
        self.retry_callback = retry_callback
        self.setObjectName("errorState")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 48, 24, 48)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        from doremi.ui.design import tokens

        icon = QLabel(Icon.get("error"))
        icon.setFont(Icon.font(42))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(f"color: {tokens.CURRENT.error}; background: transparent;")
        layout.addWidget(icon)

        label = QLabel(message)
        label.setFont(AppFont.body(14))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        label.setStyleSheet(f"color: {tokens.CURRENT.text_secondary}; background: transparent;")
        layout.addWidget(label)

        if retry_callback:
            retry = QPushButton(action_text)
            retry.setCursor(Qt.CursorShape.PointingHandCursor)
            retry.clicked.connect(retry_callback)
            retry.setStyleSheet(f"""
                QPushButton {{
                    background-color: {tokens.CURRENT.accent};
                    color: {tokens.CURRENT.text_on_accent};
                    border: none;
                    border-radius: 8px;
                    padding: 8px 18px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {tokens.CURRENT.accent_bright};
                }}
            """)
            layout.addWidget(retry, alignment=Qt.AlignmentFlag.AlignCenter)
