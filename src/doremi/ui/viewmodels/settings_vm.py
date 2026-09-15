from __future__ import annotations

from PySide6.QtCore import (
    QAbstractListModel, Property, QModelIndex, QObject, Qt, QTimer, Signal, Slot,
)

CATEGORIES = [
    {"key": "appearance", "label": "Apariencia", "icon": ""},       # palette
    {"key": "player", "label": "Reproductor", "icon": ""},          # graphic_eq
    {"key": "equalizer", "label": "Ecualizador", "icon": ""},       # equalizer
    {"key": "subtitles", "label": "Letras y Subtítulos", "icon": ""},  # lyrics
    {"key": "accounts", "label": "Cuentas", "icon": ""},            # person
    {"key": "storage", "label": "Almacenamiento", "icon": ""},      # storage
    {"key": "about", "label": "Acerca de", "icon": ""},             # info
]

ACCENT_PRESETS = [
    "#A78BFA", "#60A5FA", "#34D399", "#F472B6",
    "#FB923C", "#FBBF24", "#22D3EE", "#F87171",
]

_SLEEP_OPTIONS = [
    {"text": "Apagado", "value": "0"},
    {"text": "5 minutos", "value": "5"},
    {"text": "15 minutos", "value": "15"},
    {"text": "30 minutos", "value": "30"},
    {"text": "45 minutos", "value": "45"},
    {"text": "60 minutos", "value": "60"},
]


class SettingsRowsModel(QAbstractListModel):
    """Lista plana de filas de la página actual (incluye headers de sección)."""

    TypeRole = Qt.UserRole + 1
    RowIdRole = Qt.UserRole + 2
    LabelRole = Qt.UserRole + 3
    DescRole = Qt.UserRole + 4
    ValueRole = Qt.UserRole + 5
    OptionsRole = Qt.UserRole + 6     # [{text, value}]
    MinRole = Qt.UserRole + 7
    MaxRole = Qt.UserRole + 8
    StepRole = Qt.UserRole + 9
    UnitRole = Qt.UserRole + 10
    EnabledRole = Qt.UserRole + 11
    VariantRole = Qt.UserRole + 12    # primary | secondary | danger
    PasswordRole = Qt.UserRole + 13
    DecimalsRole = Qt.UserRole + 14
    ItemsRole = Qt.UserRole + 15      # color swatches (color type)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[dict] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        if role == self.TypeRole:
            return row.get("type", "")
        if role == self.RowIdRole:
            return row.get("id", "")
        if role == self.LabelRole:
            return row.get("label", "")
        if role == self.DescRole:
            return row.get("desc", "")
        if role == self.ValueRole:
            return row.get("value")
        if role == self.OptionsRole:
            return row.get("options", [])
        if role == self.MinRole:
            return row.get("min", 0)
        if role == self.MaxRole:
            return row.get("max", 100)
        if role == self.StepRole:
            return row.get("step", 1)
        if role == self.UnitRole:
            return row.get("unit", "")
        if role == self.EnabledRole:
            return row.get("enabled", True)
        if role == self.VariantRole:
            return row.get("variant", "secondary")
        if role == self.PasswordRole:
            return row.get("password", False)
        if role == self.DecimalsRole:
            return row.get("decimals", 0)
        if role == self.ItemsRole:
            return row.get("items", [])
        return None

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.TypeRole: b"rowType",
            self.RowIdRole: b"rowId",
            self.LabelRole: b"label",
            self.DescRole: b"desc",
            self.ValueRole: b"value",
            self.OptionsRole: b"options",
            self.MinRole: b"minV",
            self.MaxRole: b"maxV",
            self.StepRole: b"stepV",
            self.UnitRole: b"unitV",
            self.EnabledRole: b"rowEnabled",
            self.VariantRole: b"variant",
            self.PasswordRole: b"password",
            self.DecimalsRole: b"decimals",
            self.ItemsRole: b"items",
        }

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()


class SettingsViewModel(QObject):
    """Puente Python → QML para Ajustes (isla QML).

    Las filas se construyen como datos (schema) a partir de AppSettings y el
    QML las renderiza genéricamente según `rowType`. Efectos especiales
    (idioma, presets EQ, acciones de cuenta/almacenamiento) viven aquí o se
    redirigen al wrapper vía `action_requested` cuando requieren QtWidgets.
    """

    category_changed = Signal()
    rows_changed = Signal()
    settings_changed = Signal()          # → wrapper.on_changed(settings)
    toast_requested = Signal(str, str)   # (mensaje, kind)
    action_requested = Signal(str)       # botones que requieren diálogos/widgets
    eq_bands_changed = Signal()

    def __init__(self, settings, yt_client=None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._yt = yt_client
        self._category = 0
        self._rows = SettingsRowsModel(self)
        self._eq_timer = QTimer(self)
        self._eq_timer.setSingleShot(True)
        self._eq_timer.setInterval(200)
        self._eq_timer.timeout.connect(self.settings_changed.emit)
        self.refresh()

    # ── Properties ─────────────────────────────────────────────────────────

    @Property(QObject, constant=True)
    def rows(self) -> SettingsRowsModel:
        return self._rows

    @Property(int, notify=category_changed)
    def categoryIndex(self) -> int:
        return self._category

    @Property("QVariantList", constant=True)
    def categories(self) -> list:
        return [{"key": c["key"], "label": c["label"], "icon": c["icon"]} for c in CATEGORIES]

    @Property(str, notify=category_changed)
    def currentTitle(self) -> str:
        return CATEGORIES[self._category]["label"]

    @Property("QVariantList", notify=eq_bands_changed)
    def eqBands(self) -> list:
        return list(self._settings.equalizer.bands)

    @Property("QVariantList", constant=True)
    def eqBandLabels(self) -> list:
        from doremi.config.themes import EQ_BAND_LABELS
        return list(EQ_BAND_LABELS)

    @Property(bool, notify=eq_bands_changed)
    def eqEnabled(self) -> bool:
        return self._settings.equalizer.enabled

    # ── Navegación ─────────────────────────────────────────────────────────

    @Slot(int)
    def set_category(self, index: int) -> None:
        if 0 <= index < len(CATEGORIES) and index != self._category:
            self._category = index
            self.refresh()
            self.category_changed.emit()

    # ── Helpers de schema ──────────────────────────────────────────────────

    def _get(self, path: str):
        obj = self._settings
        for part in path.split("."):
            obj = getattr(obj, part, None)
            if obj is None:
                return None
        return obj

    def _set(self, path: str, value) -> None:
        parts = path.split(".")
        obj = self._settings
        for part in parts[:-1]:
            obj = getattr(obj, part)
        setattr(obj, parts[-1], value)

    @staticmethod
    def _section(title: str) -> dict:
        return {"type": "section", "id": f"sec:{title}", "label": title}

    def _toggle(self, path: str, label: str, desc: str) -> dict:
        return {"type": "toggle", "id": path, "label": label, "desc": desc,
                "value": bool(self._get(path))}

    def _combo(self, path: str, label: str, desc: str, options: list[dict]) -> dict:
        return {"type": "combo", "id": path, "label": label, "desc": desc,
                "options": options, "value": str(self._get(path))}

    def _slider(self, path: str, label: str, desc: str, mn: int, mx: int,
                unit: str, enabled: bool = True) -> dict:
        return {"type": "slider", "id": path, "label": label, "desc": desc,
                "value": int(self._get(path) or 0), "min": mn, "max": mx,
                "unit": unit, "enabled": enabled}

    def _stepper(self, path: str, label: str, desc: str, step: float, unit: str,
                 mn: float, mx: float, decimals: int = 0) -> dict:
        return {"type": "stepper", "id": path, "label": label, "desc": desc,
                "value": self._get(path), "min": mn, "max": mx, "step": step,
                "unit": unit, "decimals": decimals}

    def _color(self, path: str, label: str, desc: str) -> dict:
        return {"type": "color", "id": path, "label": label, "desc": desc,
                "value": self._get(path), "items": ACCENT_PRESETS}

    def _button(self, action: str, label: str, desc: str, variant: str = "secondary") -> dict:
        return {"type": "button", "id": action, "label": label, "desc": desc,
                "variant": variant}

    def _info(self, label: str, desc: str, value: str) -> dict:
        return {"type": "info", "id": f"info:{label}", "label": label, "desc": desc,
                "value": value}

    def _input(self, path: str, label: str, desc: str, password: bool = False) -> dict:
        return {"type": "input", "id": path, "label": label, "desc": desc,
                "value": self._get(path) or "", "password": password}

    # ── Páginas ────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        key = CATEGORIES[self._category]["key"]
        builder = getattr(self, f"_page_{key}")
        self._rows.set_rows(builder())
        self.rows_changed.emit()

    def _page_appearance(self) -> list[dict]:
        from doremi.utils.i18n import _
        return [
            self._section(_("Tema")),
            self._color("appearance.accent_color", _("Color de acento"),
                        _("Color principal de la interfaz")),
            self._toggle("appearance.use_dynamic_color", _("Color dinámico"),
                         _("Cambia el acento según el artwork actual")),
            self._combo("appearance.theme_mode", _("Tema"), _("Modo visual preferido"),
                        [{"text": "dark", "value": "dark"},
                         {"text": "light", "value": "light"},
                         {"text": "system", "value": "system"}]),
            self._section(_("Interfaz")),
            self._toggle("appearance.compact_sidebar", _("Barra lateral compacta"),
                         _("Reduce la barra lateral a iconos")),
            self._toggle("appearance.show_artwork_blur_bg", _("Brillo de carátula en fondo"),
                         _("Usa el artwork como atmósfera del reproductor")),
            self._combo("language", _("Idioma"), _("Idioma de la aplicación"),
                        [{"text": "Español", "value": "es"}, {"text": "English", "value": "en"}]),
        ]

    def _page_player(self) -> list[dict]:
        crossfade_on = self._settings.player.crossfade_enabled
        return [
            self._section("Audio"),
            self._slider("player.volume", "Volumen", "Volumen inicial del reproductor",
                         0, 200, "%"),
            self._toggle("player.normalize_audio", "Normalizar volumen",
                         "Iguala el volumen entre canciones"),
            self._toggle("player.skip_silence", "Saltar silencios",
                         "Omite fragmentos silenciosos"),
            self._toggle("player.crossfade_enabled", "Crossfade",
                         "Transición suave entre canciones"),
            self._slider("player.crossfade_duration_sec", "Duración de Crossfade",
                         "Tiempo de transición entre canciones", 1, 15, " s",
                         enabled=crossfade_on),
            self._toggle("player.gapless_playback", "Reproducción sin gaps",
                         "Evita pausas entre canciones compatibles"),
            self._toggle("player.resume_on_startup", "Reanudar al iniciar",
                         "Continúa la última sesión al abrir la app"),
            self._toggle("player.stop_on_close", "Parar al cerrar",
                         "Detiene la reproducción al cerrar Doremi"),
            self._toggle("player.minimize_to_tray", "Minimizar al cerrar",
                         "Minimiza Doremi al área de notificaciones al cerrar"),
            self._combo("player.sleep_timer_minutes", "Temporizador de apagado",
                        "Pausa la música después del tiempo seleccionado", _SLEEP_OPTIONS),
        ]

    def _page_equalizer(self) -> list[dict]:
        from doremi.config.themes import EQ_PRESETS
        return [
            self._section("Control"),
            self._toggle("equalizer.enabled", "Activado",
                         "Aplica el ecualizador de 10 bandas"),
            self._combo("equalizer.preset_name", "Preset", "Curva base para ajustar rápido",
                        [{"text": k, "value": k} for k in EQ_PRESETS.keys()]),
            self._section("Ganancia"),
            {"type": "preamp", "id": "equalizer.preamp", "label": "Preamp",
             "desc": "Nivel general antes de las bandas",
             "value": int(self._settings.equalizer.preamp * 10), "min": -120,
             "max": 120, "unit": " dB"},
            {"type": "eq_bands", "id": "equalizer.bands", "label": "Bandas",
             "desc": ""},
            self._button("equalizer.reset", "Reiniciar", "Volver a la curva plana",
                         variant="secondary"),
        ]

    def _page_subtitles(self) -> list[dict]:
        s = self._settings.subtitles
        return [
            self._section("Visualización"),
            self._combo("subtitles.alignment", "Alineación del texto",
                        "Alinea las letras horizontalmente",
                        [{"text": "Centrado", "value": "center"},
                         {"text": "Izquierda", "value": "left"},
                         {"text": "Derecha", "value": "right"}]),
            self._stepper("subtitles.font_size", "Tamaño de letra",
                          "Tamaño de la fuente de las letras", 1, " pt", 10, 36),
            {"type": "stepper", "id": "subtitles.line_spacing", "label": "Espacio entre líneas",
             "desc": "Ajusta la separación entre párrafos de letra", "value": s.line_spacing,
             "min": 1.0, "max": 3.0, "step": 0.1, "unit": "x", "decimals": 1},
            self._section("Sincronización"),
            self._stepper("subtitles.delay_ms", "Retraso de letras",
                          "Retrasa/adelanta manualmente las letras respecto al audio",
                          100, " ms", -5000, 5000),
            self._toggle("subtitles.auto_scroll", "Auto-desplazamiento",
                         "Desplaza verticalmente de manera automática al cantar"),
            self._section("Efectos"),
            self._combo("subtitles.animation_style", "Efecto de Desplazamiento",
                        "Estilo de la animación al pasar de línea",
                        [{"text": "Ninguno", "value": "none"},
                         {"text": "Desvanecer", "value": "fade"},
                         {"text": "Brillar", "value": "glow"},
                         {"text": "Slide", "value": "slide"},
                         {"text": "Karaoke", "value": "karaoke"}]),
            self._toggle("subtitles.glow_effect", "Efecto de Brillo Activo",
                         "Resalta e ilumina la línea que se está cantando"),
        ]

    def _page_accounts(self) -> list[dict]:
        rows: list[dict] = [self._section("YouTube Music")]
        if self._yt and self._yt.is_authenticated:
            rows.append(self._button("accounts.logout", "Cerrar sesión",
                                     "Cuenta conectada a YouTube Music", variant="danger"))
        else:
            rows.append(self._button("accounts.login", "Conectar cuenta",
                                     "Autoriza YouTube Music en el navegador",
                                     variant="primary"))

        rows.append(self._section("Last.fm"))
        rows.append(self._toggle("integrations.lastfm_enabled", "Scrobbling",
                                 "Registra las canciones escuchadas en Last.fm"))
        if self._settings.integrations.lastfm_enabled:
            if self._settings.integrations.lastfm_session_key:
                rows.append(self._button("accounts.lastfm_disconnect", "Desconectar",
                                         "Sesión de Last.fm activa y autorizada",
                                         variant="danger"))
            else:
                rows.append(self._input("integrations.lastfm_api_key", "API Key",
                                        "Credencial pública de Last.fm"))
                rows.append(self._input("integrations.lastfm_api_secret", "API Secret",
                                        "Credencial privada de Last.fm", password=True))
                rows.append(self._input("integrations.lastfm_username", "Usuario",
                                        "Tu nombre de usuario en Last.fm"))
                rows.append(self._input("integrations.lastfm_password", "Contraseña",
                                        "Tu contraseña de Last.fm", password=True))
                rows.append(self._button("accounts.lastfm_auth", "Autenticar en Last.fm",
                                         "Conecta e inicia sesión de forma segura",
                                         variant="primary"))

        rows.append(self._section("Discord"))
        rows.append(self._toggle("integrations.discord_rpc_enabled", "Rich Presence",
                                 "Muestra lo que escuchas en tu perfil"))
        return rows

    def _page_storage(self) -> list[dict]:
        from doremi.config.paths import AppDirs
        return [
            self._section("Uso"),
            self._info("Base de datos", "Historial y biblioteca local",
                       self._dir_size(AppDirs.database)),
            self._info("Cache", "Imágenes y datos temporales",
                       self._dir_size(AppDirs.cache)),
            self._info("Descargas", "Canciones guardadas offline",
                       self._dir_size(AppDirs.downloads)),
            self._section("Limpieza"),
            self._button("storage.clear_cache", "Limpiar cache", "Elimina archivos temporales"),
            self._button("storage.clear_downloads", "Eliminar descargas",
                         "Elimina los archivos descargados", variant="danger"),
            self._section("Copia de seguridad"),
            self._button("storage.export_backup", "Exportar copia",
                         "Exporta tu biblioteca y configuraciones en un zip", variant="primary"),
            self._button("storage.import_backup", "Restaurar copia",
                         "Restaura tu biblioteca y configuraciones desde un zip"),
        ]

    @staticmethod
    def _dir_size(path) -> str:
        try:
            if not path.exists():
                return "0 MB"
            total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            return f"{total / (1024 * 1024):.1f} MB"
        except Exception:
            return "0 MB"

    def _page_about(self) -> list[dict]:
        try:
            from doremi.utils.updater import CURRENT_VERSION
            version = CURRENT_VERSION
        except Exception:
            version = "?"
        from doremi.changelog import CURRENT_CHANGELOG, CURRENT_CHANGELOG_SUMMARY
        rows: list[dict] = [
            self._info("Doremi", "Cliente de música para YouTube Music",
                       f"Versión {version}"),
            self._section("Changelog"),
        ]
        rows.append(self._info("Últimos cambios", CURRENT_CHANGELOG_SUMMARY, ""))
        for section_title, items in CURRENT_CHANGELOG:
            rows.append(self._section(section_title))
            for item in items:
                rows.append(self._info("", item, ""))
        rows.extend([
            self._section("Actualizaciones"),
            self._button("about.check_updates", "Buscar actualizaciones",
                         "Comprueba si hay una versión nueva"),
            self._button("about.open_github", "Ver proyecto",
                         "Abre el repositorio en GitHub", variant="primary"),
        ])
        return rows

    # ── Slots de QML ───────────────────────────────────────────────────────

    @Slot(str, "QVariant")
    def set_value(self, row_id: str, value) -> None:
        """Actualiza un valor de settings; aplica efectos especiales."""
        s = self._settings
        if row_id == "language":
            s.language = str(value)
            try:
                from doremi.utils.i18n import set_language
                set_language(str(value))
            except Exception:
                pass
            self.settings_changed.emit()
            self.toast_requested.emit(
                "Idioma cambiado. Reinicia la aplicación para aplicarlo en toda la interfaz.",
                "success")
            return
        if row_id == "equalizer.preset_name":
            from doremi.config.themes import EQ_PRESETS
            preamp, bands = EQ_PRESETS.get(str(value), (0.0, [0.0] * 10))
            eq = s.equalizer
            eq.preset_name = str(value)
            eq.preamp = preamp
            eq.bands = list(bands)
            self.eq_bands_changed.emit()
            self.refresh()
            self.settings_changed.emit()
            return
        if row_id == "equalizer.preamp":
            s.equalizer.preamp = float(value) / 10.0
            self._eq_timer.start()  # debounce (aplicar a VLC es pesado)
            return

        # Genérico: ruta 'seccion.atributo' o 'atributo' de primer nivel
        target = value
        if isinstance(value, bool):
            target = value
        else:
            current = self._get(row_id)
            if isinstance(current, bool):
                target = bool(value)
            elif isinstance(current, int):
                try:
                    target = int(float(value))
                except (TypeError, ValueError):
                    return
            elif isinstance(current, float):
                try:
                    target = float(value)
                except (TypeError, ValueError):
                    return
            elif current is None:
                target = value
        self._set(row_id, target)
        self.settings_changed.emit()
        if row_id.startswith("equalizer."):
            self.eq_bands_changed.emit()
        # Refrescar página cuando se requiere (p.ej. crossfade activa su slider)
        if row_id in ("player.crossfade_enabled", "integrations.lastfm_enabled"):
            self.refresh()

    @Slot(int, float)
    def set_eq_band(self, index: int, db: float) -> None:
        bands = list(self._settings.equalizer.bands)
        while len(bands) < 10:
            bands.append(0.0)
        if 0 <= index < 10:
            bands[index] = round(db, 1)
            self._settings.equalizer.bands = bands
            self.eq_bands_changed.emit()
            self._eq_timer.start()

    @Slot(str)
    def action(self, action_id: str) -> None:
        if action_id == "equalizer.reset":
            self.set_value("equalizer.preset_name", "Flat")
            return
        self.action_requested.emit(action_id)
