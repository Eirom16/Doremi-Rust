from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QLabel


MATERIAL_FONT = "Material Symbols Rounded"

CODEPOINTS: dict[str, str] = {
    # ── Playback ──────────────────────────────────────────────────
    "play_arrow":          "\ue037",
    "pause":               "\ue034",
    "stop":                "\ue047",
    "skip_next":           "\ue044",
    "skip_previous":       "\ue045",
    "replay":              "\ue042",
    "shuffle":             "\ue043",
    "repeat":              "\ue040",
    "repeat_one":          "\ue041",
    "queue_music":         "\ue03d",
    "playlist_add":        "\ue03b",
    "playlist_play":       "\ue05f",
    "playlist_remove":     "\ueb80",
    "library_music":       "\ue030",
    "music_note":          "\ue405",
    "album":               "\ue019",
    "artist":              "\ueb99",
    "mic":                 "\ue029",
    "lyrics":              "\uec0b",
    "speed":               "\ue9c4",
    "timer":               "\ue425",
    "sleep":               "\ue4c2",
    "queue_play_next":     "\ue066",
    "play_circle":         "\ue14f",

    # ── Volume ────────────────────────────────────────────────────
    "volume_up":           "\ue050",
    "volume_down":         "\ue04d",
    "volume_off":          "\ue04f",
    "volume_mute":         "\ue04e",

    # ── Like / Rating ─────────────────────────────────────────────
    "favorite":            "\ue87d",
    "favorite_border":     "\ue87e",
    "thumb_up":            "\ue8dc",
    "thumb_down":          "\ue8db",

    # ── Navigation ────────────────────────────────────────────────
    "home":                "\ue88a",
    "home_filled":         "\ue9b2",
    "search":              "\ue8b6",
    "explore":             "\ue87a",
    "library_add":         "\ue02e",
    "download":            "\uf090",
    "download_done":       "\ueb9d",
    "cloud_download":      "\ue2c0",
    "history":             "\ue889",
    "bar_chart":           "\ue26b",
    "settings":            "\ue8b8",

    # ── General actions ───────────────────────────────────────────
    "add":                 "\ue145",
    "remove":              "\ue15b",
    "close":               "\ue5cd",
    "check":               "\ue5ca",
    "check_circle":        "\ue86c",
    "error":               "\ue000",
    "warning":             "\ue002",
    "info":                "\ue88e",
    "more_vert":           "\ue5d4",
    "more_horiz":          "\ue5d3",
    "edit":                "\ue3c9",
    "delete":              "\ue872",
    "share":               "\ue80d",
    "open_in_new":         "\ue89e",
    "copy":                "\ue14d",
    "link":                "\ue157",
    "refresh":             "\ue5d5",
    "sort":                "\ue164",
    "filter_list":         "\ue152",
    "drag_indicator":      "\ue945",
    "menu":                "\ue5d2",

    # ── Account / Settings ────────────────────────────────────────
    "account_circle":      "\ue853",
    "person":              "\ue7fd",
    "manage_accounts":     "\uf011",
    "logout":              "\ue9ba",
    "login":               "\uea77",
    "key":                 "\ue73c",
    "vpn_key":             "\ue0da",
    "palette":             "\ue40a",
    "dark_mode":           "\ue51c",
    "light_mode":          "\ue518",
    "contrast":            "\ueb37",
    "text_fields":         "\ue262",
    "tune":                "\ue429",
    "equalizer":           "\ue01d",
    "graphic_eq":          "\ue1b8",
    "notifications":       "\ue7f4",
    "notifications_off":   "\ue7f6",
    "storage":             "\ue1db",
    "folder":              "\ue2c7",
    "folder_open":         "\ue2c8",

    # ── Player / Navigation ───────────────────────────────────────
    "expand_less":         "\ue5ce",
    "expand_more":         "\ue5cf",
    "fullscreen":          "\ue5d0",
    "fullscreen_exit":     "\ue5d1",
    "chevron_left":        "\ue5cb",
    "chevron_right":       "\ue5cc",
    "arrow_back":          "\ue5c4",
    "arrow_forward":       "\ue5c8",
    "arrow_upward":        "\ue5d8",
    "arrow_downward":      "\ue5db",

    # ── Network / Sync ────────────────────────────────────────────
    "wifi":                "\ue63e",
    "wifi_off":            "\ue648",
    "sync":                "\ue627",
    "sync_disabled":       "\ue628",
    "cloud":               "\ue2bd",
    "cloud_off":           "\ue2c1",

    # ── External / Media ──────────────────────────────────────────
    "radio":               "\ue03e",
    "podcasts":            "\uef04",
    "new_releases":        "\ue031",
    "trending_up":         "\ue8e8",
    "star":                "\ue838",
    "star_border":         "\ue83a",
}


class Icon:
    @staticmethod
    def get(name: str) -> str:
        # Use ligature name directly for Material Symbols font
        return name

    @staticmethod
    def icon(name: str, color: str = "#F1F0FF", size: int = 24, filled: bool = True) -> QIcon:
        from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
        from PySide6.QtCore import Qt
        
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        font = Icon.font(size, filled)
        painter.setFont(font)
        painter.setPen(QColor(color))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, Icon.get(name))
        painter.end()
        
        return QIcon(pixmap)

    @staticmethod
    def font(size: int = 20, filled: bool = True) -> QFont:
        font = QFont(MATERIAL_FONT)
        font.setPixelSize(size)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        try:
            fill_tag = QFont.Tag('FILL')
            font.setVariableAxis(fill_tag, 1.0 if filled else 0.0)
        except Exception:
            pass
        return font

    @staticmethod
    def label(
        name: str,
        size: int = 20,
        color: str = "#F1F0FF",
        filled: bool = True,
        parent=None,
    ) -> QLabel:
        label = QLabel(Icon.get(name), parent)
        label.setFont(Icon.font(size, filled))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Make the label big enough so the icon glyph is not clipped
        label.setFixedSize(max(size + 8, 28), max(size + 8, 28))
        label.setStyleSheet(f"color: {color}; background: transparent; font-family: '{MATERIAL_FONT}'; font-size: {size}px;")
        return label
