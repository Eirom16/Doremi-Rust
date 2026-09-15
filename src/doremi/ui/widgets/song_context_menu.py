from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from doremi.ui.design.fonts import AppFont
from doremi.ui.design.icons import Icon
from doremi.ui.widgets.glass_panel import GlassPanel


class SongContextMenu(GlassPanel):
    play_next = Signal()
    add_to_queue = Signal()
    add_to_playlist = Signal()
    go_to_artist = Signal()
    go_to_album = Signal()
    copy_link = Signal()
    download = Signal()
    delete_download = Signal()
    remove_from_playlist = Signal()

    def __init__(
        self,
        parent=None,
        is_downloaded: bool = False,
        has_album: bool = False,
        can_remove_from_playlist: bool = False,
    ):
        super().__init__(parent)
        self.is_downloaded = is_downloaded
        self.has_album = has_album
        self.can_remove_from_playlist = can_remove_from_playlist
        self.setMinimumWidth(250)
        self._build()

    def _build(self) -> None:
        layout = self.layout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)

        actions = [
            ("play_arrow", "Reproducir a continuacion", "play_next"),
            ("queue_music", "Anadir a la cola", "add_to_queue"),
            ("playlist_add", "Anadir a playlist", "add_to_playlist"),
            ("person", "Ir a artista", "go_to_artist"),
            ("link", "Copiar enlace", "copy_link"),
            None,
        ]
        if self.has_album:
            actions.insert(4, ("album", "Ir a album", "go_to_album"))
        
        if self.is_downloaded:
            actions.append(("delete", "Borrar descarga", "delete_download"))
        else:
            actions.append(("download", "Descargar", "download"))

        if self.can_remove_from_playlist:
            actions.append(("playlist_remove", "Quitar de playlist", "remove_from_playlist"))

        for action in actions:
            if action is None:
                from doremi.ui.design import tokens
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setStyleSheet(f"background-color: {tokens.CURRENT.border}; max-height: 1px; margin: 4px 8px;")
                layout.addWidget(sep)
                continue
            icon_name, label, signal_name = action
            layout.addWidget(self._action_button(icon_name, label, signal_name))

    def _action_button(self, icon_name: str, label: str, signal_name: str) -> QPushButton:
        from doremi.ui.design import tokens
        from PySide6.QtGui import QColor
        
        accent_c = QColor(tokens.CURRENT.accent)
        ar, ag, ab = accent_c.red(), accent_c.green(), accent_c.blue()
        
        err_c = QColor(tokens.CURRENT.error)
        er, eg, eb = err_c.red(), err_c.green(), err_c.blue()

        button = QPushButton()
        button.setFixedHeight(40)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        
        if icon_name == "delete":
            button.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    border-radius: 10px;
                    text-align: left;
                    padding: 0;
                }}
                QPushButton:hover {{
                    background: rgba({er}, {eg}, {eb}, 0.15);
                }}
            """)
        else:
            button.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    border-radius: 10px;
                    text-align: left;
                    padding: 0;
                }}
                QPushButton:hover {{
                    background: rgba({ar}, {ag}, {ab}, 0.10);
                }}
            """)
            
        row = QHBoxLayout(button)
        row.setContentsMargins(10, 0, 10, 0)
        row.setSpacing(12)
        
        text = QLabel(label)
        text.setFont(AppFont.body(13))
        
        if icon_name == "delete":
            icon = Icon.label(icon_name, 16, tokens.CURRENT.error)
            text.setStyleSheet(f"color: {tokens.CURRENT.error}; background: transparent;")
        else:
            icon = Icon.label(icon_name, 16, tokens.CURRENT.text_secondary)
            text.setStyleSheet(f" background: transparent;")
            
        icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        text.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row.addWidget(icon)
        row.addWidget(text)
        row.addStretch()

        signal = getattr(self, signal_name)
        button.clicked.connect(lambda checked=False, sig=signal: (sig.emit(), self.dismiss()))
        return button
