from loguru import logger

from doremi.config.paths import AppDirs
from doremi.config.settings import AppSettings


class SettingsController:
    """Specialized controller for applying runtime settings changes.

    Owns the logic previously living in MainWindow._on_settings_changed:
    persisting settings, updating player
    volume/equalizer, crossfade, sleep timer, sidebar compactness and the theme.
    Dependencies are accessed via the ``main_window`` reference; ``run_async`` is a
    callable (MainWindow._run_async) used to launch coroutines as asyncio tasks.
    """

    def __init__(self, main_window, run_async):
        self.main_window = main_window
        self.run_async = run_async
        self._last_offline_limit: int | None = None

    def restore_persisted_sleep_timer(self) -> None:
        """Start the persisted countdown when a new window is constructed.

        ``sleep_timer_minutes`` is a visible, persisted preference.  Before
        this hook only a *new* change to that preference started the timer, so
        a restart left the selected value in Settings without any countdown.
        A restart deliberately begins a fresh full interval: elapsed wall time
        was never stored and guessing it would make the pause surprising.
        """
        sleep_timer = getattr(self.main_window, "sleep_timer", None)
        if sleep_timer is None:
            return
        minutes = int(getattr(self.main_window.settings.player, "sleep_timer_minutes", 0) or 0)
        if minutes <= 0 or sleep_timer.is_running:
            return
        self.run_async(
            sleep_timer.start(minutes * 60, self.main_window._on_sleep_timer_expired)
        )

    def on_settings_changed(self, settings: AppSettings) -> None:
        self.main_window.settings = settings
        if hasattr(self.main_window, 'now_playing_screen'):
            self.main_window.now_playing_screen.settings = settings
            self.main_window.now_playing_screen.update_lyrics_style()
            update_appearance = getattr(
                self.main_window.now_playing_screen, "update_appearance_settings", None
            )
            if callable(update_appearance):
                update_appearance()
        settings.save(AppDirs.settings_file)

        integrations = getattr(self.main_window, "integrations_controller", None)
        if integrations is not None:
            configure_mpris = getattr(integrations, "reconfigure_mpris", None)
            if callable(configure_mpris):
                configure_mpris(settings.integrations.mpris_enabled)

        # Update player volume
        if hasattr(self.main_window, 'player'):
            self.main_window.player.set_volume(settings.player.volume)

        # Update player equalizer
        if settings.equalizer.enabled:
            self.main_window.player.apply_equalizer(
                settings.equalizer.preamp,
                settings.equalizer.bands,
            )
        else:
            self.main_window.player.reset_equalizer()

        # Update crossfade settings dynamically
        if hasattr(self.main_window, 'crossfade_manager'):
            self.main_window.crossfade_manager.enabled = settings.player.crossfade_enabled
            self.main_window.crossfade_manager.duration_sec = settings.player.crossfade_duration_sec

        # Update sleep timer dynamically
        if hasattr(self.main_window, 'sleep_timer'):
            sleep_mins = getattr(settings.player, 'sleep_timer_minutes', 0)
            if sleep_mins > 0:
                logger.info(f"Setting sleep timer for {sleep_mins} minutes")
                self.run_async(self.main_window.sleep_timer.start(sleep_mins * 60, self.main_window._on_sleep_timer_expired))
                self.main_window.statusBar().showMessage(f"Temporizador de apagado activado: {sleep_mins} min", 3000)
            else:
                if self.main_window.sleep_timer.is_running:
                    self.main_window.sleep_timer.cancel()
                    self.main_window.statusBar().showMessage("Temporizador de apagado desactivado", 3000)

        # A smaller offline cache limit must reclaim files now, not only after
        # the next successful Home refresh.
        offline = getattr(settings, "offline", None)
        offline_limit = int(getattr(offline, "song_limit", 0) or 0)
        if offline is not None:
            try:
                from doremi.services.offline_cache import OfflineCacheManager
                offline_cache = OfflineCacheManager.get_instance()
                if not offline.enabled:
                    offline_cache.cancel_sync()
                if offline_limit != self._last_offline_limit:
                    offline_cache.enforce_limit(offline_limit)
                    self._last_offline_limit = offline_limit
            except Exception as exc:
                logger.debug(f"No se pudo aplicar el límite de caché offline: {exc}")

        # Apply appearance changes in real-time
        if hasattr(settings, 'appearance'):
            # Compact sidebar toggle
            if hasattr(self.main_window, 'sidebar'):
                set_collapsed = getattr(self.main_window.sidebar, "set_collapsed", None)
                if callable(set_collapsed):
                    set_collapsed(settings.appearance.compact_sidebar)
                elif settings.appearance.compact_sidebar != self.main_window.sidebar._collapsed:
                    self.main_window.sidebar.toggle_collapse()

            # Theme mode and accent color change — regenerate stylesheet dynamically
            accent = getattr(settings.appearance, 'accent_color', '#A78BFA')
            theme_mode = getattr(settings.appearance, 'theme_mode', 'dark')
            self.main_window.theme_manager.apply(theme_mode, accent)
