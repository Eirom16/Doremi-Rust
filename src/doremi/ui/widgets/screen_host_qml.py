"""Route compatibility layer for the QML application shell."""

from __future__ import annotations

class QmlRouteStack:
    """Compatibility router for controllers formerly coupled to QStackedWidget."""

    def __init__(self, host) -> None:
        self._host = host
        self._screens: list[object] = []
        self._current_index = -1

    def addWidget(self, screen) -> int:
        self._screens.append(screen)
        return len(self._screens) - 1

    def currentIndex(self) -> int:
        return self._current_index

    def currentWidget(self):
        if 0 <= self._current_index < len(self._screens):
            return self._screens[self._current_index]
        return None

    def setCurrentIndex(self, index: int) -> None:
        if not 0 <= index < len(self._screens):
            return
        for screen in self._screens:
            set_active = getattr(screen, "set_active", None)
            if callable(set_active):
                set_active(False)
        self._current_index = index
        set_active = getattr(self._screens[index], "set_active", None)
        if callable(set_active):
            set_active(True)
        self._host.show_screen(self._screens[index])

    def setCurrentIndexAnimated(self, index: int) -> None:
        self.setCurrentIndex(index)
