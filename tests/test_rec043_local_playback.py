"""REC043A: manual playlist playback, temporary files/SQLite and mocked VLC."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from doremi.audio.queue import QueueItem
from doremi.ui.controllers.playback_controller import PlaybackController
from test_rec042_collection_resume import rig
from test_rec041_playback_context import qapp
from test_rec042_offline_navigation import isolated_db


@pytest.mark.asyncio
@pytest.mark.parametrize('identity', ['session:1:3', 'local-list:fixture', 'smart:liked'])
@pytest.mark.parametrize('action', ['play_all', 'play_shuffle', 'play_at'])
async def test_manual_play_preserves_available_paths_context_and_occurrences(rig, isolated_db, tmp_path, identity, action):
    path = tmp_path / 'synthetic.opus'
    path.write_bytes(b'fixture; never decoded')
    tracks = [dict(videoId=vid, title=vid, artist='A', duration_ms=100000,
                   local_path=str(path), is_downloaded=True) for vid in ['local:a', 'local:a', 'local:b']]
    screen = rig.mw.playlist_screen
    screen._playlist_id = identity
    screen._vm.set_data(dict(playlist_id=identity, title='Collection', tracks=tracks))
    tasks = []
    screen.on_play_song = lambda *a: tasks.append(asyncio.create_task(rig.pc._play_song(*a)))
    screen._vm.play_queue_requested.connect(screen._on_vm_play_queue)
    rig.pc.network_monitor.is_connected = False
    rig.mw.network_monitor.is_connected = False
    getattr(screen._vm, action)(*([1] if action == 'play_at' else []))
    await asyncio.gather(*tasks)
    items = rig.pc.queue.items
    assert len(items) == 3
    assert sorted(item.video_id for item in items) == ['local:a', 'local:a', 'local:b']
    if action != 'play_shuffle':
        assert [item.video_id for item in items] == ['local:a', 'local:a', 'local:b']
    for item in items:
        assert item.is_local and item.local_path == str(path)
        assert (item.context_type, item.context_id, item.context_title) == (
            'smart' if identity.startswith('smart:') else 'playlist', identity, 'Collection')
    rig.player.play_url.assert_awaited_once_with(str(path), rig.pc.queue.current.video_id)
    rig.pc.extractor.get_stream_info.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ['play_all', 'play_shuffle', 'play_at'])
async def test_legacy_local_download_path_and_context(rig, isolated_db, tmp_path, action):
    path = tmp_path / 'download.opus'
    path.write_bytes(b'fixture')
    screen = rig.mw.playlist_screen
    screen._playlist_id = 'local_PLfixture'
    rig.mw._current_path = 'playlist?id=local_PLfixture'
    screen._vm.set_data(dict(playlist_id=screen._playlist_id, title='Downloaded', is_local=True,
        tracks=[dict(videoId='available')], local_meta=[dict(video_id='available', file_path=str(path))]))
    screen.on_play_local_playlist = rig.pc._play_local_playlist
    screen._vm.play_local_requested.connect(screen._on_vm_play_local)
    rig.pc.network_monitor.is_connected = False
    getattr(screen._vm, action)(*([0] if action == 'play_at' else []))
    item = rig.pc.queue.current
    assert item.is_local and item.local_path == str(path)
    assert item.context_id == 'local_PLfixture'
    await rig.pc._play_current()
    rig.player.play_url.assert_awaited_once_with(str(path), 'available')
    rig.pc.extractor.get_stream_info.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('state', ['missing', 'directory', 'empty', 'flag_only', 'valid_without_flag'])
async def test_local_flag_depends_on_file_not_download_flag(rig, tmp_path, state):
    path = tmp_path / 'fixture.opus'
    if state == 'directory':
        path.mkdir()
    elif state == 'empty':
        path.touch()
    elif state == 'valid_without_flag':
        path.write_bytes(b'fixture')
    track = dict(videoId='remote-id', is_downloaded=state != 'valid_without_flag', local_path=str(path))
    if state == 'flag_only':
        track.pop('local_path')
    screen = rig.mw.playlist_screen
    screen.on_play_song = Mock()
    screen._on_vm_play_queue([track, dict(videoId='remote-other')], 0)
    item, remote = screen.on_play_song.call_args.args[6]
    assert item.is_local == (state == 'valid_without_flag')
    assert item.local_path == (str(path) if state == 'valid_without_flag' else None)
    assert not remote.is_local and remote.local_path is None


@pytest.mark.asyncio
async def test_missing_local_download_is_not_marked_available(rig, tmp_path):
    rig.pc._play_local_playlist([dict(video_id='remote-id', file_path=str(tmp_path / 'missing'))])
    assert not rig.pc.queue.current.is_local
    assert rig.pc.queue.current.local_path is None


@pytest.mark.asyncio
async def test_online_remote_members_remain_in_order_and_stream(rig, isolated_db):
    screen = rig.mw.playlist_screen
    screen.on_play_song = Mock()
    screen._playlist_id = 'local-list:mixed'
    screen._vm.set_data(dict(playlist_id=screen._playlist_id, title='Mixed', tracks=[]))
    screen._on_vm_play_queue([dict(videoId=vid) for vid in ['first', 'second', 'first']], 1)
    args = screen.on_play_song.call_args.args
    await rig.pc._play_song(*args)
    assert [item.video_id for item in rig.pc.queue.items] == ['first', 'second', 'first']
    assert rig.pc.queue.current.video_id == 'second'
    rig.pc.extractor.get_stream_info.assert_awaited_once_with('second')
    rig.player.play_url.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('connected', [True, False])
async def test_disappeared_import_does_not_stream_a_local_identity(rig, isolated_db, tmp_path, connected):
    rig.pc.network_monitor.is_connected = connected
    rig.pc.queue.set_queue([QueueItem('local:missing', 'Missing', '', '', 100000, '',
                                     is_local=True, local_path=str(tmp_path / 'gone'))])
    await rig.pc._play_current()
    rig.pc.extractor.get_stream_info.assert_not_awaited()
    rig.player.play_url.assert_not_awaited()
    rig.mw._handle_playback_failure.assert_awaited_once()


@pytest.mark.asyncio
async def test_obsolete_download_result_does_not_mutate_reused_queue_item(rig, tmp_path, monkeypatch):
    import doremi.db.repository as repositories
    old, new = tmp_path / 'old', tmp_path / 'new'
    old.write_bytes(b'old fixture')
    new.write_bytes(b'new fixture')
    entered, release = asyncio.Event(), asyncio.Event()
    async def get_download(vid):
        entered.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            await release.wait()
        return SimpleNamespace(file_path=str(old))
    monkeypatch.setattr(repositories.DownloadRepository, 'get_download', lambda self, vid: get_download(vid))
    item = QueueItem('same', 'Same', '', '', 100000, '')
    rig.pc.queue.set_queue([item])
    pending = asyncio.create_task(rig.pc._play_current())
    await asyncio.wait_for(entered.wait(), 2)
    rig.pc._current_play_id += 1
    item.is_local, item.local_path = True, str(new)
    release.set()
    await pending
    assert item.local_path == str(new)
    rig.player.play_url.assert_not_awaited()


@pytest.mark.asyncio
async def test_late_download_error_does_not_apply_cache_to_new_playback(rig, tmp_path, monkeypatch):
    import doremi.db.repository as repositories
    from doremi.services.offline_cache import OfflineCacheManager
    path = tmp_path / 'old-cache'
    path.write_bytes(b'fixture')
    entered, release = asyncio.Event(), asyncio.Event()
    async def download(self, vid):
        entered.set()
        await release.wait()
        raise RuntimeError('late DB error')
    monkeypatch.setattr(repositories.DownloadRepository, 'get_download', download)
    monkeypatch.setattr(OfflineCacheManager, 'get_instance', lambda: SimpleNamespace(local_path=lambda vid: str(path)))
    item = QueueItem('same', 'Same', '', '', 100000, '')
    rig.pc.queue.set_queue([item])
    pending = asyncio.create_task(rig.pc._play_current())
    await asyncio.wait_for(entered.wait(), 2)
    rig.pc._current_play_id += 1
    release.set()
    await pending
    assert not item.is_local and item.local_path is None
    rig.player.play_url.assert_not_awaited()


@pytest.mark.asyncio
async def test_local_download_producer_captures_collection_before_navigation_context_changes(rig, tmp_path):
    path = tmp_path / 'download'
    path.write_bytes(b'fixture')
    screen = rig.mw.playlist_screen
    screen._playlist_id = 'local_PLfixture'
    screen._vm.set_data(dict(playlist_id=screen._playlist_id, title='Downloaded', is_local=True,
        tracks=[dict(videoId='available')], local_meta=[dict(video_id='available', file_path=str(path))]))
    screen.on_play_local_playlist = rig.pc._play_local_playlist
    screen._vm.play_local_requested.connect(screen._on_vm_play_local)
    # The next route can be selected before its fade/load starts.
    rig.mw._current_path = 'album?id=ALnew'
    screen._vm.play_at(0)
    item = rig.pc.queue.current
    assert (item.context_type, item.context_id, item.context_title) == ('playlist', 'local_PLfixture', 'Downloaded')
    assert screen._vm._local_meta == [dict(video_id='available', file_path=str(path))]


@pytest.mark.asyncio
@pytest.mark.parametrize('producer', ['restored', 'local_metadata'])
async def test_disappeared_previously_local_download_keeps_offline_failure_skip_boundary(rig, isolated_db, tmp_path, producer):
    rig.pc.network_monitor.is_connected = False
    if producer == 'local_metadata':
        rig.mw._current_path = 'playlist?id=local_PLfixture'
        rig.pc._play_local_playlist([dict(video_id='remote-id', file_path=str(tmp_path / 'gone'))])
    else:
        rig.pc.queue.set_queue([QueueItem('remote-id', 'Missing download', '', '', 100000, '',
                                         is_local=True, local_path=str(tmp_path / 'gone'))])
    await rig.pc._play_current()
    rig.pc.extractor.get_stream_info.assert_not_awaited()
    rig.player.play_url.assert_not_awaited()
    rig.mw._handle_playback_failure.assert_awaited_once()
