"""The visible, single-scene QML application shell."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QUrl
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
        close_controller,
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
            "closeController": close_controller,
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
        host = root.findChild(QObject, "screenHost")
        if host is None:
            logger.error("QML ScreenHost no está disponible para navegar")
            return
        # A single QML call makes the URL and its view model atomic. Setting
        # them as separate root properties temporarily cross-wired adjacent
        # routes (e.g. HomeViewModel inside NowPlayingScreen).
        host.showScreen(screen.qml_source, getattr(screen, "_vm", screen))

    def set_notifications_open(self, is_open: bool) -> None:
        root = self.rootObject()
        if root is not None:
            root.setProperty("notificationsOpen", bool(is_open))

    def set_toast_controller(self, controller) -> None:
        root = self.rootObject()
        if root is not None:
            root.setProperty("toastController", controller)

    def set_close_confirmation(self, visible: bool, active_downloads: int = 0) -> None:
        root = self.rootObject()
        if root is not None:
            root.setProperty("activeDownloadCount", max(0, int(active_downloads)))
            root.setProperty("closeConfirmationVisible", bool(visible))
