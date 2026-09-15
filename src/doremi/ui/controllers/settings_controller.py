from loguru import logger

from doremi.config.paths import AppDirs
from doremi.api.lastfm import LastFmScrobbler
from doremi.config.settings import AppSettings


class SettingsController:
    """Specialized controller for applying runtime settings changes.

    Owns the logic previously living in MainWindow._on_settings_changed:
    persisting settings, (re)initializing the Last.fm scrobbler, updating player
    volume/equalizer, crossfade, sleep timer, sidebar compactness and the theme.
    Dependencies are accessed via the ``main_window`` reference; ``run_async`` is a
    callable (MainWindow._run_async) used to launch coroutines as asyncio tasks.
    """

    def __init__(self, main_window, run_async):
        self.main_window = main_window
        self.run_async = run_async

    def on_settings_changed(self, settings: AppSettings) -> None:
        self.main_window.settings = settings
        if hasattr(self.main_window, 'now_playing_screen'):
            self.main_window.now_playing_screen.settings = settings
            self.main_window.now_playing_screen.update_lyrics_style()
        settings.save(AppDirs.settings_file)

        # Update Last.fm scrobbler dynamically
        if settings.integrations.lastfm_enabled and settings.integrations.lastfm_session_key:
            if not getattr(self.main_window, 'scrobbler', None) or getattr(self.main_window, '_lastfm_session_key', None) != settings.integrations.lastfm_session_key:
                try:
                    self.main_window.scrobbler = LastFmScrobbler(
                        settings.integrations.lastfm_api_key,
                        settings.integrations.lastfm_api_secret,
                        settings.integrations.lastfm_session_key,
                    )
                    self.main_window._lastfm_session_key = settings.integrations.lastfm_session_key
                    logger.info("Dynamic Last.fm scrobbler initialized/updated")
                except Exception as e:
                    logger.error(f"Failed to initialize dynamic scrobbler: {e}")
        else:
            self.main_window.scrobbler = None
            self.main_window._lastfm_session_key = None

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

        # Apply appearance changes in real-time
        if hasattr(settings, 'appearance'):
            # Compact sidebar toggle
            if hasattr(self.main_window, 'sidebar'):
                if settings.appearance.compact_sidebar and not self.main_window.sidebar._collapsed:
                    self.main_window.sidebar.toggle_collapse()
                elif not settings.appearance.compact_sidebar and self.main_window.sidebar._collapsed:
                    self.main_window.sidebar.toggle_collapse()

            # Theme mode and accent color change — regenerate stylesheet dynamically
            accent = getattr(settings.appearance, 'accent_color', '#A78BFA')
            theme_mode = getattr(settings.appearance, 'theme_mode', 'dark')
            self.main_window.theme_manager.apply(theme_mode, accent)
