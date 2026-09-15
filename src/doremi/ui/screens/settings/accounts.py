from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QMessageBox, QVBoxLayout, QWidget

from doremi.config.paths import AppDirs
from doremi.ui.screens.settings.components import SettingsRow, SettingsSection, page_title
from doremi.ui.widgets.animated_toggle import AnimatedToggle
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

        self.lastfm_section = SettingsSection("Last.fm")
        layout.addWidget(self.lastfm_section)
        self._update_lastfm_rows()

        discord = SettingsSection("Discord")
        rpc = AnimatedToggle()
        rpc.setChecked(self.settings.integrations.discord_rpc_enabled)
        rpc.toggled.connect(lambda checked: self._set_integration("discord_rpc_enabled", checked))
        discord.add_row(SettingsRow("Rich Presence", "Muestra lo que escuchas en tu perfil", rpc))
        layout.addWidget(discord)
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

    def _line_edit(self, value: str, placeholder: str) -> QLineEdit:
        line = QLineEdit()
        line.setText(value)
        line.setPlaceholderText(placeholder)
        line.setMinimumWidth(220)
        if not hasattr(self, "_line_edits"):
            self._line_edits = []
        self._line_edits.append(line)
        self._update_line_edit_style(line)
        return line

    def _update_line_edit_style(self, line: QLineEdit) -> None:
        from doremi.ui.design import tokens
        line.setStyleSheet(f"""
            QLineEdit {{
                background-color: {tokens.CURRENT.bg_elevated};
                
                border: 1px solid {tokens.CURRENT.border};
                border-radius: 8px;
                padding: 6px 12px;
                font-family: Inter;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {tokens.CURRENT.accent};
            }}
        """)

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

    def _update_lastfm_rows(self) -> None:
        if not hasattr(self, "lastfm_section"):
            return
            
        card_layout = self.lastfm_section.card_layout
        # Clear existing
        while card_layout.count():
            item = card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        # Row 1: Scrobbling Toggle
        enabled = AnimatedToggle()
        enabled.setChecked(self.settings.integrations.lastfm_enabled)
        enabled.toggled.connect(self._on_lastfm_toggled)
        self.lastfm_section.add_row(SettingsRow("Scrobbling", "Registra las canciones escuchadas en Last.fm", enabled))
        
        if not self.settings.integrations.lastfm_enabled:
            return
            
        # Clean up self._line_edits to avoid leaks/RuntimeError
        if hasattr(self, "_line_edits"):
            valid = []
            for x in self._line_edits:
                try:
                    x.parent()
                    valid.append(x)
                except RuntimeError:
                    pass
            self._line_edits = valid
            
        is_authenticated = bool(self.settings.integrations.lastfm_session_key)
        
        if is_authenticated:
            btn_disconnect = RippleButton("Desconectar", "danger")
            btn_disconnect.clicked.connect(self._on_lastfm_disconnect)
            self.lastfm_section.add_row(SettingsRow("Cuenta Conectada", "Sesión de Last.fm activa y autorizada", btn_disconnect))
        else:
            self.lastfm_api_key = self._line_edit(self.settings.integrations.lastfm_api_key, "API Key")
            self.lastfm_api_key.editingFinished.connect(lambda: self._set_integration("lastfm_api_key", self.lastfm_api_key.text()))
            self.lastfm_section.add_row(SettingsRow("API Key", "Credencial pública de Last.fm", self.lastfm_api_key))
            
            self.lastfm_api_secret = self._line_edit(self.settings.integrations.lastfm_api_secret, "API Secret")
            self.lastfm_api_secret.editingFinished.connect(lambda: self._set_integration("lastfm_api_secret", self.lastfm_api_secret.text()))
            self.lastfm_section.add_row(SettingsRow("API Secret", "Credencial privada de Last.fm", self.lastfm_api_secret))
            
            self.lastfm_username = self._line_edit("", "Usuario")
            self.lastfm_section.add_row(SettingsRow("Usuario", "Tu nombre de usuario en Last.fm", self.lastfm_username))
            
            self.lastfm_password = self._line_edit("", "Contraseña")
            self.lastfm_password.setEchoMode(QLineEdit.EchoMode.Password)
            self.lastfm_section.add_row(SettingsRow("Contraseña", "Tu contraseña de Last.fm", self.lastfm_password))
            
            btn_auth = RippleButton("Autenticar en Last.fm", "primary")
            btn_auth.clicked.connect(self._on_lastfm_authenticate)
            self.lastfm_section.add_row(SettingsRow("Autenticación", "Conecta e inicia sesión de forma segura", btn_auth))

    def _on_lastfm_toggled(self, checked: bool) -> None:
        self._set_integration("lastfm_enabled", checked)
        self._update_lastfm_rows()

    def _on_lastfm_disconnect(self) -> None:
        from doremi.utils.secure_storage import SecureStorage
        SecureStorage.delete_lastfm_credentials()
        self.settings.integrations.lastfm_api_key = ""
        self.settings.integrations.lastfm_api_secret = ""
        self._set_integration("lastfm_session_key", "")
        from doremi.ui.widgets.toast import ToastNotification
        ToastNotification.show(self, "Cuenta de Last.fm desconectada con éxito", "success")
        self._update_lastfm_rows()

    def _on_lastfm_authenticate(self) -> None:
        api_key = self.lastfm_api_key.text().strip()
        api_secret = self.lastfm_api_secret.text().strip()
        username = self.lastfm_username.text().strip()
        password = self.lastfm_password.text()
        
        if not api_key or not api_secret:
            from doremi.ui.widgets.toast import ToastNotification
            ToastNotification.show(self, "Debes ingresar API Key y API Secret", "warning")
            return
            
        if not username or not password:
            from doremi.ui.widgets.toast import ToastNotification
            ToastNotification.show(self, "Debes ingresar tu usuario y contraseña", "warning")
            return
            
        import asyncio
        asyncio.create_task(self._async_lastfm_auth(api_key, api_secret, username, password))

    async def _async_lastfm_auth(self, api_key: str, api_secret: str, username: str, password: str) -> None:
        from doremi.ui.widgets.toast import ToastNotification
        toast = ToastNotification.show(self, "Autenticando con Last.fm...", "info")
        
        def do_auth():
            import pylast
            password_hash = pylast.md5(password)
            network = pylast.LastFMNetwork(
                api_key=api_key,
                api_secret=api_secret,
                username=username,
                password_hash=password_hash
            )
            return network.session_key
            
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            session_key = await loop.run_in_executor(None, do_auth)
            
            if session_key:
                from doremi.utils.secure_storage import SecureStorage
                SecureStorage.save_lastfm_credentials(api_key, api_secret, session_key)
                self.settings.integrations.lastfm_api_key = api_key
                self.settings.integrations.lastfm_api_secret = api_secret
                self.settings.integrations.lastfm_session_key = session_key
                # Save and notify setting change
                self._set_integration("lastfm_session_key", session_key)
                
                ToastNotification.show(self, "¡Autenticación con Last.fm exitosa!", "success")
                self._update_lastfm_rows()
            else:
                ToastNotification.show(self, "No se pudo recuperar la clave de sesión", "error")
        except Exception as e:
            import logging
            logging.getLogger().error(f"Last.fm auth error: {e}", exc_info=True)
            error_msg = str(e)
            if "WSError" in error_msg or "failed" in error_msg.lower() or "invalid" in error_msg.lower():
                ToastNotification.show(self, "Error de autenticación: Credenciales inválidas", "error")
            else:
                ToastNotification.show(self, f"Error al conectar con Last.fm: {error_msg}", "error")

    def _set_integration(self, key: str, value) -> None:
        setattr(self.settings.integrations, key, value)
        self.on_changed(self.settings)

    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange,):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    if hasattr(self, "_line_edits"):
                        for line in self._line_edits:
                            self._update_line_edit_style(line)
                finally:
                    self._in_style_change = False
        super().changeEvent(event)
