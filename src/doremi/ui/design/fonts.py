from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from loguru import logger

from doremi.ui.design.tokens import TypeScale


_LOADED = False


def _font_dirs() -> list[Path]:
    import sys
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        bundle_root = Path(sys._MEIPASS)
        return [
            bundle_root / "doremi" / "assets" / "fonts",
            bundle_root / "assets" / "fonts",
        ]
    root = Path(__file__).resolve().parents[4]
    package = Path(__file__).resolve().parents[2]
    return [
        package / "assets" / "fonts",  # Priorizar la ubicación correcta
        root / "assets" / "fonts",
    ]


def load_fonts() -> None:
    """Load bundled fonts if present, falling back to system fonts."""
    global _LOADED
    if _LOADED:
        return

    seen: set[Path] = set()
    for fonts_dir in _font_dirs():
        if not fonts_dir.exists():
            logger.debug(f"Font directory does not exist: {fonts_dir}")
            continue
        for path in sorted(fonts_dir.iterdir()):
            if path in seen or path.suffix.lower() not in {".ttf", ".otf"}:
                continue
            seen.add(path)
            fid = QFontDatabase.addApplicationFont(str(path))
            if fid == -1:
                logger.debug(f"Font failed to load: {path}")
            else:
                families = QFontDatabase.applicationFontFamilies(fid)
                logger.debug(f"Loaded font {path.name}: {families}")

    _LOADED = True


class AppFont:
    """API canónica de tipografía. Roles y tamaños: DESIGN-apple.md + tokens.TypeScale.

    Inter es la familia única (bundleada en assets/fonts). Nunito está deprecada.
    Display/heading/title usan tracking negativo ("Apple tight") y peso DemiBold (600).
    """

    FAMILY = "Inter"
    FAMILY_BODY = "Inter"

    @staticmethod
    def display(size: int = TypeScale.DISPLAY) -> QFont:
        font = QFont(AppFont.FAMILY, size, QFont.Weight.DemiBold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, -0.4)
        return font

    @staticmethod
    def heading(size: int = TypeScale.HEADING) -> QFont:
        font = QFont(AppFont.FAMILY, size, QFont.Weight.DemiBold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, -0.3)
        return font

    @staticmethod
    def title(size: int = TypeScale.TITLE) -> QFont:
        font = QFont(AppFont.FAMILY, size, QFont.Weight.DemiBold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, -0.2)
        return font

    @staticmethod
    def body(size: int = TypeScale.BODY) -> QFont:
        return QFont(AppFont.FAMILY_BODY, size, QFont.Weight.Normal)

    @staticmethod
    def label(size: int = TypeScale.LABEL) -> QFont:
        return QFont(AppFont.FAMILY_BODY, size, QFont.Weight.Medium)

    @staticmethod
    def caption(size: int = TypeScale.CAPTION) -> QFont:
        return QFont(AppFont.FAMILY_BODY, size, QFont.Weight.Normal)

    @staticmethod
    def mono(size: int = TypeScale.MONO) -> QFont:
        font = QFont("JetBrains Mono", size, QFont.Weight.Medium)
        font.setStyleHint(QFont.StyleHint.Monospace)
        return font

