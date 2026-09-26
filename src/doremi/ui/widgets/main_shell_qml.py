"""The visible, single-scene QML application shell."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor
from PySide6.QtQuickWidgets import QQuickWidget
from loguru import logger

from doremi.ui.theme_bridge import theme_bridge

QML_DIR = Path(__file__).resolve().parent.parent / "qml"


class MainShellQml(QQuickWidget):
    """QML root for the application chrome and the active screen."""

    def __init__(
        self,
        *,
        sidebar,
        search_bar,
        offline_banner,
        notification_panel,
        mini_player,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._load_ok = False
        self.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self.setClearColor(QColor(0, 0, 0, 0))
        self.engine().addImportPath(str(QML_DIR))
        self.rootContext().setContextProperty("themeBridge", theme_bridge())
        self.setInitialProperties({
            "navigationController": sidebar,
            "headerController": search_bar._vm,
            "offlineController": offline_banner,
            "notificationController": notification_panel._vm,
            "playerController": mini_player._vm,
        })
        self.setSource(QUrl.fromLocalFile(str(QML_DIR / "MainShell.qml")))
        self._load_ok = self.status() == QQuickWidget.Status.Ready
        if not self._load_ok:
            for error in self.errors():
                logger.error(f"QML MainShell: {error.toString()}")

    @property
    def is_ok(self) -> bool:
        return self._load_ok

    def show_screen(self, screen) -> None:
        root = self.rootObject()
        if root is None:
            return
        root.setProperty("screenVm", getattr(screen, "_vm", screen))
        root.setProperty("screenSource", screen.qml_source)

    def set_notifications_open(self, is_open: bool) -> None:
        root = self.rootObject()
        if root is not None:
            root.setProperty("notificationsOpen", bool(is_open))

    def set_toast_controller(self, controller) -> None:
        root = self.rootObject()
        if root is not None:
            root.setProperty("toastController", controller)
