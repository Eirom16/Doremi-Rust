from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from doremi.ui.design.fonts import AppFont
from doremi.ui.design.icons import Icon
from doremi.ui.screens.settings.about import AboutScreen
from doremi.ui.screens.settings.accounts import AccountsSettingsScreen
from doremi.ui.screens.settings.appearance import AppearanceSettingsScreen
from doremi.ui.screens.settings.equalizer import EqualizerSettingsScreen
from doremi.ui.screens.settings.player_settings import PlayerSettingsScreen
from doremi.ui.screens.settings.storage import StorageSettingsScreen
from doremi.ui.screens.settings.subtitles import SubtitlesSettingsScreen
from doremi.ui.widgets.fade_stack import FadeStackedWidget


class SettingsScreen(QWidget):
    CATEGORIES = [
        ("palette", "Apariencia"),
        ("graphic_eq", "Reproductor"),
        ("equalizer", "Ecualizador"),
        ("lyrics", "Letras y Subtítulos"),
        ("person", "Cuentas"),
        ("storage", "Almacenamiento"),
        ("info", "Acerca de"),
    ]

    def __init__(self, yt_client, settings, on_settings_changed, on_auth_changed=None):
        super().__init__()
        self._yt = yt_client
        self.settings = settings
        self.on_settings_changed = on_settings_changed
        self.on_auth_changed = on_auth_changed
        self._cat_buttons: list[QPushButton] = []
        self._build_ui()

    @property
    def yt(self):
        return self._yt

    @yt.setter
    def yt(self, client):
        self._yt = client
        if hasattr(self, "accounts_screen"):
            self.accounts_screen.yt = client

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        sidebar.setObjectName("settingsSidebar")
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(12, 22, 12, 22)
        side_layout.setSpacing(4)

        title = QLabel("Ajustes")
        title.setFont(AppFont.heading(18))
        title.setObjectName("settingsTitle")
        side_layout.addWidget(title)

        for i, (icon_name, label) in enumerate(self.CATEGORIES):
            button = self._make_cat_button(icon_name, label, i)
            self._cat_buttons.append(button)
            side_layout.addWidget(button)
        side_layout.addStretch()
        root.addWidget(sidebar)

        self.stack = FadeStackedWidget()
        self.stack.setObjectName("settingsStack")
        self.stack.setStyleSheet("#settingsStack { background: transparent; }")
        root.addWidget(self.stack)

        self.accounts_screen = AccountsSettingsScreen(self.yt, self.settings, self.on_settings_changed, on_auth_changed=self.on_auth_changed)
        pages = [
            AppearanceSettingsScreen(self.settings, self.on_settings_changed),
            PlayerSettingsScreen(self.settings, self.on_settings_changed),
            EqualizerSettingsScreen(self.settings, self.on_settings_changed),
            SubtitlesSettingsScreen(self.settings, self.on_settings_changed),
            self.accounts_screen,
            StorageSettingsScreen(self.settings),
            AboutScreen(),
        ]
        for page in pages:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            scroll.setStyleSheet("background: transparent; border: none;")
            
            def make_scroll_handler(p):
                from PySide6.QtWidgets import QComboBox
                def on_scroll(_):
                    for cb in p.findChildren(QComboBox):
                        cb.hidePopup()
                return on_scroll
            scroll.verticalScrollBar().valueChanged.connect(make_scroll_handler(page))

            wrapper = QWidget()
            wrapper.setObjectName("settingsPageWrapper")
            wrapper_layout = QVBoxLayout(wrapper)
            wrapper_layout.setContentsMargins(34, 26, 34, 26)
            wrapper_layout.addWidget(page)
            wrapper_layout.addStretch()
            scroll.setWidget(wrapper)
            self.stack.addWidget(scroll)

        for previous, current in zip(self._cat_buttons, self._cat_buttons[1:], strict=False):
            QWidget.setTabOrder(previous, current)

        self._select_category(0)

    def _make_cat_button(self, icon_name: str, label: str, index: int) -> QPushButton:
        button = QPushButton()
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedHeight(40)
        button.setAccessibleName(label)
        row = QHBoxLayout(button)
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(10)
        from doremi.ui.design import tokens
        icon = Icon.label(icon_name, 18, tokens.CURRENT.text_secondary)
        text = QLabel(label)
        text.setFont(AppFont.body(13))
        icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        text.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row.addWidget(icon)
        row.addWidget(text)
        row.addStretch()
        button._icon_label = icon
        button._text_label = text
        button.clicked.connect(lambda checked=False, i=index: self._select_category(i))
        self._style_cat_button(button, False)
        return button

    def _style_cat_button(self, button: QPushButton, active: bool) -> None:
        from doremi.ui.design import tokens
        from PySide6.QtGui import QColor
        accent = tokens.CURRENT.accent
        c = QColor(accent)
        r, g, b, _ = c.getRgb()

        color = accent if active else tokens.CURRENT.text_secondary
        bg = f"rgba({r},{g},{b},0.15)" if active else "transparent"
        hover_bg = f"rgba({r},{g},{b},0.09)"
        button._icon_label.setStyleSheet(f"color: {color}; background: transparent; font-family: 'Material Symbols Rounded'; font-size: 18px;")
        button._text_label.setStyleSheet(f"color: {color}; background: transparent; font-weight: {'700' if active else '500'};")
        button.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                border: none;
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background: {hover_bg};
            }}
        """)

    def _select_category(self, index: int) -> None:
        for i, button in enumerate(self._cat_buttons):
            active = i == index
            button.setChecked(active)
            self._style_cat_button(button, active)
        self.stack.setCurrentIndexAnimated(index)

    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    for i, button in enumerate(self._cat_buttons):
                        self._style_cat_button(button, button.isChecked())
                finally:
                    self._in_style_change = False
        super().changeEvent(event)
