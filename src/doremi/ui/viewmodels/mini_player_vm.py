from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot


class MiniPlayerViewModel(QObject):
    """Puente Python → QML para el mini-player (isla QML).

    Re-emite las mismas intenciones que MiniPlayerWidget (on_prev,
    on_play_pause, on_next, on_seek, on_expand, artist_clicked) para que
    el wrapper QML pueda re-exponerlas con las mismas firmas.
    """

    prev_requested = Signal()
    play_pause_requested = Signal()
    next_requested = Signal()
    seek_fraction = Signal(float)       # 0.0-1.0; el wrapper convierte a ms
    expand_requested = Signal()
    artist_clicked = Signal(str)

    _p_title_changed = Signal()
    _p_artist_changed = Signal()
    _p_artwork_changed = Signal()
    _p_playing_changed = Signal()
    _p_loading_changed = Signal()
    _p_progress_changed = Signal()
    _p_position_text_changed = Signal()
    _p_duration_text_changed = Signal()
    _p_expand_less_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._title = "Sin reproduccion"
        self._artist = ""
        self._artwork = ""
        self._playing = False
        self._loading = False
        self._progress = 0.0
        self._position_text = "0:00"
        self._duration_text = "0:00"
        self._expand_less = True

    # ── Properties para QML ──────────────────────────────────────────────

    @Property(str, notify=_p_title_changed)
    def title(self) -> str:
        return self._title

    def set_title(self, value: str) -> None:
        if self._title != value:
            self._title = value
            self._p_title_changed.emit()

    @Property(str, notify=_p_artist_changed)
    def artist(self) -> str:
        return self._artist

    def set_artist(self, value: str) -> None:
        if self._artist != value:
            self._artist = value
            self._p_artist_changed.emit()

    @Property(str, notify=_p_artwork_changed)
    def artwork(self) -> str:
        return self._artwork

    def set_artwork(self, value: str) -> None:
        if self._artwork != value:
            self._artwork = value
            self._p_artwork_changed.emit()

    @Property(bool, notify=_p_playing_changed)
    def playing(self) -> bool:
        return self._playing

    def set_playing(self, value: bool) -> None:
        if self._playing != value:
            self._playing = value
            self._p_playing_changed.emit()

    @Property(bool, notify=_p_loading_changed)
    def loading(self) -> bool:
        return self._loading

    def set_loading(self, value: bool) -> None:
        if self._loading != value:
            self._loading = value
            self._p_loading_changed.emit()

    @Property(float, notify=_p_progress_changed)
    def progress(self) -> float:
        return self._progress

    def set_progress(self, value: float) -> None:
        if abs(self._progress - value) > 0.0005:
            self._progress = value
            self._p_progress_changed.emit()

    @Property(str, notify=_p_position_text_changed)
    def positionText(self) -> str:
        return self._position_text

    def set_position_text(self, value: str) -> None:
        if self._position_text != value:
            self._position_text = value
            self._p_position_text_changed.emit()

    @Property(str, notify=_p_duration_text_changed)
    def durationText(self) -> str:
        return self._duration_text

    def set_duration_text(self, value: str) -> None:
        if self._duration_text != value:
            self._duration_text = value
            self._p_duration_text_changed.emit()

    @Property(bool, notify=_p_expand_less_changed)
    def expandLess(self) -> bool:
        """True → chevron hacia abajo (colapsar); False → hacia arriba."""
        return self._expand_less

    def set_expand_less(self, value: bool) -> None:
        if self._expand_less != value:
            self._expand_less = value
            self._p_expand_less_changed.emit()

    # ── Slots llamados desde QML ─────────────────────────────────────────

    @Slot()
    def emit_prev(self) -> None:
        self.prev_requested.emit()

    @Slot()
    def emit_play_pause(self) -> None:
        self.play_pause_requested.emit()

    @Slot()
    def emit_next(self) -> None:
        self.next_requested.emit()

    @Slot(float)
    def emit_seek(self, fraction: float) -> None:
        self.seek_fraction.emit(max(0.0, min(1.0, fraction)))

    @Slot()
    def emit_expand(self) -> None:
        self.expand_requested.emit()

    @Slot(str)
    def emit_artist_clicked(self, name: str) -> None:
        if name:
            self.artist_clicked.emit(name)
