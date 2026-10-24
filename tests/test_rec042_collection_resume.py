"""REC-04.1.2B: collection resume over real controllers, mocked VLC/network."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio

from doremi.audio.player import MusicPlayer, PlayerState
from doremi.audio.queue import QueueItem
from doremi.ui.controllers.playback_controller import PlaybackController
from doremi.ui.screens.playlist_qml import PlaylistScreenQml
from doremi.ui.screens.album_qml import AlbumScreenQml
from doremi.ui.viewmodels.playlist_vm import PlaylistViewModel
from doremi.ui.viewmodels.album_vm import AlbumViewModel
from test_rec042_offline_navigation import host, isolated_db
from test_rec041_playback_context import _controller, qapp


@pytest_asyncio.fixture
async def rig(qapp, monkeypatch):
    import doremi.ui.screens.playlist_data as playlist_data
    import doremi.ui.screens.album_data as album_data
    from doremi.system.network import NetworkMonitor
    from doremi.services.offline_cache import OfflineCacheManager
    monkeypatch.setattr(NetworkMonitor, 'current_connectivity', lambda: True)
    monkeypatch.setattr(OfflineCacheManager, 'get_instance', lambda: SimpleNamespace(local_path=lambda vid: None))
    nav, mw = host(connected=True)
    tracks = [dict(videoId=v, title=v, artist='Artist', album='Album', duration_ms=100000,
                   thumbnail_url='', is_downloaded=False) for v in ['first', 'target', 'last']]
    data = dict(playlist_id='PLfixture', browse_id='ALfixture', title='Collection', tracks=tracks)
    for route, cls, vmcls, attr in [('playlist', PlaylistScreenQml, PlaylistViewModel, '_playlist_id'),
                                   ('album', AlbumScreenQml, AlbumViewModel, '_browse_id')]:
        screen = cls.__new__(cls)
        from PySide6.QtCore import QObject
        QObject.__init__(screen)
        screen._vm = vmcls()
        screen._load_task = None
        screen._load_generation = 0
        setattr(screen, attr, None)
        screen.yt = Mock()
        screen._refresh_download_state = Mock()
        setattr(mw, route + '_screen', screen)
    gather = AsyncMock(side_effect=lambda *a, **k: dict(data, playlist_id=a[1]))
    monkeypatch.setattr(playlist_data, 'gather_playlist', gather)
    monkeypatch.setattr(album_data, 'gather_album', gather)
    pc = _controller()
    pc.now_playing_screen = Mock()
    pc._play_current = PlaybackController._play_current.__get__(pc)
    pc.settings.player.crossfade_enabled = False
    player = MusicPlayer()  # conftest mocks the VLC module; no real media opened
    player._player = Mock()
    player._player.get_length.return_value = 100000
    player._player.set_time = Mock()
    async def play(url, vid):
        player.status.state = PlayerState.PLAYING
        player.status.current_video_id = vid
        player.status.duration_ms = 100000
        return True
    player.play_url = AsyncMock(side_effect=play)
    pc.player = player
    pc.main_window = mw
    mw._stream_recovery_attempts = set()
    mw._handle_playback_failure = AsyncMock()
    pc.extractor.get_stream_info = AsyncMock(return_value={'url': 'https://example.invalid/audio', 'duration': 100})
    pc._fetch_and_populate_auto_queue = AsyncMock()
    mw.playback_controller, mw.player, mw.queue = pc, player, pc.queue
    return SimpleNamespace(nav=nav, mw=mw, pc=pc, player=player, data=data, tracks=tracks, gather=gather)


def resume_path(rig, **params):
    return rig.nav._path_for('playlist', dict(id='PLfixture', resume='target', position='25000', **params))


@pytest.mark.asyncio
@pytest.mark.parametrize('route,identity,context', [('playlist', 'PLfixture', 'playlist'),
    ('playlist', 'smart:liked', 'smart'), ('album', 'ALfixture', 'album')])
async def test_resume_correct_member_once_with_rec041_context(rig, isolated_db, route, identity, context):
    await rig.nav.navigate(rig.nav._path_for(route, dict(id=identity, resume='target', position='25000')))
    current = rig.mw.queue.current
    assert current is not None, 'resume route loaded without selecting its member'
    assert current.video_id == 'target'
    assert (current.context_type, current.context_id, current.context_title) == (context, identity, 'Collection')
    assert [t.video_id for t in rig.mw.queue.items] == ['first', 'target', 'last']
    rig.player.play_url.assert_awaited_once()
    rig.player._player.set_time.assert_called_once_with(25000)
    rig.pc._fetch_and_populate_auto_queue.assert_not_awaited()
    # Existing ListeningSession/ListenResult persistence, one entry only.
    rig.pc._listen_session.observe(25000, 100000, True)
    rig.pc._listen_session.observe(30000, 100000, True)
    result = rig.pc._listen_session.finish('paused')
    await rig.pc._persist_listen(result)
    assert rig.pc._listen_session.finish('paused') is None
    from doremi.db.models import PlayHistory
    from sqlalchemy import select
    async with isolated_db.get_session() as session:
        rows = list((await session.scalars(select(PlayHistory))).all())
    assert len(rows) == 1
    assert (rows[0].video_id, rows[0].context_type, rows[0].context_id, rows[0].position_ms) == ('target', context, identity, 30000)


@pytest.mark.asyncio
@pytest.mark.parametrize('position,expected', [('25000', 25000), ('9999999999', 100000),
    ('0', None), ('-5', None), ('invalid', None), ('nan', None), ('1.5', None), ('', None)])
async def test_position_validation_and_bounds(rig, isolated_db, position, expected):
    await rig.nav.navigate(rig.nav._path_for('playlist', dict(id='PLfixture', resume='target', position=position)))
    assert rig.mw.queue.current and rig.mw.queue.current.video_id == 'target'
    if expected is None:
        rig.player._player.set_time.assert_not_called()
    else:
        rig.player._player.set_time.assert_called_once_with(expected)


@pytest.mark.asyncio
@pytest.mark.parametrize('resume,extra,expected', [('absent', {}, None), ('target', {'next': '1'}, 'last'),
    ('last', {'next': '1'}, None), ('target', {'next': '0'}, 'target')])
async def test_membership_and_producer_next_semantics(rig, isolated_db, resume, extra, expected):
    await rig.nav.navigate(rig.nav._path_for('playlist', dict(id='PLfixture', resume=resume, position='25000', **extra)))
    assert (rig.mw.queue.current.video_id if rig.mw.queue.current else None) == expected
    if extra.get('next') == '1':
        rig.player._player.set_time.assert_not_called()
    rig.pc._fetch_and_populate_auto_queue.assert_not_awaited()


@pytest.mark.asyncio
async def test_back_history_does_not_replay_resume_or_external_autoplay(rig, isolated_db):
    await rig.nav.navigate(resume_path(rig))
    assert rig.mw._current_path == 'playlist?id=PLfixture'
    await rig.nav.navigate('downloads')
    rig.nav.go_back()
    await rig.mw._current_nav_task
    rig.player.play_url.assert_awaited_once()
    assert rig.mw._current_path == 'playlist?id=PLfixture'
    await rig.nav.navigate('playlist?id=PLfixture&autoplay=play')
    rig.player.play_url.assert_awaited_once()


@pytest.mark.asyncio
async def test_navigation_supersedes_slow_collection_even_if_loader_ignores_cancel(rig, isolated_db):
    entered, release = asyncio.Event(), asyncio.Event()
    async def gather(*args, **kwargs):
        entered.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            await release.wait()
        return rig.data
    rig.gather.side_effect = gather
    rig.nav.navigate_to(resume_path(rig))
    pending = rig.mw._current_nav_task
    await asyncio.wait_for(entered.wait(), 2)
    rig.nav.navigate_to('downloads')
    await rig.mw._current_nav_task
    release.set()
    await pending
    assert rig.mw._current_route == 'downloads'
    rig.player.play_url.assert_not_awaited()
    rig.player._player.set_time.assert_not_called()


@pytest.mark.asyncio
async def test_screen_reload_generation_invalidates_resume(rig, isolated_db):
    entered, release = asyncio.Event(), asyncio.Event()
    async def gather(yt, pid):
        if pid == 'PLfixture':
            entered.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                await release.wait()
        return dict(rig.data, playlist_id=pid)
    rig.gather.side_effect = gather
    pending = asyncio.create_task(rig.nav.navigate(resume_path(rig)))
    await asyncio.wait_for(entered.wait(), 2)
    await rig.mw.playlist_screen.load('PLreplacement')
    release.set()
    await pending
    rig.player.play_url.assert_not_awaited()


@pytest.mark.asyncio
async def test_playback_selected_during_loading_is_not_replaced(rig, isolated_db):
    entered, release = asyncio.Event(), asyncio.Event()
    async def gather(*a):
        entered.set()
        await release.wait()
        return rig.data
    rig.gather.side_effect = gather
    pending = asyncio.create_task(rig.nav.navigate(resume_path(rig)))
    await asyncio.wait_for(entered.wait(), 2)
    other = QueueItem('other', 'Other', '', '', 100000, '')
    rig.mw.queue.set_queue([other])
    rig.pc._current_play_id += 1
    release.set()
    await pending
    assert rig.mw.queue.current is other
    rig.player.play_url.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('replacement', ['play_id', 'queue', 'media', 'paused', 'navigation'])
async def test_seek_rechecks_intent_inside_player_lock(rig, isolated_db, replacement):
    # Force the resume seek to wait behind a player operation. Then replace
    # its intent before the lock becomes available (the TOCTOU regression).
    entered = asyncio.Event()
    original_seek = rig.player.seek
    async def seek(*args, **kwargs):
        entered.set()
        await original_seek(*args, **kwargs)
    rig.player.seek = seek
    await rig.player._play_lock.acquire()
    pending = asyncio.create_task(rig.nav.navigate(resume_path(rig)))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        if replacement == 'play_id':
            rig.pc._current_play_id += 1
        elif replacement == 'queue':
            rig.mw.queue.set_queue([QueueItem('other', '', '', '', 100000, '')])
        elif replacement == 'media':
            rig.player.status.current_video_id = 'other'
        elif replacement == 'paused':
            rig.player.status.state = PlayerState.PAUSED
        else:
            await rig.nav.navigate('downloads')
    finally:
        rig.player._play_lock.release()
        await asyncio.gather(pending, return_exceptions=True)
    rig.player._player.set_time.assert_not_called()


@pytest.mark.asyncio
async def test_seek_waits_for_media_ready(rig, isolated_db):
    entered, ready = asyncio.Event(), asyncio.Event()
    async def play(url, vid):
        rig.player.status.state = PlayerState.LOADING
        rig.player.status.current_video_id = vid
        entered.set()
        await ready.wait()
        rig.player.status.state = PlayerState.PLAYING
        return True
    rig.player.play_url.side_effect = play
    pending = asyncio.create_task(rig.nav.navigate(resume_path(rig)))
    await asyncio.wait_for(entered.wait(), 2)
    rig.player._player.set_time.assert_not_called()
    ready.set()
    await pending
    rig.player._player.set_time.assert_called_once_with(25000)


@pytest.mark.asyncio
async def test_failed_start_never_seeks(rig, isolated_db):
    rig.player.play_url.side_effect = None
    rig.player.play_url.return_value = False
    rig.pc.extractor.get_alternative_stream = AsyncMock(return_value=None)
    await rig.nav.navigate(resume_path(rig))
    rig.player._player.set_time.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('available', [True, False])
async def test_local_resume_offline_requires_existing_file(rig, isolated_db, tmp_path, available):
    rig.mw.network_monitor.is_connected = False
    rig.pc.network_monitor.is_connected = False
    path = tmp_path / 'fixture.mp3'
    if available:
        path.write_bytes(b'fixture, no actual music')
    rig.tracks[1].update(local_path=str(path), is_downloaded=True)
    await rig.nav.navigate(rig.nav._path_for('playlist', dict(id='local-list:fixture', resume='target', position='25000')))
    rig.pc.extractor.get_stream_info.assert_not_awaited()
    if available:
        assert rig.mw.queue.current and rig.mw.queue.current.local_path == str(path)
        assert rig.mw.queue.current.context_id == 'local-list:fixture'
        rig.player._player.set_time.assert_called_once_with(25000)
    else:
        rig.player.play_url.assert_not_awaited()
        assert rig.mw.queue.current is None


@pytest.mark.asyncio
async def test_local_download_metadata_preserves_path(rig, isolated_db, tmp_path):
    path = tmp_path / 'fixture.mp3'
    path.write_bytes(b'fixture')
    rig.data.update(is_local=True, local_meta=[dict(video_id='target', file_path=str(path))])
    rig.mw.network_monitor.is_connected = False
    rig.pc.network_monitor.is_connected = False
    await rig.nav.navigate(rig.nav._path_for('playlist', dict(id='local_PLfixture', resume='target', position='25000')))
    assert rig.mw.queue.current and rig.mw.queue.current.local_path == str(path)
    rig.pc.extractor.get_stream_info.assert_not_awaited()


@pytest.mark.asyncio
async def test_offline_unavailable_remote_member_does_not_touch_playback(rig, isolated_db):
    rig.mw.network_monitor.is_connected = False
    rig.pc.network_monitor.is_connected = False
    await rig.nav.navigate(rig.nav._path_for('playlist', dict(id='smart:liked', resume='target', position='25000')))
    assert rig.mw.queue.current is None
    rig.player.play_url.assert_not_awaited()
    rig.pc.extractor.get_stream_info.assert_not_awaited()


@pytest.mark.asyncio
async def test_playback_selection_during_navigation_animation_cancels_resume(rig, isolated_db):
    rig.nav.navigate_to(resume_path(rig))
    pending = rig.mw._current_nav_task
    # navigate() updates the route synchronously before its animation wait.
    while rig.mw._current_route != 'playlist':
        await asyncio.sleep(0)
    other = QueueItem('other', 'Other', '', '', 100000, '')
    rig.mw.queue.set_queue([other])
    rig.pc._current_play_id += 1
    await pending
    assert rig.mw.queue.current is other
    rig.player.play_url.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('length,expected', [(0, None), (10000, 10000)])
async def test_guarded_seek_uses_prepared_media_length(rig, isolated_db, length, expected):
    rig.player._player.get_length.return_value = length
    await rig.nav.navigate(resume_path(rig))
    if expected is None:
        rig.player._player.set_time.assert_not_called()
    else:
        rig.player._player.set_time.assert_called_once_with(expected)


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['artist', 'album'])
async def test_resolving_a_new_destination_invalidates_pending_resume(rig, isolated_db, kind):
    entered, release, resolving = asyncio.Event(), asyncio.Event(), asyncio.Event()
    async def gather(*args, **kwargs):
        entered.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            await release.wait()
        return rig.data
    async def search(*args, **kwargs):
        resolving.set()
        await asyncio.Event().wait()
    rig.gather.side_effect = gather
    rig.mw.yt = SimpleNamespace(search=search)
    rig.nav.navigate_to(resume_path(rig))
    pending = rig.mw._current_nav_task
    try:
        await asyncio.wait_for(entered.wait(), 2)
        getattr(rig.nav, f'resolve_and_navigate_{kind}')('New destination')
        await asyncio.wait_for(resolving.wait(), 2)
        release.set()
        await pending
        rig.player.play_url.assert_not_awaited()
        rig.player._player.set_time.assert_not_called()
    finally:
        release.set()
        rig.nav._resolution_task.cancel()
        await asyncio.gather(pending, rig.nav._resolution_task, return_exceptions=True)
