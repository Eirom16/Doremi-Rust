from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QWidget
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineScript
from PySide6.QtCore import Qt, Signal, QTimer, QUrl
import json
from loguru import logger
from doremi.config.paths import AppDirs


class WebLoginDialog(QDialog):
    login_successful = Signal(str)  # Emits avatar_url

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Iniciar sesión en YouTube Music")
        self.resize(1000, 700)
        self.setAccessibleName("Iniciar sesión en YouTube Music")
        from doremi.ui.design import tokens
        self.setStyleSheet(f"background-color: {tokens.CURRENT.bg_base};")

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Minimal header — thin strip with hint + close icon
        header = QWidget()
        header.setFixedHeight(32)
        header.setStyleSheet(f"background-color: {tokens.CURRENT.bg_elevated}; border-bottom: 1px solid {tokens.CURRENT.border};")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 8, 0)

        hint = QLabel("Inicia sesión — la ventana se cerrará automáticamente")
        hint.setStyleSheet(f"color: {tokens.CURRENT.text_disabled}; font-family: Inter; font-size: 11px;")
        header_layout.addWidget(hint)
        header_layout.addStretch()

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setAutoDefault(False)
        self.btn_close.setDefault(False)
        self.btn_close.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.btn_close.setAccessibleName("Cerrar inicio de sesión")
        self.btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {tokens.CURRENT.text_secondary};
                border: none;
                border-radius: 12px;
                font-size: 14px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                color: {tokens.CURRENT.error};
                background-color: rgba(239, 68, 68, 0.1);
            }}
        """)
        self.btn_close.clicked.connect(self.reject)
        header_layout.addWidget(self.btn_close)

        self.layout.addWidget(header)

        # Web View
        self.view = QWebEngineView()
        self.view.setAccessibleName("Página de inicio de sesión de YouTube Music")
        self.profile = QWebEngineProfile.defaultProfile()
        self.cookie_store = self.profile.cookieStore()

        self.cookies = {}
        self._login_detected = False

        # Inject script to auto-grant Storage Access API (fixes "Permission denied" errors)
        storage_script = QWebEngineScript()
        storage_script.setName("doremi_storage_access")
        storage_script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        storage_script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        storage_script.setRunsOnSubFrames(True)
        storage_script.setSourceCode("""
            // Auto-grant Storage Access API to prevent cross-site cookie blocks
            Document.prototype.requestStorageAccess = function() { return Promise.resolve(); };
            Document.prototype.requestStorageAccessFor = function() { return Promise.resolve(); };
        """)
        self.view.page().scripts().insert(storage_script)

        self.cookie_store.cookieAdded.connect(self._on_cookie_added)
        self.view.loadFinished.connect(self._on_load_finished)

        self.layout.addWidget(self.view)
        QWidget.setTabOrder(self.btn_close, self.view)

        self.view.load(QUrl("https://music.youtube.com"))

        # Periodic timer to re-check login status every 2 seconds
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(2000)
        self._poll_timer.timeout.connect(self._poll_login)
        self._poll_timer.start()

    def reject(self):
        self._poll_timer.stop()
        super().reject()

    def _on_cookie_added(self, cookie):
        domain = cookie.domain()
        if "youtube" in domain or "google" in domain:
            name = bytearray(cookie.name()).decode()
            value = bytearray(cookie.value()).decode()
            self.cookies[name] = value

    def _on_load_finished(self, ok):
        if ok:
            self._check_login()

    def _poll_login(self):
        if not self._login_detected:
            self._check_login()

    def _check_login(self):
        if self._login_detected:
            return

        # Only target the specific profile avatar button — not generic images
        js = """
        (() => {
            let img = document.querySelector('ytmusic-settings-button img') ||
                      document.querySelector('#avatar-btn img');
            if (!img || !img.src) return JSON.stringify({avatar: '', name: ''});
            let src = img.src;
            if (src.startsWith('data:') || !src.startsWith('http')) return JSON.stringify({avatar: '', name: ''});
            let name = img.alt || '';
            return JSON.stringify({avatar: src, name: name});
        })()
        """
        self.view.page().runJavaScript(js, self._on_login_result)

    def _on_login_result(self, result_str):
        if self._login_detected:
            return

        try:
            res = json.loads(result_str) if isinstance(result_str, str) else {}
        except Exception:
            return

        avatar_url = res.get("avatar", "")
        user_name = res.get("name", "")

        if not avatar_url:
            return

        has_session = any(k in self.cookies for k in [
            "SAPISID", "__Secure-3PAPISID", "__Secure-1PAPISID"
        ])

        if has_session:
            self._login_detected = True
            self._poll_timer.stop()
            logger.info(f"Login detected. Name: '{user_name}', Avatar: {avatar_url}")
            self._save_cookies_and_close(avatar_url=avatar_url, name=user_name)

    def _save_cookies_and_close(self, avatar_url="", name=""):
        # Build cookie string
        cookie_parts = []
        for name_key, value in self.cookies.items():
            cookie_parts.append(f"{name_key}={value}")

        cookie_str = "; ".join(cookie_parts)

        headers = {
            "cookie": cookie_str,
            "x-goog-authuser": "0",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "accept": "*/*",
            "origin": "https://music.youtube.com",
            "x-origin": "https://music.youtube.com",
            "authorization": "SAPISIDHASH 1"  # ytmusicapi 1.12+ needs this to detect AuthType.BROWSER
        }

        from doremi.utils.secure_storage import SecureStorage
        SecureStorage.save_youtube_headers(headers)

        # Save user profile
        profile_file = AppDirs.config / "user_profile.json"
        try:
            with open(profile_file, "w") as f:
                json.dump({"name": name, "avatar_url": avatar_url}, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save user profile: {e}")

        logger.info(f"Browser cookies saved successfully. Avatar: {avatar_url}")
        self.login_successful.emit(avatar_url)
        self.accept()
