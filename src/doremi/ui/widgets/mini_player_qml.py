from __future__ import annotations

import asyncio
from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtWidgets import QApplication

from doremi.audio.player import PlayerState
from doremi.utils.image_cache import ImageCache
from doremi.utils.time_utils import format_duration_short
from doremi.ui.theme_bridge import theme_bridge
from doremi.ui.viewmodels.mini_player_vm import MiniPlayerViewModel

_image_cache = ImageCache()


class _ExpandButtonShim:
    """Compat shim: el controller escribe el icono del botón expand vía
    `mini_player.btn_expand.setText(...)`; traducimos el glyph a estado."""

    def __init__(self, vm: MiniPlayerViewModel) -> None:
        self._vm = vm

    def setText(self, glyph: str) -> None:
        from doremi.ui.design.icons import Icon
        self._vm.set_expand_less(glyph == Icon.get("expand_less"))


class MiniPlayerQml(QObject):
    """Mini-player presenter. MainShell.qml owns its rendering.
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

        self._vm = MiniPlayerViewModel(QApplication.instance())
        self.btn_expand = _ExpandButtonShim(self._vm)

        self._load_ok = True

        self._vm.prev_requested.connect(self.on_prev)
        self._vm.play_pause_requested.connect(self.on_play_pause)
        self._vm.next_requested.connect(self.on_next)
        self._vm.expand_requested.connect(self.on_expand)
        self._vm.artist_clicked.connect(self.artist_clicked)
        self._vm.seek_fraction.connect(self._on_seek_fraction)

    @property
    def is_ok(self) -> bool:
        return self._load_ok

    def show_animated(self) -> None:
        if self._is_visible:
            return
        self._is_visible = True
        theme_bridge().set_mini_player_visible(True)

    def set_shell_managed(self) -> None:
        """Keep this compatibility presenter out of the visible widget tree."""
        return None

    def show(self) -> None:
        theme_bridge().set_mini_player_visible(self._is_visible)

    def hide(self) -> None:
        theme_bridge().set_mini_player_visible(False)

    def raise_(self) -> None:
        """Compatibility no-op: z-order belongs to MainShell.qml."""

    def update(self) -> None:
        """Compatibility no-op: ViewModel signals update QML bindings."""

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
