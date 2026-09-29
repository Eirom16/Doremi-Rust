"""Regresiones verificables de la auditoría de septiembre de 2026."""
import asyncio
import os
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from doremi.audio.player import MusicPlayer, PlayerState
from doremi.audio.queue import PlayQueue, QueueItem, RepeatMode
from doremi.audio.listening import ListeningSession
from doremi.services.download_manager import DownloadManager, DownloadTask


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def manager(tmp_path, monkeypatch):
    from doremi.config.paths import AppDirs
    monkeypatch.setattr(type(AppDirs), "downloads", property(lambda self: tmp_path / "audio"))
    mgr = DownloadManager()
    mgr._state_file = tmp_path / "tasks.json"
    return mgr


@pytest.mark.asyncio
@pytest.mark.parametrize("action,state", [("stop", PlayerState.IDLE), ("pause", PlayerState.PAUSED)])
async def test_controls_interrupt_pending_vlc_start(action, state):
    player = MusicPlayer()
    player._player.play.return_value = 0
    task = asyncio.create_task(player.play_url("fake://audio", "a"))
    await asyncio.sleep(0)
    assert player.status.state == PlayerState.LOADING
    await asyncio.wait_for(getattr(player, action)(), 0.2)
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 0.2)
    player._on_playing(None)
    await asyncio.sleep(0)
    assert player.status.state == state
    player.release()


@pytest.mark.asyncio
async def test_stale_scheduled_vlc_event_does_not_restart_stopped_player():
    player = MusicPlayer()
    player._on_playing(None)
    await player.stop()
    await asyncio.sleep(0)
    assert player.status.state == PlayerState.IDLE
    player.release()


@pytest.mark.asyncio
async def test_resume_restarts_position_poll_even_before_cancel_delivery():
    player = MusicPlayer()
    player._poll_task = asyncio.create_task(asyncio.sleep(60))
    old = player._poll_task
    await player.pause()
    await player.resume()
    assert player._poll_task is not old
    player.release()
    await asyncio.sleep(0)


@pytest.mark.asyncio
@pytest.mark.parametrize("state_name", ["IDLE", "ERROR"])
async def test_play_control_starts_current_queue_item_when_vlc_cannot_resume(state_name):
    from doremi.audio.player import PlayerState
    from doremi.ui.controllers.playback_controller import PlaybackController

    controller = PlaybackController.__new__(PlaybackController)
    queue = PlayQueue()
    queue.add_to_end(QueueItem("first", "First", "Artist", "", 0, ""))
    controller.queue = queue
    controller.player = SimpleNamespace(
        status=SimpleNamespace(state=getattr(PlayerState, state_name)),
        _player=SimpleNamespace(is_playing=lambda: False),
        resume=AsyncMock(),
    )
    controller._play_task = None
    controller._restart_after_pause = False
    controller.crossfade_manager = SimpleNamespace(cancel=lambda: None)
    controller._play_current = AsyncMock()

    await controller._toggle_play_pause()

    controller._play_current.assert_awaited_once()
    controller.player.resume.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("state_name", ["IDLE", "ERROR"])
async def test_external_play_starts_a_queued_song_when_vlc_is_idle(state_name):
    from doremi.ui.controllers.playback_controller import PlaybackController

    controller = PlaybackController.__new__(PlaybackController)
    controller.player = SimpleNamespace(
        status=SimpleNamespace(state=getattr(PlayerState, state_name)),
        resume=AsyncMock(),
    )
    controller._play_current = AsyncMock()

    await controller.resume_or_start()

    controller._play_current.assert_awaited_once()
    controller.player.resume.assert_not_awaited()


@pytest.mark.asyncio
async def test_external_stop_finalizes_listening_before_stopping_vlc():
    from doremi.ui.controllers.playback_controller import PlaybackController

    controller = PlaybackController.__new__(PlaybackController)
    controller._current_play_id = 7
    controller._play_task = None
    controller._restart_after_pause = True
    controller.crossfade_manager = SimpleNamespace(cancel=Mock())
    controller._finalize_listening = Mock()
    controller.player = SimpleNamespace(stop=AsyncMock())

    await controller.stop_playback()

    assert controller._current_play_id == 8
    assert controller._restart_after_pause is False
    controller.crossfade_manager.cancel.assert_called_once_with()
    controller._finalize_listening.assert_called_once_with("stopped")
    controller.player.stop.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_previous_on_first_track_restarts_without_recording_a_skip():
    from doremi.ui.controllers.playback_controller import PlaybackController

    controller = PlaybackController.__new__(PlaybackController)
    controller.queue = PlayQueue()
    controller.queue.add_to_end(QueueItem("first", "First", "Artist", "", 0, ""))
    controller.player = SimpleNamespace(status=SimpleNamespace(position_ms=1_500), seek=AsyncMock())
    controller._finalize_listening = Mock()
    controller._play_current = AsyncMock()

    await controller._go_prev()

    controller.player.seek.assert_awaited_once_with(0)
    controller._finalize_listening.assert_not_called()
    controller._play_current.assert_not_awaited()


@pytest.mark.asyncio
async def test_previous_before_three_seconds_on_later_track_marks_current_as_skipped():
    from doremi.ui.controllers.playback_controller import PlaybackController

    controller = PlaybackController.__new__(PlaybackController)
    controller.queue = PlayQueue()
    controller.queue.set_queue([
        QueueItem("first", "First", "Artist", "", 0, ""),
        QueueItem("second", "Second", "Artist", "", 0, ""),
    ], start_index=1)
    controller.player = SimpleNamespace(status=SimpleNamespace(position_ms=1_500), seek=AsyncMock())
    controller._finalize_listening = Mock()
    controller._play_current = AsyncMock()

    await controller._go_prev()

    assert controller.queue.current.video_id == "first"
    controller._finalize_listening.assert_called_once_with("skipped")
    controller._play_current.assert_awaited_once()
    controller.player.seek.assert_not_awaited()


@pytest.mark.asyncio
async def test_next_on_last_track_stops_manual_playback_when_no_autoplay_exists():
    from doremi.ui.controllers.playback_controller import PlaybackController

    controller = PlaybackController.__new__(PlaybackController)
    controller.queue = PlayQueue()
    controller.queue.add_to_end(QueueItem("only", "Only", "Artist", "", 0, ""))
    controller.network_monitor = SimpleNamespace(is_connected=False)
    controller.player = SimpleNamespace(stop=AsyncMock())
    controller._finalize_listening = Mock()

    await controller._advance_queue(manual=True)

    controller._finalize_listening.assert_called_once_with("skipped")
    controller.player.stop.assert_awaited_once()


def test_repeat_one_only_repeats_on_natural_end():
    queue = PlayQueue()
    queue.set_queue([QueueItem(x, x, "", "", 0, "") for x in ("a", "b")])
    queue.repeat_mode = RepeatMode.ONE
    assert queue.advance().video_id == "a"
    assert queue.advance(ignore_repeat_one=True).video_id == "b"


def test_listening_session_records_real_time_not_media_duration_for_skip():
    item = QueueItem("song", "Song", "Artist", "", 120_000, "")
    session = ListeningSession()
    session.start(item)
    session.observe(0, 120_000, True)
    session.observe(5_000, 120_000, True)
    # A seek near the end must update completion position but not pretend the
    # skipped 100 seconds were listened.
    session.observe(110_000, 120_000, True)
    result = session.finish("skipped")

    assert result.listen_time_ms == 5_000
    assert result.completion_ratio == pytest.approx(110_000 / 120_000)
    assert result.skip_count == 0  # >=90% completion is a completion, not a skip
    assert result.completed is True
    assert result.was_played is True


def test_listening_session_marks_early_next_as_skip_not_play():
    item = QueueItem("song", "Song", "Artist", "", 180_000, "")
    session = ListeningSession()
    session.start(item)
    session.observe(0, 180_000, True)
    session.observe(4_000, 180_000, True)
    result = session.finish("skipped")

    assert result.listen_time_ms == 4_000
    assert result.skip_count == 1
    assert not result.completed
    assert not result.was_played


def test_cancel_queued_download_allows_readding(manager):
    assert manager.add_download("a", "A", "B", "")
    old = manager._tasks["a"]
    manager.cancel_download("a")
    assert manager.active_count == 0
    assert manager.add_download("a", "A", "B", "")
    assert manager._tasks["a"] is not old
    assert old._cancel_flag


def test_pause_resume_does_not_duplicate_queue_entry(manager):
    manager.add_download("a", "A", "B", "")
    manager.pause_download("a")
    manager.resume_download("a")
    assert manager._queue.qsize() == 1
    assert manager.active_count == 1


@pytest.mark.parametrize("name", ["../../escape", "/tmp/escape", "..\\escape", "%(title)s", "á" * 200])
def test_download_paths_are_confined(manager, name):
    from doremi.config.paths import AppDirs
    task = DownloadTask("a", name, name, "", "pl", name)
    output = Path(manager._output_template(task))
    assert output.resolve().is_relative_to(AppDirs.downloads.resolve())
    assert output.name.count("%") == 1
    assert len(output.name.encode()) < 255


def test_download_rejects_symlink_destination(manager, tmp_path):
    task = DownloadTask("a", "A", "B", "")
    output = Path(manager._output_template(task).replace("%(ext)s", "mp3"))
    output.symlink_to(tmp_path / "outside")
    with pytest.raises(ValueError, match="symlink"):
        manager._output_template(task)


def _slow_download(connection, url, options, convert):
    # Función de módulo importable por multiprocessing spawn; sin red ni yt-dlp.
    if os.name == "posix":
        os.setsid()
    connection.send(("progress", 1.0, "ready"))
    time.sleep(60)


@pytest.mark.asyncio
async def test_shutdown_reaps_real_download_process(manager, monkeypatch):
    import doremi.services.download_manager as module
    monkeypatch.setattr(module, "download_audio", _slow_download)
    ready = asyncio.Event()
    manager.download_progress.connect(lambda *args: ready.set())
    manager.add_download("a", "A", "B", "")
    manager.start(1)
    try:
        await asyncio.wait_for(ready.wait(), 10)
        process = manager._processes["a"]
        pid = process.pid
        await asyncio.wait_for(manager.async_stop(), 3)
        assert not manager._processes
        assert not manager._workers
        assert manager._queue.empty()
        import multiprocessing
        assert pid not in [child.pid for child in multiprocessing.active_children()]
        assert '"status": "queued"' in manager._state_file.read_text()
    finally:
        await manager.async_stop()


@pytest.mark.asyncio
async def test_failed_unlink_preserves_database_entry(tmp_path, monkeypatch):
    import doremi.db.repository as repository
    from doremi.ui.screens.downloads_data import delete_download_files, DownloadDeletionError
    good, bad = tmp_path / "good.mp3", tmp_path / "bad.mp3"
    good.write_bytes(b"audio")
    bad.write_bytes(b"audio")
    repo = SimpleNamespace(get_downloads=AsyncMock(return_value=[
        SimpleNamespace(video_id="good", file_path=str(good)),
        SimpleNamespace(video_id="bad", file_path=str(bad)),
    ]), remove_download=AsyncMock())
    monkeypatch.setattr(repository, "DownloadRepository", lambda: repo)
    unlink = Path.unlink
    def guarded(path, *args, **kwargs):
        if path == bad:
            raise PermissionError("denied")
        return unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", guarded)
    with pytest.raises(DownloadDeletionError) as failure:
        await delete_download_files(["good", "bad"])
    assert (failure.value.deleted, failure.value.failed) == (1, 1)
    repo.remove_download.assert_awaited_once_with("good")
    assert bad.exists()


@pytest.mark.asyncio
async def test_clear_all_downloads_cancels_tasks_and_clears_db_nested_and_orphan_files(tmp_path, monkeypatch):
    import doremi.db.repository as repository
    from doremi.config.paths import AppDirs
    from doremi.ui.screens.downloads_data import clear_all_downloads

    root = tmp_path / "downloads"
    managed = root / "playlist" / "song.mp3"
    orphan = root / "old" / "orphan.mp3"
    managed.parent.mkdir(parents=True)
    orphan.parent.mkdir(parents=True)
    managed.write_bytes(b"audio")
    orphan.write_bytes(b"audio")
    monkeypatch.setattr(type(AppDirs), "downloads", property(lambda self: root))

    repo = SimpleNamespace(
        get_downloads=AsyncMock(return_value=[SimpleNamespace(video_id="song", file_path=str(managed))]),
        remove_download=AsyncMock(),
    )
    monkeypatch.setattr(repository, "DownloadRepository", lambda: repo)

    class Manager:
        def __init__(self):
            self._tasks = {"active": object()}
            self.cancelled = []

        def cancel_download(self, video_id):
            self.cancelled.append(video_id)
            self._tasks.pop(video_id)

    manager = Manager()
    deleted = await clear_all_downloads(manager)

    assert manager.cancelled == ["active"]
    assert deleted == 2
    repo.remove_download.assert_awaited_once_with("song")
    assert not managed.exists()
    assert not orphan.exists()


@pytest.mark.asyncio
async def test_download_listing_reconciles_record_for_externally_deleted_file(monkeypatch):
    import doremi.db.repository as repository
    from doremi.ui.screens.downloads_data import gather_downloaded_songs

    downloads = SimpleNamespace(
        get_downloads=AsyncMock(return_value=[
            SimpleNamespace(
                video_id="gone", title="Gone", artist="Artist", file_path="/does/not/exist",
                parent_playlist_title="", thumbnail_url="",
            ),
        ]),
        remove_download=AsyncMock(),
    )
    songs = SimpleNamespace(get_liked_video_ids=AsyncMock(return_value=set()))
    monkeypatch.setattr(repository, "DownloadRepository", lambda: downloads)
    monkeypatch.setattr(repository, "SongRepository", lambda: songs)

    rows = await gather_downloaded_songs()

    assert rows == []
    downloads.remove_download.assert_awaited_once_with("gone")


@pytest.mark.asyncio
async def test_download_group_listing_reconciles_records_for_deleted_files(monkeypatch):
    import doremi.db.repository as repository
    from doremi.ui.screens.downloads_data import gather_download_groups

    downloads = SimpleNamespace(
        get_downloads=AsyncMock(return_value=[
            SimpleNamespace(
                video_id="gone", title="Gone", artist="Artist", file_path="/does/not/exist",
                parent_playlist_id="local-playlist", parent_playlist_title="Missing",
                thumbnail_url="", parent_playlist_thumbnail_url="",
            ),
        ]),
        remove_download=AsyncMock(),
    )
    monkeypatch.setattr(repository, "DownloadRepository", lambda: downloads)

    groups = await gather_download_groups("playlists")

    assert groups == []
    downloads.remove_download.assert_awaited_once_with("gone")


def test_header_button_has_a_visible_and_non_interactive_disabled_state():
    from pathlib import Path

    source = (Path(__file__).parents[1] / "src/doremi/ui/qml/Doremi/HeaderButton.qml").read_text()
    assert "opacity: enabled ? 1.0 : 0.5" in source
    assert "color: !btn.enabled ? themeBridge.colors[\"text_disabled\"]" in source
    assert "enabled: btn.enabled" in source


@pytest.mark.asyncio
async def test_search_failure_can_retry_identical_query(qapp):
    from doremi.ui.screens.search_qml import SearchScreenQml
    client = SimpleNamespace(search=AsyncMock(side_effect=[RuntimeError("offline"), []]))
    screen = SearchScreenQml(client, None)
    screen._vm.set_category("album")
    await screen.search("test")
    assert "album" not in screen._results_by_cat
    assert screen._vm.errorText
    assert not screen._vm.loading
    await screen.search("test")
    assert client.search.await_count == 2
    assert screen._results_by_cat["album"] == []
    assert not screen._vm.errorText
    screen.close()


@pytest.mark.asyncio
async def test_search_retry_ignores_cancelled_request_loading_state(qapp, monkeypatch):
    from doremi.ui.screens.search_qml import SearchScreenQml
    from doremi.ui.screens import search_data

    first_started = asyncio.Event()
    release_second = asyncio.Event()
    calls = 0

    async def gather(_client, _query, _category):
        nonlocal calls
        calls += 1
        if calls == 1:
            first_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                # A third-party request can unwind after a replacement is
                # already loading; it must not clear the new request's state.
                return []
        await release_second.wait()
        return []

    monkeypatch.setattr(search_data, "gather_search", gather)
    screen = SearchScreenQml(SimpleNamespace(), None)
    screen._current_query = "same"
    screen._vm.set_query("same")
    screen._schedule_fetch("same", "song")
    await asyncio.wait_for(first_started.wait(), 1)
    screen._schedule_fetch("same", "song")
    await asyncio.sleep(0)

    assert screen._vm.loading is True
    release_second.set()
    await screen._fetch_task
    assert screen._vm.loading is False
    screen.close()


@pytest.mark.asyncio
async def test_home_failure_has_error_state_and_retry_clears_it(qapp, monkeypatch):
    from doremi.ui.screens.home_qml import HomeScreenQml
    from doremi.ui.screens import home_data

    screen = HomeScreenQml(SimpleNamespace(), None)
    calls = 0

    async def gather(_client):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("offline")
        return {"greeting": "Hola", "spotlight": [], "tiles": [], "horizontal": [], "songs": []}

    monkeypatch.setattr(home_data, "gather_home", gather)
    await screen.load()
    assert screen._vm.errorText
    assert not screen._loaded

    screen.force_reload()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert screen._vm.errorText == ""
    assert screen._loaded


@pytest.mark.asyncio
async def test_home_reload_ignores_cancelled_response_state(qapp, monkeypatch):
    from doremi.ui.screens.home_qml import HomeScreenQml
    from doremi.ui.screens import home_data

    first_started = asyncio.Event()
    release_second = asyncio.Event()
    calls = 0

    async def gather(_client):
        nonlocal calls
        calls += 1
        if calls == 1:
            first_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                return {"greeting": "old", "spotlight": [], "tiles": [], "horizontal": [], "songs": []}
        await release_second.wait()
        return {"greeting": "new", "spotlight": [], "tiles": [], "horizontal": [], "songs": []}

    monkeypatch.setattr(home_data, "gather_home", gather)
    screen = HomeScreenQml(SimpleNamespace(), None)
    first = asyncio.create_task(screen.load())
    await asyncio.wait_for(first_started.wait(), 1)
    screen.force_reload()
    await asyncio.sleep(0)

    assert screen._vm.loading is True
    release_second.set()
    await screen._load_task
    await first
    assert screen._vm.greeting == "new"
    assert screen._vm.loading is False


@pytest.mark.asyncio
async def test_library_tab_switch_ignores_cancelled_loading_state(qapp, monkeypatch):
    from doremi.ui.screens.library_qml import LibraryScreenQml
    from doremi.ui.screens import library_data

    first_started = asyncio.Event()
    release_second = asyncio.Event()

    async def songs(_client):
        first_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            return [{"videoId": "old"}]

    async def albums(_client):
        await release_second.wait()
        return [{"browseId": "new", "title": "New"}]

    monkeypatch.setattr(library_data, "gather_liked_songs", songs)
    monkeypatch.setattr(library_data, "gather_library_albums", albums)
    screen = LibraryScreenQml(SimpleNamespace(is_authenticated=True), None)
    screen._schedule_load()
    await asyncio.wait_for(first_started.wait(), 1)
    screen._vm.set_tab("albums")
    await asyncio.sleep(0)

    assert screen._vm.loading is True
    release_second.set()
    await screen._load_task
    assert screen._vm.tab == "albums"
    assert screen._vm.albums.rowCount() == 1
    assert screen._vm.loading is False


@pytest.mark.asyncio
async def test_history_retry_keeps_loading_until_current_request_finishes(qapp, monkeypatch):
    from doremi.ui.screens.history_qml import HistoryScreenQml
    from doremi.ui.screens import history_data

    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def gather(_client):
        nonlocal calls
        calls += 1
        if calls == 1:
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                return [], set(), 0
        await release.wait()
        return [], set(), 0

    monkeypatch.setattr(history_data, "gather_history", gather)
    screen = HistoryScreenQml(None, None)
    screen._schedule_load()
    await asyncio.wait_for(started.wait(), 1)
    screen._schedule_load()
    await asyncio.sleep(0)
    assert screen._vm.loading is True
    release.set()
    await screen._load_task
    assert screen._vm.loading is False


@pytest.mark.asyncio
async def test_stats_retry_keeps_loading_until_current_request_finishes(qapp, monkeypatch):
    from doremi.ui.screens.stats_qml import StatsScreenQml
    from doremi.ui.screens import stats_data

    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def gather():
        nonlocal calls
        calls += 1
        if calls == 1:
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                return {"_error": ""}
        await release.wait()
        return {"_error": ""}

    monkeypatch.setattr(stats_data, "gather_stats", gather)
    screen = StatsScreenQml(None, None)
    screen._schedule_load()
    await asyncio.wait_for(started.wait(), 1)
    screen._schedule_load()
    await asyncio.sleep(0)
    assert screen._vm.loading is True
    release.set()
    await screen._load_task
    assert screen._vm.loading is False


@pytest.mark.asyncio
async def test_playlist_navigation_ignores_cancelled_response(qapp, monkeypatch):
    from doremi.ui.screens.playlist_qml import PlaylistScreenQml
    from doremi.ui.screens import playlist_data

    first_started = asyncio.Event()
    release_second = asyncio.Event()

    async def gather(_client, playlist_id):
        if playlist_id == "A":
            first_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                return {"playlist_id": "A", "title": "Old", "tracks": []}
        await release_second.wait()
        return {"playlist_id": "B", "title": "Current", "tracks": []}

    monkeypatch.setattr(playlist_data, "gather_playlist", gather)
    screen = PlaylistScreenQml(SimpleNamespace(), None)
    first = asyncio.create_task(screen.load("A"))
    await asyncio.wait_for(first_started.wait(), 1)
    second = asyncio.create_task(screen.load("B"))
    await asyncio.sleep(0)

    assert screen._vm.loading is True
    release_second.set()
    await asyncio.gather(first, second)
    assert screen._vm.title == "Current"
    assert screen._vm.loading is False


@pytest.mark.asyncio
async def test_library_failure_has_error_instead_of_empty_state(qapp, monkeypatch):
    from doremi.ui.screens.library_qml import LibraryScreenQml
    from doremi.ui.screens import library_data

    client = SimpleNamespace(is_authenticated=True)
    screen = LibraryScreenQml(client, None)

    async def fail(_client):
        raise RuntimeError("offline")

    monkeypatch.setattr(library_data, "gather_liked_songs", fail)
    await screen.load()

    assert screen._vm.errorText


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "screen_module,data_module,screen_class,identifier",
    [
        ("doremi.ui.screens.playlist_qml", "doremi.ui.screens.playlist_data", "PlaylistScreenQml", "PL1"),
        ("doremi.ui.screens.album_qml", "doremi.ui.screens.album_data", "AlbumScreenQml", "AL1"),
        ("doremi.ui.screens.artist_qml", "doremi.ui.screens.artist_data", "ArtistScreenQml", "AR1"),
    ],
)
async def test_detail_load_failure_has_explicit_error_and_retry(
    qapp, monkeypatch, screen_module, data_module, screen_class, identifier
):
    import importlib

    async def fail(*_args):
        raise OSError("offline")

    monkeypatch.setattr(importlib.import_module(data_module), "gather_" + data_module.rsplit(".", 1)[-1].replace("_data", ""), fail)
    cls = getattr(importlib.import_module(screen_module), screen_class)
    if screen_class == "PlaylistScreenQml":
        screen = cls(SimpleNamespace(), lambda *_: None, lambda *_: None, lambda: None)
    elif screen_class == "AlbumScreenQml":
        screen = cls(SimpleNamespace(), lambda *_: None, lambda: None)
    else:
        screen = cls(SimpleNamespace(), lambda *_: None, lambda *_: None, lambda: None)

    await screen.load(identifier)
    assert screen._vm.loading is False
    assert screen._vm.found is False
    assert screen._vm.errorText
    assert not screen._vm.loading


def test_queue_remove_action_never_emits_download_deletion(qapp):
    from doremi.audio.queue import QueueItem
    from doremi.ui.viewmodels.now_playing_vm import NowPlayingViewModel

    vm = NowPlayingViewModel()
    vm.set_queue([QueueItem("v1", "Song", "Artist", "", 0, "")], set())
    removed, download_deletions = [], []
    vm.queue_remove_requested.connect(removed.append)
    vm.delete_download_requested.connect(download_deletions.append)

    vm.queue_action(0, "remove_from_queue")

    assert removed == [0]
    assert download_deletions == []


def test_now_playing_add_to_playlist_uses_song_title_not_artwork(qapp):
    from doremi.audio.queue import QueueItem
    from doremi.ui.viewmodels.now_playing_vm import NowPlayingViewModel

    vm = NowPlayingViewModel()
    vm.set_queue([QueueItem("v1", "Correct title", "Artist", "", 0, "https://art")], set())
    received = []
    vm.add_to_playlist_requested.connect(lambda *payload: received.append(payload))

    vm.queue_action(0, "add_to_playlist")

    assert received == [("v1", "Correct title")]


def test_queue_model_marks_only_current_duplicate_occurrence(qapp):
    from doremi.audio.queue import QueueItem
    from doremi.ui.viewmodels.now_playing_vm import NowPlayingViewModel

    vm = NowPlayingViewModel()
    vm.set_queue(
        [
            QueueItem("same", "First", "Artist", "", 0, ""),
            QueueItem("same", "Second", "Artist", "", 0, ""),
        ],
        set(),
        current_index=1,
    )
    role = vm.queueModel.IsCurrentRole

    assert vm.queueModel.data(vm.queueModel.index(0, 0), role) is False
    assert vm.queueModel.data(vm.queueModel.index(1, 0), role) is True


@pytest.mark.asyncio
async def test_fades_use_configured_total_duration(monkeypatch):
    from doremi.audio.crossfade import CrossfadeManager
    elapsed = []
    async def sleep(duration):
        elapsed.append(duration)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    status = SimpleNamespace(volume=80)
    player = SimpleNamespace(status=status, set_volume=lambda value: setattr(status, "volume", value))
    fade = CrossfadeManager(duration_sec=8)
    await fade.fade_out(player)
    assert status.volume == 0
    await fade.fade_in(player, 80)
    assert status.volume == 80
    assert sum(elapsed) == pytest.approx(8)


@pytest.mark.asyncio
async def test_manual_volume_change_stops_fade(monkeypatch):
    from doremi.audio.crossfade import CrossfadeManager
    status = SimpleNamespace(volume=80)
    player = SimpleNamespace(status=status, set_volume=lambda value: setattr(status, "volume", value))
    async def sleep(duration):
        status.volume = 37
    monkeypatch.setattr(asyncio, "sleep", sleep)
    await CrossfadeManager().fade_out(player)
    assert status.volume == 37


@pytest.mark.parametrize("component", ["SongRow", "MediaCard", "EmptyStateView", "ModalDialog", "HeaderButton", "HeroButton"])
def test_shared_qml_components_instantiate(qapp, component):
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlEngine, QQmlComponent
    from doremi.ui.theme_bridge import theme_bridge
    directory = Path(__file__).parents[1] / "src/doremi/ui/qml"
    engine = QQmlEngine()
    engine.addImportPath(str(directory))
    engine.rootContext().setContextProperty("themeBridge", theme_bridge())
    qml = QQmlComponent(engine, QUrl.fromLocalFile(str(directory / "Doremi" / f"{component}.qml")))
    instance = qml.create()
    assert instance is not None, [error.toString() for error in qml.errors()]
    instance.setParent(engine)


@pytest.mark.parametrize("accent", [
    "#A78BFA", "#7C4DFF", "#60A5FA", "#34D399", "#F472B6",
    "#FB923C", "#FBBF24", "#22D3EE", "#F87171",
])
def test_text_on_accent_uses_the_best_available_aa_contrast(accent):
    from PySide6.QtGui import QColor
    from doremi.native_rs import compute_color_variants
    from doremi.ui.theme_manager import _contrast_ratio, _text_on_accent

    background = QColor(accent)
    hover_background = QColor(compute_color_variants(accent, "dark").dark_hex)
    selected = QColor(_text_on_accent(accent))
    white = QColor("#FFFFFF")
    dark = QColor("#0A0A14")

    assert _contrast_ratio(background, selected) == pytest.approx(
        max(_contrast_ratio(background, white), _contrast_ratio(background, dark))
    )
    assert _contrast_ratio(background, selected) >= 4.5
    assert _contrast_ratio(hover_background, selected) >= 4.5


@pytest.mark.parametrize("scheme, expected", [
    ("Light", "light"),
    ("Dark", "dark"),
])
def test_system_theme_uses_qt_color_scheme_before_gsettings(monkeypatch, scheme, expected):
    import doremi.ui.theme_manager as theme_manager
    from PySide6.QtCore import Qt

    class Hints:
        def colorScheme(self):
            return getattr(Qt.ColorScheme, scheme)

    class App:
        @staticmethod
        def styleHints():
            return Hints()

    monkeypatch.setattr(theme_manager.QApplication, "instance", lambda: App())
    assert theme_manager._system_theme_mode() == expected


@pytest.mark.asyncio
async def test_runtime_recovery_cannot_replace_newer_track():
    from doremi.ui.controllers.playback_controller import PlaybackController
    started, release = asyncio.Event(), asyncio.Event()
    async def alternative(video_id):
        started.set()
        await release.wait()
        return "fake://old"
    controller = PlaybackController.__new__(PlaybackController)
    controller.queue = PlayQueue()
    first, second = [QueueItem(x, x, "", "", 0, "") for x in ("a", "b")]
    controller.queue.set_queue([first, second])
    controller._current_play_id = 1
    controller._recovering_id = 1
    controller.main_window = SimpleNamespace(_stream_recovery_attempts=set())
    controller.network_monitor = SimpleNamespace(is_connected=True)
    controller.extractor = SimpleNamespace(get_alternative_stream=alternative)
    controller.player = SimpleNamespace(play_url=AsyncMock(), stop=AsyncMock())
    pending = asyncio.create_task(controller._recover_stream(first, 1))
    await asyncio.wait_for(started.wait(), 1)
    controller.queue.jump_to(1)
    controller._current_play_id = 2
    release.set()
    await pending
    controller.player.play_url.assert_not_awaited()
    controller.player.stop.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", list(RepeatMode))
async def test_failed_tracks_do_not_repeat_indefinitely(mode, monkeypatch):
    from doremi.ui.controllers.playback_controller import PlaybackController
    from doremi.ui.widgets.toast import ToastNotification
    monkeypatch.setattr(ToastNotification, "show", lambda *args: None)
    controller = PlaybackController.__new__(PlaybackController)
    controller.queue = PlayQueue()
    controller.queue.set_queue([QueueItem(x, x, "", "", 0, "") for x in ("a", "b")])
    controller.queue.repeat_mode = mode
    controller.main_window = None
    controller.player = SimpleNamespace(stop=AsyncMock())
    controller._update_queue_panel = lambda: None
    async def fail_next(**kwargs):
        await controller.handle_playback_failure(controller.queue.current, "error")
    controller._play_current = fail_next
    await controller.handle_playback_failure(controller.queue.current, "error")
    assert controller._failed_video_ids == {"a", "b"}
    controller.player.stop.assert_awaited_once()


def test_now_playing_dispatches_each_intention_once(qapp):
    from doremi.config.settings import AppSettings
    from doremi.ui.screens.now_playing_qml import NowPlayingScreenQml
    player = SimpleNamespace(status=SimpleNamespace(current_video_id="a"))
    screen = NowPlayingScreenQml(player, PlayQueue(), None, lambda i: None, AppSettings(), lambda: None)
    screen._vm.set_track_info("Title", "Artist", "", "Album", "a")
    for signal, emit in [
        ("like_requested", screen._vm.toggle_like_current),
        ("artist_clicked", lambda: screen._vm.current_track_action("go_artist")),
        ("album_clicked", lambda: screen._vm.current_track_action("go_album")),
    ]:
        calls = []
        callback = lambda *args: calls.append(args)
        getattr(screen, signal).connect(callback)
        getattr(screen.queue_tab, signal).connect(callback)
        emit()
        assert len(calls) == 1, signal
    screen.close()


@pytest.mark.parametrize("name", ["HeaderButton", "HeroButton"])
def test_buttons_support_keyboard_and_disabled_state(qapp, name):
    from PySide6.QtCore import QUrl, Qt
    from PySide6.QtQuickWidgets import QQuickWidget
    from PySide6.QtTest import QTest, QSignalSpy
    from doremi.ui.theme_bridge import theme_bridge
    directory = Path(__file__).parents[1] / "src/doremi/ui/qml"
    widget = QQuickWidget()
    widget.engine().addImportPath(str(directory))
    widget.rootContext().setContextProperty("themeBridge", theme_bridge())
    widget.setSource(QUrl.fromLocalFile(str(directory / "Doremi" / f"{name}.qml")))
    widget.resize(180, 50)
    widget.show()
    root = widget.rootObject()
    spy = QSignalSpy(root.clicked)
    root.forceActiveFocus()
    QTest.keyClick(widget, Qt.Key_Return)
    QTest.keyClick(widget, Qt.Key_Space)
    assert spy.count() == 2
    root.setProperty("enabled", False)
    QTest.keyClick(widget, Qt.Key_Space)
    assert spy.count() == 2
    widget.close()


def test_empty_state_action_supports_keyboard_and_accessible_focus(qapp):
    from PySide6.QtCore import QObject, QUrl, Qt
    from PySide6.QtQuickWidgets import QQuickWidget
    from PySide6.QtTest import QSignalSpy, QTest
    from doremi.ui.theme_bridge import theme_bridge

    directory = Path(__file__).parents[1] / "src/doremi/ui/qml"
    widget = QQuickWidget()
    widget.engine().addImportPath(str(directory))
    widget.rootContext().setContextProperty("themeBridge", theme_bridge())
    widget.setSource(QUrl.fromLocalFile(str(directory / "Doremi" / "EmptyStateView.qml")))
    widget.resize(360, 260)
    widget.show()
    root = widget.rootObject()
    root.setProperty("actionText", "Reintentar")
    qapp.processEvents()
    action = root.findChild(QObject, "emptyStateAction")
    assert action is not None
    assert action.property("activeFocusOnTab") is True
    spy = QSignalSpy(root.actionClicked)
    action.forceActiveFocus()
    QTest.keyClick(widget, Qt.Key_Return)
    QTest.keyClick(widget, Qt.Key_Space)
    assert spy.count() == 2
    widget.close()


def test_header_actions_support_keyboard_and_have_accessible_names(qapp):
    from PySide6.QtCore import QObject, Property, QUrl, Slot, Qt
    from PySide6.QtQuickWidgets import QQuickWidget
    from PySide6.QtTest import QTest
    from doremi.ui.theme_bridge import theme_bridge

    class HeaderController(QObject):
        def __init__(self):
            super().__init__()
            self.clear_calls = self.notification_calls = self.profile_calls = 0

        @Property(bool, constant=True)
        def notificationsOpen(self):
            return False

        @Property(bool, constant=True)
        def hasUnread(self):
            return False

        @Property(str, constant=True)
        def profileLabel(self):
            return "Perfil"

        @Property(str, constant=True)
        def avatarUrl(self):
            return ""

        @Slot()
        def clearQuery(self):
            self.clear_calls += 1

        @Slot()
        def requestNotifications(self):
            self.notification_calls += 1

        @Slot()
        def requestProfile(self):
            self.profile_calls += 1

    directory = Path(__file__).parents[1] / "src/doremi/ui/qml"
    controller = HeaderController()
    widget = QQuickWidget()
    widget.engine().addImportPath(str(directory))
    widget.rootContext().setContextProperty("themeBridge", theme_bridge())
    widget.setInitialProperties({"headerController": controller})
    widget.setSource(QUrl.fromLocalFile(str(directory / "HeaderBar.qml")))
    widget.resize(800, 70)
    widget.show()
    widget.setFocus()
    root = widget.rootObject()
    search = root.findChild(QObject, "searchInput")
    search.setProperty("text", "query")
    qapp.processEvents()

    for name, expected in (
        ("clearSearchButton", "clear_calls"),
        ("notificationsButton", "notification_calls"),
        ("profileButton", "profile_calls"),
    ):
        control = root.findChild(QObject, name)
        assert control is not None
        assert control.property("activeFocusOnTab") is True
        control.forceActiveFocus()
        qapp.processEvents()
        assert control.property("activeFocus") is True
        QTest.keyClick(widget, Qt.Key_Return)
        assert getattr(controller, expected) == 1
    widget.close()

@pytest.mark.asyncio
async def test_window_close_waits_for_async_cleanup(qapp, monkeypatch):
    from unittest.mock import Mock
    from PySide6.QtGui import QCloseEvent
    from doremi.ui.main_window import MainWindow
    import doremi.db.database as db
    monkeypatch.setattr(db, "close_db", AsyncMock())
    ready, release = asyncio.Event(), asyncio.Event()
    async def cleanup():
        ready.set()
        await release.wait()
    window = SimpleNamespace(
        _save_playback_session=Mock(), _save_window_state=Mock(),
        settings=SimpleNamespace(player=SimpleNamespace(minimize_to_tray=False)),
        download_manager=SimpleNamespace(active_count=0),
        async_shutdown=cleanup, close=Mock(),
    )
    window._finish_close = lambda: MainWindow._finish_close(window)
    event = QCloseEvent()
    MainWindow.closeEvent(window, event)
    assert not event.isAccepted()
    await ready.wait()
    window.close.assert_not_called()
    again = QCloseEvent()
    MainWindow.closeEvent(window, again)
    assert not again.isAccepted()
    release.set()
    await window._shutdown_task
    db.close_db.assert_awaited_once()
    window.close.assert_called_once()
    final = QCloseEvent()
    MainWindow.closeEvent(window, final)
    assert final.isAccepted()


def test_close_to_tray_honors_stop_on_close(qapp):
    from unittest.mock import Mock
    from PySide6.QtGui import QCloseEvent
    from doremi.ui.main_window import MainWindow

    playback = SimpleNamespace(stop_for_window_close=Mock())
    window = SimpleNamespace(
        _save_playback_session=Mock(),
        _save_window_state=Mock(),
        settings=SimpleNamespace(player=SimpleNamespace(minimize_to_tray=True, stop_on_close=True)),
        tray=SimpleNamespace(isVisible=lambda: True),
        playback_controller=playback,
        hide=Mock(),
    )
    event = QCloseEvent()

    MainWindow.closeEvent(window, event)

    playback.stop_for_window_close.assert_called_once()
    window.hide.assert_called_once()
    assert not event.isAccepted()


@pytest.mark.asyncio
async def test_pause_cancels_pending_extraction_and_resume_retries():
    from unittest.mock import Mock
    from doremi.ui.controllers.playback_controller import PlaybackController
    from doremi.audio.crossfade import CrossfadeManager
    controller = PlaybackController.__new__(PlaybackController)
    controller._current_play_id = 1
    controller.crossfade_manager = CrossfadeManager()
    controller.player = SimpleNamespace(
        status=SimpleNamespace(state=PlayerState.LOADING),
        _player=SimpleNamespace(is_playing=lambda: False),
        pause=AsyncMock(), resume=AsyncMock(),
    )
    pending = asyncio.create_task(asyncio.sleep(60))
    controller._play_task = pending
    await controller._toggle_play_pause()
    with pytest.raises(asyncio.CancelledError):
        await pending
    controller.player.pause.assert_awaited_once()
    controller.player.status.state = PlayerState.PAUSED
    controller._play_current = AsyncMock()
    await controller._toggle_play_pause()
    controller._play_current.assert_awaited_once()
    controller.player.resume.assert_not_awaited()


@pytest.mark.asyncio
async def test_stop_on_close_cancels_pending_play_request():
    from doremi.ui.controllers.playback_controller import PlaybackController
    from doremi.audio.crossfade import CrossfadeManager

    controller = PlaybackController.__new__(PlaybackController)
    controller._current_play_id = 7
    controller._play_task = asyncio.create_task(asyncio.sleep(60))
    controller._restart_after_pause = True
    controller.crossfade_manager = CrossfadeManager()
    controller.player = SimpleNamespace(stop=AsyncMock())
    controller._finalize_listening = Mock()
    spawned = []
    controller.run_async = lambda coro: spawned.append(asyncio.create_task(coro))

    controller.stop_for_window_close()

    assert controller._current_play_id == 8
    assert controller._restart_after_pause is False
    with pytest.raises(asyncio.CancelledError):
        await controller._play_task
    await asyncio.gather(*spawned)
    controller.player.stop.assert_awaited_once()
    controller._finalize_listening.assert_called_once_with("stopped")
