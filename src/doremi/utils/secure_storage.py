from __future__ import annotations
import json
import os
import sys
import tempfile
from pathlib import Path
from loguru import logger
from doremi.config.paths import AppDirs

try:
    import keyring
    HAS_KEYRING = True
except ImportError:
    HAS_KEYRING = False
    logger.warning("Librería 'keyring' no encontrada. Se usará el almacenamiento en texto plano.")

SERVICE_NAME = "doremi"
YT_AUTH_USER = "youtube_music_auth"
LASTFM_KEY_USER = "lastfm_api_key"
LASTFM_SECRET_USER = "lastfm_api_secret"
LASTFM_SESSION_USER = "lastfm_session_key"

class SecureStorage:
    _ignore_legacy_youtube_headers = False

    @staticmethod
    def _is_functional() -> bool:
        """Check if keyring is installed and has a functional backend."""
        if not HAS_KEYRING:
            return False
        try:
            # Try a quick test write/read to ensure a backend daemon is running
            keyring.set_password("doremi_test", "test", "val")
            val = keyring.get_password("doremi_test", "test")
            keyring.delete_password("doremi_test", "test")
            return val == "val"
        except Exception as e:
            logger.debug(f"El llavero del sistema no es funcional o está bloqueado: {e}")
            return False

    @classmethod
    def save_youtube_headers(cls, headers: dict) -> bool:
        """Save YouTube Music headers securely."""
        cls._ignore_legacy_youtube_headers = False
        headers_str = json.dumps(headers)
        if cls._is_functional():
            try:
                keyring.set_password(SERVICE_NAME, YT_AUTH_USER, headers_str)
                logger.info("Credenciales de YouTube Music guardadas de forma segura en el llavero del sistema.")
                # If a legacy file exists, delete it for security
                legacy_file = AppDirs.config / "headers_auth.json"
                try:
                    if legacy_file.exists():
                        legacy_file.unlink()
                except Exception as e:
                    logger.warning(f"No se pudo eliminar el archivo legacy de credenciales: {e}")
                return True
            except Exception as e:
                logger.error(f"Error guardando en llavero: {e}")

        # Fallback to local config file
        cls._ignore_legacy_youtube_headers = False
        try:
            legacy_file = AppDirs.config / "headers_auth.json"
            with open(legacy_file, "w") as f:
                json.dump(headers, f, indent=4)
            logger.warning("Llavero no funcional. Sesión de YouTube Music guardada en texto plano.")
            return True
        except Exception as e:
            logger.error(f"Error en fallback local de guardado de credenciales: {e}")
            return False

    @classmethod
    def load_youtube_headers(cls) -> dict | None:
        """Load YouTube Music headers securely."""
        if cls._is_functional():
            try:
                headers_str = keyring.get_password(SERVICE_NAME, YT_AUTH_USER)
                if headers_str:
                    logger.debug("Credenciales de YouTube Music cargadas de forma segura desde el llavero.")
                    return json.loads(headers_str)
            except Exception as e:
                logger.error(f"Error al leer del llavero: {e}")

        # Fallback to local config file
        legacy_file = AppDirs.config / "headers_auth.json"
        if not cls._ignore_legacy_youtube_headers and legacy_file.exists():
            try:
                with open(legacy_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error al leer credenciales locales: {e}")
        return None

    @classmethod
    def delete_youtube_headers(cls) -> None:
        """Delete YouTube Music headers secure storage."""
        cls._ignore_legacy_youtube_headers = True
        if cls._is_functional():
            try:
                # Check if it exists before trying to delete
                if keyring.get_password(SERVICE_NAME, YT_AUTH_USER):
                    keyring.delete_password(SERVICE_NAME, YT_AUTH_USER)
                    logger.info("Credenciales de YouTube Music eliminadas del llavero del sistema.")
            except Exception as e:
                logger.error(f"Error eliminando credenciales del llavero: {e}")

        legacy_file = AppDirs.config / "headers_auth.json"
        try:
            if legacy_file.exists():
                legacy_file.unlink()
                logger.info("Archivo local de credenciales de YouTube Music eliminado.")
        except Exception as e:
            logger.warning(f"No se pudo eliminar el archivo local de credenciales: {e}")

    @classmethod
    def save_lastfm_credentials(cls, api_key: str, api_secret: str, session_key: str) -> None:
        """Save Last.fm secrets to keyring if available."""
        if cls._is_functional():
            try:
                if api_key:
                    keyring.set_password(SERVICE_NAME, LASTFM_KEY_USER, api_key)
                if api_secret:
                    keyring.set_password(SERVICE_NAME, LASTFM_SECRET_USER, api_secret)
                if session_key:
                    keyring.set_password(SERVICE_NAME, LASTFM_SESSION_USER, session_key)
                logger.info("Credenciales de Last.fm guardadas de forma segura en el llavero.")
                return
            except Exception as e:
                logger.error(f"Error guardando Last.fm en llavero: {e}")

    @classmethod
    def load_lastfm_credentials(cls) -> tuple[str, str, str]:
        """Load Last.fm secrets from keyring if available. Returns (api_key, api_secret, session_key)."""
        api_key, api_secret, session_key = "", "", ""
        if cls._is_functional():
            try:
                api_key = keyring.get_password(SERVICE_NAME, LASTFM_KEY_USER) or ""
                api_secret = keyring.get_password(SERVICE_NAME, LASTFM_SECRET_USER) or ""
                session_key = keyring.get_password(SERVICE_NAME, LASTFM_SESSION_USER) or ""
            except Exception as e:
                logger.error(f"Error cargando Last.fm desde llavero: {e}")
        return api_key, api_secret, session_key

    @classmethod
    def delete_lastfm_credentials(cls) -> None:
        """Delete Last.fm secrets from keyring."""
        if cls._is_functional():
            try:
                for user in [LASTFM_KEY_USER, LASTFM_SECRET_USER, LASTFM_SESSION_USER]:
                    if keyring.get_password(SERVICE_NAME, user):
                        keyring.delete_password(SERVICE_NAME, user)
                logger.info("Credenciales de Last.fm eliminadas del llavero del sistema.")
            except Exception as e:
                logger.error(f"Error eliminando Last.fm del llavero: {e}")

    @classmethod
    def make_secure_temp_auth_file(cls) -> tuple[str, Path | None]:
        """
        Creates a temporary secure file with decrypted YouTube Music headers
        for ytmusicapi. Returns (temp_filepath, temp_file_object).
        Make sure to close and delete the temp file after use!
        """
        headers = cls.load_youtube_headers()
        if not headers:
            return "", None

        # Create a temp file in a secure subdirectory
        temp_dir = Path(tempfile.gettempdir()) / "doremi_sec"
        temp_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        
        fd, path = tempfile.mkstemp(suffix=".json", prefix="auth_", dir=str(temp_dir))
        try:
            with os.fdopen(fd, 'w') as tmp:
                json.dump(headers, tmp)
            # Set restrictive permissions (read/write only by owner)
            os.chmod(path, 0o600)
            return path, Path(path)
        except Exception as e:
            logger.error(f"Failed to create secure temp auth file: {e}")
            try:
                os.close(fd)
            except Exception as close_error:
                logger.debug(f"Could not close secure temp auth fd after failure: {close_error}")
            try:
                os.unlink(path)
            except Exception as unlink_error:
                logger.debug(f"Could not delete secure temp auth file after failure: {unlink_error}")
            return "", None
