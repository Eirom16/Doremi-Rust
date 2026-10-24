"""Real offscreen PlaylistScreen interactions; no user music/config/database."""
import asyncio
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')

import pytest
import pytest_asyncio
from PySide6.QtCore import QObject, QPoint, QPointF, Qt, QUrl, QEvent, QCoreApplication
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from doremi.ui.screens.playlist_qml import PlaylistScreenQml, QML_DIR
from doremi.ui.theme_bridge import ThemeBridge


@pytest.fixture(scope='module')
def qapp_ui():
    app = QApplication.instance() or QApplication([])
    from doremi.ui.design.fonts import load_fonts
    load_fonts()
    return app


class World:
    def __init__(self, screen, app, tmp_path):
        self.screen, self.vm, self.app, self.tmp_path = screen, screen._vm, app, tmp_path
        self.widget = None

    def show(self):
        self.theme = ThemeBridge(self.app)
        self.widget = QQuickWidget()
        self.widget.resize(1100, 760)
        self.widget.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self.widget.engine().addImportPath(str(QML_DIR))
        self.widget.rootContext().setContextProperty('themeBridge', self.theme)
        self.widget.setInitialProperties({'screenVm': self.vm})
        self.widget.setSource(QUrl.fromLocalFile(str(QML_DIR/'PlaylistScreen.qml')))
        assert self.widget.status() == QQuickWidget.Ready, [e.toString() for e in self.widget.errors()]
        self.widget.show()
        self.widget.activateWindow(); self.widget.setFocus()
        self.pump()

    def pump(self):
        self.app.processEvents()
        QTest.qWait(10)
        self.app.processEvents()

    def visual_items(self, root=None):
        root = root or self.widget.quickWindow().contentItem()
        yield root
        for child in root.childItems():
            yield from self.visual_items(child)

    def item(self, name):
        return next((i for i in self.visual_items() if i.objectName() == name), None)

    def click(self, name):
        item = self.item(name)
        assert item is not None, f'missing real QML control {name}'
        assert item.isVisible() and item.isEnabled(), f'not operable: {name}'
        point = item.mapToScene(QPointF(item.width()/2, item.height()/2))
        assert 0 <= point.x() <= self.widget.width() and 0 <= point.y() <= self.widget.height(), (name, point)
        QTest.mouseClick(self.widget, Qt.LeftButton, Qt.NoModifier, QPoint(round(point.x()), round(point.y())))
        self.pump()

    async def wait(self, predicate, timeout=3):
        end = asyncio.get_running_loop().time() + timeout
        while not predicate():
            assert asyncio.get_running_loop().time() < end, 'QML/async action timed out'
            self.pump()
            await asyncio.sleep(.01)
        self.pump()

    def end(self):
        item = self.item('playlistList')
        assert item is not None, 'playlist needs a virtualized ListView'
        item.forceActiveFocus()
        QTest.keyClick(self.widget, Qt.Key_End)
        self.pump()

    def home(self):
        self.item('playlistList').forceActiveFocus()
        QTest.keyClick(self.widget, Qt.Key_Home)
        self.pump()

    def screenshot(self, name):
        destination = Path(os.environ.get('DOREMI_UI_EVIDENCE_DIR', self.tmp_path))
        destination.mkdir(parents=True, exist_ok=True)
        assert self.widget.grab().save(str(destination / name))


@pytest_asyncio.fixture
async def ui(qapp_ui, monkeypatch, tmp_path):
    for key in ['CONFIG', 'CACHE', 'DATA']:
        monkeypatch.setenv('XDG_'+key+'_HOME', str(tmp_path/key.lower()))
    from doremi.services.download_manager import DownloadManager
    monkeypatch.setattr(DownloadManager, 'get_instance', lambda: SimpleNamespace(
        download_progress=Mock(), download_completed=Mock(), _tasks={}))
    screen = PlaylistScreenQml(SimpleNamespace(get_playlist=AsyncMock(side_effect=AssertionError('remote request'))),
                              Mock(), Mock(), on_back=Mock())
    screen._refresh_download_state = Mock()
    world = World(screen, qapp_ui, tmp_path)
    yield world
    if world.widget:
        world.widget.setSource(QUrl())
        world.widget.close(); world.widget.deleteLater()
    for task in [getattr(screen, '_load_task', None), getattr(screen, '_page_task', None)]:
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    assert not getattr(screen, '_save_busy', False), 'save must finish before fixture disposal'
    screen._vm.deleteLater(); screen.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    qapp_ui.processEvents()


def data(identity='local-list:test', offset=0, limit=5, more=True, ids=None):
    ids = ids if ids is not None else [f'v{i}' for i in range(offset, offset+limit)]
    return dict(playlist_id=identity, title='Synthetic playlist', author='Fixture',
        offset=offset, limit=limit, has_more=more, track_count=len(ids), tracks=[
            dict(videoId=vid, title=vid, artist='Fixture', duration='1:00', duration_ms=60000,
                 thumbnail_url='', is_downloaded=False, setVideoId='') for vid in ids])


@pytest.mark.asyncio
async def test_qml_load_more_button_appends_exactly_one_page(ui, monkeypatch):
    import doremi.ui.screens.playlist_data as module
    gather = AsyncMock(side_effect=[data(), data(offset=5, more=False, ids=['v0', 'last'])])
    monkeypatch.setattr(module, 'gather_playlist', gather)
    await ui.screen.load('local-list:test', limit=5)
    ui.show()
    assert ui.item('playlistList') is not None, 'Repeater is not virtualized'
    ui.end()
    ui.click('playlistLoadMore')
    await ui.wait(lambda: ui.vm.loadedCount == 7)
    assert [t['videoId'] for t in ui.vm.tracks.all_items()] == ['v0','v1','v2','v3','v4','v0','last']
    assert gather.await_count == 2 and gather.await_args.kwargs == {'limit': 5, 'offset': 5}
    assert not ui.item('playlistLoadMore').isVisible()
    ui.screen.on_play_song.assert_not_called()


@pytest.mark.asyncio
async def test_qml_more_error_retry_keeps_rows_and_busy_is_accessible(ui, monkeypatch):
    import doremi.ui.screens.playlist_data as module
    entered, release = asyncio.Event(), asyncio.Event()
    async def failed(*a, **k):
        entered.set(); await release.wait(); raise RuntimeError('temporary')
    calls = 0
    async def load(yt, identity, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1: return data()
        if calls == 2: return await failed()
        return data(offset=5, more=False, ids=['last'])
    gather = AsyncMock(side_effect=load)
    monkeypatch.setattr(module, 'gather_playlist', gather)
    await ui.screen.load('local-list:test', limit=5); ui.show(); ui.end()
    ui.click('playlistLoadMore')
    try:
        await asyncio.wait_for(entered.wait(), 2)
        assert ui.vm.loadingMore and not ui.item('playlistLoadMore').isEnabled()
        assert ui.vm.loadedCount == 5
    finally:
        release.set()
    await ui.wait(lambda: bool(ui.vm.loadMoreError))
    assert ui.vm.loadedCount == 5 and ui.item('playlistPaginationError').isVisible()
    ui.click('playlistLoadMore')
    await ui.wait(lambda: ui.vm.loadedCount == 6)
    assert not ui.vm.loadMoreError and gather.await_count == 3


from test_rec042_offline_navigation import isolated_db


@pytest.mark.asyncio
async def test_real_offline_1007_occurrences_added_row_playback_and_navigation(ui, isolated_db, tmp_path, monkeypatch):
    from doremi.db.models import Song
    from doremi.db.local_library_repository import LocalLibraryRepository
    import doremi.ui.screens.playlist_data as module
    path = tmp_path/'synthetic.opus'; path.write_bytes(b'fixture; VLC is not invoked')
    ids = [f'local:{i}' for i in range(1005)]
    async with isolated_db.get_session() as session:
        session.add_all([Song(video_id=v, title=v, artist='Fixture', local_path=str(path)) for v in ids])
        await session.commit()
    repo = LocalLibraryRepository(); identity = await repo.create_playlist('Offline 1007')
    occurrences = ids[:500]+[ids[0]]+ids[500:]+[ids[0]]
    await repo.append(identity, occurrences)
    gather = AsyncMock(wraps=module.gather_playlist)
    monkeypatch.setattr(module, 'gather_playlist', gather)
    await ui.screen.load(identity); ui.show()
    assert ui.vm.loadedCount == 1000
    assert len([i for i in ui.visual_items() if i.objectName().startswith('playlistTrackRow')]) < 40
    ui.click('playlistTrackRow0')
    previous_queue = ui.screen.on_play_song.call_args.args[6]
    assert len(previous_queue) == 1000
    ui.end(); ui.click('playlistLoadMore')
    # Keyboard activation of the now-disabled control cannot repeat the request.
    QTest.keyClick(ui.widget, Qt.Key_Return)
    await ui.wait(lambda: ui.vm.loadedCount == 1007)
    assert gather.await_count == 2 and gather.await_args.kwargs == dict(limit=1000, offset=1000)
    assert [t['videoId'] for t in ui.vm.tracks.all_items()] == occurrences
    assert len(previous_queue) == 1000 and ui.screen.on_play_song.call_count == 1
    ui.end()
    await ui.wait(lambda: ui.item('playlistTrackRow1006') is not None)
    ui.click('playlistTrackRow1006')
    args = ui.screen.on_play_song.call_args.args
    assert args[7] == 1006 and len(args[6]) == 1007 and args[0] == ids[0]
    assert all(t.is_local and t.local_path == str(path) and t.context_id == identity for t in args[6])
    ui.item('playlistTrackRow1006').forceActiveFocus()
    QTest.keyClick(ui.widget, Qt.Key_Menu); ui.pump()
    assert ui.item('playlistPlayNext1006') is not None
    assert ui.item('playlistPlayNext1006').isVisible()
    QTest.keyClick(ui.widget, Qt.Key_Escape); ui.pump()
    ui.screenshot('playlist-offline-1007.png')
    ui.home(); ui.click('playlistBack')
    ui.screen.on_back.assert_called_once_with()
    ui.screen.yt.get_playlist.assert_not_awaited()


@pytest.mark.asyncio
async def test_large_list_keeps_delegate_allocation_bounded(ui):
    import json, resource, time
    ids = [str(i) for i in range(10007)]
    ui.screen._playlist_id = 'local-list:large'
    ui.vm.set_data(data('local-list:large', more=False, ids=ids)); ui.vm.set_loading(False)
    before = int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')//1024
    started = time.perf_counter(); ui.show()
    initial_rows = len([i for i in ui.visual_items() if i.objectName().startswith('playlistTrackRow')])
    ui.end(); await ui.wait(lambda: ui.item('playlistTrackRow10006') is not None)
    final_rows = len([i for i in ui.visual_items() if i.objectName().startswith('playlistTrackRow')])
    assert 0 < initial_rows < 40 and 0 < final_rows < 60
    after = int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')//1024
    evidence = dict(rows=10007, initial_delegates=initial_rows, final_delegates=final_rows,
        elapsed_ms=round((time.perf_counter()-started)*1000,2), rss_delta_kib=after-before,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    destination = Path(os.environ.get('DOREMI_UI_EVIDENCE_DIR', ui.tmp_path)); destination.mkdir(parents=True, exist_ok=True)
    (destination/'virtualization-10007.json').write_text(json.dumps(evidence,indent=2))


@pytest.mark.asyncio
@pytest.mark.parametrize('old_error', [False, True])
async def test_qml_navigation_discards_a_late_page(ui, monkeypatch, old_error):
    import doremi.ui.screens.playlist_data as module
    entered, release = asyncio.Event(), asyncio.Event()
    async def gather(yt, identity, **kwargs):
        offset = kwargs.get('offset',0)
        if offset:
            entered.set()
            try: await release.wait()
            except asyncio.CancelledError: await release.wait()
            if old_error: raise RuntimeError('old page error')
        return data(identity, offset=offset, more=not offset)
    monkeypatch.setattr(module, 'gather_playlist', gather)
    await ui.screen.load('local-list:old', limit=5); ui.show(); ui.end(); ui.click('playlistLoadMore')
    await asyncio.wait_for(entered.wait(), 2)
    pending = ui.screen._page_task
    tasks=[]
    ui.screen.on_back = lambda: tasks.append(asyncio.create_task(ui.screen.load('local-list:new', limit=5)))
    try:
        ui.home(); ui.click('playlistBack')
        await asyncio.gather(*tasks)
    finally:
        release.set(); await asyncio.gather(pending, return_exceptions=True)
    assert ui.vm._playlist_id == 'local-list:new' and ui.vm.loadedCount == 5
    assert not ui.vm.loadMoreError and not ui.vm.loadingMore
    assert ui.item('playlistLoadMore').isEnabled()
    ui.screen.on_play_song.assert_not_called()


@pytest.mark.asyncio
async def test_remote_playlist_has_no_fake_load_more_control(ui):
    ui.screen._playlist_id = 'PLremote'
    ui.vm.set_data(data('PLremote', more=True)); ui.vm.set_loading(False)
    ui.show(); ui.end()
    assert not ui.item('playlistLoadMore').isVisible()


@pytest.mark.asyncio
async def test_keyboard_context_menu_remains_operable(ui):
    ui.screen._playlist_id = 'local-list:test'
    ui.vm.set_data(data(more=False)); ui.vm.set_loading(False)
    calls=[]
    ui.vm.play_next_requested.connect(lambda *args: calls.append(args))
    ui.show(); ui.end()
    ui.item('playlistTrackRow4').forceActiveFocus()
    QTest.keyClick(ui.widget, Qt.Key_Menu); ui.pump()
    assert ui.item('playlistPlayNext4') is not None
    ui.click('playlistPlayNext4')
    assert calls and calls[-1][0] == 'v4'


async def confirm_save_with_real_controls(ui, title):
    ui.home(); ui.click('playlistSaveSession')
    await ui.wait(lambda: ui.item('sessionPlaylistTitle') is not None and ui.item('sessionPlaylistTitle').isVisible())
    ui.click('sessionPlaylistTitle')
    QTest.keyClick(ui.widget, Qt.Key_A, Qt.ControlModifier)
    QTest.keyClicks(ui.widget, title)
    ui.click('sessionPlaylistConfirm')


@pytest.mark.asyncio
async def test_save_boundary_claims_before_task_and_blocks_button_plus_keyboard(ui, monkeypatch):
    import doremi.ui.screens.playlist_data as module
    from doremi.services.listening_periods import ListeningPeriods
    monkeypatch.setattr(module, 'gather_playlist', AsyncMock(return_value=data('session:1:3', more=False)))
    entered, release = asyncio.Event(), asyncio.Event()
    async def save(*args, **kwargs):
        entered.set(); await release.wait(); return 'local-list:saved'
    command = AsyncMock(side_effect=save)
    monkeypatch.setattr(ListeningPeriods, 'save_as_playlist', command)
    await ui.screen.load('session:1:3', limit=5); ui.show()
    try:
        assert ui.item('playlistSaveSession') is not None, 'missing session save action'
        await confirm_save_with_real_controls(ui, 'Saved session')
        assert ui.vm.saveBusy and command.await_count == 0, 'claim must happen before the task runs'
        ui.vm.save_session('Duplicate')  # same synchronous boundary as keyboard/accessibility
        QTest.keyClick(ui.widget, Qt.Key_Return)
        await asyncio.wait_for(entered.wait(), 2)
        assert command.await_count == 1 and not ui.item('playlistSaveSession').isEnabled()
    finally:
        release.set()
        task = getattr(ui.screen, '_save_task', None)
        if task: await asyncio.gather(task, return_exceptions=True)
    await ui.wait(lambda: ui.vm.savedPlaylistId == 'local-list:saved')
    assert not ui.vm.saveBusy and not ui.vm.saveError
    assert command.await_args.args[:3] == (1, 3, 'Saved session')
    ui.screen.on_navigate = Mock()
    ui.click('playlistOpenSaved')
    ui.screen.on_navigate.assert_called_once_with('playlist?id=local-list%3Asaved')
