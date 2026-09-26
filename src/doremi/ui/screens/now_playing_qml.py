from __future__ import annotations

import asyncio
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtWidgets import QApplication
from loguru import logger

from doremi.audio.player import PlayerState
from doremi.ui.viewmodels.now_playing_vm import NowPlayingViewModel
from doremi.utils.image_cache import ImageCache
from doremi.utils.i18n import _

QML_DIR = Path(__file__).resolve().parent.parent / "qml"
_image_cache = ImageCache()


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


class NowPlayingScreenQml(QObject):
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
        self._video_task: asyncio.Task | None = None
        self._active = False
        self._video_request_generation = 0
        self._video_player = None
        self._video_audio = None

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

        self.qml_source = QUrl.fromLocalFile(str(QML_DIR / "NowPlayingScreen.qml"))
        self._load_ok = True

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

        # El shim conserva su API, pero las intenciones salen sólo por la pantalla.

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
        self._vm.details_requested.connect(self._load_track_details)
        self._vm.video_requested.connect(self._show_video_clip)
        self._vm.video_closed_requested.connect(self._close_video_clip)
        self._vm.video_changed.connect(self._sync_video_player)
        self._vm.playing_changed.connect(self._sync_video_playback)
        self._vm.position_changed.connect(self._sync_video_position)

    @property
    def is_ok(self) -> bool:
        return self._load_ok

    def set_active(self, active: bool) -> None:
        self._active = bool(active)
        if self._active:
            self._sync_video_player()
        elif self._video_player is not None:
            self._video_player.stop()

    def close(self) -> None:
        """Release video resources retained by the former widget lifecycle."""
        self._cancel_video_request()
        self._vm.clear_video()
        if self._video_player is not None:
            self._video_player.stop()

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

    def _load_track_details(self, video_id: str) -> None:
        """Recupera sólo los créditos que publique la fuente de la pista."""
        main = self._find_main_window()
        extractor = getattr(main, "extractor", None) if main else None
        if extractor is None:
            self._vm.set_details_error("No se pudieron cargar los detalles.")
            return
        asyncio.ensure_future(self._load_track_details_async(video_id, extractor))

    async def _load_track_details_async(self, video_id: str, extractor) -> None:
        try:
            details = await extractor.get_stream_info(video_id)
        except Exception as exc:
            logger.debug(f"No se pudieron cargar los créditos: {exc}")
            details = {}
        if video_id != self._vm.videoId:
            return
        if details:
            self._vm.set_track_details(details)
        else:
            self._vm.set_details_error("No hay créditos disponibles para esta canción.")

    def _show_video_clip(self, video_id: str) -> None:
        """Carga el stream visual en la isla sin duplicar el audio principal."""
        if not video_id:
            return
        self._cancel_video_request()
        self._vm.begin_video_loading()

        main = self._find_main_window()
        extractor = getattr(main, "extractor", None) if main else None
        if extractor is None or not hasattr(extractor, "get_video_stream_info"):
            self._vm.set_video_error(_("No se pudo cargar el videoclip."))
            return

        generation = self._video_request_generation
        self._video_task = asyncio.ensure_future(
            self._load_video_stream(video_id, extractor, generation)
        )

    async def _load_video_stream(self, video_id: str, extractor, generation: int) -> None:
        try:
            info = await extractor.get_video_stream_info(video_id)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.warning(f"No se pudo extraer el videoclip: {exc}")
            info = {}

        if (
            generation != self._video_request_generation
            or video_id != self._vm.videoId
            or self._vm.mediaMode != "video"
        ):
            return
        stream_url = str((info or {}).get("url", "") or "")
        if stream_url:
            self._vm.set_video_stream(stream_url)
        else:
            self._vm.set_video_error(_("No se pudo cargar el videoclip."))

    def _ensure_video_player(self) -> bool:
        if self._video_player is not None:
            return True
        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

            self._video_audio = QAudioOutput(self)
            self._video_audio.setMuted(True)
            self._video_player = QMediaPlayer(self)
            self._video_player.setAudioOutput(self._video_audio)
            self._vm.set_video_player(self._video_player)
            self._video_player.mediaStatusChanged.connect(self._on_video_media_status)
            self._video_player.errorOccurred.connect(self._on_video_player_error)
            return True
        except Exception as exc:
            logger.warning(f"No se pudo inicializar el visor de vídeo: {exc}")
            self._vm.set_video_error(_("No se pudo reproducir el videoclip."))
            return False

    def _sync_video_player(self) -> None:
        if not self._active:
            return
        if self._vm.mediaMode != "video" or not self._vm.videoStreamUrl:
            if self._video_player is not None:
                self._stop_video_player()
            return
        if not self._ensure_video_player():
            return
        from PySide6.QtCore import QUrl

        source = QUrl(self._vm.videoStreamUrl)
        if self._video_player.source() != source:
            self._video_player.setSource(source)
        self._sync_video_playback()

    def _stop_video_player(self) -> None:
        if self._vm.mediaMode == "video":
            return
        if self._video_player is not None:
            self._video_player.stop()

    def _sync_video_playback(self) -> None:
        if self._video_player is None or self._vm.mediaMode != "video":
            return
        if not self._vm.videoStreamUrl:
            return
        if self._vm.playing:
            self._video_player.play()
        else:
            self._video_player.pause()

    def _sync_video_position(self) -> None:
        if self._video_player is None or self._vm.mediaMode != "video":
            return
        if self._video_player.duration() > 0 and abs(self._video_player.position() - self._vm.positionMs) > 1800:
            self._video_player.setPosition(max(0, self._vm.positionMs))

    def _on_video_media_status(self, status) -> None:
        try:
            from PySide6.QtMultimedia import QMediaPlayer

            loaded = status in (
                QMediaPlayer.MediaStatus.LoadedMedia,
                QMediaPlayer.MediaStatus.BufferedMedia,
            )
        except Exception:
            loaded = False
        if loaded:
            self._video_player.setPosition(max(0, self._vm.positionMs))
            self._sync_video_playback()

    def _on_video_player_error(self, _error, error_string: str) -> None:
        if self._vm.mediaMode == "video":
            self._vm.report_video_error(error_string or _("No se pudo reproducir el videoclip."))

    def _cancel_video_request(self) -> None:
        self._video_request_generation += 1
        task = self._video_task
        self._video_task = None
        if task is not None and not task.done():
            task.cancel()

    def _close_video_clip(self) -> None:
        self._cancel_video_request()
        if self._video_player is not None:
            self._stop_video_player()
        generation = self._video_request_generation
        # Conserva el último frame mientras QML completa el crossfade a artwork.
        QTimer.singleShot(280, lambda: self._clear_video_after_transition(generation))

    def _clear_video_after_transition(self, generation: int) -> None:
        if generation == self._video_request_generation and self._vm.mediaMode == "audio":
            self._vm.clear_video()

    # ── API pública (llamada por los controllers) ─────────────────────────

    def update_track_info(self, title: str, artist: str, thumbnail_url: str) -> None:
        video_id = getattr(self.player.status, "current_video_id", "") if self.player else ""
        previous_video_id = self._vm.videoId
        album = ""
        if getattr(self.queue, "current", None):
            album = getattr(self.queue.current, "album", "") or ""
        self._vm.set_track_info(title, artist, thumbnail_url, album=album, video_id=video_id)
        if self._vm.mediaMode == "video" and video_id and video_id != previous_video_id:
            self._show_video_clip(video_id)
        if thumbnail_url:
            asyncio.ensure_future(self._load_thumbnail(thumbnail_url))
        # Marcar el actual en la cola (set_queue ya conoce _video_id)
        if self.queue is not None:
            self._vm.set_queue(list(self.queue.items), set())
        else:
            self._vm.set_queue([], set())

    async def _load_thumbnail(self, url: str) -> None:
        path = await _image_cache.download(url)
        # No reemplazar la carátula de la pista nueva con una descarga tardía.
        if path and self._vm.artworkUrl == url:
            self._vm.set_artwork(QUrl.fromLocalFile(str(path)).toString())

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
