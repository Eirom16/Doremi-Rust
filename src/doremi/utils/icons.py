from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QFontDatabase
from PySide6.QtCore import Qt, QSize
from pathlib import Path
from loguru import logger
from doremi.config.paths import AppDirs

class MaterialIcons:
    _font_id = -1
    _font_name = ""

    # Map names to codepoints (keep in sync with design/icons.py)
    ICONS = {
        "play_arrow": "\ue037",
        "pause": "\ue034",
        "skip_next": "\ue044",
        "skip_previous": "\ue045",
        "home": "\ue88a",
        "search": "\ue8b6",
        "library_music": "\ue030",
        "queue_music": "\ue03d",
        "history": "\ue889",
        "download": "\uf090",
        "settings": "\ue8b8",
        "more_vert": "\ue5d4",
        "close": "\ue5cd",
        "keyboard_arrow_up": "\ue316",
        "keyboard_arrow_down": "\ue313",
        "add": "\ue145",
        "favorite": "\ue87d",
        "subtitles": "\ue048",
        "album": "\ue019",
        "person": "\ue7fd",
        "queue_play_next": "\ue066",
        "palette": "\ue40a",
        "play_circle": "\ue14f",
        "tune": "\ue429",
        "manage_accounts": "\uf011",
        "storage": "\ue1db",
        "info": "\ue88e",
        "playlist_add": "\ue03b",
        "menu": "\ue5d2",
        "delete": "\ue872",
        "music_note": "\ue405",
    }

    @classmethod
    def init(cls):
        if cls._font_id != -1:
            return
            
        font_path = Path(__file__).parent.parent / "assets" / "fonts" / "MaterialSymbolsRounded.ttf"
        if not font_path.exists():
            logger.warning(f"Material Symbols font not found at {font_path}")
            return
            
        cls._font_id = QFontDatabase.addApplicationFont(str(font_path))
        if cls._font_id != -1:
            families = QFontDatabase.applicationFontFamilies(cls._font_id)
            if families:
                cls._font_name = families[0]
                logger.info(f"Loaded Material Symbols font: {cls._font_name}")

    @classmethod
    def icon(cls, name: str, color: str = "#FFFFFF", size: int = 24) -> QIcon:
        """Draws the font icon into a QIcon."""
        if not cls._font_name:
            cls.init()
            
        # Use ligature directly
        char = name
        
        # Use a pixmap that matches the requested icon size with some padding
        pixmap_size = int(size * 1.6)
        pixmap = QPixmap(QSize(pixmap_size, pixmap_size))
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        font = QFont(cls._font_name)
        font.setPixelSize(size)
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        painter.setFont(font)
        painter.setPen(QColor(color))
        
        # Draw text exactly in the center
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, char)
        painter.end()
        
        return QIcon(pixmap)
