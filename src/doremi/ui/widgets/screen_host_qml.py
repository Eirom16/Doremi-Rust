"""Single QML surface used to render the active application screen."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor
from PySide6.QtQuickWidgets import QQuickWidget
from loguru import logger

from doremi.ui.theme_bridge import theme_bridge

QML_DIR = Path(__file__).resolve().parent.parent / "qml"


class QmlScreenHost(QQuickWidget):
    """Renders one route at a time through ``ScreenHost.qml``.

    Presenters still own their data and public signals during the transition,
    while this view owns the only visible screen scene.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._load_ok = False
        self.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self.setClearColor(QColor(0, 0, 0, 0))
        self.engine().addImportPath(str(QML_DIR))
        self.rootContext().setContextProperty("themeBridge", theme_bridge())
        self.setSource(QUrl.fromLocalFile(str(QML_DIR / "ScreenHost.qml")))
        self._load_ok = self.status() == QQuickWidget.Status.Ready
        if not self._load_ok:
            for error in self.errors():
                logger.error(f"QML ScreenHost: {error.toString()}")

    @property
    def is_ok(self) -> bool:
        return self._load_ok

    def show_screen(self, screen) -> None:
        root = self.rootObject()
        if root is None:
            return
        root.setProperty("screenVm", getattr(screen, "_vm", screen))
        root.setProperty("screenSource", screen.qml_source)


class QmlRouteStack:
    """Compatibility router for controllers formerly coupled to QStackedWidget."""

    def __init__(self, host: QmlScreenHost) -> None:
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
