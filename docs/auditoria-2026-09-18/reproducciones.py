"""Reproducciones de defectos: pasar significa reproducir, no corregir."""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.modules['vlc'] = MagicMock()

@pytest.fixture(scope='module')
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])

def item(vid):
    from doremi.audio.queue import QueueItem
    return QueueItem(vid, vid, '', '', 0, '')

@pytest.mark.asyncio
async def test_search_hides_network_error():
    from doremi.ui.screens.search_data import gather_search
    result = await gather_search(NS(search=AsyncMock(side_effect=ConnectionError('offline'))), 'abc', 'song')
    assert result == []

@pytest.mark.asyncio
async def test_cancel_queued_download_blocks_readding(app, tmp_path, monkeypatch):
    from doremi.services.download_manager import DownloadManager
    manager = DownloadManager()
    manager._state_file = tmp_path / 'downloads.json'
    manager._restored_state = True
    assert manager.add_download('a', 'A', 'B', '')
    manager.cancel_download('a')
    manager.start(1)
    await asyncio.wait_for(manager._queue.join(), 1)
    assert manager.active_count == 1
    assert not manager.add_download('a', 'A', 'B', '')
    workers = list(manager._workers)
    manager.stop()
    await asyncio.gather(*workers, return_exceptions=True)

@pytest.mark.asyncio
async def test_recovery_can_play_stale_track(monkeypatch):
    from doremi.audio.queue import PlayQueue
    from doremi.ui.controllers.integrations_controller import IntegrationsController, ToastNotification
    q = PlayQueue()
    q.set_queue([item('A'), item('B')])
    entered, release = asyncio.Event(), asyncio.Event()
    async def alternative(vid):
        entered.set()
        await release.wait()
        return 'https://example.invalid/A'
    player = NS(play_url=AsyncMock(return_value=True))
    window = NS(_stream_recovery_attempts=set(), _should_show_offline_state=lambda _: False)
    controller = IntegrationsController(player, q, None, None, None, None, NS(get_alternative_stream=alternative), None, window)
    monkeypatch.setattr(ToastNotification, 'show', lambda *a: None)
    task = asyncio.create_task(controller.recover_player_error(None))
    await entered.wait()
    q.jump_to(1)
    release.set()
    await task
    assert q.current.video_id == 'B'
    player.play_url.assert_awaited_once_with('https://example.invalid/A', 'A')

@pytest.mark.asyncio
async def test_stop_waits_behind_startup_lock():
    from doremi.audio.player import MusicPlayer
    p = MusicPlayer()
    started = asyncio.create_task(p.play_url('https://example.invalid/A', 'A'))
    await asyncio.sleep(0)
    stopped = asyncio.create_task(p.stop())
    await asyncio.sleep(.03)
    assert not stopped.done()
    started.cancel()
    await asyncio.gather(started, return_exceptions=True)
    await stopped
    p.release()

def test_now_playing_duplicates_like_dispatch(app):
    from doremi.audio.queue import PlayQueue
    from doremi.config.settings import AppSettings
    from doremi.ui.screens.now_playing_qml import NowPlayingScreenQml
    player = NS(status=NS(current_video_id='A', position_ms=0, duration_ms=1000))
    screen = NowPlayingScreenQml(player, PlayQueue(), None, lambda _: None, AppSettings())
    assert screen.is_ok
    calls = []
    def receive(*args):
        calls.append(args)
    # Las dos conexiones usadas por MainWindow._build_ui.
    screen.like_requested.connect(receive)
    screen.queue_tab.like_requested.connect(receive)
    screen._vm.set_track_info('A', 'Artist', '', '', 'A')
    screen._vm.toggle_like_current()
    assert len(calls) == 2
    screen.close()
    screen.deleteLater()

@pytest.mark.asyncio
async def test_playlist_title_escapes_download_root(app, tmp_path, monkeypatch):
    import doremi.services.download_manager as mod
    manager = mod.DownloadManager()
    manager._state_file = tmp_path / 'state.json'
    monkeypatch.setattr(mod, 'AppDirs', NS(downloads=tmp_path / 'downloads'))
    options = []
    class FakeYDL:
        def __init__(self, opts):
            options.append(opts)
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass
        def extract_info(self, *a, **kw):
            raise RuntimeError('Fin de prueba: no se descarga nada')
    monkeypatch.setattr(mod.yt_dlp, 'YoutubeDL', FakeYDL)
    await manager._process_download(mod.DownloadTask('A', 'A', 'B', '', parent_playlist_title='../outside'))
    assert (tmp_path / 'outside').is_dir()
    assert not Path(options[0]['outtmpl']).resolve().is_relative_to(tmp_path / 'downloads')

def test_unintegrated_songrow_does_not_parse(app):
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlEngine, QQmlComponent
    root = Path(__file__).resolve().parents[2] / 'src/doremi/ui/qml'
    engine = QQmlEngine()
    engine.addImportPath(str(root))
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(root / 'Doremi/SongRow.qml')))
    assert component.isError()
    assert any('Unexpected token' in e.toString() for e in component.errors())

@pytest.mark.asyncio
async def test_shutdown_leaves_download_thread_running(app, tmp_path, monkeypatch):
    import threading
    import doremi.services.download_manager as mod
    manager = mod.DownloadManager()
    manager._state_file = tmp_path / 'state.json'
    manager._restored_state = True
    monkeypatch.setattr(mod, 'AppDirs', NS(downloads=tmp_path / 'downloads'))
    running, finish, done = threading.Event(), threading.Event(), threading.Event()
    class FakeYDL:
        def __init__(self, opts):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass
        def extract_info(self, *a, **kw):
            running.set()
            finish.wait(2)
            done.set()
            raise RuntimeError('Fin de prueba')
    monkeypatch.setattr(mod.yt_dlp, 'YoutubeDL', FakeYDL)
    manager.add_download('A', 'A', 'B', '')
    manager.start(1)
    try:
        for _ in range(100):
            if running.is_set():
                break
            await asyncio.sleep(.01)
        assert running.is_set()
        await manager.async_stop(timeout=.03)
        assert not done.is_set()
        assert not manager._tasks['A']._cancel_flag
    finally:
        finish.set()
        await asyncio.to_thread(done.wait, 1)
