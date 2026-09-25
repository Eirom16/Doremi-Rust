from __future__ import annotations

import asyncio
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Qt

from doremi.changelog import CURRENT_CHANGELOG, CURRENT_CHANGELOG_SUMMARY, CURRENT_CHANGELOG_VERSION
from doremi.ui.design.fonts import AppFont
from doremi.ui.screens.settings.components import page_title
from doremi.ui.widgets.ripple_button import RippleButton


class AboutScreen(QWidget):
    def __init__(self):
        super().__init__()
        self._changelog_labels: list[QLabel] = []
        self._changelog_icons: list[QLabel] = []
        self._build_ui()

    def _build_ui(self) -> None:
        from doremi.ui.design import tokens
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(page_title("Acerca de"))

        from PySide6.QtGui import QPixmap
        from doremi.config.paths import AppDirs
        logo_path = AppDirs.root / "assets" / "Doremi_Withoth_Background.png"
        if logo_path.exists():
            self._logo = QLabel()
            pixmap = QPixmap(str(logo_path))
            self._logo.setPixmap(pixmap.scaledToWidth(200, Qt.TransformationMode.SmoothTransformation))
            self._logo.setAlignment(Qt.AlignmentFlag.AlignLeft)
            self._logo.setStyleSheet("background: transparent; margin-bottom: 10px;")
            layout.addWidget(self._logo)

        self.name = QLabel("Doremi")
        self.name.setFont(AppFont.display(32))
        self._update_about_styles()
        layout.addWidget(self.name)

        try:
            from doremi import __version__ as ver
        except ImportError:
            try:
                from importlib.metadata import version as pkg_version
                ver = pkg_version("doremi")
            except Exception:
                ver = CURRENT_CHANGELOG_VERSION
        self.version = QLabel(f"Versión {ver}")
        self.version.setFont(AppFont.body(14))
        layout.addWidget(self.version)

        self.description = QLabel(
            "Cliente de escritorio para YouTube Music construido con Python, PySide6 y VLC.\n"
            "Incluye streaming, descargas offline, letras sincronizadas, ecualizador e integraciones."
        )
        self.description.setFont(AppFont.body(14))
        self.description.setWordWrap(True)
        layout.addWidget(self.description)

        layout.addWidget(self._build_changelog_card())

        github = RippleButton("Ver proyecto", "secondary")
        github.clicked.connect(lambda: __import__('webbrowser').open("https://github.com/Eirom16/Doremi"))
        layout.addWidget(github)

        # ── Sección de actualizaciones ─────────────────────────────────
        from doremi.utils.updater import CURRENT_VERSION
        from doremi.ui.design.icons import Icon

        current_ver_lbl = QLabel(f"Versión instalada: {CURRENT_VERSION}")
        current_ver_lbl.setFont(AppFont.mono(13))
        self._current_ver_lbl = current_ver_lbl
        layout.addWidget(current_ver_lbl)

        self._check_btn = RippleButton("Buscar actualizaciones", variant="secondary")
        self._check_btn.setIcon(Icon.icon("sync", tokens.CURRENT.accent, 20))
        self._check_btn.setFont(AppFont.body(14))
        self._check_btn.setMinimumHeight(44)
        self._check_btn.clicked.connect(lambda: asyncio.ensure_future(self._manual_check()))
        layout.addWidget(self._check_btn)

        self._update_status_lbl = QLabel("")
        self._update_status_lbl.setFont(AppFont.label(12))
        layout.addWidget(self._update_status_lbl)

        layout.addStretch()
        
        self._update_about_styles()

    def _build_changelog_card(self) -> QFrame:
        from doremi.ui.design import tokens
        from doremi.ui.design.icons import Icon

        card = QFrame()
        card.setObjectName("settingsCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 18)
        card_layout.setSpacing(12)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)

        icon = Icon.label("new_releases", size=22, color=tokens.CURRENT.accent)
        self._changelog_icons.append(icon)
        header.addWidget(icon, alignment=Qt.AlignmentFlag.AlignTop)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(3)

        title = QLabel(f"Changelog v{CURRENT_CHANGELOG_VERSION}")
        title.setFont(AppFont.body(16))
        title.setWordWrap(True)
        self._changelog_labels.append(title)
        title_col.addWidget(title)

        summary = QLabel(CURRENT_CHANGELOG_SUMMARY)
        summary.setFont(AppFont.label(12))
        summary.setWordWrap(True)
        self._changelog_labels.append(summary)
        title_col.addWidget(summary)

        header.addLayout(title_col, stretch=1)
        card_layout.addLayout(header)

        for section_title, items in CURRENT_CHANGELOG:
            section = QLabel(section_title.upper())
            section.setFont(AppFont.label(11))
            self._changelog_labels.append(section)
            card_layout.addWidget(section)

            for item in items:
                row = QHBoxLayout()
                row.setContentsMargins(0, 0, 0, 0)
                row.setSpacing(8)

                item_icon = Icon.label("check_circle", size=16, color=tokens.CURRENT.success)
                self._changelog_icons.append(item_icon)
                row.addWidget(item_icon, alignment=Qt.AlignmentFlag.AlignTop)

                label = QLabel(item)
                label.setFont(AppFont.label(12))
                label.setWordWrap(True)
                self._changelog_labels.append(label)
                row.addWidget(label, stretch=1)
                card_layout.addLayout(row)

        return card

    async def _manual_check(self) -> None:
        from doremi.utils.updater import (
            check_for_updates,
            CURRENT_VERSION,
            is_dev_build,
        )
        from doremi.ui.widgets.update_dialog_qml import UpdateDialogQml

        self._check_btn.setEnabled(False)
        self._check_btn.setText("Comprobando...")

        release = await check_for_updates()

        self._check_btn.setEnabled(True)
        self._check_btn.setText("Buscar actualizaciones")

        if is_dev_build():
            main_win = self.window()
            show_notification = getattr(main_win, "show_notification", None)
            msg = "Estás en una versión de desarrollo (siempre es la última)"
            if callable(show_notification):
                show_notification(msg, "info")
            else:
                from doremi.ui.widgets.toast import ToastNotification
                ToastNotification.show(main_win, msg, kind="info")
            return

        if release:
            dlg = UpdateDialogQml(release, parent=self.window())
            dlg.show()
        else:
            main_win = self.window()
            show_notification = getattr(main_win, "show_notification", None)
            if callable(show_notification):
                show_notification(
                    f"Ya tienes la última versión ({CURRENT_VERSION})",
                    "success"
                )
            else:
                from doremi.ui.widgets.toast import ToastNotification
                ToastNotification.show(
                    main_win,
                    f"Ya tienes la última versión ({CURRENT_VERSION})",
                    kind="success"
                )

    def _update_about_styles(self) -> None:
        from doremi.ui.design import tokens
        self.name.setStyleSheet(f"color: {tokens.CURRENT.accent}; background: transparent;")
        if hasattr(self, '_logo') and self._logo:
            from PySide6.QtWidgets import QGraphicsColorizeEffect
            from PySide6.QtGui import QColor
            self._logo_effect = QGraphicsColorizeEffect()
            self._logo_effect.setColor(QColor(tokens.CURRENT.accent))
            self._logo_effect.setStrength(1.0)
            self._logo.setGraphicsEffect(self._logo_effect)
            self._logo.update()
        if hasattr(self, "version") and self.version:
            self.version.setStyleSheet(" background: transparent;")
        if hasattr(self, "description") and self.description:
            self.description.setStyleSheet(" background: transparent;")
        if hasattr(self, "_current_ver_lbl") and self._current_ver_lbl:
            self._current_ver_lbl.setStyleSheet(f"color: {tokens.CURRENT.text_secondary}; background: transparent;")
        if hasattr(self, "_update_status_lbl") and self._update_status_lbl:
            self._update_status_lbl.setStyleSheet(f"color: {tokens.CURRENT.text_secondary}; background: transparent;")
        if hasattr(self, "_changelog_labels"):
            for index, label in enumerate(self._changelog_labels):
                color = tokens.CURRENT.text_primary if index == 0 else tokens.CURRENT.text_secondary
                if label.text().isupper():
                    color = tokens.CURRENT.accent
                label.setStyleSheet(f"color: {color}; background: transparent;")
        if hasattr(self, "_changelog_icons"):
            from doremi.ui.design.icons import MATERIAL_FONT
            for icon in self._changelog_icons:
                icon.setStyleSheet(
                    f"color: {tokens.CURRENT.accent}; background: transparent; "
                    f"font-family: '{MATERIAL_FONT}';"
                )

    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._update_about_styles()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)
