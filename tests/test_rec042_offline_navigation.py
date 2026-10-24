"""REC-04.1.2A: real route loading over temporary SQLite/files, no network."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio

from doremi.audio.queue import PlayQueue
from doremi.ui.controllers.navigation_controller import NavigationController
from doremi.ui.controllers.integrations_controller import IntegrationsController


@pytest_asyncio.fixture
async def isolated_db(monkeypatch, tmp_path):
    import doremi.db.database as db
    from doremi.system.network import NetworkMonitor
    await db.close_db()
    monkeypatch.setattr(db, 'DATABASE_URL', f'sqlite+aiosqlite:///{tmp_path / "test.db"}')
    monkeypatch.setattr(db, '_engine', None)
    monkeypatch.setattr(db, '_session_factory', None)
    monkeypatch.setattr(NetworkMonitor, 'current_connectivity', lambda: False)
    await db.init_db()
    yield db
    await db.close_db()


def host(*, connected=False):
    mw = SimpleNamespace(
        ROUTES={'home': 0, 'playlist': 1, 'downloads': 2, 'album': 3,
                'artist': 4, 'search': 5, 'library': 6, 'history': 7, 'stats': 8},
        ONLINE_ROUTES={'home', 'playlist', 'album', 'artist', 'search', 'library'},
        network_monitor=SimpleNamespace(is_connected=connected),
        _current_path='downloads', _current_route='downloads', _nav_history=[],
        _current_nav_task=None, _offline_blocked_path='playlist?id=REMOTE',
        _offline_state_index=99, search_bar=Mock(), sidebar=Mock(),
        stack=Mock(), offline_banner=Mock(),
        playlist_screen=SimpleNamespace(load=AsyncMock()),
        home_screen=SimpleNamespace(_loaded=False, load=AsyncMock()),
        downloads_screen=SimpleNamespace(load=AsyncMock()),
        history_screen=SimpleNamespace(load=AsyncMock()),
        stats_screen=SimpleNamespace(load=AsyncMock()),
        library_screen=SimpleNamespace(load=AsyncMock()),
        search_screen=SimpleNamespace(load=AsyncMock()),
    )
    nav = NavigationController(mw, asyncio.create_task)
    nav.set_stack_index = Mock()
    mw.navigation_controller = nav
    mw._show_offline_state = nav.show_offline_state
    mw._navigate_to = nav.navigate_to
    return nav, mw


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['session', 'local-list', 'smart', 'local_'])
async def test_local_collections_load_offline_without_youtube(kind, isolated_db, tmp_path):
    from doremi.db.repository import SongRepository, HistoryRepository, DownloadRepository
    from doremi.db.local_library_repository import LocalLibraryRepository
    from doremi.services.listening_periods import ListeningPeriods
    from doremi.ui.screens.playlist_data import gather_playlist
    path = tmp_path / 'synthetic.mp3'
    path.write_bytes(b'fixture only; VLC mocked')
    await SongRepository().upsert_song(video_id='available', title='Available', artist='A',
                                       local_path=str(path), is_liked=True)
    await SongRepository().upsert_song(video_id='remote', title='Remote', artist='B', is_liked=True)
    if kind == 'local-list':
        repo = LocalLibraryRepository()
        identity = await repo.create_playlist('Local')
        await repo.append(identity, ['available', 'remote'])
    elif kind == 'session':
        for vid in ['available', 'remote']:
            await HistoryRepository().add_entry(vid, vid, 'A', 100000, listen_time_ms=60000)
        identity = (await ListeningPeriods().recent())[0]['navigate'].split('id=')[1]
    elif kind == 'smart':
        identity = 'smart:liked'
    else:
        await DownloadRepository().add_download(video_id='available', title='Available', artist='A',
            file_path=str(path), parent_playlist_id='PLfixture', parent_playlist_title='Downloaded')
        identity = 'local_PLfixture'
    nav, mw = host()
    yt = SimpleNamespace(get_playlist=AsyncMock(side_effect=AssertionError('YouTube forbidden')))
    loaded = []
    async def load(pid):
        loaded.append(await gather_playlist(yt, pid))
    mw.playlist_screen.load.side_effect = load
    await nav.navigate(nav._path_for('playlist', {'id': identity}))
    assert loaded, 'local collection was incorrectly blocked offline'
    assert [t['videoId'] for t in loaded[0]['tracks']] == ['available']
    assert mw._offline_blocked_path is None
    assert mw._nav_history == ['downloads']
    yt.get_playlist.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('path', [
    'playlist?id=PLremote', 'playlist', 'playlist?id=', 'playlist?id=session:bogus',
    'playlist?id=session:0:2', 'playlist?id=session:3:2', 'playlist?id=local-list:',
    'playlist?id=local_', 'playlist?id=smart:bogus', 'playlist?id=local-list:x%2Fremote',
    'https://example.invalid/playlist?id=smart:liked',
    'playlist?id=PLremote&id=smart:liked', 'playlist?id=smart:liked#remote',
])
async def test_remote_and_malformed_routes_do_not_bypass_offline(path):
    nav, mw = host()
    mw._current_path = 'playlist?id=smart:liked'  # stale previous local route
    await nav.navigate(path)
    mw.playlist_screen.load.assert_not_awaited()
    assert mw._offline_blocked_path is not None
    nav.set_stack_index.assert_called_with(99)


def test_legacy_policy_and_other_screens_remain_unchanged():
    nav, mw = host()
    assert nav.should_show_offline_state('playlist')
    for route in mw.ONLINE_ROUTES - {'playlist'}:
        assert nav.should_show_offline_state(route)
    for route in ['downloads', 'history', 'stats']:
        assert not nav.should_show_offline_state(route)
    mw.network_monitor.is_connected = True
    assert not nav.should_show_offline_state('playlist')


@pytest.mark.asyncio
async def test_history_and_back_restore_local_identity():
    nav, mw = host()
    await nav.navigate('playlist?id=local-list:fixture')
    await nav.navigate('downloads')
    nav.go_back()
    await mw._current_nav_task
    assert mw._current_path == 'playlist?id=local-list%3Afixture'
    assert mw._nav_history == ['downloads']
    assert mw._offline_blocked_path is None
    assert mw.playlist_screen.load.await_count == 2


@pytest.mark.parametrize('identity', ['local-list:fixture', 'session:1:2', 'local_PLfixture', 'smart:liked'])
def test_connection_loss_keeps_local_playlist_visible(identity, monkeypatch):
    import doremi.ui.controllers.integrations_controller as module
    monkeypatch.setattr(module.ToastNotification, 'show', Mock())
    nav, mw = host(connected=True)
    mw._current_route = 'playlist'
    mw._current_path = nav._path_for('playlist', {'id': identity})
    mw._offline_blocked_path = None
    ic = IntegrationsController(None, PlayQueue(), None, None, None, lambda coro: coro.close(), mw)
    ic.on_connectivity_change(False)
    nav.set_stack_index.assert_not_called()
    assert mw._offline_blocked_path is None


def test_connection_loss_preserves_remote_query_for_retry(monkeypatch):
    import doremi.ui.controllers.integrations_controller as module
    monkeypatch.setattr(module.ToastNotification, 'show', Mock())
    nav, mw = host(connected=True)
    mw._current_route = 'playlist'
    mw._current_path = 'playlist?id=PLremote'
    ic = IntegrationsController(None, PlayQueue(), None, None, None, Mock(), mw)
    ic.on_connectivity_change(False)
    assert mw._offline_blocked_path == 'playlist?id=PLremote'
    nav.set_stack_index.assert_called_once_with(99)
    mw._navigate_to = Mock()
    ic.on_connectivity_change(True)
    mw._navigate_to.assert_called_once_with('playlist?id=PLremote')


@pytest.mark.asyncio
async def test_connection_loss_refreshes_smart_offline_filter(isolated_db, tmp_path, monkeypatch):
    from doremi.db.repository import SongRepository
    from doremi.system.network import NetworkMonitor
    from doremi.ui.screens.playlist_data import gather_playlist
    import doremi.ui.controllers.integrations_controller as module
    monkeypatch.setattr(module.ToastNotification, 'show', Mock())
    nav, mw = host(connected=True)
    monkeypatch.setattr(NetworkMonitor, 'current_connectivity', lambda: mw.network_monitor.is_connected)
    path = tmp_path / 'fixture.mp3'
    path.write_bytes(b'fixture')
    await SongRepository().upsert_song(video_id='available', title='A', artist='A', local_path=str(path), is_liked=True)
    await SongRepository().upsert_song(video_id='remote', title='R', artist='R', is_liked=True)
    snapshots = []
    async def load(pid):
        snapshots.append(await gather_playlist(None, pid))
    mw.playlist_screen.load.side_effect = load
    await nav.navigate('playlist?id=smart:liked')
    assert len(snapshots[-1]['tracks']) == 2
    tasks = []
    ic = IntegrationsController(None, PlayQueue(), None, None, None,
                               lambda coro: tasks.append(asyncio.create_task(coro)), mw)
    mw.network_monitor.is_connected = False
    ic.on_connectivity_change(False)
    await asyncio.gather(*tasks)
    assert [t['videoId'] for t in snapshots[-1]['tracks']] == ['available']
    assert mw._nav_history == ['downloads']
    assert mw._offline_blocked_path is None
