from __future__ import annotations

import asyncio
from pathlib import Path

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, Qt, QUrl, Signal
from PySide6.QtGui import QColor
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QApplication
from loguru import logger

from doremi.audio.player import PlayerState
from doremi.utils.image_cache import ImageCache
from doremi.utils.time_utils import format_duration_short
from doremi.ui.theme_bridge import theme_bridge
from doremi.ui.viewmodels.mini_player_vm import MiniPlayerViewModel

QML_DIR = Path(__file__).resolve().parent.parent / "qml"

_image_cache = ImageCache()


class _ExpandButtonShim:
    """Compat shim: el controller escribe el icono del botón expand vía
    `mini_player.btn_expand.setText(...)`; traducimos el glyph a estado."""

    def __init__(self, vm: MiniPlayerViewModel) -> None:
        self._vm = vm

    def setText(self, glyph: str) -> None:
        from doremi.ui.design.icons import Icon
        self._vm.set_expand_less(glyph == Icon.get("expand_less"))


class MiniPlayerQml(QQuickWidget):
    """Isla QML del mini-player. API pública idéntica a MiniPlayerWidget:
    mismas señales (on_expand/on_prev/on_play_pause/on_next/on_seek,
    artist_clicked) y métodos (update_track_info, update_state,
    update_position, show_animated)."""

    _qml_island = True  # fade_stack.py: sin cross-fade

    on_expand = Signal()
    on_prev = Signal()
    on_play_pause = Signal()
    on_next = Signal()
    on_seek = Signal(int)
    artist_clicked = Signal(str)

    def __init__(self, player, queue, on_expand, on_prev, on_play_pause, on_next, on_seek, parent=None):
        super().__init__(parent)
        self.player = player
        self.queue = queue

        self.on_expand.connect(on_expand)
        self.on_prev.connect(on_prev)
        self.on_play_pause.connect(on_play_pause)
        self.on_next.connect(on_next)
        self.on_seek.connect(on_seek)

        self._is_visible = False
        self.setFixedHeight(0)

        # La isla es el propio QQuickWidget: envolverla y recortar el wrapper con
        # setMask() crea una región nativa que algunos compositores interpretan
        # como un agujero en la ventana principal.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, True)
        self.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self.setClearColor(QColor(0, 0, 0, 0))

        self._vm = MiniPlayerViewModel(QApplication.instance())
        self.btn_expand = _ExpandButtonShim(self._vm)

        self.engine().addImportPath(str(QML_DIR))
        ctx = self.rootContext()
        ctx.setContextProperty("themeBridge", theme_bridge())
        ctx.setContextProperty("vm", self._vm)
        self.setSource(QUrl.fromLocalFile(str(QML_DIR / "MiniPlayer.qml")))

        self._load_ok = self.status() == QQuickWidget.Status.Ready
        if not self._load_ok:
            for err in self.errors():
                logger.error(f"QML MiniPlayer: {err.toString()}")

        self._vm.prev_requested.connect(self.on_prev)
        self._vm.play_pause_requested.connect(self.on_play_pause)
        self._vm.next_requested.connect(self.on_next)
        self._vm.expand_requested.connect(self.on_expand)
        self._vm.artist_clicked.connect(self.artist_clicked)
        self._vm.seek_fraction.connect(self._on_seek_fraction)

    @property
    def is_ok(self) -> bool:
        return self._load_ok

    # ── Animación de altura (parity con la versión widgets) ─────────────

    def _get_player_height(self) -> int:
        return self.height()

    def _set_player_height(self, value: int) -> None:
        self.setFixedHeight(value)
        theme_bridge().set_mini_player_visible(value > 0 and self.isVisible())
        positioner = getattr(self.window(), "_position_mini_player", None)
        if callable(positioner):
            positioner()

    player_height = Property(int, _get_player_height, _set_player_height)

    def show_animated(self) -> None:
        if self._is_visible:
            return
        self._is_visible = True
        self._pop_anim = QPropertyAnimation(self, b"player_height", self)
        self._pop_anim.setDuration(600)
        self._pop_anim.setStartValue(0)
        self._pop_anim.setEndValue(88)
        self._pop_anim.setEasingCurve(QEasingCurve.Type.OutExpo)
        self._pop_anim.start()

    # ── API pública (llamada por controllers) ───────────────────────────

    def _on_seek_fraction(self, fraction: float) -> None:
        duration_ms = self.player.status.duration_ms
        if duration_ms > 0:
            self.on_seek.emit(int(fraction * duration_ms))

    def update_track_info(self, title: str, artist: str, thumbnail_url: str) -> None:
        self.show_animated()
        self._vm.set_title(title)
        self._vm.set_artist(artist)
        if thumbnail_url:
            asyncio.ensure_future(self._load_thumbnail(thumbnail_url))
        else:
            self._vm.set_artwork("")

    async def _load_thumbnail(self, url: str) -> None:
        path = await _image_cache.download(url)
        if path:
            self._vm.set_artwork(QUrl.fromLocalFile(str(path)).toString())
        else:
            self._vm.set_artwork("")

    def update_state(self, status) -> None:
        self._vm.set_loading(status.state == PlayerState.LOADING)
        self._vm.set_playing(status.state == PlayerState.PLAYING)

    def update_position(self, position_ms: int, duration_ms: int) -> None:
        if duration_ms > 0:
            self._vm.set_progress(position_ms / duration_ms)
        self._vm.set_position_text(format_duration_short(position_ms))
        self._vm.set_duration_text(format_duration_short(duration_ms))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.update()
        positioner = getattr(self.window(), "_position_mini_player", None)
        if callable(positioner):
            positioner()

    def _update_mini_player_styles(self) -> None:
        self.setClearColor(QColor(0, 0, 0, 0))
