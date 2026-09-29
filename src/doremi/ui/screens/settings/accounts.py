from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QVBoxLayout, QWidget

from doremi.config.paths import AppDirs
from doremi.ui.screens.settings.components import SettingsRow, SettingsSection, page_title
from doremi.ui.widgets.ripple_button import RippleButton


class AccountsSettingsScreen(QWidget):
    def __init__(self, yt_client, settings, on_changed, on_auth_changed=None):
        super().__init__()
        self._yt = yt_client
        self.settings = settings
        self.on_changed = on_changed
        self.on_auth_changed = on_auth_changed
        self._build_ui()

    @property
    def yt(self):
        return self._yt

    @yt.setter
    def yt(self, client):
        self._yt = client
        self._update_yt_row()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(page_title("Cuentas"))

        self.yt_section = SettingsSection("YouTube Music")
        layout.addWidget(self.yt_section)
        self._update_yt_row()

        layout.addStretch()

    def _update_yt_row(self) -> None:
        if not hasattr(self, "yt_section"):
            return
        
        # Clear existing items in yt_section's card layout
        card_layout = self.yt_section.card_layout
        while card_layout.count():
            item = card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        is_auth = self._yt and self._yt.is_authenticated
        if is_auth:
            logout = RippleButton("Cerrar sesión", "danger")
            logout.clicked.connect(self._on_logout)
            row = SettingsRow("Cuenta Conectada", "Has iniciado sesión en YouTube Music", logout)
            card_layout.addWidget(row)
        else:
            login = RippleButton("Conectar cuenta", "primary")
            login.clicked.connect(self._on_browser_login)
            row = SettingsRow("Cuenta de Google", "Autoriza YouTube Music en el navegador", login)
            card_layout.addWidget(row)

    def _on_browser_login(self) -> None:
        from doremi.ui.dialogs.login_dialog import WebLoginDialog
        dialog = WebLoginDialog(self)
        dialog.login_successful.connect(self._handle_login_success)
        dialog.exec()

    def _handle_login_success(self, avatar_url: str = "") -> None:
        if self._yt:
            self._yt.reload_auth()
        self._update_yt_row()
        if self.on_auth_changed:
            self.on_auth_changed(True, avatar_url)

    def _on_logout(self) -> None:
        result = QMessageBox.question(
            self,
            "Cerrar sesión",
            "¿Cerrar sesión y borrar las cookies, credenciales y perfil local de YouTube Music?",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        try:
            from PySide6.QtWebEngineCore import QWebEngineProfile
            QWebEngineProfile.defaultProfile().cookieStore().deleteAllCookies()
        except Exception:
            pass

        from doremi.utils.secure_storage import SecureStorage
        SecureStorage.delete_youtube_headers()
            
        profile_file = AppDirs.config / "user_profile.json"
        if profile_file.exists():
            profile_file.unlink()
            
        if self._yt:
            self._yt.reload_auth()
        self._update_yt_row()
        self.on_changed(self.settings)
        if self.on_auth_changed:
            self.on_auth_changed(False, "")
