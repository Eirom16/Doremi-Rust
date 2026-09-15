from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Slot


class SystemTray(QSystemTrayIcon):

    def __init__(self, parent, on_show, on_play_pause, on_prev, on_next, on_quit):
        super().__init__(parent)
        self.on_show = on_show
        self.on_play_pause = on_play_pause
        self.on_prev = on_prev
        self.on_next = on_next
        self.on_quit = on_quit
        self._title = ""
        self._artist = ""
        self._is_playing = False
        
        # Load own application icon from assets if available
        from doremi.config.paths import AppDirs
        icon_path = AppDirs.root / "assets" / "icon.png"
        if icon_path.exists():
            self.setIcon(QIcon(str(icon_path)))
        else:
            self.setIcon(QIcon.fromTheme("media-playback-start"))
            
        self.setToolTip("Doremi")
        self._build_menu()
        self.activated.connect(self._on_activated)

    def _build_menu(self):
        menu = QMenu()
        
        show_action = QAction("Mostrar Doremi", menu)
        show_action.triggered.connect(self.on_show)
        menu.addAction(show_action)
        
        menu.addSeparator()
        
        play_pause_action = QAction("Reproducir/Pausar", menu)
        play_pause_action.triggered.connect(self.on_play_pause)
        menu.addAction(play_pause_action)

        prev_action = QAction("Anterior", menu)
        prev_action.triggered.connect(self.on_prev)
        menu.addAction(prev_action)
        
        next_action = QAction("Siguiente", menu)
        next_action.triggered.connect(self.on_next)
        menu.addAction(next_action)
        
        menu.addSeparator()
        
        quit_action = QAction("Salir", menu)
        quit_action.triggered.connect(self.on_quit)
        menu.addAction(quit_action)
        
        self.setContextMenu(menu)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            parent = self.parent()
            if parent:
                if parent.isVisible() and not parent.isMinimized():
                    parent.hide()
                else:
                    self.on_show()

    @Slot()
    def update_play_state(self, is_playing: bool):
        self._is_playing = is_playing
        self._update_tooltip()

    def update_track_info(self, title: str, artist: str) -> None:
        self._title = title
        self._artist = artist
        self._update_tooltip()

    def _update_tooltip(self) -> None:
        state_text = "Reproduciendo" if self._is_playing else "Pausado"
        if self._title:
            track = f"{self._title} - {self._artist}" if self._artist else self._title
            self.setToolTip(f"Doremi - {state_text}\n{track}")
        else:
            self.setToolTip(f"Doremi - {state_text}")
