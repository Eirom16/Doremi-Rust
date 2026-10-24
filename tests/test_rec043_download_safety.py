"""REC044 / D6: reserved local namespaces must never reach the provider."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from doremi.ui.controllers.download_controller import DownloadController


def controller():
    mw = SimpleNamespace(yt=SimpleNamespace(get_playlist=AsyncMock(return_value={'tracks': []})),
        statusBar=Mock(return_value=SimpleNamespace(showMessage=Mock())),
        show_notification=Mock(), _navigate_to=Mock())
    dm = SimpleNamespace(_repo=SimpleNamespace(get_download=AsyncMock(return_value=None)),
                         add_download=Mock(return_value=True))
    schedule = Mock(side_effect=lambda coro: coro.close())
    return DownloadController(mw, dm, schedule), mw, dm, schedule


@pytest.mark.asyncio
@pytest.mark.parametrize('identity', [
    'session:1:2', 'session:bogus', 'smart:liked', 'smart:bogus',
    'local-list:abc', 'local-list:', 'local_PLabc', 'local_', 'local:hash',
    'VLlocal_PLabc', 'VLsession:1:2', '', None,
    'playlist?id=PLabc', 'https://music.youtube.com/playlist?list=PLabc',
    ' smart:liked', 'local%2Dlist%3Aabc',
])
async def test_non_downloadable_identity_rejected_before_scheduling_or_state(identity):
    dc, mw, dm, schedule = controller()
    dc.on_download_playlist_requested(identity, 'Title', '')
    await dc.download_playlist_async(identity, 'Title', '')
    schedule.assert_not_called()
    mw.yt.get_playlist.assert_not_awaited()
    dm._repo.get_download.assert_not_awaited()
    dm.add_download.assert_not_called()
    mw.statusBar.assert_not_called()
    mw.show_notification.assert_not_called()
    mw._navigate_to.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('identity', ['PLabc', 'VLPLabc', 'RDCLAKabc', 'OLAK5uyabc', 'LM', 'XYZ'])
async def test_remote_ids_keep_existing_download_contract(identity):
    dc, mw, dm, schedule = controller()
    mw.yt.get_playlist.return_value = dict(tracks=[dict(videoId='v1', title='Song', artists=[dict(name='A')])])
    await dc.download_playlist_async(identity, 'Title', 'thumb')
    mw.yt.get_playlist.assert_awaited_once_with(identity)
    dm.add_download.assert_called_once_with('v1', 'Song', 'A', '', identity, 'Title', 'thumb')
