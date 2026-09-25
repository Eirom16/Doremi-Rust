"""QML overlay for application updates, shared by startup and settings."""

from __future__ import annotations

import asyncio
import subprocess
import sys
import webbrowser
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Property, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QApplication, QWidget
from loguru import logger

from doremi.ui.theme_bridge import theme_bridge
from doremi.utils.updater import CURRENT_VERSION, ReleaseInfo, download_update, install_update_async

QML_DIR = Path(__file__).resolve().parent.parent / "qml"


class UpdateDialogQml(QObject):
    """Modal QML update surface with the legacy dialog's public ``show`` API."""

    update_installed = Signal()
    _active_instance: "UpdateDialogQml | None" = None

    def __init__(self, release: ReleaseInfo, parent: QWidget) -> None:
        self._host = parent.window() or parent
        super().__init__(self._host)
        self.release = release
        self._downloading = False
        self._progress_visible = False
        self._progress = 0.0
        self._status_text = ""
        self._install_complete = False
        self._visible = False
        self._quick = QQuickWidget(self._host)
        self._quick.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self._quick.setClearColor(QColor(0, 0, 0, 0))
        self._quick.engine().addImportPath(str(QML_DIR))
        context = self._quick.rootContext()
        context.setContextProperty("themeBridge", theme_bridge())
        context.setContextProperty("updateDialog", self)
        self._quick.setSource(QUrl.fromLocalFile(str(QML_DIR / "UpdateDialog.qml")))
        self._quick.hide()
        self._host.installEventFilter(self)

        active = UpdateDialogQml._active_instance
        if active is not None and active is not self:
            if active._downloading:
                return
            active.close()
        UpdateDialogQml._active_instance = self

    @Property(str, constant=True)
    def version(self) -> str:
        return self.release.version

    @Property(str, constant=True)
    def currentVersion(self) -> str:
        return CURRENT_VERSION

    @Property(str, constant=True)
    def releaseNotes(self) -> str:
        return self.release.release_notes or "Sin notas de versión."

    state_changed = Signal()

    @Property(bool, notify=state_changed)
    def downloading(self) -> bool:
        return self._downloading

    @Property(bool, notify=state_changed)
    def progressVisible(self) -> bool:
        return self._progress_visible

    @Property(float, notify=state_changed)
    def progress(self) -> float:
        return self._progress

    @Property(str, notify=state_changed)
    def statusText(self) -> str:
        return self._status_text

    @Property(bool, notify=state_changed)
    def installComplete(self) -> bool:
        return self._install_complete

    @Property(str, notify=state_changed)
    def updateButtonText(self) -> str:
        return "Reiniciando..." if self._install_complete else f"Actualizar a {self.release.version}"

    def show(self) -> None:
        self._quick.setGeometry(self._host.rect())
        self._visible = True
        self._quick.show()
        self._quick.raise_()

    def close(self) -> None:
        if self._downloading:
            return
        self._visible = False
        self._quick.hide()
        if UpdateDialogQml._active_instance is self:
            UpdateDialogQml._active_instance = None

    @Slot()
    def closeDialog(self) -> None:
        self.close()

    @Slot()
    def openGithub(self) -> None:
        if self.release.html_url:
            webbrowser.open(self.release.html_url)

    @Slot()
    def startUpdate(self) -> None:
        if not self._downloading and not self._install_complete:
            asyncio.ensure_future(self._download_and_install())

    async def _download_and_install(self) -> None:
        asset = self.release.get_asset_for_platform()
        self._progress_visible = True
        if not asset:
            self._status_text = "No hay paquete disponible para esta plataforma. Descárgalo desde GitHub."
            self.state_changed.emit()
            return

        self._downloading = True
        self._status_text = "Iniciando descarga..."
        self.state_changed.emit()

        def on_progress(percent: float, message: str) -> None:
            self._progress = percent
            self._status_text = message
            self.state_changed.emit()

        package_path = await download_update(asset, on_progress)
        if not package_path:
            self._status_text = "Error en la descarga. Comprueba tu conexión e inténtalo de nuevo."
            self._downloading = False
            self.state_changed.emit()
            return

        self._progress = 100.0
        self._status_text = "Instalando actualización. No cierres la aplicación."
        self.state_changed.emit()
        success = await install_update_async(package_path, None)
        if not success:
            self._status_text = f"No se pudo completar la instalación automática. Archivo descargado en: {package_path}"
            self._downloading = False
            self.state_changed.emit()
            return

        self._status_text = "Instalación completada. Reiniciando Doremi..."
        self._install_complete = True
        self.state_changed.emit()
        self.update_installed.emit()
        QTimer.singleShot(2000, self._restart_app)

    def eventFilter(self, watched, event) -> bool:
        if watched is self._host and event.type() == QEvent.Type.Resize and self._visible:
            self._quick.setGeometry(self._host.rect())
        return False

    def _restart_app(self) -> None:
        logger.info("Reiniciando Doremi para aplicar la actualización...")
        try:
            command = [sys.executable] + (sys.argv[1:] if getattr(sys, "frozen", False) else sys.argv)
            subprocess.Popen(command)
        except Exception as exc:
            logger.error(f"Error al reiniciar Doremi: {exc}")
        QApplication.quit()
