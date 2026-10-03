import asyncio
import json
from urllib.parse import parse_qs, urlencode, urlsplit

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
        # Artist/album resolution is a separate network request from route
        # loading.  Keep an explicit intent token so a slow response cannot
        # navigate after the user has chosen a newer destination.
        self._resolution_generation = 0
        self._resolution_task: asyncio.Task | None = None
        self._pin_lock = asyncio.Lock()
        from doremi.services.view_state import ViewStateStore
        self.view_states = ViewStateStore()

    @staticmethod
    def _parse_path(path: str) -> tuple[str, dict[str, str]]:
        """Parse an internal route without treating query text as a route.

        Internal navigation is deliberately URL-shaped.  ``parse_qs`` handles
        encoded separators, Unicode and repeated parameters correctly, unlike
        splitting strings on ``?`` and ``=``.
        """
        parsed = urlsplit((path or "").strip())
        route = parsed.path.strip("/")
        params = {
            key: values[-1]
            for key, values in parse_qs(parsed.query, keep_blank_values=True).items()
            if values
        }
        return route, params

    @staticmethod
    def _path_for(route: str, params: dict[str, str]) -> str:
        """Return the canonical form used for route history and sidebar state."""
        return f"{route}?{urlencode(params)}" if params else route

    async def navigate(self, path: str, *, record_history: bool = True) -> None:
        route, params = self._parse_path(path)
        # ``podcast`` intentionally reuses the album screen and remains a
        # supported deep-link even in lightweight hosts that only declare the
        # concrete stack routes.
        known_routes = set(self.main_window.ROUTES) | {"podcast"}
        if route not in known_routes:
            logger.warning(f"Ignoring unknown internal route: {path!r}")
            route, params = "home", {}
        current_path = getattr(self.main_window, "_current_path", "")
        if not isinstance(current_path, str) or not current_path:
            current_path = getattr(self.main_window, "_current_route", "home")
        if not isinstance(current_path, str) or not current_path:
            current_path = "home"
        target_path = self._path_for(route, {k: v for k, v in params.items() if k not in {"resume", "position", "next", "autoplay"}})
        host = getattr(self.main_window, "main_shell", None)
        if host is not None and hasattr(host, "capture_view_state"):
            self.view_states.save(current_path, host.capture_view_state())
        if record_history and current_path and current_path != target_path:
            self.main_window._nav_history.append(current_path)
            # Keep history bounded without losing the most recent routes.
            if len(self.main_window._nav_history) > 30:
                self.main_window._nav_history = self.main_window._nav_history[-20:]

        self.main_window._current_path = target_path
        self.main_window._current_route = route
        local_collection = route == "playlist" and params.get("id", "").startswith(("smart:", "local_", "local-list:", "session:"))
        if self.should_show_offline_state(route) and not local_collection:
            self.main_window._offline_blocked_path = target_path
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
            set_active(target_path)

        await self.load_screen_with_query(route, params)
        if host is not None and hasattr(host, "restore_view_state"):
            host.restore_view_state(self.view_states.get(target_path))
        if params.get("resume") and target_path == self.main_window._current_path:
            await self._resume_collection(route, params)
        elif params.get("autoplay") in {"play", "shuffle"} and target_path == self.main_window._current_path:
            screen = getattr(self.main_window, f"{'album' if route == 'podcast' else route}_screen", None)
            vm = getattr(screen, "_vm", None)
            method = getattr(vm, "play_shuffle" if params["autoplay"] == "shuffle" else "play_all", None)
            if callable(method) and getattr(vm, "found", True) and not getattr(vm, "loading", False) and not getattr(vm, "errorText", ""):
                method()

    async def _resume_collection(self, route, params):
        from doremi.audio.queue import QueueItem
        from doremi.services.playback_context import playback_context
        screen = getattr(self.main_window, f"{route}_screen", None)
        vm = getattr(screen, "_vm", None)
        if vm is None or not hasattr(vm, "tracks"):
            return
        tracks = vm.tracks.all_items()
        index = next((i for i, t in enumerate(tracks) if t.get("videoId") == params["resume"]), None)
        if index is None:
            return
        if params.get("next") == "1":
            if index + 1 >= len(tracks):
                return
            index += 1
        context = playback_context(self.main_window)
        items = [QueueItem(t["videoId"], t.get("title", ""), t.get("artist", ""), t.get("album", ""),
                           t.get("duration_ms", 0), t.get("thumbnail_url", ""),
                           is_local=bool(t.get("local_path")), local_path=t.get("local_path"), **context) for t in tracks]
        current = items[index]
        await self.main_window.playback_controller._play_song(current.video_id, current.title, current.artist,
            current.album, current.duration_ms, current.thumbnail_url, items, index)
        try:
            position = max(0, int(params.get("position", 0)))
        except ValueError:
            position = 0
        if position and self.main_window.queue.current is current:
            await self.main_window.player.seek(min(position, current.duration_ms or position))

    def should_show_offline_state(self, route: str) -> bool:
        return (
            route in self.main_window.ONLINE_ROUTES and route not in {"library", "search"}
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

        self._resolution_generation += 1
        generation = self._resolution_generation
        if self._resolution_task and not self._resolution_task.done():
            self._resolution_task.cancel()
        current_nav = getattr(self.main_window, "_current_nav_task", None)
        if current_nav and not current_nav.done():
            current_nav.cancel()

        async def _resolve_task():
            try:
                results = await self.main_window.yt.search(artist_name, filter="artists")
                if generation != self._resolution_generation:
                    return
                if results and len(results) > 0:
                    artist_id = results[0].get("browseId")
                    if artist_id:
                        self.navigate_to(f"artist?id={artist_id}")
                        return
                # Fallback to search screen if no ID found
                self.navigate_to(f"search?query={artist_name}")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if generation != self._resolution_generation:
                    return
                logger.error(f"Failed to resolve artist '{artist_name}': {e}")
                self.navigate_to(f"search?query={artist_name}")

        self._resolution_task = asyncio.create_task(_resolve_task())

    def resolve_and_navigate_album(self, album_name: str) -> None:
        if not album_name:
            return

        self._resolution_generation += 1
        generation = self._resolution_generation
        if self._resolution_task and not self._resolution_task.done():
            self._resolution_task.cancel()
        current_nav = getattr(self.main_window, "_current_nav_task", None)
        if current_nav and not current_nav.done():
            current_nav.cancel()

        async def _resolve_task():
            try:
                results = await self.main_window.yt.search(album_name, filter="albums")
                if generation != self._resolution_generation:
                    return
                if results:
                    album_id = results[0].get("browseId")
                    if album_id:
                        self.navigate_to(f"album?id={album_id}")
                        return
                self.navigate_to(f"search?query={album_name}")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if generation != self._resolution_generation:
                    return
                logger.error(f"Failed to resolve album '{album_name}': {e}")
                self.navigate_to(f"search?query={album_name}")

        self._resolution_task = asyncio.create_task(_resolve_task())

    def navigate_to(self, path: str, *, record_history: bool = True) -> None:
        # Any explicit route selection supersedes an unresolved artist/album
        # lookup.  Do not cancel a resolver here: it may be the caller that is
        # now scheduling its resolved route, but its token makes it harmless.
        self._resolution_generation += 1
        if (
            hasattr(self.main_window, "_current_nav_task")
            and self.main_window._current_nav_task
            and not self.main_window._current_nav_task.done()
        ):
            self.main_window._current_nav_task.cancel()
        self.main_window._current_nav_task = self.run_async(
            self.navigate(path, record_history=record_history)
        )

    async def load_screen_with_query(self, route: str, params: dict[str, str]) -> None:
        if route == "playlist" and params.get("id"):
            playlist_id = params["id"]
            await self.main_window.playlist_screen.load(playlist_id)
        elif route == "album" and params.get("id"):
            album_id = params["id"]
            await self.main_window.album_screen.load(album_id)
        elif route == "podcast" and params.get("id"):
            podcast_id = params["id"]
            await self.main_window.album_screen.load(podcast_id)
        elif route == "artist" and params.get("id"):
            artist_id = params["id"]
            await self.main_window.artist_screen.load(artist_id)
        elif route == "search" and "query" in params:
            query_param = params["query"]
            self.main_window.search_bar.set_query(query_param, fetch=False)
            await self.main_window.search_screen.search(query_param)
        elif route == "library" and "tab" in params:
            tab = params["tab"]
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
        from doremi.ui.screens.library_data import gather_library_playlists
        from doremi.db.experience_repository import ExperienceRepository
        playlists = await gather_library_playlists(self.main_window.yt)
        try:
            repo = ExperienceRepository()
            await repo.remember_collections(playlists)
            ranked = await repo.quick_access(limit=6)
        except Exception as exc:
            logger.warning(f"Quick access unavailable: {exc}")
            ranked = playlists[:6]
        self.main_window.sidebar.set_playlists(ranked)

    async def refresh_local_quick_access(self):
        from doremi.db.experience_repository import ExperienceRepository
        try:
            self.main_window.sidebar.set_playlists(await ExperienceRepository().quick_access(limit=6))
            self.main_window.home_screen._loaded = False
        except Exception as exc:
            logger.warning(f"Could not refresh quick access: {exc}")

    def toggle_pin(self, identity, title, thumbnail):
        self.run_async(self._toggle_pin(identity, title, thumbnail))

    async def _toggle_pin(self, identity, title, thumbnail):
        from doremi.db.experience_repository import ExperienceRepository
        from doremi.services.experience_events import events
        # Serialize toggles so a rapid second click reads the committed state.
        async with self._pin_lock:
            pinned = None
            try:
                repo = ExperienceRepository()
                pinned = await repo.is_pinned(identity)
                events.pin_changed.emit(identity, not pinned)
                await repo.set_pin(identity, title, thumbnail, pinned=not pinned)
                events.changed.emit()
                self.main_window.show_notification("Desfijada de la barra lateral" if pinned else "Fijada en la barra lateral", "success")
            except Exception as exc:
                if pinned is not None:
                    events.pin_changed.emit(identity, pinned)
                logger.warning(f"Could not pin collection: {exc}")
                self.main_window.show_notification("No se pudo cambiar el acceso fijado", "error")

    def move_pinned(self, source_route, target_route):
        async def move():
            from doremi.db.experience_repository import ExperienceRepository
            from doremi.services.experience_events import events
            repo = ExperienceRepository()
            routes = await repo.pinned_routes()
            if source_route not in routes or target_route not in routes:
                return
            routes.remove(source_route)
            routes.insert(routes.index(target_route), source_route)
            if await repo.reorder_pins(routes):
                events.changed.emit()
        self.run_async(move())

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
        query = (query or "").strip()
        if not query:
            return

        # Suggestions may intentionally provide one of our known routes.  A
        # normal search such as ``What Was I Made For?`` must always stay text.
        route, _ = self._parse_path(query)
        if route in self.main_window.ROUTES and route != "search":
            self.navigate_to(query)
            return
        self.navigate_to(self._path_for("search", {"query": query}))

    def set_stack_index(self, index: int) -> None:
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

    def go_back(self) -> None:
        """Restore the complete previous route, including its query parameters."""
        if not self.main_window._nav_history:
            self.navigate_to("home", record_history=False)
            return
        previous_path = self.main_window._nav_history.pop()
        self.navigate_to(previous_path, record_history=False)

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
