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
    gather = AsyncMock(side_effect=[data(), failed, data(offset=5, more=False, ids=['last'])])
    # AsyncMock sequence does not invoke callable entries; use an explicit counter.
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
