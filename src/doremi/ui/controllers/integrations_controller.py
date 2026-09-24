import asyncio
import time

from loguru import logger

from doremi.audio.player import MusicPlayer, PlayerState
from doremi.audio.queue import PlayQueue, QueueItem, RepeatMode
from doremi.api.lastfm import LastFmScrobbler
from doremi.api.discord_rpc import DiscordRPC
from doremi.api.stream_extractor import StreamExtractor
from doremi.config.settings import AppSettings
from doremi.system.mpris import MprisPlayer
from doremi.system.network import NetworkMonitor
from doremi.ui.widgets.toast import ToastNotification


class IntegrationsController:
    """Specialized controller for external integrations.

    Owns the player-callback wiring and the integrations that were previously
    spread across MainWindow's god object: VLC callbacks, Last.fm scrobbling,
    MPRIS, Discord RPC and network connectivity handling.

    Dependencies are injected through the constructor; ``run_async`` is a
    callable (MainWindow._run_async) used to launch coroutines as asyncio tasks.
    ``main_window`` is a back-reference to MainWindow for the cross-cutting
    concerns that remain on it (navigation, settings, playback wrappers).
    """

    def __init__(
        self,
        player: MusicPlayer,
        queue: PlayQueue,
        mpris: MprisPlayer,
        scrobbler: LastFmScrobbler | None,
        discord: DiscordRPC | None,
        settings: AppSettings,
        extractor: StreamExtractor,
        run_async,
        main_window,
    ):
        self.player = player
        self.queue = queue
        self.mpris = mpris
        self.scrobbler = scrobbler
        self.discord = discord
        self.settings = settings
        self.extractor = extractor
        self.run_async = run_async
        self.main_window = main_window

        # Last.fm scrobble state (moved from MainWindow).
        self._lastfm_track_key: tuple[str, str, str] | None = None
        self._lastfm_started_at: int | None = None
        self._lastfm_scrobbled = False
        self._lastfm_scrobble_pending = False

        # Populated lazily by setup_integrations().
        self.network_monitor: NetworkMonitor | None = None

    def connect_player_callbacks(self) -> None:
        self.player.on("track_ended", self.on_track_ended_callback)
        self.player.on("state_changed", self.on_state_changed_callback)
        self.player.on("position_changed", self.on_position_changed_callback)
        self.player.on("error", self.on_player_error_callback)

    def on_track_ended_callback(self, status) -> None:
        self.run_async(self.main_window.playback_controller._advance_queue())

    def on_player_error_callback(self, status) -> None:
        self.main_window.playback_controller.on_player_error(status)

    async def recover_player_error(self, status) -> None:
        # Compatibilidad: la reproducción es la única dueña de los reintentos.
        self.main_window.playback_controller.on_player_error(status)

    async def handle_playback_failure(self, item: QueueItem, message: str) -> None:
        await self.main_window.playback_controller.handle_playback_failure(item, message)

    def on_state_changed_callback(self, status) -> None:
        self.main_window.mini_player.update_state(status)
        self.main_window.now_playing_screen.update_state(status)
        is_playing = status.state == PlayerState.PLAYING

        if self.mpris:
            self.mpris.update_playback_status(is_playing)

        if hasattr(self.main_window, "tray") and self.main_window.tray:
            self.main_window.tray.update_play_state(is_playing)

        if self.discord and self.queue.current:
            item = self.queue.current
            self.run_async(self.discord.update(
                item.title, item.artist, item.album, is_playing, item.thumbnail_url
            ))

    def on_position_changed_callback(self, status) -> None:
        self.main_window.mini_player.update_position(
            status.position_ms, status.duration_ms
        )
        self.main_window.now_playing_screen.update_position(
            status.position_ms, status.duration_ms
        )
        self.maybe_scrobble_lastfm(status)
        if self.mpris:
            self.mpris.update_position(status.position_ms)
            self.mpris.update_volume(status.volume)

    def reset_lastfm_scrobble_state(self, item: QueueItem) -> None:
        self._lastfm_track_key = (item.video_id, item.title, item.artist)
        self._lastfm_started_at = int(time.time())
        self._lastfm_scrobbled = False
        self._lastfm_scrobble_pending = False

    def maybe_scrobble_lastfm(self, status) -> None:
        if (
            not self.scrobbler
            or self._lastfm_scrobbled
            or self._lastfm_scrobble_pending
            or status.duration_ms <= 0
        ):
            return

        item = self.queue.current
        if not item or self._lastfm_track_key != (item.video_id, item.title, item.artist):
            return

        threshold_ms = min(status.duration_ms * 0.5, 240_000)
        if status.position_ms < threshold_ms:
            return

        self._lastfm_scrobble_pending = True
        self.run_async(self.scrobble_current_lastfm(item, self._lastfm_started_at))

    async def scrobble_current_lastfm(self, item: QueueItem, started_at: int | None) -> None:
        if not self.scrobbler or not started_at:
            self._lastfm_scrobble_pending = False
            return
        track_key = (item.video_id, item.title, item.artist)
        if self._lastfm_track_key != track_key:
            self._lastfm_scrobble_pending = False
            return
        try:
            success = await self.scrobbler.scrobble(
                item.artist, item.title, item.album, timestamp=started_at
            )
            if success:
                self._lastfm_scrobbled = True
                logger.info(f"Last.fm scrobbled: {item.artist} - {item.title}")
            else:
                logger.info(f"Last.fm scrobble queued for retry: {item.artist} - {item.title}")
        except Exception as e:
            logger.warning(f"Last.fm scrobble failed for {item.video_id}: {e}")
        finally:
            self._lastfm_scrobble_pending = False

    def setup_integrations(self) -> None:
        # Initialize player parameters from settings
        self.player.set_volume(self.settings.player.volume)
        if self.settings.equalizer.enabled:
            self.player.apply_equalizer(
                self.settings.equalizer.preamp,
                self.settings.equalizer.bands,
            )
        else:
            self.player.reset_equalizer()

        if self.settings.integrations.mpris_enabled:
            # Wire MPRIS2 callbacks
            self.mpris.on_play_pause = self.main_window._on_play_pause
            self.mpris.on_play = lambda: self.run_async(self.player.resume())
            self.mpris.on_pause = lambda: self.run_async(self.player.pause())
            self.mpris.on_stop = lambda: self.run_async(self.player.stop())
            self.mpris.on_next = self.main_window._on_next
            self.mpris.on_prev = self.main_window._on_prev
            self.mpris.on_seek = lambda offset_us: self.main_window.playback_controller._on_seek(self.player.status.position_ms + int(offset_us / 1000))
            self.mpris.on_set_position = lambda track_id, position_us: self.main_window.playback_controller._on_seek(int(position_us / 1000))
            self.mpris.on_set_volume = lambda vol: (self.player.set_volume(int(vol * 100)), self.on_mpris_volume_changed(int(vol * 100)))
            self.mpris.on_set_shuffle = lambda shuffle: self.toggle_shuffle_from_mpris(shuffle)
            self.mpris.on_set_loop_status = self.set_repeat_from_mpris
            self.mpris.on_raise = lambda: (self.main_window.show(), self.main_window.raise_(), self.main_window.activateWindow())
            self.mpris.on_quit = self.main_window.close
            self.mpris.start()
            self.mpris.update_shuffle(self.queue.shuffle_enabled)
            self.mpris.update_loop_status()

        if self.settings.integrations.lastfm_enabled and self.settings.integrations.lastfm_session_key:
            self.scrobbler = LastFmScrobbler(
                self.settings.integrations.lastfm_api_key,
                self.settings.integrations.lastfm_api_secret,
                self.settings.integrations.lastfm_session_key,
            )
            self.main_window.scrobbler = self.scrobbler
        if self.settings.integrations.discord_rpc_enabled:
            self.discord = DiscordRPC()
            self.main_window.discord = self.discord
            task = self.run_async(self.discord.connect())

        # Setup and start network monitor
        from doremi.system.network import NetworkMonitor
        self.network_monitor = NetworkMonitor(on_connectivity_change=self.on_connectivity_change)
        self.main_window.network_monitor = self.network_monitor
        self.run_async(self.network_monitor.start())

    def on_mpris_volume_changed(self, volume: int) -> None:
        self.settings.player.volume = volume
        self.main_window._on_settings_changed(self.settings)
        try:
            from doremi.ui.screens.settings.player_settings import PlayerSettingsScreen
            player_settings_page = self.main_window.settings_screen.stack.findChild(PlayerSettingsScreen)
            if player_settings_page:
                player_settings_page.update_fields()
        except Exception as e:
            logger.debug(f"Could not sync player settings screen volume: {e}")

    def on_connectivity_change(self, is_connected: bool) -> None:
        """Handle network status transitions dynamically."""
        if not is_connected:
            self.main_window.offline_banner.show_banner()
            ToastNotification.show(self.main_window, "Modo sin conexión: usando música guardada", "warning")
            if (
                self.main_window._current_route == "home"
                and getattr(self.main_window.home_screen, "_loaded", False)
            ):
                self.main_window.home_screen.force_reload()
            if self.main_window._current_route in self.main_window.ONLINE_ROUTES:
                self.main_window._offline_blocked_path = self.main_window._current_route
                self.main_window._show_offline_state(self.main_window._current_route)
        else:
            self.main_window.offline_banner.hide_banner()
            ToastNotification.show(self.main_window, "Conexión de red restablecida", "success")

            if self.main_window._current_route == "home":
                self.main_window.home_screen.force_reload()
                return

            # Reload active static screen to resume online capabilities
            if self.main_window._offline_blocked_path:
                blocked_path = self.main_window._offline_blocked_path
                self.main_window._offline_blocked_path = None
                self.main_window._navigate_to(blocked_path)
            else:
                current_index = self.main_window.stack.currentIndex()
                active_route = next((k for k, v in self.main_window.ROUTES.items() if v == current_index), None)
                if active_route:
                    self.run_async(self.main_window._load_screen(active_route))

    def toggle_shuffle_from_mpris(self, enable: bool) -> None:
        if enable != self.queue.shuffle_enabled:
            self.queue.toggle_shuffle()
            self.persist_queue_playback_settings()
            self.main_window.now_playing_screen.update_shuffle_repeat_state()
            self.main_window.playback_controller._update_queue_panel()
            if self.mpris:
                self.mpris.update_shuffle(enable)

    def persist_queue_playback_settings(self) -> None:
        self.settings.player.shuffle_enabled = self.queue.shuffle_enabled
        self.settings.player.repeat_mode = self.queue.repeat_mode.value
        self.main_window._on_settings_changed(self.settings)

    def set_repeat_from_mpris(self, loop_status: str) -> None:
        mapping = {
            "None": RepeatMode.OFF,
            "Playlist": RepeatMode.ALL,
            "Track": RepeatMode.ONE,
        }
        repeat_mode = mapping.get(loop_status, RepeatMode.OFF)
        if self.queue.repeat_mode == repeat_mode:
            return
        self.queue.repeat_mode = repeat_mode
        self.persist_queue_playback_settings()
        if hasattr(self.main_window, "now_playing_screen"):
            self.main_window.now_playing_screen.update_shuffle_repeat_state()
        if self.mpris:
            self.mpris.update_loop_status()
