from __future__ import annotations

import asyncio
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QApplication, QMessageBox, QVBoxLayout, QWidget
from loguru import logger

from doremi.config.paths import AppDirs
from doremi.ui.theme_bridge import theme_bridge
from doremi.ui.viewmodels.settings_vm import SettingsViewModel

QML_DIR = Path(__file__).resolve().parent.parent / "qml"


class SettingsScreenQml(QWidget):
    """Isla QML: Ajustes como QQuickWidget (schema-driven).

    Drop-in replacement de SettingsScreen (QtWidgets): mismo constructor,
    mismas propiedades (`settings`, `yt`) y callbacks. Las acciones que
    necesitan diálogos QtWidgets (login web, backup, confirmaciones) se
    resuelven aquí.
    """

    _qml_island = True  # fade_stack.py: sin cross-fade

    def __init__(self, yt_client, settings, on_settings_changed, on_auth_changed=None):
        super().__init__()
        self._yt = yt_client
        self.settings = settings
        self.on_settings_changed = on_settings_changed
        self.on_auth_changed = on_auth_changed
        self.setAutoFillBackground(False)

        self._vm = SettingsViewModel(settings, yt_client, QApplication.instance())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._quick = QQuickWidget(self)
        self._quick.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self._quick.setAutoFillBackground(False)
        from PySide6.QtGui import QColor
        self._quick.setClearColor(QColor(0, 0, 0, 0))

        engine = self._quick.engine()
        engine.addImportPath(str(QML_DIR))

        ctx = self._quick.rootContext()
        ctx.setContextProperty("themeBridge", theme_bridge())
        ctx.setContextProperty("vm", self._vm)

        self._quick.setSource(QUrl.fromLocalFile(str(QML_DIR / "SettingsScreen.qml")))

        self._load_ok = self._quick.status() == QQuickWidget.Status.Ready
        if not self._load_ok:
            for err in self._quick.errors():
                logger.error(f"QML SettingsScreen: {err.toString()}")

        layout.addWidget(self._quick)

        self._vm.settings_changed.connect(self._on_vm_settings_changed)
        self._vm.toast_requested.connect(self._show_toast)
        self._vm.action_requested.connect(self._on_action)

    @property
    def is_ok(self) -> bool:
        return self._load_ok

    @property
    def yt(self):
        return self._yt

    @yt.setter
    def yt(self, client):
        self._yt = client
        self._vm._yt = client
        self._vm.refresh()

    def _on_vm_settings_changed(self) -> None:
        if self.on_settings_changed:
            self.on_settings_changed(self.settings)

    def _show_toast(self, message: str, kind: str = "info") -> None:
        try:
            from doremi.ui.widgets.toast import ToastNotification
            ToastNotification.show(self.window(), message, kind)
        except Exception:
            logger.debug(f"Toast: {message} ({kind})")

    # ── Acciones (botones) ─────────────────────────────────────────────────

    def _on_action(self, action_id: str) -> None:
        handlers = {
            "accounts.login": self._accounts_login,
            "accounts.logout": self._accounts_logout,
            "accounts.lastfm_auth": self._lastfm_auth,
            "accounts.lastfm_disconnect": self._lastfm_disconnect,
            "storage.clear_cache": self._clear_cache,
            "storage.clear_downloads": self._clear_downloads,
            "storage.export_backup": self._export_backup,
            "storage.import_backup": self._import_backup,
            "about.check_updates": lambda: asyncio.ensure_future(self._check_updates()),
            "about.open_github": self._open_github,
        }
        handler = handlers.get(action_id)
        if handler:
            handler()
        else:
            logger.debug(f"Acción de settings desconocida: {action_id}")

    # — Cuentas / YouTube —

    def _accounts_login(self) -> None:
        from doremi.ui.dialogs.login_dialog import WebLoginDialog
        dialog = WebLoginDialog(self)
        from PySide6.QtWebEngineCore import QWebEngineProfile  # noqa: F401 — asegura backend

        def _ok(avatar_url: str = "") -> None:
            if self._yt:
                self._yt.reload_auth()
            if self.on_auth_changed:
                self.on_auth_changed(True, avatar_url)
            self._vm.refresh()

        dialog.login_successful.connect(_ok)
        dialog.exec()

    def _accounts_logout(self) -> None:
        from doremi.ui.design import tokens
        result = QMessageBox.question(
            self.window(),
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
        if self.on_auth_changed:
            self.on_auth_changed(False, "")
        self._vm.refresh()
        self._on_vm_settings_changed()

    # — Cuentas / Last.fm —

    def _lastfm_disconnect(self) -> None:
        from doremi.utils.secure_storage import SecureStorage
        SecureStorage.delete_lastfm_credentials()
        self.settings.integrations.lastfm_api_key = ""
        self.settings.integrations.lastfm_api_secret = ""
        self.settings.integrations.lastfm_session_key = ""
        self._show_toast("Cuenta de Last.fm desconectada con éxito", "success")
        self._vm.refresh()
        self._on_vm_settings_changed()

    def _lastfm_auth(self) -> None:
        asyncio.ensure_future(self._lastfm_auth_async())

    async def _lastfm_auth_async(self) -> None:
        s = self.settings.integrations
        if not s.lastfm_api_key or not s.lastfm_api_secret:
            self._show_toast("Debes ingresar API Key y API Secret", "warning")
            return
        if not s.lastfm_username or not s.lastfm_password:
            self._show_toast("Debes ingresar tu usuario y contraseña", "warning")
            return

        self._show_toast("Autenticando con Last.fm...", "info")

        def do_auth():
            import pylast
            password_hash = pylast.md5(s.lastfm_password)
            network = pylast.LastFMNetwork(
                api_key=s.lastfm_api_key,
                api_secret=s.lastfm_api_secret,
                username=s.lastfm_username,
                password_hash=password_hash,
            )
            return network.session_key

        try:
            loop = asyncio.get_running_loop()
            session_key = await loop.run_in_executor(None, do_auth)
            if session_key:
                from doremi.utils.secure_storage import SecureStorage
                SecureStorage.save_lastfm_credentials(
                    s.lastfm_api_key, s.lastfm_api_secret, session_key)
                s.lastfm_session_key = session_key
                self._show_toast("¡Autenticación con Last.fm exitosa!", "success")
                self._vm.refresh()
                self._on_vm_settings_changed()
            else:
                self._show_toast("No se pudo recuperar la clave de sesión", "error")
        except Exception as e:
            logger.error(f"Last.fm auth error: {e}")
            self._show_toast(f"Error al conectar con Last.fm: {e}", "error")

    # — Storage —

    def _clear_cache(self) -> None:
        for f in AppDirs.cache.glob("*"):
            if f.is_file():
                f.unlink()
        self._show_toast("Caché limpiada con éxito", "success")
        self._vm.refresh()

    def _clear_downloads(self) -> None:
        for f in AppDirs.downloads.glob("*"):
            if f.is_file():
                f.unlink()
        self._show_toast("Descargas eliminadas con éxito", "success")
        self._vm.refresh()

    def _export_backup(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getSaveFileName(
            self.window(), "Exportar copia de seguridad",
            str(Path.home() / "doremi_backup.zip"), "Zip Files (*.zip)")
        if not file_path:
            return
        from doremi.utils.backup import BackupManager
        if BackupManager.export_backup(Path(file_path)):
            self._show_toast("Copia de seguridad exportada con éxito", "success")
        else:
            self._show_toast("Error al exportar copia de seguridad", "error")

    def _import_backup(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self.window(), "Importar copia de seguridad",
            str(Path.home()), "Zip Files (*.zip)")
        if file_path:
            asyncio.ensure_future(self._import_backup_async(Path(file_path)))

    async def _import_backup_async(self, path: Path) -> None:
        from doremi.utils.backup import BackupManager
        self._show_toast("Restaurando copia de seguridad...", "info")
        success = await BackupManager.import_backup_async(path)
        if success:
            self._show_toast("Copia de seguridad restaurada. Reinicia la aplicación.", "success")
            self._vm.refresh()
        else:
            self._show_toast("Error al restaurar la copia de seguridad", "error")

    # — About —

    def _open_github(self) -> None:
        import webbrowser
        webbrowser.open("https://github.com/Eirom16/Doremi")

    async def _check_updates(self) -> None:
        try:
            from doremi.utils.updater import CURRENT_VERSION, check_for_updates, is_dev_build
            self._show_toast("Comprobando actualizaciones…", "info")
            release = await check_for_updates()

            if is_dev_build():
                self._show_toast("Estás en una versión de desarrollo (siempre es la última)", "info")
                return
            if release:
                from doremi.ui.widgets.update_dialog import UpdateDialog
                dlg = UpdateDialog(release, parent=self.window())
                dlg.show()
            else:
                self._show_toast(f"Ya tienes la última versión ({CURRENT_VERSION})", "success")
        except Exception as e:
            logger.error(f"Update check error: {e}")
            self._show_toast("No se pudo comprobar actualizaciones", "error")
