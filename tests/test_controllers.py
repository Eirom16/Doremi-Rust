import asyncio
import json
import os
from types import SimpleNamespace

import pytest
from unittest.mock import MagicMock, AsyncMock

# Must be set before importing any PySide6-backed module (download_controller
# imports QMessageBox at module level). Headless-friendly.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from doremi.audio.player import PlayerState
from doremi.audio.queue import PlayQueue, QueueItem, RepeatMode
from doremi.config.settings import AppSettings
from doremi.config import paths as paths_mod

from doremi.ui.controllers.navigation_controller import NavigationController
from doremi.ui.controllers.queue_controller import QueueController
from doremi.ui.controllers.download_controller import DownloadController
from doremi.ui.controllers.settings_controller import SettingsController
from doremi.ui.controllers.session_manager import PlaybackSessionManager
from doremi.ui.controllers.integrations_controller import IntegrationsController


def real_run_async(coro):
    """A real run_async that schedules coroutines on the running loop."""
    return asyncio.ensure_future(coro)


def _make_stub_mw():
    """Build a StubMainWindow: a MagicMock with fixed sub-objects so that call
    assertions on specific collaborators are deterministic (every attribute
    access returns the same cached mock)."""
    mw = MagicMock()

    # statusBar() must return a *consistent* mock so we can assert on showMessage
    status_bar = MagicMock()
    mw.statusBar = MagicMock(return_value=status_bar)
    mw._status_bar = status_bar

    screen_names = [
        "home_screen", "library_screen", "playlist_screen", "album_screen",
        "artist_screen", "search_screen", "downloads_screen", "now_playing_screen",
        "history_screen", "settings_screen", "stats_screen",
    ]
    for name in screen_names:
        screen = MagicMock()
        # load()/search() are awaited by the navigation controller
        screen.load = AsyncMock()
        screen.search = AsyncMock()
        setattr(mw, name, screen)

    mw.mini_player = MagicMock()
    mw.playback_controller = MagicMock()
    mw.download_controller = MagicMock()
    mw.queue_controller = MagicMock()
    mw.integrations_controller = MagicMock()
    mw.settings_controller = MagicMock()
    mw.navigation_controller = MagicMock()
    mw.session_manager = MagicMock()

    mw.player = MagicMock()
    mw.mpris = MagicMock()
    mw.stack = MagicMock()
    mw.search_bar = MagicMock()
    mw.sidebar = MagicMock()
    mw.theme_manager = MagicMock()
    mw.crossfade_manager = MagicMock()
    mw.sleep_timer = MagicMock()
    mw.offline_banner = MagicMock()
    mw.network_monitor = MagicMock()
    mw.yt = MagicMock()
    mw.show_notification = MagicMock()

    # Shared state accessed by controllers
    mw.queue = PlayQueue()
    mw.settings = AppSettings()

    mw.ROUTES = {
        "home": 0, "library": 1, "history": 2, "stats": 3, "search": 4,
        "downloads": 5, "album": 6, "artist": 7, "settings": 8, "playlist": 9,
    }
    mw.ONLINE_ROUTES = {"home", "library", "playlist", "album", "artist", "search"}
    mw._offline_state_index = 99
    mw._offline_blocked_path = None
    mw._current_route = None
    mw._nav_history = []
    mw._current_nav_task = None
    return mw


# ---------------------------------------------------------------------------
# NavigationController
# ---------------------------------------------------------------------------

class TestNavigation:
    def _nav(self, mw=None, connected=True):
        mw = mw or _make_stub_mw()
        mw.network_monitor.is_connected = connected
        return NavigationController(mw, real_run_async), mw

    @pytest.mark.asyncio
    async def test_navigate_album_loads_album_screen(self):
        nav, mw = self._nav()
        await nav.navigate("album?id=XYZ")
        mw.album_screen.load.assert_called_with("XYZ")

    @pytest.mark.asyncio
    async def test_navigate_podcast_loads_collection_screen(self):
        nav, mw = self._nav()
        await nav.navigate("podcast?id=MPSP123")
        mw.album_screen.load.assert_called_with("MPSP123")

    @pytest.mark.asyncio
    async def test_navigate_search_dispatches_query(self):
        nav, mw = self._nav()
        await nav.navigate("search?query=hello")
        mw.search_screen.search.assert_called_with("hello")

    @pytest.mark.asyncio
    async def test_search_route_decodes_reserved_and_unicode_characters(self):
        nav, mw = self._nav()
        await nav.navigate("search?query=What+Was+I+Made+For%3F+%26+%F0%9F%8E%B5")
        mw.search_screen.search.assert_called_with("What Was I Made For? & 🎵")

    @pytest.mark.asyncio
    async def test_back_restores_full_deep_link_not_only_screen_index(self):
        nav, mw = self._nav()
        await nav.navigate("playlist?id=playlist-a")
        await nav.navigate("playlist?id=playlist-b")

        nav.go_back()
        await mw._current_nav_task

        assert mw._current_path == "playlist?id=playlist-a"
        assert mw._current_route == "playlist"
        assert mw._nav_history == ["home"]
        assert [call.args[0] for call in mw.playlist_screen.load.call_args_list] == [
            "playlist-a", "playlist-b", "playlist-a",
        ]

    @pytest.mark.asyncio
    async def test_question_mark_in_text_search_is_not_a_deep_link(self):
        nav, mw = self._nav()
        nav.on_search_submitted("What Was I Made For?")
        await mw._current_nav_task

        assert mw._current_path == "search?query=What+Was+I+Made+For%3F"
        mw.search_screen.search.assert_called_once_with("What Was I Made For?")

    @pytest.mark.asyncio
    async def test_navigate_library_playlist_tab_reuses_library_screen(self):
        nav, mw = self._nav()
        await nav.navigate("library?tab=playlists")
        mw.library_screen.select_tab.assert_called_once_with("playlists")
        mw.library_screen.load.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_sidebar_playlists_limits_to_four(self, monkeypatch):
        nav, mw = self._nav()
        mw.yt.is_authenticated = True

        async def gather(_yt):
            return [
                {"title": f"Playlist {i}", "navigate": f"playlist?id={i}"}
                for i in range(6)
            ]

        from doremi.ui.screens import library_data
        monkeypatch.setattr(library_data, "gather_library_playlists", gather)
        await nav.refresh_sidebar_playlists()
        shown = mw.sidebar.set_playlists.call_args.args[0]
        assert [item["title"] for item in shown] == [
            "Playlist 0", "Playlist 1", "Playlist 2", "Playlist 3",
        ]

    def test_sidebar_tracks_deep_link_path_separately_from_section(self):
        from doremi.ui.widgets.nav_sidebar_qml import NavSidebarQml

        sidebar = NavSidebarQml(lambda _: None)
        sidebar.set_active("playlist?id=playlist-a")

        assert sidebar.activeRoute == "playlist"
        assert sidebar.activePath == "playlist?id=playlist-a"

    def test_sidebar_restores_compact_state_idempotently(self):
        from doremi.ui.widgets.nav_sidebar_qml import NavSidebarQml

        sidebar = NavSidebarQml(lambda _: None)
        sidebar.set_collapsed(True)
        sidebar.set_collapsed(True)

        assert sidebar.collapsed is True
        assert sidebar.sidebar_width == sidebar.COLLAPSED_WIDTH

    @pytest.mark.asyncio
    async def test_offline_route_shows_offline_state(self):
        nav, mw = self._nav(connected=False)
        await nav.navigate("home")
        # home_screen.load must NOT have been called
        mw.home_screen.load.assert_not_called()
        # Offline bookkeeping set
        assert mw._offline_blocked_path == "home"
        assert mw._current_route == "home"
        # Stack switched to offline-state index
        mw.stack.setCurrentIndexAnimated.assert_called_with(mw._offline_state_index)

    def test_should_show_offline_state(self):
        nav, mw = self._nav(connected=False)
        # online route + offline -> True
        assert nav.should_show_offline_state("home") is True
        # offline route (downloads not in ONLINE_ROUTES) -> always False
        assert nav.should_show_offline_state("downloads") is False
        # online route + online -> False
        mw.network_monitor.is_connected = True
        assert nav.should_show_offline_state("home") is False

    @pytest.mark.asyncio
    async def test_resolve_and_navigate_artist(self, monkeypatch):
        nav, mw = self._nav()
        mw.yt.search = AsyncMock(return_value=[{"browseId": "ART123"}])

        # Capture every task spawned via asyncio.create_task (the resolve task)
        # so we can await it explicitly and avoid lingering tasks at loop close.
        spawned = []
        real_create = asyncio.create_task

        def _capture(coro, *args, **kwargs):
            task = real_create(coro, *args, **kwargs)
            spawned.append(task)
            return task

        monkeypatch.setattr(asyncio, "create_task", _capture)

        nav.resolve_and_navigate_artist("Some Artist")
        # Drain the resolve task + the nested navigate task (which sleeps 0.3s).
        for _ in range(8):
            await asyncio.sleep(0.1)
        # Explicitly await every spawned task (and the navigate task stored on
        # the stub) so nothing remains pending when the loop is torn down.
        for task in list(spawned):
            try:
                await task
            except Exception:
                pass
        if mw._current_nav_task is not None:
            try:
                await mw._current_nav_task
            except Exception:
                pass

        mw.artist_screen.load.assert_called_with("ART123")

    @pytest.mark.asyncio
    async def test_new_artist_resolution_cancels_an_older_slow_one(self):
        nav, mw = self._nav()
        first_started = asyncio.Event()
        never = asyncio.Event()

        async def search(name, filter):
            if name == "Primero":
                first_started.set()
                await never.wait()
            return [{"browseId": "SECOND"}]

        mw.yt.search = search
        nav.navigate_to = MagicMock()
        nav.resolve_and_navigate_artist("Primero")
        await first_started.wait()
        first_task = nav._resolution_task

        nav.resolve_and_navigate_artist("Segundo")
        await nav._resolution_task

        assert first_task.cancelled()
        nav.navigate_to.assert_called_once_with("artist?id=SECOND")

    @pytest.mark.asyncio
    async def test_explicit_navigation_invalidates_a_slow_artist_resolution(self):
        nav, mw = self._nav()
        started = asyncio.Event()
        release = asyncio.Event()

        async def search(name, filter):
            started.set()
            await release.wait()
            return [{"browseId": "STALE"}]

        mw.yt.search = search
        nav.resolve_and_navigate_artist("Lento")
        await started.wait()

        nav.navigate_to("downloads")
        release.set()
        await nav._resolution_task
        await mw._current_nav_task

        mw.downloads_screen.load.assert_awaited_once()
        mw.artist_screen.load.assert_not_awaited()


# ---------------------------------------------------------------------------
# QueueController
# ---------------------------------------------------------------------------

class TestQueue:
    def _qc(self, mw=None):
        mw = mw or _make_stub_mw()
        extractor = MagicMock()
        extractor.get_stream_info = AsyncMock(return_value={"duration": 180})
        qc = QueueController(mw, PlayQueue(), extractor, real_run_async)
        return qc, mw

    @pytest.mark.asyncio
    async def test_add_to_queue_appends_item(self):
        qc, mw = self._qc()
        await qc.add_to_queue_async("v1", "T", "A", "u")
        assert len(qc.queue.items) == 1
        item = qc.queue.items[0]
        assert item.video_id == "v1"
        assert item.duration_ms == 180000  # 180s -> 180000ms
        mw.playback_controller._update_queue_panel.assert_called()

    @pytest.mark.asyncio
    async def test_like_toggles_and_syncs(self, monkeypatch):
        import doremi.db.repository as repo_mod

        class StubSongRepo:
            def __init__(self):
                self.get_song = AsyncMock(return_value=None)
                self.upsert_song = AsyncMock(return_value=None)
                self.toggle_like = AsyncMock(return_value=True)
                StubSongRepo.last = self

        class StubDLRepo:
            def __init__(self):
                self.get_download = AsyncMock(return_value=None)
                StubDLRepo.last = self

        monkeypatch.setattr(repo_mod, "SongRepository", StubSongRepo)
        monkeypatch.setattr(repo_mod, "DownloadRepository", StubDLRepo)

        qc, mw = self._qc()
        # Force the offline/non-authenticated branch (no YT rate_song call)
        mw.yt.is_authenticated = False
        btn = MagicMock()
        btn.objectName = MagicMock(return_value="nowPlayingLikeBtn")

        await qc.toggle_like_async("v1", btn)

        StubSongRepo.last.toggle_like.assert_called()
        StubDLRepo.last.get_download.assert_called()
        mw.library_screen.invalidate_songs_cache.assert_called()
        # Not authenticated -> YT rate_song must NOT be called
        mw.yt.rate_song.assert_not_called()
        # now-playing branch executed
        mw.now_playing_screen.set_liked_state.assert_called_with(True)
        mw.playback_controller._update_queue_panel.assert_called()


# ---------------------------------------------------------------------------
# DownloadController
# ---------------------------------------------------------------------------

class TestDownload:
    def _dc(self, existing_download):
        mw = _make_stub_mw()
        dm = MagicMock()
        dm._repo = MagicMock()
        dm._repo.get_download = AsyncMock(return_value=existing_download)
        dm.add_download = MagicMock(return_value=True)
        dc = DownloadController(mw, dm, real_run_async)
        return dc, mw, dm

    @pytest.mark.asyncio
    async def test_download_requested_enqueues(self):
        dc, mw, dm = self._dc(existing_download=None)
        await dc.on_download_requested_async("v1", "T", "A", "u")
        dm.add_download.assert_called_with("v1", "T", "A", "u")
        mw._status_bar.showMessage.assert_called()
        mw.show_notification.assert_called()

    @pytest.mark.asyncio
    async def test_download_requested_dedupes(self):
        dc, mw, dm = self._dc(existing_download={"title": "T"})
        await dc.on_download_requested_async("v1", "T", "A", "u")
        dm.add_download.assert_not_called()
        mw._status_bar.showMessage.assert_called()
        mw.show_notification.assert_called()


# ---------------------------------------------------------------------------
# SettingsController
# ---------------------------------------------------------------------------

@pytest.fixture
def isolated_settings_file(monkeypatch):
    # Avoid writing an actual settings.toml to disk: stub the persist step.
    monkeypatch.setattr(AppSettings, "save", lambda self, path: None)


class TestSettings:
    def _sc(self, mw=None):
        mw = mw or _make_stub_mw()
        return SettingsController(mw, real_run_async), mw

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("isolated_settings_file")
    async def test_apply_volume_and_equalizer(self):
        sc, mw = self._sc()
        settings = AppSettings()
        settings.player.volume = 42
        settings.equalizer.enabled = True
        settings.equalizer.preamp = 0.0
        settings.equalizer.bands = [0.0] * 10
        sc.on_settings_changed(settings)
        mw.player.set_volume.assert_called_with(42)
        mw.player.apply_equalizer.assert_called_with(0.0, [0.0] * 10)
        mw.player.reset_equalizer.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("isolated_settings_file")
    async def test_equalizer_reset_when_disabled(self):
        sc, mw = self._sc()
        settings = AppSettings()
        settings.player.volume = 50
        settings.equalizer.enabled = False
        sc.on_settings_changed(settings)
        mw.player.set_volume.assert_called_with(50)
        mw.player.reset_equalizer.assert_called()
        mw.player.apply_equalizer.assert_not_called()

    @pytest.mark.usefixtures("isolated_settings_file")
    def test_disabling_offline_cache_cancels_its_current_sync(self, monkeypatch):
        from doremi.services.offline_cache import OfflineCacheManager

        sc, _ = self._sc()
        cache = MagicMock()
        monkeypatch.setattr(OfflineCacheManager, "get_instance", lambda: cache)
        settings = AppSettings()
        settings.offline.enabled = False

        sc.on_settings_changed(settings)

        cache.cancel_sync.assert_called_once_with()
        cache.enforce_limit.assert_called_once_with(settings.offline.song_limit)

    @pytest.mark.asyncio
    async def test_persisted_sleep_timer_starts_on_new_window(self):
        mw = _make_stub_mw()
        mw.settings.player.sleep_timer_minutes = 30
        mw.sleep_timer = MagicMock()
        mw.sleep_timer.is_running = False
        mw.sleep_timer.start = AsyncMock()
        scheduled = []
        controller = SettingsController(mw, scheduled.append)

        controller.restore_persisted_sleep_timer()

        assert len(scheduled) == 1
        await scheduled[0]
        mw.sleep_timer.start.assert_awaited_once_with(1800, mw._on_sleep_timer_expired)


# ---------------------------------------------------------------------------
# PlaybackSessionManager
# ---------------------------------------------------------------------------

class TestSession:
    @pytest.mark.asyncio
    async def test_initialize_restores_queue_but_does_not_autoplay_by_default(self):
        mw = _make_stub_mw()
        mw._navigate = AsyncMock()
        mw.settings.player.resume_on_startup = False
        sm = PlaybackSessionManager(mw, real_run_async)
        sm.restore_playback_session = MagicMock()

        await sm.initialize()

        mw._navigate.assert_awaited_once_with("home")
        sm.restore_playback_session.assert_called_once()
        mw.playback_controller._update_queue_panel.assert_not_called()
        mw.mini_player.update_track_info.assert_not_called()
        mw.now_playing_screen.update_track_info.assert_not_called()

    @pytest.mark.asyncio
    async def test_initialize_restores_queue_without_autoplay_when_resume_is_off(self, tmp_path):
        mw = _make_stub_mw()
        mw._navigate = AsyncMock()
        mw.settings.player.resume_on_startup = False
        sm = PlaybackSessionManager(mw, real_run_async)
        sm._queue_state_file = tmp_path / "queue_state.json"
        sm._queue_state_file.write_text(json.dumps({
            "queue": {"items": [{
                "video_id": "saved", "title": "Guardada", "artist": "Artista",
                "album": "", "duration_ms": 1_000, "thumbnail_url": "cover",
            }]},
            "position_ms": 12_000,
        }), encoding="utf-8")

        await sm.initialize()

        assert mw.queue.current is not None
        assert mw.queue.current.video_id == "saved"
        mw.playback_controller._update_queue_panel.assert_called_once()
        # La cola se conserva, pero el arranque no muestra una canción previa
        # ni activa el miniplayer hasta que se pulse reproducir.
        mw.mini_player.update_track_info.assert_not_called()
        mw.now_playing_screen.update_track_info.assert_not_called()
        mw.playback_controller._play_current.assert_not_called()

    @pytest.mark.asyncio
    async def test_restore_playback_session(self, tmp_path):
        mw = _make_stub_mw()
        sm = PlaybackSessionManager(mw, real_run_async)

        payload = {
            "queue": {
                "items": [{
                    "video_id": "v9", "title": "T", "artist": "A",
                    "album": "", "duration_ms": 1000, "thumbnail_url": "",
                }]
            },
            "position_ms": 5000,
            "last_video_id": "v9",
        }
        state_file = tmp_path / "queue_state.json"
        state_file.write_text(json.dumps(payload), encoding="utf-8")
        sm._queue_state_file = state_file

        sm.restore_playback_session()

        assert len(mw.queue.items) == 1
        assert mw.queue.items[0].video_id == "v9"
        assert sm._resume_position_ms == 5000
        # Collaborators received the restored queue
        assert mw.mini_player.queue is mw.queue
        assert mw.now_playing_screen.queue is mw.queue
        assert mw.mpris.queue is mw.queue
        assert mw.playback_controller.queue is mw.queue
        assert mw.queue_controller.queue is mw.queue
        assert mw.integrations_controller.queue is mw.queue


# ---------------------------------------------------------------------------
# IntegrationsController (light, logic-only — no VLC/network)
# ---------------------------------------------------------------------------

class TestIntegrations:
    def test_runtime_mpris_toggle_starts_and_stops_service(self):
        from doremi.ui.controllers.integrations_controller import IntegrationsController

        mpris = MagicMock()
        main = MagicMock()
        main.playback_controller = MagicMock()
        controller = IntegrationsController(
            MagicMock(), PlayQueue(), mpris, AppSettings(), MagicMock(), lambda _: None, main
        )

        controller.reconfigure_mpris(True)
        mpris.start.assert_called_once()
        mpris.update_shuffle.assert_called_once_with(False)
        controller.reconfigure_mpris(False)
        mpris.stop.assert_called_once()

    def test_enabling_mpris_publishes_the_current_playback_snapshot(self):
        mpris = MagicMock()
        main = MagicMock()
        main.playback_controller = MagicMock()
        queue = PlayQueue()
        item = QueueItem("current", "Current", "Artist", "Album", 123_000, "cover")
        queue.add_to_end(item)
        player = SimpleNamespace(
            status=SimpleNamespace(state=PlayerState.PLAYING, position_ms=4_000, volume=73)
        )
        controller = IntegrationsController(
            player, queue, mpris, AppSettings(), MagicMock(), lambda _: None, main
        )

        controller.reconfigure_mpris(True)

        mpris.update_playback_status.assert_called_once_with("playing")
        mpris.update_position.assert_called_once_with(4_000)
        mpris.update_volume.assert_called_once_with(73)
        mpris.update_shuffle.assert_called_once_with(False)
        mpris.update_metadata.assert_called_once_with(
            "Current", "Artist", "Album", 123_000_000, "cover", "current",
        )

    @pytest.mark.asyncio
    async def test_mpris_play_and_stop_use_playback_state_boundaries(self):
        mpris = MagicMock()
        playback = SimpleNamespace(
            resume_or_start=AsyncMock(),
            stop_playback=AsyncMock(),
            _on_seek=MagicMock(),
        )
        main = MagicMock()
        main.playback_controller = playback
        main._on_play_pause = MagicMock()
        main._on_next = MagicMock()
        main._on_prev = MagicMock()
        player = SimpleNamespace(status=SimpleNamespace(position_ms=0))
        tasks = []
        controller = IntegrationsController(
            player, PlayQueue(), mpris, AppSettings(), MagicMock(),
            lambda coro: tasks.append(asyncio.create_task(coro)), main,
        )

        controller._wire_mpris_callbacks()
        mpris.on_play()
        mpris.on_stop()
        await asyncio.gather(*tasks)

        playback.resume_or_start.assert_awaited_once_with()
        playback.stop_playback.assert_awaited_once_with()

    def test_mpris_start_is_idempotent_when_dbus_is_available(self, monkeypatch):
        import doremi.system.mpris as module

        monkeypatch.setattr(module, "_DBUS_OK", True)
        player = module.MprisPlayer(MagicMock(), PlayQueue())
        player._active = True
        player.start()
        assert player._active is True

    def test_mpris_retains_complete_playback_state_while_inactive(self):
        from doremi.system.mpris import MprisPlayer

        mpris = MprisPlayer(MagicMock(), PlayQueue())
        mpris.update_playback_status("idle")
        assert mpris.playback_status == "Stopped"
        mpris.update_playback_status("paused")
        assert mpris.playback_status == "Paused"
        mpris.update_playback_status("playing")
        assert mpris.playback_status == "Playing"

    def test_mpris_receives_stopped_not_paused_when_player_is_idle(self):
        ic, mw, _, _ = self._ic()
        mw.mini_player = MagicMock()
        mw.now_playing_screen = MagicMock()
        status = SimpleNamespace(state=PlayerState.IDLE)

        ic.on_state_changed_callback(status)

        ic.mpris.update_playback_status.assert_called_once_with("idle")

    def _ic(self):
        mw = MagicMock()
        player = MagicMock()
        queue = MagicMock()
        mpris = MagicMock()
        settings = AppSettings()
        extractor = MagicMock()
        run_async = MagicMock()
        ic = IntegrationsController(
            player, queue, mpris, settings, extractor,
            run_async, mw,
        )
        return ic, mw, queue, run_async

    def test_on_track_ended_callback_advances_queue(self):
        ic, mw, queue, run_async = self._ic()
        ic.on_track_ended_callback(MagicMock())
        run_async.assert_called_once()
