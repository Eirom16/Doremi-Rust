import asyncio
import json

from loguru import logger

from doremi.api.youtube_music import YouTubeMusicClient
from doremi.config.paths import AppDirs


class NavigationController:
    """Specialized controller for routing and navigation.

    Owns the navigation/routing logic previously living in MainWindow's god
    object: route parsing, offline-state handling, deep-link resolution (artist/
    album), login flow, auth-state propagation to screens and search submission.

    ``main_window`` is the back-reference to MainWindow. All shared state
    (``_current_route``, ``_offline_blocked_path``, ``_offline_state_index``,
    ``_current_nav_task``, ``_nav_history``) and UI objects are accessed through
    ``self.main_window`` rather than cached, because MainWindow finishes building
    them after this controller is constructed.

    ``run_async`` is a callable (MainWindow._run_async) used to launch coroutines
    as asyncio tasks.
    """

    def __init__(self, main_window, run_async):
        self.main_window = main_window
        self.run_async = run_async

    async def navigate(self, path: str) -> None:
        # Parse route and query
        route = path
        query = ""
        if "?" in path:
            route, query = path.split("?", 1)

        self.main_window._current_route = route
        if self.should_show_offline_state(route):
            self.main_window._offline_blocked_path = path
            self.show_offline_state(route)
            return
        if route not in self.main_window.ONLINE_ROUTES:
            self.main_window._offline_blocked_path = None

        if route != "search":
            self.main_window.search_bar.clear_query()

        index = self.main_window.ROUTES.get(route, 0)
        self.set_stack_index(index)
        set_active = getattr(self.main_window.sidebar, "set_active", None)
        if callable(set_active):
            set_active(route)

        # Wait for the FadeStackedWidget animation (260ms) to complete before blocking thread with UI updates
        await asyncio.sleep(0.3)
        await self.load_screen_with_query(route, query)

    def should_show_offline_state(self, route: str) -> bool:
        return (
            route in self.main_window.ONLINE_ROUTES
            and hasattr(self.main_window, "network_monitor")
            and not self.main_window.network_monitor.is_connected
        )

    def show_offline_state(self, route: str) -> None:
        self.main_window._current_route = route
        self.set_stack_index(self.main_window._offline_state_index)

    def resolve_and_navigate_artist(self, artist_name: str) -> None:
        """Dynamically searches for the artist by name and navigates to their profile."""
        if not artist_name:
            return

        async def _resolve_task():
            try:
                results = await self.main_window.yt.search(artist_name, filter="artists")
                if results and len(results) > 0:
                    artist_id = results[0].get("browseId")
                    if artist_id:
                        self.navigate_to(f"artist?id={artist_id}")
                        return
                # Fallback to search screen if no ID found
                self.navigate_to(f"search?query={artist_name}")
            except Exception as e:
                logger.error(f"Failed to resolve artist '{artist_name}': {e}")
                self.navigate_to(f"search?query={artist_name}")

        asyncio.create_task(_resolve_task())

    def resolve_and_navigate_album(self, album_name: str) -> None:
        if not album_name:
            return

        async def _resolve_task():
            try:
                results = await self.main_window.yt.search(album_name, filter="albums")
                if results:
                    album_id = results[0].get("browseId")
                    if album_id:
                        self.navigate_to(f"album?id={album_id}")
                        return
                self.navigate_to(f"search?query={album_name}")
            except Exception as e:
                logger.error(f"Failed to resolve album '{album_name}': {e}")
                self.navigate_to(f"search?query={album_name}")

        asyncio.create_task(_resolve_task())

    def navigate_to(self, path: str) -> None:
        if (
            hasattr(self.main_window, "_current_nav_task")
            and self.main_window._current_nav_task
            and not self.main_window._current_nav_task.done()
        ):
            self.main_window._current_nav_task.cancel()
        self.main_window._current_nav_task = self.run_async(self.navigate(path))

    async def load_screen_with_query(self, route: str, query: str) -> None:
        if route == "playlist" and "id=" in query:
            playlist_id = query.split("=", 1)[1]
            await self.main_window.playlist_screen.load(playlist_id)
        elif route == "album" and "id=" in query:
            album_id = query.split("=", 1)[1]
            await self.main_window.album_screen.load(album_id)
        elif route == "podcast" and "id=" in query:
            podcast_id = query.split("=", 1)[1]
            await self.main_window.album_screen.load(podcast_id)
        elif route == "artist" and "id=" in query:
            artist_id = query.split("=", 1)[1]
            await self.main_window.artist_screen.load(artist_id)
        elif route == "search" and "query=" in query:
            query_param = query.split("=", 1)[1]
            self.main_window.search_bar.set_query(query_param, fetch=False)
            await self.main_window.search_screen.search(query_param)
        elif route == "library" and query.startswith("tab="):
            tab = query.split("=", 1)[1]
            self.main_window.library_screen.select_tab(tab)
        else:
            await self.load_screen(route)

    def show_login(self) -> None:
        if not self.main_window.yt or not self.main_window.yt.is_authenticated:
            from doremi.ui.dialogs.login_dialog import WebLoginDialog
            dialog = WebLoginDialog(self.main_window)
            dialog.login_successful.connect(self.on_web_login_success)
            dialog.exec()
        else:
            self.navigate_to("settings")

    def on_web_login_success(self, avatar_url: str) -> None:
        self.on_auth_changed(True, avatar_url)
        self.navigate_to("home")

    def on_auth_changed(self, is_authenticated: bool, avatar_url: str = "") -> None:
        if is_authenticated:
            self.main_window.notification_service.start()
            self.main_window.yt = YouTubeMusicClient(self.main_window.settings)
            self.update_screens_yt_client()

            name = "YouTube Music"

            # Try to get account info from ytmusicapi
            try:
                if (
                    self.main_window.yt.is_authenticated
                    and hasattr(self.main_window.yt, "_ytmusicapi")
                    and self.main_window.yt._ytmusicapi
                ):
                    account_info = self.main_window.yt._ytmusicapi.get_account_info()
                    name = account_info.get("accountName", "") or name
                    if not avatar_url:
                        avatar_url = account_info.get("accountPhotoUrl", "")
                    # Save updated profile
                    profile_file = AppDirs.config / "user_profile.json"
                    with open(profile_file, "w") as f:
                        json.dump({"name": name, "avatar_url": avatar_url}, f, indent=4)
            except Exception as e:
                logger.debug(f"Could not fetch account info: {e}")

            # Fallback: read from saved profile
            if name == "YouTube Music":
                profile_file = AppDirs.config / "user_profile.json"
                if profile_file.exists():
                    try:
                        with open(profile_file, "r") as f:
                            data = json.load(f)
                            name = data.get("name", "YouTube Music") or "YouTube Music"
                            if not avatar_url:
                                avatar_url = data.get("avatar_url", "")
                    except Exception as e:
                        logger.debug(f"Could not read saved user profile after login: {e}")

            self.main_window.search_bar.update_profile(True, name, avatar_url)
            self.run_async(self.refresh_sidebar_playlists())
            logger.info(f"Post-login: yt client propagated, name={name}, avatar={avatar_url}")

            # Auto-refresh home and library if we just logged in
            self.main_window.home_screen.force_reload()
            self.run_async(self.main_window.library_screen.load())
        else:
            self.main_window.notification_service.stop()
            # Delete user profile file on logout so it's clean
            profile_file = AppDirs.config / "user_profile.json"
            if profile_file.exists():
                try:
                    profile_file.unlink()
                except Exception as e:
                    logger.warning(f"Could not delete saved user profile on logout: {e}")

            self.main_window.yt = YouTubeMusicClient(self.main_window.settings)
            self.update_screens_yt_client()
            self.main_window.search_bar.update_profile(False)
            self.main_window.sidebar.set_playlists([])
            logger.info("Auth changed (logout): yt client reset and sidebar updated")

            # Auto-refresh home and library for unauthenticated session
            self.main_window.home_screen.force_reload()
            self.run_async(self.main_window.library_screen.load())

    async def refresh_sidebar_playlists(self) -> None:
        """Carga las playlists recientes para los accesos rápidos del lateral."""
        if not self.main_window.yt or not self.main_window.yt.is_authenticated:
            self.main_window.sidebar.set_playlists([])
            return
        from doremi.ui.screens.library_data import gather_library_playlists

        playlists = await gather_library_playlists(self.main_window.yt)
        self.main_window.sidebar.set_playlists(playlists[:4])

    def update_screens_yt_client(self) -> None:
        """Propagate the current yt client reference to all screens that use it."""
        self.main_window.search_bar.yt = self.main_window.yt
        for screen in [
            self.main_window.home_screen,
            self.main_window.library_screen,
            self.main_window.playlist_screen,
            self.main_window.album_screen,
            self.main_window.artist_screen,
            self.main_window.search_screen,
            self.main_window.history_screen,
            self.main_window.settings_screen,
            self.main_window.stats_screen,
        ]:
            screen.yt = self.main_window.yt

    def on_search_submitted(self, query: str) -> None:
        """Called when user presses Enter or picks a suggestion."""
        if query:
            if "?" in query:
                self.navigate_to(query)
                return
            self.navigate_to(f"search?query={query}")

    def set_stack_index(self, index: int) -> None:
        current = self.main_window.stack.currentIndex()
        if current != index:
            self.main_window._nav_history.append(current)
            # Keep history bounded
            if len(self.main_window._nav_history) > 30:
                self.main_window._nav_history = self.main_window._nav_history[-20:]
        if hasattr(self.main_window.stack, "setCurrentIndexAnimated"):
            self.main_window.stack.setCurrentIndexAnimated(index)
        else:
            self.main_window.stack.setCurrentIndex(index)
        # El mini-player NO debe solapar la pantalla completa de Now Playing
        # (visualmente parece duplicado: mismos controles dos veces)
        mp = getattr(self.main_window, "mini_player", None)
        if mp is not None:
            np_index = self.main_window.ROUTES.get("now_playing", -1)
            is_now_playing = (index == np_index)
            if is_now_playing:
                mp.hide()
                from doremi.ui.theme_bridge import theme_bridge
                theme_bridge().set_mini_player_visible(False)
            else:
                if getattr(mp, "_is_visible", True):
                    mp.show()
                    from doremi.ui.theme_bridge import theme_bridge
                    theme_bridge().set_mini_player_visible(True)
                    self.main_window._position_mini_player()
                    mp.raise_()
                    mp.update()
        # Update mini player expand icon based on whether we're on now_playing
        self.main_window.playback_controller._update_expand_icon()

    async def load_screen(self, route: str) -> None:
        screens = {
            "home": self.main_window.home_screen,
            "library": self.main_window.library_screen,
            "history": self.main_window.history_screen,
            "stats": self.main_window.stats_screen,
            "search": self.main_window.search_screen,
            "downloads": self.main_window.downloads_screen,
        }
        screen = screens.get(route)
        if screen and hasattr(screen, "load"):
            await screen.load()
