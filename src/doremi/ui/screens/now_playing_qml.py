from __future__ import annotations

import asyncio
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
from loguru import logger

from doremi.audio.player import PlayerState
from doremi.ui.theme_bridge import theme_bridge
from doremi.ui.viewmodels.now_playing_vm import NowPlayingViewModel

QML_DIR = Path(__file__).resolve().parent.parent / "qml"


class QueueTabShim(QObject):
    """Sustituto ligero de QueuePanel para la isla QML.

    Mantiene compatibles los connect de MainWindow
    (`now_playing_screen.queue_tab.<señal>`) y el método `set_queue`.
    """

    artist_clicked = Signal(str)
    album_clicked = Signal(str)
    like_requested = Signal(str, object)
    download_requested = Signal(str, str, str, str)
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    add_to_playlist_requested = Signal(str, str)
    delete_download_requested = Signal(str)
    queue_move_requested = Signal(int, int)

    def set_queue(self, items, liked_ids=None) -> None:
        if self._vm is not None:
            self._vm.set_queue(list(items), set(liked_ids or set()))


class NowPlayingScreenQml(QWidget):
    """Isla QML: Now Playing como QQuickWidget.

    Drop-in replacement de NowPlayingScreen (QtWidgets): mismas señales,
    mismo constructor, misma API pública (update_track_info, update_state,
    update_position, set_lyrics_loading, set_lyrics, set_related,
    set_liked_state, update_shuffle_repeat_state, update_lyrics_style).
    """

    _qml_island = True  # fade_stack.py: sin cross-fade

    download_requested = Signal(str, str, str, str)
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    like_requested = Signal(str, object)
    add_to_playlist_requested = Signal(str, str)
    delete_download_requested = Signal(str)
    artist_clicked = Signal(str)
    album_clicked = Signal(str)

    def __init__(self, player, queue, yt_client, play_queue_item_cb, settings=None, on_back=None):
        super().__init__()
        self.player = player
        self.queue = queue
        self.yt = yt_client
        self.on_back = on_back
        self.settings = settings
        self._play_queue_item_cb = play_queue_item_cb
        self.setAutoFillBackground(False)

        self._vm = NowPlayingViewModel(QApplication.instance())
        self._apply_lyrics_style()

        # Shuffle/repeat iniciales
        try:
            from doremi.audio.queue import RepeatMode
            mode = queue.repeat_mode
            repeat = {RepeatMode.OFF: "off", RepeatMode.ALL: "all", RepeatMode.ONE: "one"}.get(mode, "off")
        except Exception:
            repeat = "off"
        self._vm.set_shuffle_repeat(bool(getattr(queue, "shuffle_enabled", False)), repeat)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._quick = QQuickWidget(self)
        self._quick.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self._quick.setAutoFillBackground(False)
        from PySide6.QtGui import QColor
        self._quick.setClearColor(QColor(0, 0, 0, 0))

        engine = self._quick.engine()
        engine.addImportPath(str(QML_DIR))

        ctx = self._quick.rootContext()
        ctx.setContextProperty("themeBridge", theme_bridge())
        ctx.setContextProperty("vm", self._vm)

        self._quick.setSource(QUrl.fromLocalFile(str(QML_DIR / "NowPlayingScreen.qml")))

        self._load_ok = self._quick.status() == QQuickWidget.Status.Ready
        if not self._load_ok:
            for err in self._quick.errors():
                logger.error(f"QML NowPlayingScreen: {err.toString()}")

        layout.addWidget(self._quick)

        # Shim de la cola (paridad con NowPlayingScreen.queue_tab)
        self.queue_tab = QueueTabShim(self)
        self.queue_tab._vm = self._vm

        # Señales de la VM → señales de la pantalla
        self._vm.download_requested.connect(self.download_requested)
        self._vm.play_next_requested.connect(self.play_next_requested)
        self._vm.add_to_queue_requested.connect(self.add_to_queue_requested)
        self._vm.like_requested.connect(self.like_requested)
        self._vm.add_to_playlist_requested.connect(self.add_to_playlist_requested)
        self._vm.delete_download_requested.connect(self.delete_download_requested)
        self._vm.artist_clicked.connect(self.artist_clicked)
        self._vm.album_clicked.connect(self.album_clicked)

        # Y al shim de cola
        self._vm.like_requested.connect(self.queue_tab.like_requested)
        self._vm.artist_clicked.connect(self.queue_tab.artist_clicked)
        self._vm.album_clicked.connect(self.queue_tab.album_clicked)

        # Intenciones de control → MainWindow
        self._vm.toggle_play_requested.connect(self._mw_toggle_play)
        self._vm.prev_requested.connect(self._mw_prev)
        self._vm.next_requested.connect(self._mw_next)
        self._vm.seek_ms_requested.connect(self._mw_seek)
        self._vm.shuffle_toggled.connect(self._mw_shuffle)
        self._vm.repeat_cycled.connect(self._mw_repeat)
        self._vm.minimize_requested.connect(self._mw_back)
        self._vm.queue_play_at.connect(self._mw_play_queue_index)
        self._vm.queue_move_requested.connect(self.queue_tab.queue_move_requested)
        self._vm.copy_link_requested.connect(self._copy_link)
        self._vm.play_related_requested.connect(self._on_related_play)

    @property
    def is_ok(self) -> bool:
        return self._load_ok

    # ── Find MainWindow (paridad con versión widgets) ──────────────────────

    def _find_main_window(self):
        w = self.parent()
        while w:
            if hasattr(w, "_on_play_pause"):
                return w
            w = w.parent() if hasattr(w, "parent") and callable(w.parent) else None
        return None

    def _mw_toggle_play(self) -> None:
        main = self._find_main_window()
        if main:
            main._on_play_pause()

    def _mw_prev(self) -> None:
        main = self._find_main_window()
        if main:
            main._on_prev()

    def _mw_next(self) -> None:
        main = self._find_main_window()
        if main:
            main._on_next()

    def _mw_seek(self, ms: int) -> None:
        main = self._find_main_window()
        if main:
            main._on_seek(ms)

    def _mw_shuffle(self) -> None:
        main = self._find_main_window()
        if main is None:
            return
        is_shuffled = self.queue.toggle_shuffle()
        self._vm.set_shuffle_repeat(is_shuffled, self._vm.repeatMode)
        main.playback_controller._update_queue_panel()
        if hasattr(main, "_persist_queue_playback_settings"):
            main._persist_queue_playback_settings()
        if getattr(main, "mpris", None):
            main.mpris.update_shuffle(is_shuffled)

    def _mw_repeat(self) -> None:
        main = self._find_main_window()
        if main is None:
            return
        self.queue.toggle_repeat()
        self._refresh_repeat_state()
        if hasattr(main, "_persist_queue_playback_settings"):
            main._persist_queue_playback_settings()
        if getattr(main, "mpris", None):
            main.mpris.update_loop_status()

    def _mw_back(self) -> None:
        if self.on_back:
            self.on_back()

    def _mw_play_queue_index(self, index: int) -> None:
        if self._play_queue_item_cb:
            self._play_queue_item_cb(index)

    def _copy_link(self, video_id: str) -> None:
        if not video_id:
            return
        QApplication.clipboard().setText(f"https://music.youtube.com/watch?v={video_id}")
        try:
            from doremi.ui.widgets.toast import ToastNotification
            ToastNotification.show(self.window(), "Enlace copiado", "success")
        except Exception:
            pass

    def _on_related_play(self, video_id, title, artist, duration_ms, thumb) -> None:
        main = self._find_main_window()
        play = getattr(main, "_play_song_sync", None) if main else None
        if play:
            try:
                play(video_id, title, artist, "", duration_ms, thumb)
            except Exception as e:
                logger.error(f"Play error desde isla QML NowPlaying: {e}")

    # ── API pública (llamada por los controllers) ─────────────────────────

    def update_track_info(self, title: str, artist: str, thumbnail_url: str) -> None:
        video_id = getattr(self.player.status, "current_video_id", "") if self.player else ""
        album = ""
        if getattr(self.queue, "current", None):
            album = getattr(self.queue.current, "album", "") or ""
        self._vm.set_track_info(title, artist, thumbnail_url, album=album, video_id=video_id)
        # Marcar el actual en la cola (set_queue ya conoce _video_id)
        if self.queue is not None:
            self._vm.set_queue(list(self.queue.items), set())
        else:
            self._vm.set_queue([], set())

    def update_state(self, status) -> None:
        self._vm.set_playing(status.state == PlayerState.PLAYING)

    def update_position(self, position_ms: int, duration_ms: int) -> None:
        self._vm.set_position(position_ms, duration_ms)

    def set_lyrics_loading(self) -> None:
        self._vm.set_lyrics_loading()

    def set_lyrics(self, lyrics) -> None:
        self._vm.set_lyrics(lyrics)

    def set_related(self, tracks, play_callback) -> None:
        items = []
        for track in (tracks or [])[:12]:
            vid = track.get("videoId", "")
            if not vid:
                continue
            artists = track.get("artists", [])
            artist_names = (
                ", ".join(a.get("name", "") for a in artists if isinstance(a, dict))
                if isinstance(artists, list) else str(artists or "Unknown")
            ) or "Unknown"
            thumbnails = track.get("thumbnail", track.get("thumbnails", []))
            if isinstance(thumbnails, list) and thumbnails:
                thumb = thumbnails[-1].get("url", "")
            elif isinstance(thumbnails, dict):
                thumb = thumbnails.get("url", "")
            else:
                thumb = ""
            duration = track.get("duration", track.get("length", ""))
            items.append({
                "videoId": vid, "title": track.get("title", "Unknown"),
                "artist": artist_names, "duration": str(duration or ""),
                "thumbnail_url": thumb,
            })
        self._vm.set_related(items)

    def set_liked_state(self, liked: bool) -> None:
        self._vm.set_liked(liked)

    def update_shuffle_repeat_state(self) -> None:
        self._refresh_repeat_state()

    def _refresh_repeat_state(self) -> None:
        try:
            from doremi.audio.queue import RepeatMode
            mode = self.queue.repeat_mode
            repeat = {RepeatMode.OFF: "off", RepeatMode.ALL: "all", RepeatMode.ONE: "one"}.get(mode, "off")
        except Exception:
            repeat = "off"
        self._vm.set_shuffle_repeat(bool(getattr(self.queue, "shuffle_enabled", False)), repeat)

    def update_lyrics_style(self) -> None:
        self._apply_lyrics_style()

    def _apply_lyrics_style(self) -> None:
        s = getattr(self.settings, "subtitles", None)
        if s:
            self._vm.set_lyrics_style(
                font_size=s.font_size + 8,
                alignment=s.alignment,
                glow=s.glow_effect,
                auto_scroll=s.auto_scroll,
                delay_ms=s.delay_ms,
            )

    def _update_styles(self) -> None:
        """Llamado por theme_manager; QML se rebindea vía themeBridge (no-op)."""
