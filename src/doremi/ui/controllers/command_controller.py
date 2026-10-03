"""Small command registry shared by the palette and desktop shortcuts."""
import unicodedata
from urllib.parse import urlencode

from PySide6.QtCore import QObject, Property, Signal, Slot


SHORTCUTS = [
    ("Espacio", "Reproducir / pausar"), ("Ctrl+K", "Paleta de comandos"),
    ("Ctrl+F", "Buscar"), ("Ctrl+→ / Ctrl+←", "Siguiente / anterior"),
    ("L", "Me gusta de la canción actual"), ("Ctrl+P", "Reproducción actual"),
]


def normalized(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))


class CommandController(QObject):
    changed = Signal()
    invoked = Signal()

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self._query = ""
        self._commands = {}
        for route, title in [("home", "Inicio"), ("library", "Biblioteca"), ("downloads", "Descargas"), ("history", "Historial"), ("stats", "Estadísticas"), ("settings", "Ajustes"), ("now_playing", "Reproducción actual")]:
            self.register(route, f"Ir a {title}", lambda r=route: window._navigate_to(r))
        self.register("search", "Buscar canción", window.search_bar.focus_search)
        self.register("play", "Reproducir / pausar", window._on_play_pause)
        self.register("next", "Siguiente canción", window._on_next)
        self.register("previous", "Canción anterior", window._on_prev)
        self.register("like", "Me gusta de la canción actual", window.now_playing_screen._vm.toggle_like_current)
        self.register("shuffle", "Activar / desactivar Shuffle", window.now_playing_screen._vm.shuffle_toggled.emit)
        self.register("repeat", "Cambiar Repeat", window.now_playing_screen._vm.repeat_cycled.emit)
        self.register("sleep30", "Temporizador 30 min", self.sleep30)
        self.register("theme", "Cambiar tema", self.cycle_theme)

    def register(self, key, label, callback):
        self._commands[key] = (label, callback)

    @Property("QVariantList", notify=changed)
    def results(self):
        query = normalized(self._query.lstrip("> "))
        entries = [dict(id=k, title=label) for k, (label, _) in self._commands.items() if query in normalized(label)]
        for item in self.window.sidebar.playlists:
            if query in normalized(item["title"]):
                entries.append(dict(id="open:" + item["navigate"], title="Abrir " + item["title"]))
        if query:
            entries.append(dict(id="query", title="Buscar: " + self._query.lstrip("> ")))
        return entries[:20]

    @Slot(str)
    def search(self, query):
        self._query = query
        self.changed.emit()

    @Slot(str)
    def execute(self, key):
        if key in self._commands:
            self._commands[key][1]()
        elif key == "query" and self._query.strip():
            self.window._navigate_to("search?" + urlencode({"query": self._query.lstrip("> ")}))
        elif key.startswith("open:") and any(key[5:] == p["navigate"] for p in self.window.sidebar.playlists):
            self.window._navigate_to(key[5:])
        else:
            return
        self.invoked.emit()

    def sleep30(self):
        self.window.settings.player.sleep_timer_minutes = 30
        self.window.settings_controller.on_settings_changed(self.window.settings)
        self.window.show_notification("Temporizador: 30 minutos", "success")

    def cycle_theme(self):
        modes = ("dark", "light", "system")
        settings = self.window.settings
        current = settings.appearance.theme_mode
        settings.appearance.theme_mode = modes[(modes.index(current) + 1) % len(modes)] if current in modes else "dark"
        self.window.settings_controller.on_settings_changed(settings)
