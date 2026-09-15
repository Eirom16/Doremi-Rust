from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from doremi.ui.design.fonts import AppFont
from doremi.ui.design.icons import Icon


class EmptyStateWidget(QWidget):
    """Centered empty-state placeholder shown when a screen has no data."""

    def __init__(
        self,
        message: str = "No hay elementos para mostrar",
        icon: str = "music_note",
        action_callback=None,
        action_text: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("emptyState")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 48, 24, 48)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        from doremi.ui.design import tokens

        icon_label = QLabel(Icon.get(icon))
        icon_label.setFont(Icon.font(42))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"color: {tokens.CURRENT.text_secondary}; background: transparent;")
        layout.addWidget(icon_label)

        label = QLabel(message)
        label.setFont(AppFont.body(14))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        label.setStyleSheet(f"color: {tokens.CURRENT.text_secondary}; background: transparent;")
        layout.addWidget(label)

        if action_callback and action_text:
            from PySide6.QtWidgets import QPushButton

            action = QPushButton(action_text)
            action.setCursor(Qt.CursorShape.PointingHandCursor)
            action.clicked.connect(action_callback)
            action.setStyleSheet(f"""
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
            layout.addWidget(action, alignment=Qt.AlignmentFlag.AlignCenter)
