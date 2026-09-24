from __future__ import annotations

import re

from PySide6.QtCore import Property, QObject, Signal

_RGBA_RE = re.compile(r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([0-9.]+)\s*\)")


def _to_qml_color(value: str) -> str:
    """QML/QColor no parsea 'rgba(r,g,b,a)' (sintaxis CSS); lo convierte a #AARRGGBB."""
    m = _RGBA_RE.fullmatch(value.strip())
    if not m:
        return value
    r, g, b = (int(m.group(i)) for i in (1, 2, 3))
    a = round(float(m.group(4)) * 255)
    return f"#{a:02X}{r:02X}{g:02X}{b:02X}"


class ThemeBridge(QObject):
    """Colores del tema como properties observables para QML.

    Los valores ESTÁTICOS (spacing/radius/type) viven en `ui/qml/Theme.qml`
    (generado desde tokens.py). Los colores son dinámicos (acento del
    usuario) y llegan a QML a través de este bridge: ThemeManager llama
    `push(tokens.CURRENT)` tras aplicar un tema y las vistas QML se
    rebindean solas vía los NOTIFY.
    """

    changed = Signal()
    mini_player_visibility_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        from doremi.ui.design import tokens
        self._colors = self._to_map(tokens.CURRENT)
        self._mini_player_visible = False

    @staticmethod
    def _to_map(scheme) -> dict:
        return {
            f.name: _to_qml_color(getattr(scheme, f.name))
            for f in scheme.__dataclass_fields__.values()
        }

    def push(self, scheme) -> None:
        """Actualiza los colores (llamado por ThemeManager tras aplicar tema)."""
        self._colors = self._to_map(scheme)
        self.changed.emit()

    @Property("QVariantMap", notify=changed)
    def colors(self) -> dict:
        return self._colors

    def set_mini_player_visible(self, visible: bool) -> None:
        visible = bool(visible)
        if self._mini_player_visible != visible:
            self._mini_player_visible = visible
            self.mini_player_visibility_changed.emit()

    @Property(bool, notify=mini_player_visibility_changed)
    def miniPlayerVisible(self) -> bool:
        return self._mini_player_visible


_instance: ThemeBridge | None = None


def theme_bridge() -> ThemeBridge:
    """Instancia única a nivel de app (se crea tras QApplication y se le parenta —
    sin parent de Qt, el engine QML puede ver el objeto como null en bindings
    tempranos)."""
    global _instance
    if _instance is None:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        _instance = ThemeBridge(app if app is not None else None)
    return _instance
