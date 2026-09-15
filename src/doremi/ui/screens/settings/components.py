from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from doremi.ui.design.fonts import AppFont
from doremi.ui.design.icons import Icon


class SettingsRow(QWidget):
    def __init__(self, title: str, description: str = "", control: QWidget | None = None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(18)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        title_label = QLabel(title)
        title_label.setFont(AppFont.body(14))
        title_label.setObjectName("settingsRowTitle")
        text_col.addWidget(title_label)

        if description:
            desc = QLabel(description)
            desc.setFont(AppFont.label(12))
            desc.setWordWrap(True)
            desc.setObjectName("settingsRowDesc")
            text_col.addWidget(desc)

        layout.addLayout(text_col, stretch=1)
        if control:
            if not control.accessibleName():
                control.setAccessibleName(title)
            if description and not control.accessibleDescription():
                control.setAccessibleDescription(description)
            layout.addWidget(control, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.setObjectName("settingsRow")


class SettingsSection(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 18)
        layout.setSpacing(0)

        header = QLabel(title.upper())
        header.setFont(AppFont.label(11))
        header.setObjectName("settingsSectionHeader")
        layout.addWidget(header)

        self.card = QFrame()
        self.card.setObjectName("settingsCard")
        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(0, 4, 0, 4)
        self.card_layout.setSpacing(0)
        layout.addWidget(self.card)

    def add_row(self, row: SettingsRow) -> None:
        if self.card_layout.count() > 0:
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setObjectName("settingsSeparator")
            self.card_layout.addWidget(sep)
        self.card_layout.addWidget(row)


class AccentColorPicker(QWidget):
    color_changed = Signal(str)

    PRESETS = [
        "#A78BFA",
        "#60A5FA",
        "#34D399",
        "#F472B6",
        "#FB923C",
        "#FBBF24",
        "#22D3EE",
        "#F87171",
    ]

    def __init__(self, current: str = "#A78BFA", parent=None):
        super().__init__(parent)
        self._current = current
        self._buttons: list[QPushButton] = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        for color in self.PRESETS:
            button = self._make_swatch(color)
            self._buttons.append(button)
            layout.addWidget(button)

        custom = QPushButton(Icon.get("add"))
        custom.setFont(Icon.font(18))
        custom.setFixedSize(28, 28)
        custom.setCursor(Qt.CursorShape.PointingHandCursor)
        custom.setToolTip("Color personalizado")
        self.custom_btn = custom
        self._update_custom_button_style()
        custom.clicked.connect(self._pick_custom)
        layout.addWidget(custom)

    def _make_swatch(self, color: str) -> QPushButton:
        button = QPushButton()
        button.setFixedSize(28, 28)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(color)
        button.clicked.connect(lambda checked=False, c=color: self._emit_color(c))
        self._style_swatch(button, color)
        return button

    def _style_swatch(self, button: QPushButton, color: str) -> None:
        from doremi.ui.design import tokens
        active = color.lower() == self._current.lower()
        border = tokens.CURRENT.text_primary if active else "transparent"
        hover_border = tokens.CURRENT.text_secondary
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border-radius: 14px;
                border: 2px solid {border};
            }}
            QPushButton:hover {{
                border: 2px solid {hover_border};
            }}
        """)

    def _emit_color(self, color: str) -> None:
        self._current = color
        for button, preset in zip(self._buttons, self.PRESETS, strict=False):
            self._style_swatch(button, preset)
        self._update_custom_button_style()
        self.color_changed.emit(color)

    def _pick_custom(self) -> None:
        color = QColorDialog.getColor(QColor(self._current), self)
        if color.isValid():
            self._emit_color(color.name())

    def _update_custom_button_style(self) -> None:
        if hasattr(self, 'custom_btn') and isinstance(self.custom_btn, QPushButton):
            from doremi.ui.design import tokens
            from PySide6.QtGui import QColor
            accent = tokens.CURRENT.accent
            c = QColor(accent)
            r, g, b, _ = c.getRgb()
            self.custom_btn.setStyleSheet(f"""
                QPushButton {{
                    border: 2px dashed rgba({r},{g},{b},0.4);
                    border-radius: 14px;
                    
                    background: transparent;
                }}
                QPushButton:hover {{
                    border-color: {accent};
                    color: {accent};
                }}
            """)

    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            self._update_custom_button_style()
            for button, preset in zip(self._buttons, self.PRESETS, strict=False):
                self._style_swatch(button, preset)
        super().changeEvent(event)


def page_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setFont(AppFont.display(24))
    label.setObjectName("settingsPageTitle")
    return label
