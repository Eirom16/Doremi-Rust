# src/doremi/ui/dialogs/sudo_dialog.py
"""
Diálogo para solicitar la contraseña de administrador (sudo) en Linux.
Permite validar la contraseña antes de proceder con la instalación
de la actualización de Doremi.
"""
from __future__ import annotations

import asyncio
import subprocess
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QWidget, QLineEdit, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from qasync import asyncSlot

from doremi.ui.design.fonts import AppFont
from doremi.ui.design.icons import Icon
from doremi.ui.widgets.ripple_button import RippleButton


class SudoPasswordDialog(QDialog):
    """
    Diálogo modal premium para ingresar la contraseña de sudo.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Autenticación requerida — Doremi")
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setMinimumWidth(460)
        self._password: str | None = None
        self._build()
        self._center_on_parent()

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

    def _build(self) -> None:
        from doremi.ui.design import tokens
        from PySide6.QtGui import QColor as _QC
        _acc = _QC(tokens.CURRENT.accent)
        _ar, _ag, _ab = _acc.red(), _acc.green(), _acc.blue()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # Panel principal con fondo y bordes estilizados
        self._panel = QFrame()
        panel = self._panel
        panel.setObjectName("sudoPanel")
        panel.setStyleSheet(f"""
            #sudoPanel {{
                background-color: {tokens.CURRENT.bg_elevated};
                border-radius: 20px;
                border: 1px solid rgba({_ar},{_ag},{_ab},0.25);
            }}
        """)

        # Sombra exterior premium
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 120))
        panel.setGraphicsEffect(shadow)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Cabecera: ícono de seguridad + título
        header_row = QHBoxLayout()
        shield_icon = Icon.label("security", size=32, color=tokens.CURRENT.accent)
        
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self._title_lbl = QLabel("Autenticación requerida")
        self._title_lbl.setFont(AppFont.heading(16))
        self._title_lbl.setStyleSheet(f"color: {tokens.CURRENT.text_primary};")
        
        self._subtitle_lbl = QLabel("Instalación de actualización de Doremi")
        self._subtitle_lbl.setFont(AppFont.body(12))
        self._subtitle_lbl.setStyleSheet(f"color: {tokens.CURRENT.text_secondary};")
        
        title_col.addWidget(self._title_lbl)
        title_col.addWidget(self._subtitle_lbl)

        header_row.addWidget(shield_icon)
        header_row.addSpacing(12)
        header_row.addLayout(title_col)
        header_row.addStretch()

        # Botón de cerrar diálogo
        close_btn = RippleButton("", variant="ghost")
        close_btn.setText(Icon.get("close"))
        close_btn.setFont(Icon.font(18))
        close_btn.setFixedSize(36, 36)
        close_btn.clicked.connect(self.reject)
        header_row.addWidget(close_btn)

        layout.addLayout(header_row)

        # Separador horizontal
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: rgba({_ar},{_ag},{_ab},0.10);")
        layout.addWidget(sep)

        # Mensaje del prompt
        self._prompt_lbl = QLabel(
            "Introduce tu contraseña de administrador (sudo) para autorizar la instalación de la nueva versión:"
        )
        self._prompt_lbl.setWordWrap(True)
        self._prompt_lbl.setFont(AppFont.body(13))
        self._prompt_lbl.setStyleSheet(f"color: {tokens.CURRENT.text_secondary};")
        layout.addWidget(self._prompt_lbl)

        # Fila de contraseña con campo de texto y botón de visibilidad
        self.input_container = QWidget()
        input_layout = QHBoxLayout(self.input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Contraseña de administrador")
        self.password_input.setMinimumHeight(42)
        self.password_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {tokens.CURRENT.bg_surface};
                border: 1px solid rgba({_ar},{_ag},{_ab},0.15);
                border-radius: 12px;
                padding: 6px 14px;
                color: {tokens.CURRENT.text_primary};
                font-family: Inter;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 1px solid {tokens.CURRENT.accent};
            }}
        """)
        self.password_input.returnPressed.connect(self._on_accept)
        input_layout.addWidget(self.password_input)

        # Botón para alternar visibilidad de contraseña
        self.toggle_visible_btn = RippleButton("", variant="ghost")
        self.toggle_visible_btn.setText(Icon.get("visibility"))
        self.toggle_visible_btn.setFont(Icon.font(18))
        self.toggle_visible_btn.setFixedSize(40, 40)
        self.toggle_visible_btn.clicked.connect(self._toggle_password_visibility)
        input_layout.addWidget(self.toggle_visible_btn)

        layout.addWidget(self.input_container)

        # Etiqueta de error oculta por defecto
        self.error_lbl = QLabel("")
        self.error_lbl.setWordWrap(True)
        self.error_lbl.setFont(AppFont.label(12))
        self.error_lbl.setStyleSheet(f"color: {tokens.CURRENT.error};")
        self.error_lbl.setVisible(False)
        layout.addWidget(self.error_lbl)

        # Botones de Acción (Confirmar / Cancelar)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.cancel_btn = RippleButton("Cancelar", variant="secondary")
        self.cancel_btn.clicked.connect(self.reject)

        self.confirm_btn = RippleButton("Confirmar e Instalar", variant="primary")
        self.confirm_btn.setFont(AppFont.body(14))
        self.confirm_btn.setMinimumHeight(44)
        self.confirm_btn.clicked.connect(self._on_accept)

        btn_row.addStretch()
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.confirm_btn)
        layout.addLayout(btn_row)

        root.addWidget(panel)

    def _toggle_password_visibility(self) -> None:
        if self.password_input.echoMode() == QLineEdit.EchoMode.Password:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_visible_btn.setText(Icon.get("visibility_off"))
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_visible_btn.setText(Icon.get("visibility"))

    @asyncSlot()
    async def _on_accept(self) -> None:
        password = self.password_input.text()
        if not password:
            self.error_lbl.setText("La contraseña no puede estar vacía.")
            self.error_lbl.setVisible(True)
            return

        self.error_lbl.setVisible(False)
        self.confirm_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.password_input.setEnabled(False)
        self.confirm_btn.setText("Verificando...")

        # Validamos usando el event loop en un executor para no congelar la UI de Qt
        loop = asyncio.get_running_loop()
        is_valid = await loop.run_in_executor(None, self._validate_password, password)

        if is_valid:
            self._password = password
            self.accept()
        else:
            self.error_lbl.setText("Contraseña incorrecta. Inténtalo de nuevo.")
            self.error_lbl.setVisible(True)
            self.confirm_btn.setEnabled(True)
            self.cancel_btn.setEnabled(True)
            self.password_input.setEnabled(True)
            self.password_input.clear()
            self.password_input.setFocus()
            self.confirm_btn.setText("Confirmar e Instalar")

    def _validate_password(self, password: str) -> bool:
        """
        Valida si la contraseña es correcta mediante una llamada sudo rápida y no destructiva.
        """
        try:
            proc = subprocess.Popen(
                ["sudo", "-S", "-k", "true"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            _, _ = proc.communicate(input=password + "\n", timeout=5)
            return proc.returncode == 0
        except Exception:
            return False

    def get_password(self) -> str | None:
        """
        Devuelve la contraseña ingresada y validada.
        """
        return self._password
