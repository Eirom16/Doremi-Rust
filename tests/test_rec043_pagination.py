"""REC043B: incremental playlist contracts, real SQLite and Qt model signals."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from doremi.ui.screens.playlist_qml import PlaylistScreenQml
from doremi.ui.viewmodels.playlist_vm import PlaylistTrackModel, PlaylistViewModel
from test_rec041_playback_context import qapp
from test_rec042_offline_navigation import isolated_db


@pytest.fixture
def screen(qapp, monkeypatch):
    from doremi.services.download_manager import DownloadManager
    monkeypatch.setattr(DownloadManager, 'get_instance', lambda: SimpleNamespace(
        download_progress=Mock(), download_completed=Mock(), _tasks={}))
    result = PlaylistScreenQml(SimpleNamespace(get_playlist=AsyncMock(side_effect=AssertionError('network'))), Mock(), Mock())
    result._refresh_download_state = Mock()
    return result


def page(identity='local-list:x', *, offset=0, limit=2, more=True, ids=None, local=False):
    ids = ids if ids is not None else ['a', 'b']
    return dict(playlist_id=identity, title=identity, author='Author', tracks=[dict(videoId=v) for v in ids],
        track_count=len(ids), offset=offset, limit=limit, has_more=more, is_local=local,
        local_meta=[dict(video_id=v, file_path='/synthetic/'+v) for v in ids] if local else [])


def test_model_appends_rows_without_reset_and_preserves_duplicates(qapp):
    model = PlaylistTrackModel()
    model.set_items([dict(videoId='a')])
    inserted, reset = [], []
    model.rowsInserted.connect(lambda parent, first, last: inserted.append((first, last)))
    model.modelReset.connect(lambda: reset.append(True))
    model.append_items([dict(videoId='a'), dict(videoId='b')])
    model.append_items([])
    assert inserted == [(1, 2)] and reset == []
    assert [t['videoId'] for t in model.all_items()] == ['a', 'a', 'b']


@pytest.mark.parametrize('local', [True, False])
def test_viewmodel_page_identity_offsets_and_totals(qapp, local):
    vm = PlaylistViewModel()
    identity = 'local_PLx' if local else 'local-list:x'
    vm.set_data(page(identity, local=local))
    assert vm.hasMore and vm.pageOffset == 0 and vm.pageLimit == 2
    assert vm.loadedCount == 2 and vm.totalCount == -1
    assert 'cargadas' in vm.meta
    assert not vm.append_page(page('local-list:other', offset=2))
    assert not vm.append_page(page(identity, offset=4))
    final = page(identity, offset=2, more=False, ids=['a'], local=local)
    assert vm.append_page(final)
    assert not vm.append_page(final)
    assert [t['videoId'] for t in vm.tracks.all_items()] == ['a', 'b', 'a']
    assert vm.loadedCount == vm.totalCount == 3 and not vm.hasMore
    assert vm.pageOffset == 2
    if local:
        assert [m['video_id'] for m in vm._local_meta] == ['a', 'b', 'a']


@pytest.mark.asyncio
async def test_consecutive_pages_and_final_no_extra_request(screen, monkeypatch):
    import doremi.ui.screens.playlist_data as module
    gather = AsyncMock(side_effect=[page(), page(offset=2, more=False, ids=['a'])])
    monkeypatch.setattr(module, 'gather_playlist', gather)
    await screen.load('local-list:x', limit=2)
    resets, inserted = [], []
    screen._vm.tracks.modelReset.connect(lambda: resets.append(True))
    screen._vm.tracks.rowsInserted.connect(lambda p, a, b: inserted.append((a, b)))
    assert await screen.load_more()
    assert not await screen.load_more()
    assert gather.await_count == 2
    assert gather.await_args.kwargs == {'limit': 2, 'offset': 2}
    assert inserted == [(2, 2)] and resets == []
    assert screen._vm.loadedCount == 3 and not screen._vm.hasMore


@pytest.mark.asyncio
async def test_more_than_1000_occurrences_with_real_offline_loader(screen, isolated_db, tmp_path):
    from doremi.db.models import Song
    from doremi.db.local_library_repository import LocalLibraryRepository
    path = tmp_path / 'synthetic.opus'
    path.write_bytes(b'fixture; no real music')
    ids = [f'local:{i}' for i in range(1005)]
    async with isolated_db.get_session() as session:
        session.add_all([Song(video_id=v, title=v, artist='A', local_path=str(path)) for v in ids])
        await session.commit()
    repo = LocalLibraryRepository()
    identity = await repo.create_playlist('Large')
    occurrences = ids[:500] + [ids[0]] + ids[500:] + [ids[0]]
    await repo.append(identity, occurrences)
    await screen.load(identity)  # legacy call, first page default 1000
    assert screen._vm.loadedCount == 1000 and screen._vm.hasMore
    assert screen._vm.totalCount == -1
    await screen.load_more()
    assert [t['videoId'] for t in screen._vm.tracks.all_items()] == occurrences
    assert screen._vm.loadedCount == 1007 and screen._vm.totalCount == 1007
    assert not screen._vm.hasMore
    screen.yt.get_playlist.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('identity', ['session:1:4', 'smart:liked', 'local_PLx'])
async def test_other_local_namespaces_support_incremental_pages(screen, monkeypatch, identity):
    import doremi.ui.screens.playlist_data as module
    gather = AsyncMock(side_effect=[page(identity), page(identity, offset=2, more=False, ids=['a'])])
    monkeypatch.setattr(module, 'gather_playlist', gather)
    await screen.load(identity, limit=2)
    await screen.load_more()
    assert [t['videoId'] for t in screen._vm.tracks.all_items()] == ['a', 'b', 'a']


@pytest.mark.asyncio
async def test_same_page_is_not_requested_concurrently(screen, monkeypatch):
    import doremi.ui.screens.playlist_data as module
    entered, release = asyncio.Event(), asyncio.Event()
    async def gather(yt, identity, **kwargs):
        offset = kwargs.get('offset', 0)
        if offset:
            entered.set()
            await release.wait()
        return page(identity, offset=offset, more=not offset, ids=['a'] if offset else None)
    mocked = AsyncMock(side_effect=gather)
    monkeypatch.setattr(module, 'gather_playlist', mocked)
    await screen.load('local-list:x', limit=2)
    pending = asyncio.create_task(screen.load_more())
    try:
        await asyncio.wait_for(entered.wait(), 2)
        assert screen._vm.loadingMore
        assert not await screen.load_more()
        assert mocked.await_count == 2
    finally:
        release.set()
        await pending
    assert screen._vm.loadedCount == 3 and not screen._vm.loadingMore


@pytest.mark.asyncio
@pytest.mark.parametrize('old_outcome', ['success', 'error'])
@pytest.mark.parametrize('replacement', ['local-list:new', 'local-list:old'])
async def test_new_playlist_invalidates_late_page_even_if_cancellation_is_swallowed(screen, monkeypatch, old_outcome, replacement):
    import doremi.ui.screens.playlist_data as module
    entered, release = asyncio.Event(), asyncio.Event()
    async def gather(yt, identity, **kwargs):
        offset = kwargs.get('offset', 0)
        if offset:
            entered.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                await release.wait()
            if old_outcome == 'error':
                raise RuntimeError('late old error')
        return page(identity, offset=offset, more=not offset, ids=['old'] if offset else None)
    monkeypatch.setattr(module, 'gather_playlist', gather)
    await screen.load('local-list:old', limit=2)
    pending = asyncio.create_task(screen.load_more())
    try:
        await asyncio.wait_for(entered.wait(), 2)
        await screen.load(replacement, limit=2)
    finally:
        release.set()
        await asyncio.gather(pending, return_exceptions=True)
    assert screen._playlist_id == screen._vm._playlist_id == replacement
    assert screen._vm.loadedCount == 2 and screen._vm.hasMore
    assert not screen._vm.loadMoreError and not screen._vm.loadingMore


@pytest.mark.asyncio
@pytest.mark.parametrize('cancel', [False, True])
async def test_load_more_failure_or_cancel_preserves_rows_and_is_retryable(screen, monkeypatch, cancel):
    import doremi.ui.screens.playlist_data as module
    error = asyncio.CancelledError() if cancel else RuntimeError('temporary')
    gather = AsyncMock(side_effect=[page(), error, page(offset=2, more=False, ids=['a'])])
    monkeypatch.setattr(module, 'gather_playlist', gather)
    await screen.load('local-list:x', limit=2)
    if cancel:
        with pytest.raises(asyncio.CancelledError):
            await screen.load_more()
    else:
        assert not await screen.load_more()
        assert screen._vm.loadMoreError
    assert screen._vm.loadedCount == 2 and screen._vm.hasMore and not screen._vm.loadingMore
    assert await screen.load_more()
    assert screen._vm.loadedCount == 3 and not screen._vm.loadMoreError


@pytest.mark.asyncio
async def test_remote_provider_payload_is_not_client_paginated(screen, isolated_db):
    screen.yt.get_playlist = AsyncMock(return_value=dict(title='Remote', trackCount=50,
        tracks=[dict(videoId=v, title=v) for v in ['remote', 'remote', 'another']]))
    await screen.load('VLPLremote', limit=2)
    assert screen._vm.loadedCount == 3 and screen._vm.totalCount == 50
    assert not screen._vm.hasMore and not await screen.load_more()
    screen.yt.get_playlist.assert_awaited_once_with('VLPLremote')


@pytest.mark.asyncio
async def test_nonzero_initial_offset_does_not_invent_collection_total(screen, monkeypatch):
    import doremi.ui.screens.playlist_data as module
    monkeypatch.setattr(module, 'gather_playlist', AsyncMock(return_value=page(offset=4, more=False)))
    await screen.load('local-list:x', limit=2, offset=4)
    assert screen._vm.loadedCount == 2 and screen._vm.totalCount == -1
    assert screen._vm.pageOffset == 4 and not screen._vm.hasMore


@pytest.mark.asyncio
async def test_error_on_first_page_can_retry_with_same_contract(screen, monkeypatch):
    import doremi.ui.screens.playlist_data as module
    mocked = AsyncMock(side_effect=[RuntimeError('temporary'), page()])
    monkeypatch.setattr(module, 'gather_playlist', mocked)
    await screen.load('local-list:x', limit=2)
    assert screen._vm.errorText and not screen._vm.loading
    await screen.load('local-list:x', limit=2)
    assert screen._vm.loadedCount == 2 and not screen._vm.errorText


@pytest.mark.asyncio
async def test_old_visible_rows_cannot_start_with_new_playlist_context_while_loading(screen, monkeypatch):
    import doremi.ui.screens.playlist_data as module
    entered, release = asyncio.Event(), asyncio.Event()
    screen._playlist_id = 'local-list:old'
    screen._vm.set_data(page('local-list:old'))
    screen._vm.set_loading(False)
    async def gather(*a, **k):
        entered.set()
        await release.wait()
        return page('local-list:new')
    monkeypatch.setattr(module, 'gather_playlist', gather)
    pending = asyncio.create_task(screen.load('local-list:new', limit=2))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        screen._vm.play_at(0)
        screen.on_play_song.assert_not_called()
    finally:
        release.set()
        await pending


@pytest.mark.asyncio
async def test_header_download_refresh_ignores_previous_generation(screen, monkeypatch):
    from doremi.db.repository import DownloadRepository
    entered, release = asyncio.Event(), asyncio.Event()
    async def downloads(self):
        entered.set()
        await release.wait()
        return [SimpleNamespace(parent_playlist_id='local-list:new')]
    monkeypatch.setattr(DownloadRepository, 'get_downloads', downloads)
    screen._playlist_id = 'local-list:old'
    screen._vm.refresh_counters = Mock()
    pending = asyncio.create_task(screen._refresh_counts())
    await asyncio.wait_for(entered.wait(), 2)
    screen._load_generation += 1
    screen._playlist_id = 'local-list:new'
    release.set()
    await pending
    screen._vm.refresh_counters.assert_not_called()


@pytest.mark.asyncio
async def test_existing_retry_callback_keeps_explicit_page_contract(screen, monkeypatch):
    import doremi.ui.screens.playlist_data as module
    mocked = AsyncMock(side_effect=[RuntimeError('temporary'), page(offset=4, more=False)])
    monkeypatch.setattr(module, 'gather_playlist', mocked)
    await screen.load('local-list:x', limit=2, offset=4)
    screen._retry()
    # ensure_future is the real callback; let it enter load() before awaiting.
    await asyncio.sleep(0)
    if screen._load_task:
        await screen._load_task
    assert mocked.await_args.kwargs == {'limit': 2, 'offset': 4}
    assert screen._vm.pageOffset == 4


@pytest.mark.asyncio
async def test_cancelled_new_identity_cannot_replay_previous_rows(screen, monkeypatch):
    import doremi.ui.screens.playlist_data as module
    screen._playlist_id = 'local-list:old'
    screen._vm.set_data(page('local-list:old'))
    screen._vm.set_loading(False)
    entered = asyncio.Event()
    async def gather(*a, **k):
        entered.set()
        await asyncio.Event().wait()
    monkeypatch.setattr(module, 'gather_playlist', gather)
    pending = asyncio.create_task(screen.load('local-list:new', limit=2))
    await asyncio.wait_for(entered.wait(), 2)
    pending.cancel()
    await asyncio.gather(pending, return_exceptions=True)
    screen._vm.play_at(0)
    screen.on_play_song.assert_not_called()


def test_download_aggregate_is_not_summed_again_for_each_local_page(qapp):
    vm = PlaylistViewModel()
    first = page('local_PLx', local=True)
    first['downloaded_count'] = 3  # loader reports the collection aggregate
    vm.set_data(first)
    vm.set_download_state(vm.DL_PARTIAL)
    assert '/0' not in vm.dlText
    final = page('local_PLx', local=True, offset=2, more=False, ids=['a'])
    final['downloaded_count'] = 3
    assert vm.append_page(final)
    assert vm._downloaded_count == 3
