from __future__ import annotations
import json
from pathlib import Path
from loguru import logger
from PySide6.QtCore import QObject, Signal

class TranslationManager(QObject):
    language_changed = Signal(str)
    BASE_LANGUAGE = "es"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_language = self.BASE_LANGUAGE
        self.base_translations: dict[str, str] = {}
        self.translations: dict[str, str] = {}
        self._missing_keys: set[tuple[str, str]] = set()
        self.base_translations = self._read_translations(self.BASE_LANGUAGE)
        self.load_translations(self.current_language)

    def _read_translations(self, lang_code: str) -> dict[str, str]:
        base_dir = Path(__file__).parent.parent
        locale_path = base_dir / "locales" / f"{lang_code}.json"

        if locale_path.exists():
            try:
                with open(locale_path, "r", encoding="utf-8") as f:
                    translations = json.load(f)
                if isinstance(translations, dict):
                    return translations
                logger.error(f"Archivo de idioma inválido para {lang_code}: se esperaba un objeto JSON")
                return {}
            except Exception as e:
                logger.error(f"Error cargando idioma {lang_code}: {e}")
        else:
            logger.warning(f"No se encontró archivo de traducción para '{lang_code}' en: {locale_path}")
        return {}

    def load_translations(self, lang_code: str) -> None:
        self.current_language = lang_code
        self.translations.clear()

        if lang_code == self.BASE_LANGUAGE:
            self.translations = self.base_translations.copy()
        else:
            self.translations = self._read_translations(lang_code)

        if self.translations:
            logger.info(f"Idioma de Doremi cargado: {lang_code}")

        self.language_changed.emit(lang_code)

    def translate(self, text: str) -> str:
        if not text:
            return ""
        translated = self.translations.get(text)
        if translated is not None:
            return translated
        fallback = self.base_translations.get(text)
        if fallback is not None:
            return fallback

        missing_key = (self.current_language, text)
        if missing_key not in self._missing_keys:
            self._missing_keys.add(missing_key)
            logger.warning(f"Traducción faltante para '{text}' en idioma '{self.current_language}'")
        return text

    def translate_format(self, text: str, **kwargs) -> str:
        translated = self.translate(text)
        try:
            return translated.format(**kwargs)
        except Exception as e:
            logger.warning(f"No se pudo aplicar formato a traducción '{text}': {e}")
            return translated

    def plural(self, singular: str, plural: str, count: int, **kwargs) -> str:
        key = singular if count == 1 else plural
        params = {"count": count, **kwargs}
        return self.translate_format(key, **params)


_manager = TranslationManager()


def _(text: str) -> str:
    """Translate the given text dynamically."""
    return _manager.translate(text)


def _f(text: str, **kwargs) -> str:
    """Translate and format a string with named placeholders."""
    return _manager.translate_format(text, **kwargs)


def ngettext(singular: str, plural: str, count: int, **kwargs) -> str:
    """Translate singular/plural forms using count and named placeholders."""
    return _manager.plural(singular, plural, count, **kwargs)


def set_language(lang_code: str) -> None:
    """Switch active translation dictionary and emit signal."""
    _manager.load_translations(lang_code)
