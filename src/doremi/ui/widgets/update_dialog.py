# src/doremi/ui/widgets/update_dialog.py
"""
Diálogo de actualización de Doremi.
Se muestra cuando check_for_updates() devuelve un ReleaseInfo.
Muestra: versión actual vs nueva, notas del release, barra de progreso,
botones Actualizar / Posponer / Ver en GitHub.
"""
from __future__ import annotations

import webbrowser
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QFrame, QWidget, QApplication
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor
from qasync import asyncSlot

from doremi.ui.design.fonts import AppFont
from doremi.ui.design.icons import Icon
from doremi.ui.widgets.ripple_button import RippleButton
from doremi.ui.widgets.animated_progress import AnimatedProgressBar
from doremi.utils.updater import (
    ReleaseInfo, download_update, install_update_async, CURRENT_VERSION
)


class UpdateDialog(QDialog):
    """
    Diálogo modal de actualización.

    Uso:
        release = await check_for_updates()
        if release:
            dlg = UpdateDialog(release, parent=main_window)
            dlg.show()   # NO bloquea — usa show() no exec()
    """

    update_installed = Signal()
    _active_instance: UpdateDialog | None = None

    def __init__(self, release: ReleaseInfo, parent=None):
        super().__init__(parent)
        self.release = release
        self._downloading = False

        if UpdateDialog._active_instance is not None:
            if getattr(UpdateDialog._active_instance, "_downloading", False):
                QTimer.singleShot(0, self.reject)
                return
            try:
                UpdateDialog._active_instance.close()
            except Exception:
                pass
        UpdateDialog._active_instance = self

        self.setWindowTitle("Actualización disponible — Doremi")
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setMinimumWidth(520)

        self._build()
        self._center_on_parent()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._center_on_parent()

    def reject(self) -> None:
        if self._downloading:
            return
        super().reject()

    def hideEvent(self, event) -> None:
        if UpdateDialog._active_instance is self:
            UpdateDialog._active_instance = None
        super().hideEvent(event)

    def _build(self) -> None:
        from doremi.ui.design import tokens
        from PySide6.QtGui import QColor as _QC
        _acc = _QC(tokens.CURRENT.accent)
        _ar, _ag, _ab = _acc.red(), _acc.green(), _acc.blue()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Panel principal con fondo ──────────────────────────────────
        self._panel = QFrame()
        panel = self._panel
        panel.setObjectName("updatePanel")
        panel.setStyleSheet(f"""
            #updatePanel {{
                background-color: {tokens.CURRENT.bg_elevated};
                border-radius: 20px;
                border: 1px solid rgba({_ar},{_ag},{_ab},0.25);
            }}
        """)

        # Sombra exterior
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 120))
        panel.setGraphicsEffect(shadow)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # ── Cabecera: ícono + título ───────────────────────────────────
        header_row = QHBoxLayout()
        update_icon = Icon.label("new_releases", size=32, color=tokens.CURRENT.accent)
        self._update_icon = update_icon

        title_col = QVBoxLayout()
        title_col.setSpacing(2)

        self._title_lbl = QLabel("Nueva versión disponible")
        self._title_lbl.setFont(AppFont.heading(18))
        self._title_lbl.setStyleSheet(f"color: {tokens.CURRENT.text_primary};")

        self._version_lbl = QLabel(
            f"{CURRENT_VERSION}  →  {self.release.version}"
        )
        self._version_lbl.setFont(AppFont.mono(13))
        self._version_lbl.setStyleSheet(f"color: {tokens.CURRENT.accent};")

        title_col.addWidget(self._title_lbl)
        title_col.addWidget(self._version_lbl)

        header_row.addWidget(update_icon)
        header_row.addSpacing(12)
        header_row.addLayout(title_col)
        header_row.addStretch()

        # Botón cerrar
        close_btn = RippleButton("", variant="ghost")
        close_btn.setText(Icon.get("close"))
        close_btn.setFont(Icon.font(18))
        close_btn.setFixedSize(36, 36)
        close_btn.clicked.connect(self.reject)
        header_row.addWidget(close_btn)

        layout.addLayout(header_row)

        # ── Separador ─────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: rgba({_ar},{_ag},{_ab},0.10);")
        layout.addWidget(sep)

        # ── Notas del release ──────────────────────────────────────────
        self._notes_label = QLabel("Novedades en esta versión:")
        self._notes_label.setFont(AppFont.label(12))
        self._notes_label.setStyleSheet(f"color: {tokens.CURRENT.text_secondary};")
        layout.addWidget(self._notes_label)

        self._notes_box = QTextEdit()
        self._notes_box.setReadOnly(True)
        self._notes_box.setPlainText(self.release.release_notes or "Sin notas de versión.")
        self._notes_box.setFont(AppFont.body(13))
        self._notes_box.setFixedHeight(140)
        self._notes_box.setStyleSheet(f"""
            QTextEdit {{
                background: {tokens.CURRENT.bg_surface};
                border: 1px solid rgba({_ar},{_ag},{_ab},0.08);
                border-radius: 12px;
                color: {tokens.CURRENT.text_secondary};
                padding: 10px;
            }}
        """)
        layout.addWidget(self._notes_box)

        # ── Barra de progreso (oculta hasta que empieza la descarga) ───
        self._progress_container = QWidget()
        prog_layout = QVBoxLayout(self._progress_container)
        prog_layout.setContentsMargins(0, 0, 0, 0)
        prog_layout.setSpacing(6)

        self._progress_bar = AnimatedProgressBar()
        self._progress_bar.set_value(0.0, animated=False)

        self._progress_label = QLabel("Preparando descarga...")
        self._progress_label.setFont(AppFont.label(12))
        self._progress_label.setStyleSheet(f"color: {tokens.CURRENT.text_secondary};")

        prog_layout.addWidget(self._progress_bar)
        prog_layout.addWidget(self._progress_label)
        self._progress_container.setVisible(False)
        layout.addWidget(self._progress_container)

        # ── Botones de acción ──────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._github_btn = RippleButton("Ver en GitHub", variant="ghost")
        self._github_btn.setIcon(Icon.icon("open_in_new", tokens.CURRENT.text_secondary, 20))

        self._github_btn.setFont(AppFont.body(13))
        self._github_btn.clicked.connect(
            lambda: webbrowser.open(self.release.html_url)
        )

        self._postpone_btn = RippleButton("Posponer", variant="secondary")
        self._postpone_btn.clicked.connect(self.reject)

        self._update_btn = RippleButton(
            f"Actualizar a {self.release.version}", variant="primary"
        )
        self._update_btn.setIcon(Icon.icon("download", tokens.CURRENT.text_on_accent, 20))
        self._update_btn.setFont(AppFont.body(14))
        self._update_btn.setMinimumHeight(44)
        self._update_btn.clicked.connect(self._on_update_clicked)

        btn_row.addWidget(self._github_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._postpone_btn)
        btn_row.addWidget(self._update_btn)

        layout.addLayout(btn_row)
        root.addWidget(panel)

    def _center_on_parent(self) -> None:
        parent = self.parentWidget()
        if parent and parent.isVisible():
            parent_geo = parent.geometry()
            x = parent_geo.x() + (parent_geo.width()  - self.width())  // 2
            y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
            self.move(x, y)
        else:
            from PySide6.QtGui import QGuiApplication
            screen = QGuiApplication.primaryScreen()
            if screen:
                screen_geo = screen.geometry()
                x = screen_geo.x() + (screen_geo.width()  - self.width())  // 2
                y = screen_geo.y() + (screen_geo.height() - self.height()) // 2
                self.move(x, y)

    @asyncSlot()
    async def _on_update_clicked(self) -> None:
        from doremi.ui.design import tokens
        import platform

        asset = self.release.get_asset_for_platform()
        if not asset:
            self._progress_label.setText(
                "No hay paquete disponible para esta plataforma. "
                "Descarga manualmente desde GitHub."
            )
            self._progress_container.setVisible(True)
            return

        # Bloquear botones durante la descarga
        self._update_btn.setEnabled(False)
        self._postpone_btn.setEnabled(False)
        self._progress_container.setVisible(True)
        self._progress_label.setText("Iniciando descarga...")
        self._downloading = True

        def _progress(pct: float, msg: str) -> None:
            self._progress_bar.set_value(pct / 100.0)
            self._progress_label.setText(msg)

        pkg_path = await download_update(asset, _progress)

        if not pkg_path:
            self._progress_label.setText(
                "Error en la descarga. Comprueba tu conexión e inténtalo de nuevo."
            )
            self._update_btn.setEnabled(True)
            self._postpone_btn.setEnabled(True)
            self._downloading = False
            return

        self._progress_bar.set_value(1.0)

        # Solicitar autenticación del sistema (pkexec) en Linux
        password = None
        if platform.system() == "Linux":
            self._progress_label.setText("Autenticación requerida para la instalación...")

        self._progress_label.setText(
            "Instalando actualización... Por favor, no cierres la aplicación."
        )

        success = await install_update_async(pkg_path, password)
        if success:
            self._progress_label.setText(
                "¡Instalación completada con éxito! Reiniciando Doremi..."
            )
            self._update_btn.setText("Reiniciando...")
            self._update_btn.setIcon(Icon.icon("check_circle", tokens.CURRENT.text_on_accent, 20))
            self.update_installed.emit()
            QTimer.singleShot(2000, self._restart_app)
        else:
            self._progress_label.setText(
                f"No se pudo completar la instalación automática.\n"
                f"Archivo descargado en: {pkg_path}"
            )
            self._update_btn.setEnabled(True)
            self._postpone_btn.setEnabled(True)
            self._downloading = False

    def _restart_app(self) -> None:
        import sys
        import subprocess
        from loguru import logger
        logger.info("Reiniciando Doremi para aplicar la actualización...")
        try:
            if getattr(sys, 'frozen', False):
                subprocess.Popen([sys.executable] + sys.argv[1:])
            else:
                subprocess.Popen([sys.executable] + sys.argv)
        except Exception as e:
            logger.error(f"Error al reiniciar la aplicación de forma automática: {e}")
        QApplication.quit()

