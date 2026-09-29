from __future__ import annotations

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from doremi.config.paths import AppDirs
class NavSidebarQml(QObject):
    """Navigation presenter rendered by MainShell.qml."""

    on_navigate = Signal(str)
    active_route_changed = Signal()
    active_path_changed = Signal()
    collapsed_changed = Signal()
    playlists_changed = Signal()
    width_changed = Signal(int)

    EXPANDED_WIDTH = 214
    COLLAPSED_WIDTH = 64

    def __init__(self, on_navigate, parent=None):
        super().__init__(parent)
        self._on_navigate = on_navigate
        self._active_route = "home"
        self._active_path = "home"
        self._collapsed = False
        self._playlists: list[dict[str, str]] = []
        self._sidebar_width = self.EXPANDED_WIDTH
        self._load_ok = True

    @property
    def is_ok(self) -> bool:
        return self._load_ok

    @Property(str, notify=active_route_changed)
    def activeRoute(self) -> str:
        return self._active_route

    @Property(str, notify=active_path_changed)
    def activePath(self) -> str:
        return self._active_path

    @Property(bool, notify=collapsed_changed)
    def collapsed(self) -> bool:
        return self._collapsed

    @Property("QVariantList", notify=playlists_changed)
    def playlists(self) -> list[dict[str, str]]:
        return self._playlists

    @Property(str, constant=True)
    def appIconSource(self) -> str:
        return QUrl.fromLocalFile(
            str(AppDirs.root / "assets" / "Doremi.png")
        ).toString()

    def _get_sidebar_width(self) -> int:
        return self._sidebar_width

    def _set_sidebar_width(self, width: int) -> None:
        self._sidebar_width = int(width)
        self.width_changed.emit(self._sidebar_width)

    sidebar_width = Property(int, _get_sidebar_width, _set_sidebar_width)

    @Slot(str)
    def navigate(self, route: str) -> None:
        if not route:
            return
        self.set_active(route)
        if callable(self._on_navigate):
            self._on_navigate(route)
        self.on_navigate.emit(route)

    @Slot()
    def toggleCollapsed(self) -> None:
        self.toggle_collapse()

    def toggle_collapse(self) -> None:
        self.set_collapsed(not self._collapsed)

    @Slot(bool)
    def setCollapsed(self, collapsed: bool) -> None:
        self.set_collapsed(collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        collapsed = bool(collapsed)
        if self._collapsed == collapsed:
            return
        self._collapsed = collapsed
        self.collapsed_changed.emit()
        self._set_sidebar_width(self.COLLAPSED_WIDTH if self._collapsed else self.EXPANDED_WIDTH)

    def set_playlists(self, playlists: list[dict]) -> None:
        self._playlists = [
            {
                "title": str(item.get("title", "")).strip(),
                "navigate": str(item.get("navigate", "")).strip(),
            }
            for item in playlists[:4]
            if item.get("title") and item.get("navigate")
        ]
        self.playlists_changed.emit()

    def set_active(self, route: str) -> None:
        """Reflect programmatic navigation in the QML selection state."""
        path = (route or "home").strip()
        base_route = path.split("?", 1)[0]
        if self._active_route != base_route:
            self._active_route = base_route
            self.active_route_changed.emit()
        if self._active_path != path:
            self._active_path = path
            self.active_path_changed.emit()

    def _update_sidebar_styles(self) -> None:
        """Theme changes bind directly in QML; retained for ThemeManager parity."""
