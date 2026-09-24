"""Regresiones verificables de la auditoría de septiembre de 2026."""
import asyncio
import os
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from doremi.audio.player import MusicPlayer, PlayerState
from doremi.audio.queue import PlayQueue, QueueItem, RepeatMode
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


def test_repeat_one_only_repeats_on_natural_end():
    queue = PlayQueue()
    queue.set_queue([QueueItem(x, x, "", "", 0, "") for x in ("a", "b")])
    queue.repeat_mode = RepeatMode.ONE
    assert queue.advance().video_id == "a"
    assert queue.advance(ignore_repeat_one=True).video_id == "b"


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
