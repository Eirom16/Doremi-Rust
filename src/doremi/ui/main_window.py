import asyncio
import json
import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QFrame, QMessageBox
)
from PySide6.QtCore import QByteArray, Qt, QSize, QEasingCurve, QPropertyAnimation, Property, QTimer
from qasync import asyncSlot
from loguru import logger
from doremi.config.settings import AppSettings
from doremi.api.youtube_music import YouTubeMusicClient
from doremi.api.stream_extractor import StreamExtractor
from doremi.api.lyrics import LyricsClient
from doremi.api.lastfm import LastFmScrobbler
from doremi.api.discord_rpc import DiscordRPC
from doremi.audio.player import MusicPlayer, PlayerState
from doremi.audio.queue import PlayQueue, QueueItem, RepeatMode
from doremi.system.mpris import MprisPlayer
from doremi.system.tray import SystemTray
from doremi.ui.widgets.nav_sidebar import NavSidebar
from doremi.ui.widgets.mini_player import MiniPlayerWidget
from doremi.ui.widgets.fade_stack import FadeStackedWidget
from doremi.ui.widgets.toast import ToastNotification
from doremi.audio.sleep_timer import SleepTimer
from doremi.audio.crossfade import CrossfadeManager
from doremi.ui.theme_manager import ThemeManager
from doremi.ui.controllers.playback_controller import PlaybackController
from doremi.ui.controllers.integrations_controller import IntegrationsController
from doremi.ui.controllers.navigation_controller import NavigationController
from doremi.ui.controllers.download_controller import DownloadController
from doremi.ui.controllers.queue_controller import QueueController
from doremi.ui.controllers.session_manager import PlaybackSessionManager
from doremi.ui.controllers.settings_controller import SettingsController


def _qml_enabled(flag: str) -> bool:
    """Las islas QML son la UI por defecto; DOREMI_QML_<X>=0 fuerza QtWidgets."""
    return os.environ.get(flag, "1") != "0"


class MainWindow(QMainWindow):
    ROUTES = {
        "home": 0,
        "library": 1,
        "history": 2,
        "downloads": 3,
        "settings": 4,
        "playlist": 5,
        "album": 6,
        "artist": 7,
        "now_playing": 8,
        "search": 9,
        "stats": 10,
    }
    ONLINE_ROUTES = {"home", "library", "playlist", "album", "artist", "search"}

    def __init__(self, settings: AppSettings, event_loop=None):
        super().__init__()
        self.settings = settings
        self._loop = event_loop
        self._pending_tasks: set[asyncio.Task] = set()
        self._current_nav_task: asyncio.Task | None = None
        self._current_play_id = 0
        self._nav_history: list[int] = []  # stack of previous screen indices for back navigation
        self.theme_manager = ThemeManager(self)

        
        self.yt = YouTubeMusicClient(settings)
        self.extractor = StreamExtractor(settings)
        
        from doremi.services.download_manager import DownloadManager
        self.download_manager = DownloadManager.get_instance()
        self.download_manager.start()
        self.download_controller = DownloadController(self, self.download_manager, self._run_async)
        self.download_manager.download_completed.connect(self._on_download_finished)
        self.download_manager.download_error.connect(self._on_download_error)
        
        self.lyrics_client = LyricsClient()
        self.player = MusicPlayer()
        self.queue = PlayQueue()
        self.queue.shuffle_enabled = self.settings.player.shuffle_enabled
        try:
            self.queue.repeat_mode = RepeatMode(self.settings.player.repeat_mode)
        except ValueError:
            self.queue.repeat_mode = RepeatMode.OFF
        self.mpris = MprisPlayer(self.player, self.queue)
        self.scrobbler: LastFmScrobbler | None = None
        self.discord: DiscordRPC | None = None
        self._force_close = False
        from doremi.config.paths import AppDirs
        self._window_state_file = AppDirs.data / "window_state.json"
        self._current_route = "home"
        self._offline_blocked_path: str | None = None
        self._stream_recovery_attempts: set[str] = set()
        self.sleep_timer = SleepTimer()
        self.crossfade_manager = CrossfadeManager(
            enabled=settings.player.crossfade_enabled,
            duration_sec=settings.player.crossfade_duration_sec
        )

        self.queue_controller = QueueController(self, self.queue, self.extractor, self._run_async)

        self.session_manager = PlaybackSessionManager(self, self._run_async)

        self.settings_controller = SettingsController(self, self._run_async)

        self._setup_window()
        self._build_ui()
        self.integrations_controller = IntegrationsController(
            self.player, self.queue, self.mpris, self.scrobbler,
            self.discord, self.settings, self.extractor, self._run_async, self,
        )
        self.integrations_controller.connect_player_callbacks()
        self.integrations_controller.setup_integrations()
        self.playback_controller = PlaybackController(
            player=self.player,
            queue=self.queue,
            yt=self.yt,
            settings=self.settings,
            extractor=self.extractor,
            download_manager=self.download_manager,
            run_async=self._run_async,
            mini_player=self.mini_player,
            now_playing_screen=self.now_playing_screen,
            tray=self.tray,
            mpris=self.mpris,
            scrobbler=self.scrobbler,
            discord=self.discord,
            crossfade_manager=self.crossfade_manager,
            network_monitor=self.network_monitor,
            lyrics_client=self.lyrics_client,
            sleep_timer=self.sleep_timer,
            main_window=self,
        )
        self._setup_shortcuts()
        
        # Apply initial theme properly (immediately on startup to prevent flash)
        theme_mode = getattr(settings.appearance, 'theme_mode', 'dark')
        accent = getattr(settings.appearance, 'accent_color', '#A78BFA')
        self.theme_manager.apply(theme_mode, accent, immediate=True)

    def _setup_shortcuts(self) -> None:
        from PySide6.QtGui import QShortcut, QKeySequence
        from PySide6.QtWidgets import QApplication, QLineEdit, QTextEdit, QAbstractSpinBox
        from PySide6.QtCore import QObject, QEvent, Qt

        search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        search_shortcut.activated.connect(self.search_bar.focus_search)
        
        slash_shortcut = QShortcut(QKeySequence("/"), self)
        slash_shortcut.activated.connect(self.search_bar.focus_search)

        class GlobalShortcutFilter(QObject):
            def __init__(self, main_window):
                super().__init__(main_window)
                self.mw = main_window

            def _close_escape_target(self) -> bool:
                search_bar = getattr(self.mw, "search_bar", None)
                dropdown = getattr(search_bar, "_dropdown", None)
                if dropdown is not None and dropdown.isVisible():
                    search_bar._hide_dropdown()
                    return True

                notification_panel = getattr(self.mw, "notification_panel", None)
                if notification_panel is not None and notification_panel.isVisible():
                    notification_panel._close_anim()
                    return True

                return False

            def eventFilter(self, obj, event):
                if event.type() == QEvent.Type.KeyPress:
                    focus_widget = QApplication.focusWidget()
                    if event.key() == Qt.Key.Key_Escape and self._close_escape_target():
                        return True

                    if isinstance(focus_widget, (QLineEdit, QTextEdit, QAbstractSpinBox)):
                        if event.key() == Qt.Key.Key_Escape:
                            focus_widget.clearFocus()
                            return True
                        return False
                        
                    key = event.key()
                    modifiers = event.modifiers()
                    if key == Qt.Key.Key_Space:
                        self.mw._on_play_pause()
                        return True
                    elif key == Qt.Key.Key_Right and modifiers & Qt.KeyboardModifier.ControlModifier:
                        self.mw._on_next()
                        return True
                    elif key == Qt.Key.Key_Left and modifiers & Qt.KeyboardModifier.ControlModifier:
                        self.mw._on_prev()
                        return True
                    elif key == Qt.Key.Key_Right:
                        if self.mw.player.status.duration_ms > 0:
                            p = self.mw.player.status.position_ms
                            self.mw._on_seek(p + 5000)
                        return True
                    elif key == Qt.Key.Key_Left:
                        if self.mw.player.status.duration_ms > 0:
                            p = self.mw.player.status.position_ms
                            self.mw._on_seek(max(0, p - 5000))
                        return True
                    elif key == Qt.Key.Key_Up:
                        v = self.mw.player.status.volume
                        self.mw.player.set_volume(min(100, v + 5))
                        return True
                    elif key == Qt.Key.Key_Down:
                        v = self.mw.player.status.volume
                        self.mw.player.set_volume(max(0, v - 5))
                        return True
                return False

        self._shortcut_filter = GlobalShortcutFilter(self)
        self.installEventFilter(self._shortcut_filter)

        # Verificar actualizaciones 10 segundos después de arrancar
        # (no al instante para no retrasar la carga inicial)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(10_000, lambda: asyncio.ensure_future(self._check_updates()))

        from doremi.services.lyrics_prefetcher import LyricsPrefetcher
        self._lyrics_prefetcher = LyricsPrefetcher()
        self._run_async(self._lyrics_prefetcher.run())

        # Connect cleanup handler to application quit
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(self._cleanup_on_close)

        self.navigation_controller = NavigationController(self, self._run_async)

        if self._loop:
            self._init_task = self._loop.create_task(self._initialize())
            self._track_task(self._init_task)
        else:
            self._init_task = asyncio.ensure_future(self._initialize())
            self._track_task(self._init_task)



    def _setup_window(self) -> None:
        self.setWindowTitle("Doremi")
        self.setMinimumSize(QSize(960, 640))
        self.resize(1300, 820)
        self._restore_window_state()

    def _restore_window_state(self) -> None:
        try:
            if not self._window_state_file.exists():
                return
            with open(self._window_state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            geometry_hex = data.get("geometry")
            if geometry_hex:
                self.restoreGeometry(QByteArray.fromHex(geometry_hex.encode("ascii")))
        except Exception as e:
            logger.debug(f"Failed to restore window state: {e}")

    def _save_window_state(self) -> None:
        try:
            self._window_state_file.parent.mkdir(parents=True, exist_ok=True)
            data = {"geometry": bytes(self.saveGeometry().toHex()).decode("ascii")}
            with open(self._window_state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.debug(f"Failed to save window state: {e}")

    def _build_ui(self) -> None:
        central = QWidget()
        self._central_widget = central
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        content_area = QWidget()
        content_area.setObjectName("contentArea")
        h_layout = QHBoxLayout(content_area)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        self.sidebar = NavSidebar(on_navigate=self._navigate_to)
        self.sidebar.on_login_click.connect(self._show_login)
        self.sidebar.auth_changed.connect(self._on_auth_changed)
        
        # Initialize Notification Service
        from doremi.services.notification_service import NotificationService
        self.notification_service = NotificationService(self.yt)
        
        if self.yt.is_authenticated:
            self.notification_service.start()
            from doremi.config.paths import AppDirs
            import json
            name = "YouTube Music"
            avatar = ""
            
            # Try fresh account info from API
            try:
                if hasattr(self.yt, '_ytmusicapi') and self.yt._ytmusicapi:
                    account_info = self.yt._ytmusicapi.get_account_info()
                    name = account_info.get("accountName", "") or name
                    avatar = account_info.get("accountPhotoUrl", "")
                    # Update saved profile
                    profile_file = AppDirs.config / "user_profile.json"
                    with open(profile_file, "w") as f:
                        json.dump({"name": name, "avatar_url": avatar}, f, indent=4)
            except Exception as e:
                logger.debug(f"Could not refresh account info from API: {e}")
            
            # Fallback: read from saved profile
            if name == "YouTube Music":
                profile_file = AppDirs.config / "user_profile.json"
                if profile_file.exists():
                    try:
                        with open(profile_file, "r") as f:
                            data = json.load(f)
                            name = data.get("name", "YouTube Music") or "YouTube Music"
                            avatar = data.get("avatar_url", "")
                    except Exception as e:
                        logger.debug(f"Could not read saved user profile: {e}")
            self.sidebar.update_auth_state(True, name, avatar)
        h_layout.addWidget(self.sidebar)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        from doremi.ui.widgets.global_search import GlobalSearchBar
        self.search_bar = GlobalSearchBar(self.yt, self._play_song_sync)
        self.search_bar.search_submitted.connect(self._on_search_submitted)
        
        self.notification_service.unread_changed.connect(self.search_bar.notif_btn.set_unread)
        self._run_async(self.notification_service.check_unread())
        
        right_layout.addWidget(self.search_bar)

        # Add glassmorphic offline warning banner
        from doremi.ui.widgets.offline_banner import OfflineBannerWidget
        self.offline_banner = OfflineBannerWidget(self)
        right_layout.addWidget(self.offline_banner)

        # Container for stack and notification panel
        self.main_content_hbox = QHBoxLayout()
        self.main_content_hbox.setContentsMargins(0, 0, 0, 0)
        self.main_content_hbox.setSpacing(0)

        self.stack = FadeStackedWidget()
        self.stack.setObjectName("screenStack")
        self.main_content_hbox.addWidget(self.stack)

        from doremi.ui.widgets.notification_panel import NotificationPanel
        if _qml_enabled("DOREMI_QML_NOTIFICATIONS"):
            self.notification_panel = self._build_notifications_qml() or NotificationPanel(self)
        else:
            self.notification_panel = NotificationPanel(self)
        self.notification_panel.hide()
        self.main_content_hbox.addWidget(self.notification_panel)

        self.search_bar.notifications_requested.connect(self.notification_panel.toggle_panel)
        self.notification_panel.panel_toggled.connect(self.search_bar.notif_btn.set_panel_open)
        self.notification_panel.artist_clicked.connect(lambda a, a_id: self._navigate_to(f"artist?id={a_id}") if a_id else self.resolve_and_navigate_artist(a))
        self.notification_panel.song_clicked.connect(lambda v, t, a, u: self._play_song_sync(v, t, a, "", 0, u))



        from doremi.ui.screens.home import HomeScreen
        from doremi.ui.screens.library import LibraryScreen
        from doremi.ui.screens.history import HistoryScreen
        from doremi.ui.screens.downloads import DownloadsScreen
        from doremi.ui.screens.settings import SettingsScreen

        from doremi.ui.screens.playlist import PlaylistScreen
        from doremi.ui.screens.album import AlbumScreen
        from doremi.ui.screens.artist import ArtistScreen

        from doremi.ui.screens.now_playing import NowPlayingScreen
        from doremi.ui.screens.search import SearchScreen
        from doremi.ui.screens.stats import StatsScreen
        from doremi.ui.widgets.error_state import ErrorStateWidget

        if _qml_enabled("DOREMI_QML_HOME"):
            self.home_screen = self._build_home_qml() or HomeScreen(self.yt, self._play_song_sync, self._navigate_to)
        else:
            self.home_screen = HomeScreen(self.yt, self._play_song_sync, self._navigate_to)
        if _qml_enabled("DOREMI_QML_LIBRARY"):
            self.library_screen = self._build_library_qml() or LibraryScreen(self.yt, self._play_song_sync, self._navigate_to)
        else:
            self.library_screen = LibraryScreen(self.yt, self._play_song_sync, self._navigate_to)
        if _qml_enabled("DOREMI_QML_HISTORY"):
            self.history_screen = self._build_history_qml() or HistoryScreen(self.yt, self._play_song_sync)
        else:
            self.history_screen = HistoryScreen(self.yt, self._play_song_sync)
        if _qml_enabled("DOREMI_QML_DOWNLOADS"):
            self.downloads_screen = self._build_downloads_qml() or DownloadsScreen(self.extractor, self._play_local_wrapper, self._play_local_playlist, self._navigate_to)
        else:
            self.downloads_screen = DownloadsScreen(self.extractor, self._play_local_wrapper, self._play_local_playlist, self._navigate_to)
        if _qml_enabled("DOREMI_QML_SETTINGS"):
            self.settings_screen = self._build_settings_qml() or SettingsScreen(
                self.yt,
                self.settings,
                on_settings_changed=self._on_settings_changed,
                on_auth_changed=self._on_auth_changed
            )
        else:
            self.settings_screen = SettingsScreen(
                self.yt,
                self.settings,
                on_settings_changed=self._on_settings_changed,
                on_auth_changed=self._on_auth_changed
            )
        if _qml_enabled("DOREMI_QML_PLAYLIST"):
            self.playlist_screen = self._build_playlist_qml() or PlaylistScreen(self.yt, self._play_song_sync, self._play_local_playlist, on_back=self._go_back)
        else:
            self.playlist_screen = PlaylistScreen(self.yt, self._play_song_sync, self._play_local_playlist, on_back=self._go_back)
        if _qml_enabled("DOREMI_QML_ALBUM"):
            self.album_screen = self._build_album_qml() or AlbumScreen(self.yt, self._play_song_sync, on_back=self._go_back)
        else:
            self.album_screen = AlbumScreen(self.yt, self._play_song_sync, on_back=self._go_back)
        if _qml_enabled("DOREMI_QML_ARTIST"):
            self.artist_screen = self._build_artist_qml() or ArtistScreen(self.yt, self._play_song_sync, self._navigate_to, on_back=self._go_back)
        else:
            self.artist_screen = ArtistScreen(self.yt, self._play_song_sync, self._navigate_to, on_back=self._go_back)
        if _qml_enabled("DOREMI_QML_NOW_PLAYING"):
            self.now_playing_screen = self._build_now_playing_qml() or NowPlayingScreen(self.player, self.queue, self.yt, self._play_queue_item, self.settings, on_back=self._go_back)
        else:
            self.now_playing_screen = NowPlayingScreen(self.player, self.queue, self.yt, self._play_queue_item, self.settings, on_back=self._go_back)
        if _qml_enabled("DOREMI_QML_SEARCH"):
            self.search_screen = self._build_search_qml() or SearchScreen(self.yt, self._play_song_sync, self._navigate_to)
        else:
            self.search_screen = SearchScreen(self.yt, self._play_song_sync, self._navigate_to)
        if _qml_enabled("DOREMI_QML_STATS"):
            self.stats_screen = self._build_stats_qml() or StatsScreen(self.yt, self._play_song_sync)
        else:
            self.stats_screen = StatsScreen(self.yt, self._play_song_sync)
        self.offline_state_screen = ErrorStateWidget(
            "No hay conexion. Puedes seguir escuchando tu musica descargada.",
            retry_callback=lambda: self._navigate_to("downloads"),
            action_text="Ir a Descargas",
        )

        for screen in [
            self.home_screen,
            self.library_screen,
            self.history_screen,
            self.downloads_screen,
            self.settings_screen,
            self.playlist_screen,
            self.album_screen,
            self.artist_screen,
            self.now_playing_screen,
            self.search_screen,
            self.stats_screen,
        ]:
            self.stack.addWidget(screen)
            # Connect all context-menu signals if they exist
            if hasattr(screen, 'download_requested'):
                screen.download_requested.connect(self._on_download_requested)
            if hasattr(screen, 'play_next_requested'):
                screen.play_next_requested.connect(self._on_play_next_requested)
            if hasattr(screen, 'add_to_queue_requested'):
                screen.add_to_queue_requested.connect(self._on_add_to_queue_requested)
            if hasattr(screen, 'add_to_playlist_requested'):
                screen.add_to_playlist_requested.connect(self._on_add_to_playlist_requested)
            if hasattr(screen, 'download_playlist_requested'):
                screen.download_playlist_requested.connect(self._on_download_playlist_requested)
            if hasattr(screen, 'download_album_requested'):
                screen.download_album_requested.connect(self._on_download_album_requested)
            if hasattr(screen, 'like_requested'):
                screen.like_requested.connect(self._on_like_requested)
            if hasattr(screen, 'delete_download_requested'):
                screen.delete_download_requested.connect(self._on_delete_download_requested)
            if hasattr(screen, 'delete_playlist_requested'):
                screen.delete_playlist_requested.connect(self._on_delete_playlist_requested)
            if hasattr(screen, 'artist_clicked'):
                screen.artist_clicked.connect(self.resolve_and_navigate_artist)
            if hasattr(screen, 'album_clicked'):
                screen.album_clicked.connect(self.resolve_and_navigate_album)

        self._offline_state_index = self.stack.addWidget(self.offline_state_screen)

        if hasattr(self.now_playing_screen, 'queue_tab'):
            self.now_playing_screen.queue_tab.like_requested.connect(self._on_like_requested)
            self.now_playing_screen.queue_tab.artist_clicked.connect(self.resolve_and_navigate_artist)
            self.now_playing_screen.queue_tab.album_clicked.connect(self.resolve_and_navigate_album)
            self.now_playing_screen.queue_tab.queue_move_requested.connect(self._on_queue_move_requested)

        right_layout.addLayout(self.main_content_hbox)

        h_layout.addWidget(right_panel)
        
        root_layout.addWidget(content_area)

        self.mini_player = self._build_mini_player(central)
        self.mini_player.raise_()
        self.sidebar._width_anim.valueChanged.connect(lambda _value: self._position_mini_player())
        self.sidebar._max_anim.valueChanged.connect(lambda _value: self._position_mini_player())
        self._position_mini_player()

        if hasattr(self, 'mini_player'):
            self.mini_player.artist_clicked.connect(self.resolve_and_navigate_artist)

        self.statusBar().setObjectName("appStatusBar")
        self.statusBar().setStyleSheet("color: #888899; font-family: Inter; font-size: 11px;")
        self.statusBar().setFixedHeight(0)
        self.statusBar().hide()

        self.tray = SystemTray(
            parent=self,
            on_show=self._show_and_activate,
            on_play_pause=self._on_play_pause,
            on_prev=self._on_prev,
            on_next=self._on_next,
            on_quit=self._on_tray_quit,
        )

    def _position_mini_player(self) -> None:
        if not hasattr(self, "mini_player") or not self.mini_player:
            return
        central = getattr(self, "_central_widget", None) or self.centralWidget()
        if central is None:
            return

        margin = 16
        player_height = self.mini_player.height()
        sidebar_width = self.sidebar.width() if hasattr(self, "sidebar") and self.sidebar.isVisible() else 0
        
        right_panel_width = 0
        if hasattr(self, "notification_panel") and self.notification_panel.isVisible():
            right_panel_width = self.notification_panel.maximumWidth()
            
        content_x = sidebar_width + margin
        available_width = max(0, central.width() - content_x - margin - right_panel_width)
        max_player_width = 1060
        width = min(available_width, max_player_width)
        x = content_x + max(0, (available_width - width) // 2)
        y = central.height() - player_height - margin if player_height > 0 else central.height()
        self.mini_player.setGeometry(x, max(0, y), width, max(0, player_height))
        self.mini_player.raise_()

        if hasattr(self, "stack"):
            # The mini player is an overlay attached to the central widget. Do not
            # reserve bottom space in the stacked content; that creates a visible
            # solid strip underneath instead of the intended floating effect.
            current_margins = self.stack.contentsMargins()
            if current_margins.bottom() != 0:
                self.stack.setContentsMargins(0, 0, 0, 0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_mini_player()
        if hasattr(self, 'theme_manager'):
            self.theme_manager.on_main_window_resized()

    def _build_mini_player(self, parent):
        """Crea el mini-player: isla QML por defecto; DOREMI_QML_MINIPLAYER=0 (o fallo) → widgets."""
        kwargs = dict(
            player=self.player,
            queue=self.queue,
            on_expand=self._show_full_player,
            on_prev=self._on_prev,
            on_play_pause=self._on_play_pause,
            on_next=self._on_next,
            on_seek=self._on_seek,
            parent=parent,
        )
        if _qml_enabled("DOREMI_QML_MINIPLAYER"):
            try:
                from doremi.ui.widgets.mini_player_qml import MiniPlayerQml
                widget = MiniPlayerQml(**kwargs)
                if widget.is_ok:
                    logger.info("Usando isla QML para mini-player")
                    return widget
                logger.warning("Isla QML mini-player no cargó; usando versión QtWidgets")
            except Exception as e:
                logger.warning(f"No se pudo crear la isla QML del mini-player: {e}")
        return MiniPlayerWidget(**kwargs)

    def _build_home_qml(self):
        """Isla QML de Inicio. Devuelve None si el backend QML falla → fallback a widgets."""
        try:
            from doremi.ui.screens.home_qml import HomeScreenQml
            screen = HomeScreenQml(self.yt, self._play_song_sync, self._navigate_to)
            if screen.is_ok:
                logger.info("Usando isla QML para Inicio")
                return screen
            logger.warning("Isla QML Inicio no cargó; usando versión QtWidgets")
        except Exception as e:
            logger.warning(f"No se pudo crear la isla QML de Inicio: {e}")
        return None

    def _build_settings_qml(self):
        """Isla QML de Ajustes. Devuelve None si el backend QML falla → fallback a widgets."""
        try:
            from doremi.ui.screens.settings_qml import SettingsScreenQml
            screen = SettingsScreenQml(
                self.yt, self.settings,
                on_settings_changed=self._on_settings_changed,
                on_auth_changed=self._on_auth_changed,
            )
            if screen.is_ok:
                logger.info("Usando isla QML para Ajustes")
                return screen
            logger.warning("Isla QML Ajustes no cargó; usando versión QtWidgets")
        except Exception as e:
            logger.warning(f"No se pudo crear la isla QML de Ajustes: {e}")
        return None

    def _build_now_playing_qml(self):
        """Isla QML de Now Playing. Devuelve None si el backend QML falla → fallback a widgets."""
        try:
            from doremi.ui.screens.now_playing_qml import NowPlayingScreenQml
            screen = NowPlayingScreenQml(
                self.player, self.queue, self.yt, self._play_queue_item,
                self.settings, on_back=self._go_back,
            )
            if screen.is_ok:
                logger.info("Usando isla QML para Now Playing")
                return screen
            logger.warning("Isla QML Now Playing no cargó; usando versión QtWidgets")
        except Exception as e:
            logger.warning(f"No se pudo crear la isla QML de Now Playing: {e}")
        return None

    def _build_notifications_qml(self):
        """Isla QML del panel de notificaciones; None → fallback a widgets."""
        try:
            from doremi.ui.widgets.notification_panel_qml import NotificationPanelQml
            panel = NotificationPanelQml(self)
            if panel.is_ok:
                logger.info("Usando isla QML para notificaciones")
                return panel
            logger.warning("Isla QML notificaciones no cargó; usando versión QtWidgets")
        except Exception as e:
            logger.warning(f"No se pudo crear la isla QML de notificaciones: {e}")
        return None

    def _build_stats_qml(self):
        """Isla QML de Estadísticas. Devuelve None si el backend QML falla → fallback a widgets."""
        try:
            from doremi.ui.screens.stats_qml import StatsScreenQml
            screen = StatsScreenQml(self.yt, self._play_song_sync)
            if screen.is_ok:
                logger.info("Usando isla QML para Estadísticas")
                return screen
            logger.warning("Isla QML Estadísticas no cargó; usando versión QtWidgets")
        except Exception as e:
            logger.warning(f"No se pudo crear la isla QML de Estadísticas: {e}")
        return None

    def _build_playlist_qml(self):
        """Isla QML de Playlist. Devuelve None si el backend QML falla → fallback a widgets."""
        try:
            from doremi.ui.screens.playlist_qml import PlaylistScreenQml
            screen = PlaylistScreenQml(self.yt, self._play_song_sync, self._play_local_playlist, on_back=self._go_back)
            if screen.is_ok:
                logger.info("Usando isla QML para Playlist")
                return screen
            logger.warning("Isla QML Playlist no cargó; usando versión QtWidgets")
        except Exception as e:
            logger.warning(f"No se pudo crear la isla QML de Playlist: {e}")
        return None

    def _build_album_qml(self):
        """Isla QML de Álbum. Devuelve None si el backend QML falla → fallback a widgets."""
        try:
            from doremi.ui.screens.album_qml import AlbumScreenQml
            screen = AlbumScreenQml(self.yt, self._play_song_sync, on_back=self._go_back)
            if screen.is_ok:
                logger.info("Usando isla QML para Álbum")
                return screen
            logger.warning("Isla QML Álbum no cargó; usando versión QtWidgets")
        except Exception as e:
            logger.warning(f"No se pudo crear la isla QML de Álbum: {e}")
        return None

    def _build_artist_qml(self):
        """Isla QML de Artista. Devuelve None si el backend QML falla → fallback a widgets."""
        try:
            from doremi.ui.screens.artist_qml import ArtistScreenQml
            screen = ArtistScreenQml(self.yt, self._play_song_sync, self._navigate_to, on_back=self._go_back)
            if screen.is_ok:
                logger.info("Usando isla QML para Artista")
                return screen
            logger.warning("Isla QML Artista no cargó; usando versión QtWidgets")
        except Exception as e:
            logger.warning(f"No se pudo crear la isla QML de Artista: {e}")
        return None

    def _build_downloads_qml(self):
        """Isla QML de Descargas. Devuelve None si el backend QML falla → fallback a widgets."""
        try:
            from doremi.ui.screens.downloads_qml import DownloadsScreenQml
            screen = DownloadsScreenQml(self.extractor, self._play_local_wrapper, self._play_local_playlist, self._navigate_to)
            if screen.is_ok:
                logger.info("Usando isla QML para Descargas")
                return screen
            logger.warning("Isla QML Descargas no cargó; usando versión QtWidgets")
        except Exception as e:
            logger.warning(f"No se pudo crear la isla QML de Descargas: {e}")
        return None

    def _build_search_qml(self):
        """Isla QML de Búsqueda. Devuelve None si el backend QML falla → fallback a widgets."""
        try:
            from doremi.ui.screens.search_qml import SearchScreenQml
            screen = SearchScreenQml(self.yt, self._play_song_sync, self._navigate_to)
            if screen.is_ok:
                logger.info("Usando isla QML para Búsqueda")
                return screen
            logger.warning("Isla QML Búsqueda no cargó; usando versión QtWidgets")
        except Exception as e:
            logger.warning(f"No se pudo crear la isla QML de Búsqueda: {e}")
        return None

    def _build_library_qml(self):
        """Isla QML de Biblioteca. Devuelve None si el backend QML falla → fallback a widgets."""
        try:
            from doremi.ui.screens.library_qml import LibraryScreenQml
            screen = LibraryScreenQml(self.yt, self._play_song_sync, self._navigate_to)
            if screen.is_ok:
                logger.info("Usando isla QML para Biblioteca")
                return screen
            logger.warning("Isla QML Biblioteca no cargó; usando versión QtWidgets")
        except Exception as e:
            logger.warning(f"No se pudo crear la isla QML de Biblioteca: {e}")
        return None

    def _build_history_qml(self):
        """Isla QML del Historial. Devuelve None si el backend QML falla → fallback a widgets."""
        try:
            from doremi.ui.screens.history_qml import HistoryScreenQml
            screen = HistoryScreenQml(self.yt, self._play_song_sync)
            if screen.is_ok:
                logger.info("Usando isla QML para Historial")
                return screen
            logger.warning("Isla QML Historial no cargó; usando versión QtWidgets")
        except Exception as e:
            logger.warning(f"No se pudo crear la isla QML de Historial: {e}")
        return None

    def _reset_lastfm_scrobble_state(self, item: QueueItem) -> None:
        self.integrations_controller.reset_lastfm_scrobble_state(item)

    async def _handle_playback_failure(self, item: QueueItem, message: str) -> None:
        await self.integrations_controller.handle_playback_failure(item, message)

    def _persist_queue_playback_settings(self) -> None:
        self.integrations_controller.persist_queue_playback_settings()

    def _track_task(self, task: asyncio.Task) -> None:
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

        def _log_task_result(t: asyncio.Task):
            try:
                t.result()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.exception(f"Unhandled exception in background task: {e}")
        task.add_done_callback(_log_task_result)


    def _run_async(self, coro) -> asyncio.Task:
        if self._loop:
            task = self._loop.create_task(coro)
        else:
            task = asyncio.ensure_future(coro)
        self._track_task(task)
        return task

    def _play_song_sync(
        self,
        video_id: str,
        title: str,
        artist: str,
        album: str,
        duration_ms: int,
        thumbnail_url: str,
        queue_items: list[QueueItem] | None = None,
        queue_index: int = 0,
    ) -> None:
        self._run_async(
            self.playback_controller._play_song(
                video_id,
                title,
                artist,
                album,
                duration_ms,
                thumbnail_url,
                queue_items,
                queue_index,
            )
        )

    def _on_download_requested(self, video_id, title, artist, thumb_url):
        self.download_controller.on_download_requested(video_id, title, artist, thumb_url)

    def _on_download_finished(self, video_id, file_path):
        self.download_controller.on_download_finished(video_id, file_path)

    def _on_download_playlist_requested(self, playlist_id, title, thumbnail_url):
        self.download_controller.on_download_playlist_requested(playlist_id, title, thumbnail_url)

    def _on_download_album_requested(self, browse_id, title, thumbnail_url):
        self.download_controller.on_download_album_requested(browse_id, title, thumbnail_url)

    def _on_download_error(self, video_id, error):
        self.download_controller.on_download_error(video_id, error)

    def _on_delete_download_requested(self, video_id: str):
        self.download_controller.on_delete_download_requested(video_id)

    def _on_delete_playlist_requested(self, playlist_id: str):
        self.download_controller.on_delete_playlist_requested(playlist_id)

    def show_notification(self, message: str, kind: str = "info", action_text: str = None, action_callback = None):
        if hasattr(self, "search_bar"):
            self.search_bar.notif_dropdown.add_custom_notification(message, kind)
        from doremi.ui.widgets.toast import ToastNotification
        ToastNotification.show(self, message, kind, action_text, action_callback)

    def _on_play_next_requested(self, video_id, title, artist, thumb_url):
        self.queue_controller.on_play_next_requested(video_id, title, artist, thumb_url)

    def _on_add_to_queue_requested(self, video_id, title, artist, thumb_url):
        self.queue_controller.on_add_to_queue_requested(video_id, title, artist, thumb_url)

    def _on_add_to_playlist_requested(self, video_id, title):
        self.queue_controller.on_add_to_playlist_requested(video_id, title)

    def _on_like_requested(self, video_id, btn_like):
        self.queue_controller.on_like_requested(video_id, btn_like)

    def _cleanup_on_close(self) -> None:
        # Synchronous cleanup for immediate Qt resources
        for task in list(self._pending_tasks):
            if not task.done():
                task.cancel()
        if self._init_task and not self._init_task.done():
            self._init_task.cancel()
        self.notification_service.stop()
        if self.mpris:
            self.mpris.stop()
        # Network monitor and download manager async cleanup will be handled in async_shutdown

    async def async_shutdown(self) -> None:
        """Async cleanup for graceful shutdown - call after event loop is still running."""
        # Wait for all pending tasks to complete/cancel
        if self._pending_tasks:
            try:
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
            except Exception as e:
                logger.error(f"Error waiting for pending tasks: {e}")
        
        if self._init_task and not self._init_task.done():
            self._init_task.cancel()
            try:
                await self._init_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error waiting for init task: {e}")
        
        # Stop network monitor
        if hasattr(self, 'network_monitor') and self.network_monitor:
            try:
                await self.network_monitor.stop()
            except Exception as e:
                logger.error(f"Error stopping network monitor: {e}")
        
        # Stop download manager gracefully
        if hasattr(self, 'download_manager') and self.download_manager:
            try:
                await self.download_manager.async_stop()
            except Exception as e:
                logger.error(f"Error stopping download manager: {e}")
        
        # Stop Discord RPC
        if self.discord:
            try:
                await self.discord.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting Discord RPC: {e}")
        
        # Release player resources
        if hasattr(self, 'player') and self.player:
            self.player.release()

    # --- PlaybackSessionManager thin delegating wrappers ---
    async def _initialize(self) -> None:
        return await self.session_manager.initialize()

    def _save_playback_session(self) -> None:
        self.session_manager.save_playback_session()

    async def _check_updates(self) -> None:
        await self.session_manager.check_updates()

    # --- NavigationController thin delegating wrappers ---
    # The real implementations live in NavigationController. These thin wrappers
    # preserve existing signal connections and external callers (which reference
    # self._navigate / self._navigate_to / self._on_auth_changed / ... by name),
    # including IntegrationsController's back-references to MainWindow.

    async def _navigate(self, path: str) -> None:
        await self.navigation_controller.navigate(path)

    def _navigate_to(self, path: str) -> None:
        self.navigation_controller.navigate_to(path)

    def _should_show_offline_state(self, route: str) -> bool:
        return self.navigation_controller.should_show_offline_state(route)

    def _show_offline_state(self, route: str) -> None:
        self.navigation_controller.show_offline_state(route)

    async def _load_screen(self, route: str) -> None:
        await self.navigation_controller.load_screen(route)

    def resolve_and_navigate_artist(self, artist_name: str) -> None:
        self.navigation_controller.resolve_and_navigate_artist(artist_name)

    def resolve_and_navigate_album(self, album_name: str) -> None:
        self.navigation_controller.resolve_and_navigate_album(album_name)

    def _on_search_submitted(self, query: str) -> None:
        self.navigation_controller.on_search_submitted(query)

    def _show_login(self) -> None:
        self.navigation_controller.show_login()

    def _on_web_login_success(self, avatar_url: str) -> None:
        self.navigation_controller.on_web_login_success(avatar_url)

    def _on_auth_changed(self, is_authenticated: bool, avatar_url: str = "") -> None:
        self.navigation_controller.on_auth_changed(is_authenticated, avatar_url)

    # --- PlaybackController thin delegating wrappers ---
    # The real implementations live in PlaybackController. These thin wrappers
    # preserve existing signal connections and screen callbacks (which reference
    # self._on_play_pause / self._go_back / ... by name).

    def _on_play_pause(self) -> None:
        self.playback_controller._on_play_pause()

    def _on_next(self) -> None:
        self.playback_controller._on_next()

    def _on_prev(self) -> None:
        self.playback_controller._on_prev()

    def _on_seek(self, position_ms: int) -> None:
        self.playback_controller._on_seek(position_ms)

    def _show_full_player(self) -> None:
        self.playback_controller._show_full_player()

    def _go_back(self) -> None:
        self.playback_controller._go_back()

    def _play_local_wrapper(self, path: str, metadata: dict) -> None:
        self.playback_controller._play_local_wrapper(path, metadata)

    def _play_local_playlist(self, tracks_metadata: list[dict], start_index: int = 0) -> None:
        self.download_controller.play_local_playlist(tracks_metadata, start_index)

    def _play_queue_item(self, index: int) -> None:
        self.playback_controller._play_queue_item(index)

    def _on_queue_move_requested(self, from_index: int, to_index: int) -> None:
        self.playback_controller._on_queue_move_requested(from_index, to_index)

    def _on_settings_changed(self, settings: AppSettings) -> None:
        self.settings_controller.on_settings_changed(settings)

    def _on_sleep_timer_expired(self) -> None:
        logger.info("Sleep timer expired! Pausing music player...")
        self._run_async(self.player.pause())
        self.statusBar().showMessage("Temporizador de apagado finalizado. Doremi en pausa.", 5000)
        
        # Reset the sleep timer in settings and notify
        self.settings.player.sleep_timer_minutes = 0
        self._on_settings_changed(self.settings)

        # Refresh PlayerSettingsScreen combobox dynamically if it's currently loaded
        try:
            from doremi.ui.screens.settings.player_settings import PlayerSettingsScreen
            player_settings_page = self.settings_screen.stack.findChild(PlayerSettingsScreen)
            if player_settings_page:
                player_settings_page.update_fields()
        except Exception as e:
            logger.debug(f"Failed to refresh settings page fields: {e}")

    def _show_and_activate(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_tray_quit(self) -> None:
        self._force_close = True
        self.close()

    def closeEvent(self, event) -> None:
        self._save_playback_session()
        self._save_window_state()
        if getattr(self.settings.player, "minimize_to_tray", True) and not getattr(self, "_force_close", False) and hasattr(self, "tray") and self.tray.isVisible():
            self.hide()
            event.ignore()
        else:
            active_downloads = getattr(self.download_manager, "active_count", 0)
            if active_downloads > 0:
                result = QMessageBox.question(
                    self,
                    "Descargas activas",
                    f"Hay {active_downloads} descargas en curso o en cola. ¿Salir de todos modos?",
                    QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
                    QMessageBox.StandardButton.Cancel,
                )
                if result != QMessageBox.StandardButton.Yes:
                    event.ignore()
                    return
            # Actual resource cleanup is done in async_shutdown() during app quit
            # Just handle UI cleanup here
            if hasattr(self, "tray") and self.tray:
                self.tray.hide()
            event.accept()
