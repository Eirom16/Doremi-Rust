from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QObject, QUrl, QCoreApplication, QEvent, QMetaObject, Qt
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("filename", ["MainShell.qml", "HomeScreen.qml", "PlaylistScreen.qml", "StatsScreen.qml", "MiniPlayer.qml", "CommandPalette.qml", "PlaylistPicker.qml", "AlbumScreen.qml", "ArtistScreen.qml", "LibraryScreen.qml", "HistoryScreen.qml", "SearchScreen.qml", "NowPlayingScreen.qml", "Doremi/MediaCard.qml", "Doremi/SongMenu.qml", "Doremi/CollectionMenu.qml", "Doremi/TrackDragArea.qml"])
def test_new_qml_components_compile(qapp, filename):
    from doremi.ui.theme_bridge import theme_bridge
    folder = Path("src/doremi/ui/qml").resolve()
    engine = QQmlEngine()
    engine.addImportPath(str(folder))
    engine.rootContext().setContextProperty("themeBridge", theme_bridge())
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(folder / filename)))
    assert component.isReady(), [error.toString() for error in component.errors()]
    component.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    engine.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


@pytest.mark.parametrize("collapsed", [False, True])
def test_sidebar_playlists_scroll_without_hiding_collapse_button(qapp, collapsed):
    from PySide6.QtCore import QPointF
    from PySide6.QtQuick import QQuickItem
    from doremi.ui.widgets.nav_sidebar_qml import NavSidebarQml
    from doremi.ui.theme_bridge import theme_bridge
    folder = Path("src/doremi/ui/qml").resolve()
    controller = NavSidebarQml(None)
    controller.set_playlists([dict(title=f"Playlist {i}", navigate=f"playlist?id={i}") for i in range(6)])
    controller.set_collapsed(collapsed)
    engine = QQmlEngine()
    engine.addImportPath(str(folder))
    engine.rootContext().setContextProperty("themeBridge", theme_bridge())
    engine.rootContext().setContextProperty("testSidebar", controller)
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
    component = QQmlComponent(engine)
    component.setData(b'import QtQuick\nimport QtQuick.Controls\nimport Doremi 1.0\n'
                      b'ApplicationWindow { width: testSidebar.collapsed ? 64 : 214; height: 520; visible: true; '
                      b'NavigationSidebar { anchors.fill: parent; navigationController: testSidebar } }',
                      QUrl.fromLocalFile(str(folder / "SidebarScrollTest.qml")))
    assert component.isReady(), [e.toString() for e in component.errors()]
    window = component.create()
    assert window is not None
    try:
        scroll = window.findChild(QObject, "sidebarPlaylistScroll")
        button = window.findChild(QQuickItem, "sidebarCollapseButton")
        window.contentItem().polish()
        qapp.processEvents()
        # Force layout polish without waiting for a render-loop timer.
        window.contentItem().ensurePolished()
        qapp.processEvents()
        y = button.mapToScene(QPointF(0, 0)).y()
        assert y >= 0
        assert y + button.height() <= window.height()
        assert button.height() == 44
        assert scroll.property("contentHeight") > scroll.property("availableHeight") > 0
        flickable = scroll.property("contentItem")
        # Repeater delegates have visual parents, not necessarily QObject
        # ownership below the window, so walk the visual tree.
        def visual_items(parent):
            for child in parent.childItems():
                yield child
                yield from visual_items(child)
        last = [item for item in visual_items(window.contentItem())
                if item.objectName() == "sidebarPlaylistShortcut"][-1]
        last.forceActiveFocus()
        assert flickable.property("contentY") > 0
        assert last.y() + last.height() <= flickable.property("contentY") + flickable.height()
        assert button.mapToScene(QPointF(0, 0)).y() == y
        QMetaObject.invokeMethod(button, "forceActiveFocus")
        QTest.keyClick(window, Qt.Key_Return)
        assert controller.collapsed != collapsed
        assert not warnings
    finally:
        window.close()
        for obj in (window, component, controller):
            obj.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_playlist_dialogs_have_bounded_width_without_binding_loops(qapp):
    from doremi.ui.viewmodels.playlist_vm import PlaylistViewModel
    from doremi.ui.theme_bridge import theme_bridge
    folder = Path("src/doremi/ui/qml").resolve()
    vm = PlaylistViewModel()
    vm.set_data(dict(playlist_id="local-list:p", title="Una playlist " * 30, tracks=[]))
    vm.set_loading(False)
    engine = QQmlEngine()
    engine.addImportPath(str(folder))
    engine.rootContext().setContextProperty("themeBridge", theme_bridge())
    engine.rootContext().setContextProperty("testPlaylist", vm)
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
    component = QQmlComponent(engine)
    component.setData(b'import QtQuick\nimport QtQuick.Controls\nimport "."\n'
                      b'ApplicationWindow { width: 640; height: 520; visible: true; '
                      b'PlaylistScreen { anchors.fill: parent; screenVm: testPlaylist } }',
                      QUrl.fromLocalFile(str(folder / "PlaylistDialogTest.qml")))
    assert component.isReady(), [e.toString() for e in component.errors()]
    window = component.create()
    assert window is not None
    try:
        for name in ("renamePlaylistDialog", "deletePlaylistDialog"):
            dialog = window.findChild(QObject, name)
            QMetaObject.invokeMethod(dialog, "open")
            qapp.processEvents()
            assert 0 < dialog.property("width") < window.width()
            assert dialog.property("visible")
            QMetaObject.invokeMethod(dialog, "close")
        assert not warnings
    finally:
        window.close()
        for obj in (window, component, vm):
            obj.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_failed_artwork_backoff_is_bounded_and_expires(qapp):
    from PySide6.QtQml import QQmlExpression
    folder = Path("src/doremi/ui/qml/Doremi").resolve()
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    component.setData(b'import QtQuick\nimport "ArtworkFailures.js" as Failures\n'
                      b'QtObject { function check() { '
                      b'Failures.remember("missing", 1000); '
                      b'if (Failures.sourceFor("missing", 1001) !== "") return false; '
                      b'if (Failures.sourceFor("other", 1001) !== "other") return false; '
                      b'if (Failures.sourceFor("missing", 301000) !== "missing") return false; '
                      b'for (var i = 0; i < 200; ++i) Failures.remember("url" + i, 1000); '
                      b'return Failures.order.length === 128 && Failures.sourceFor("url0", 1001) === "url0"; } }',
                      QUrl.fromLocalFile(str(folder / "ArtworkBackoffTest.qml")))
    assert component.isReady(), [e.toString() for e in component.errors()]
    obj = component.create()
    expression = QQmlExpression(engine.rootContext(), obj, "check()")
    assert expression.evaluate()[0] is True
    assert not expression.hasError(), expression.error().toString()
    for item in (expression, obj, component):
        item.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    engine.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_media_card_missing_artwork_has_fallback_and_is_not_refetched(qapp, tmp_path):
    from PySide6.QtTest import QSignalSpy
    from doremi.ui.theme_bridge import theme_bridge
    folder = Path("src/doremi/ui/qml").resolve()
    engine = QQmlEngine()
    engine.addImportPath(str(folder))
    engine.rootContext().setContextProperty("themeBridge", theme_bridge())
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(folder / "Doremi/MediaCard.qml")))
    assert component.isReady(), [e.toString() for e in component.errors()]
    url = QUrl.fromLocalFile(str(tmp_path / "missing.jpg")).toString()
    card = component.createWithInitialProperties(dict(thumbnail=url, width=180, height=240))
    assert card is not None
    second = None
    try:
        artwork = card.findChild(QObject, "mediaCardArtwork")
        fallback = card.findChild(QObject, "mediaCardArtworkFallback")
        status = QSignalSpy(artwork.statusChanged)
        if not fallback.property("visible"):
            assert status.wait(1000)
        qapp.processEvents()
        assert fallback.property("visible")
        second = component.createWithInitialProperties(dict(thumbnail=url, width=180, height=240))
        assert second is not None
        assert second.findChild(QObject, "mediaCardArtwork").property("source").isEmpty()
        assert second.findChild(QObject, "mediaCardArtworkFallback").property("visible")
    finally:
        for obj in (second, card, component):
            if obj is not None:
                obj.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


@pytest.mark.parametrize("name", ["CommandPalette", "PlaylistPicker"])
def test_new_popups_follow_dark_and_light_tokens(qapp, name):
    from doremi.ui.theme_bridge import ThemeBridge
    from doremi.ui.design import tokens
    folder = Path("src/doremi/ui/qml").resolve()
    bridge = ThemeBridge()
    engine = QQmlEngine()
    engine.addImportPath(str(folder))
    engine.rootContext().setContextProperty("themeBridge", bridge)
    component = QQmlComponent(engine)
    component.setData(('import QtQuick\nimport "."\n' + name +
                       ' { readonly property color observedText: palette.text; '
                       'readonly property color observedBase: palette.base }').encode(),
                      QUrl.fromLocalFile(str(folder / "PaletteTest.qml")))
    assert component.isReady(), [e.toString() for e in component.errors()]
    popup = component.create()
    assert popup is not None
    for scheme in (tokens.DARK, tokens.LIGHT):
        bridge.push(scheme)
        qapp.processEvents()
        assert popup.property("observedText").name() == scheme.text_primary.lower()
        assert popup.property("observedBase").name() == scheme.bg_surface.lower()
    for obj in (popup, component):
        obj.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    engine.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_miniplayer_shares_likes_and_restores_muted_volume(qapp):
    from doremi.ui.viewmodels.mini_player_vm import MiniPlayerViewModel
    from doremi.ui.viewmodels.now_playing_vm import NowPlayingViewModel
    vm = MiniPlayerViewModel()
    actions = NowPlayingViewModel()
    vm.set_track_actions(actions)
    actions.set_liked(True)
    assert vm.trackActions.liked
    volumes = []
    vm.volume_requested.connect(volumes.append)
    vm.change_volume(42)
    vm.toggle_mute()
    vm.toggle_mute()
    assert volumes == [42, 0, 42]


def test_displayed_track_actions_follow_queue_while_vlc_loads(qapp):
    from doremi.audio.queue import PlayQueue, QueueItem
    from doremi.ui.screens.now_playing_qml import NowPlayingScreenQml
    queue = PlayQueue()
    queue.set_queue([QueueItem("local:new", "New", "", "", 1000, "")])
    player = SimpleNamespace(status=SimpleNamespace(current_video_id="old", position_ms=0, duration_ms=1000))
    screen = NowPlayingScreenQml(player, queue, None, Mock())
    screen.update_track_info("New", "", "")
    requested = []
    screen.like_requested.connect(lambda video_id, _: requested.append(video_id))
    screen._vm.toggle_like_current()
    assert requested == ["local:new"]
    assert screen._vm.localTrack
    screen.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_download_feedback_updates_menu_state_and_rows_without_reset(qapp):
    from doremi.services.experience_events import events
    from doremi.ui.viewmodels.playlist_vm import PlaylistTrackModel
    from doremi.ui.viewmodels.now_playing_vm import NowPlayingViewModel
    model = PlaylistTrackModel()
    model.set_items([dict(videoId="v"), dict(videoId="other"), dict(videoId="v")])
    resets = []
    model.modelReset.connect(lambda: resets.append(True))
    vm = NowPlayingViewModel()
    vm.set_track_info("Song", "", "", video_id="v")
    events.downloaded_changed.emit("v", True)
    assert vm.downloaded
    assert [model.track_info(i).get("is_downloaded", False) for i in range(3)] == [True, False, True]
    events.downloaded_changed.emit("v", False)
    assert not vm.downloaded
    assert not resets
    events.downloaded_changed.emit("v", True)
    vm.set_track_info("Other", "", "", video_id="other")
    assert not vm.downloaded
    for obj in (model, vm):
        obj.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


@pytest.mark.parametrize("video_id,url", [("remote", "https://music.youtube.com/watch?v=remote"), ("local:123", None), ("local", None)])
def test_mpris_never_publishes_a_youtube_url_for_imported_audio(video_id, url, monkeypatch):
    import doremi.system.mpris as module
    from doremi.audio.queue import PlayQueue
    fake_dbus = SimpleNamespace(Dictionary=lambda value, **kw: value, ObjectPath=str, Int64=int,
                                String=str, Array=lambda value, **kw: value)
    monkeypatch.setattr(module, "dbus", fake_dbus)
    monkeypatch.setattr(module, "_DBUS_OK", True)
    player = module.MprisPlayer(Mock(), PlayQueue())
    player._active = True
    player._service = Mock()
    player.update_metadata("Song", "Artist", "Album", 1000000, "", video_id)
    assert player.metadata.get("xesam:url") == url
    player._service.notify_properties_changed.assert_called_once()


def test_command_search_and_invocation(qapp):
    from doremi.ui.controllers.command_controller import CommandController
    window = QObject()
    window._navigate_to = Mock()
    window._on_play_pause = Mock()
    window._on_next = Mock()
    window._on_prev = Mock()
    window.search_bar = SimpleNamespace(focus_search=Mock())
    window.now_playing_screen = SimpleNamespace(_vm=Mock())
    window.sidebar = SimpleNamespace(playlists=[dict(title="Gym", navigate="playlist?id=g")])
    controller = CommandController(window)
    controller.search("estadisticas")
    assert controller.results[0]["id"] == "stats"
    controller.execute("stats")
    window._navigate_to.assert_called_with("stats")
    controller.search("a&b")
    controller.execute("query")
    window._navigate_to.assert_called_with("search?query=a%26b")
    controller.execute("open:playlist?id=g")
    window._navigate_to.assert_called_with("playlist?id=g")


def test_collection_enqueue_order_and_direct_home_play(qapp):
    from doremi.ui.viewmodels.track_actions import dispatch_collection_action
    from doremi.ui.viewmodels.home_vm import HomeViewModel
    vm = SimpleNamespace(play_next_requested=Mock(), add_to_queue_requested=Mock())
    tracks = [dict(videoId="a", title="A"), dict(videoId="b", title="B")]
    dispatch_collection_action(vm, tracks, "play_next")
    assert [call.args[0] for call in vm.play_next_requested.emit.call_args_list] == ["b", "a"]
    dispatch_collection_action(vm, tracks, "add_to_queue")
    assert [call.args[0] for call in vm.add_to_queue_requested.emit.call_args_list] == ["a", "b"]
    home = HomeViewModel()
    routes = []
    home.navigate_requested.connect(routes.append)
    home.play_collection("playlist?id=p&resume=old", False)
    home.play_collection("album?id=album", True)
    home.play_collection("artist?id=artist", False)
    assert routes == ["playlist?id=p&autoplay=play", "album?id=album&autoplay=shuffle"]


def test_album_menu_uses_real_share_url_and_distinct_track_copy_signal(qapp):
    from doremi.ui.viewmodels.album_vm import AlbumViewModel
    vm = AlbumViewModel()
    vm.set_data(dict(browse_id="a", title="Album", primary_artist="Artist",
                     share_url="https://music.youtube.com/playlist?list=OLAK5uy_real",
                     tracks=[dict(videoId="song", title="Song")]))
    collections, tracks, artists = [], [], []
    vm.collection_copy_link_requested.connect(collections.append)
    vm.copy_link_requested.connect(tracks.append)
    vm.artist_clicked.connect(artists.append)
    vm.collection_action("copy_link")
    vm.collection_action("go_artist")
    vm.track_action(0, "copy_link")
    assert collections == ["https://music.youtube.com/playlist?list=OLAK5uy_real"]
    assert tracks == ["song"]
    assert artists == ["Artist"]
    vm.set_data(dict(title="No link", tracks=[]))
    assert not vm.canCopyLink
    assert not vm.hasPrimaryArtist


@pytest.mark.asyncio
async def test_queue_reuses_known_duration_without_extracting_stream(qapp):
    from doremi.audio.queue import PlayQueue
    from doremi.ui.controllers.queue_controller import QueueController
    queue = PlayQueue()
    window = SimpleNamespace(statusBar=Mock(), playback_controller=Mock())
    extractor = Mock()
    controller = QueueController(window, queue, extractor, Mock())
    await controller.add_to_queue_async("v", "Song", "Artist", "", metadata=dict(album="Album", duration_ms=60000))
    assert queue.current.duration_ms == 60000
    assert queue.current.album == "Album"
    extractor.get_stream_info.assert_not_called()


def test_destructive_playlist_confirmation_targets_exact_occurrence(qapp):
    from doremi.ui.viewmodels.playlist_vm import PlaylistViewModel
    vm = PlaylistViewModel()
    vm.set_data(dict(playlist_id="local-list:p", title="P", tracks=[
        dict(videoId="same", title="Song", local_position=0),
        dict(videoId="same", title="Song", local_position=1),
    ]))
    vm.set_loading(False)
    removed, edited, errors = [], [], []
    vm.remove_local_requested.connect(lambda *args: removed.append(args))
    vm.local_edit_requested.connect(lambda *args: edited.append(args))
    vm.notification_requested.connect(lambda *args: errors.append(args))
    target = vm.removal_target(1)
    vm.remove_target(target)
    assert removed == [("local-list:p", 1, "same", "Song")]
    vm.tracks.set_items([dict(videoId="same", title="Song", local_position=0)])
    vm.remove_target(target)
    assert len(removed) == 1  # Never delete another duplicate after a refresh.
    vm.set_data(dict(playlist_id="local-list:other", title="Other", tracks=[]))
    vm.edit_local_target("local-list:p", "delete", "")
    vm.remove_target(target)
    assert not edited
    assert len(removed) == 1
    assert len(errors) == 3


def test_view_state_is_bounded_and_primitive():
    from doremi.services.view_state import ViewStateStore
    store = ViewStateStore(limit=2)
    store.save("library", {"scroll": 500, "filter": "rock", "tab": "albums", "object": object(), "bad": float("nan")})
    assert store.get("library") == dict(scroll=500, filter="rock", tab="albums")
    copy = store.get("library")
    copy["scroll"] = 0
    assert store.get("library")["scroll"] == 500
    store.save("album?id=a", {})
    store.save("album?id=b", {})
    assert store.get("library") == {}


def test_drop_payload_validation_and_queue_dispatch(qapp):
    from doremi.ui.controllers.desktop_controller import DesktopController
    window = QObject()
    window.sidebar = SimpleNamespace(playlists=[])
    window.queue_controller = SimpleNamespace(on_add_to_queue_requested=Mock())
    controller = DesktopController(window)
    controller.drop_track('{"videoId":"local:123","title":"Song","artist":"Artist"}', "queue")
    window.queue_controller.on_add_to_queue_requested.assert_called_once_with(
        "local:123", "Song", "Artist", "")
    for payload in ("not json", "{}", '{"videoId":17}', '{"videoId":""}'):
        controller.drop_track(payload, "queue")
    controller.drop_track('{"videoId":"other","title":"Other"}', "playlist?id=forged")
    window.queue_controller.on_add_to_queue_requested.assert_called_once()


def test_queue_drop_checks_indices(qapp):
    from doremi.ui.viewmodels.now_playing_vm import NowPlayingViewModel
    vm = NowPlayingViewModel()
    vm.set_queue([{"videoId": "a", "title": "A"}, {"videoId": "b", "title": "B"}], set(), 0)
    moved = []
    vm.queue_move_requested.connect(lambda source, target: moved.append((source, target)))
    vm.reorder_queue(-1, 0)
    vm.reorder_queue(0, 2)
    vm.reorder_queue(0, 0)
    vm.reorder_queue(0, 1)
    assert moved == [(0, 1)]


def test_queue_copy_preserves_exact_occurrence_and_local_file(qapp):
    from doremi.audio.queue import PlayQueue, QueueItem
    from doremi.ui.controllers.queue_controller import QueueController
    from doremi.ui.viewmodels.now_playing_vm import NowPlayingViewModel
    queue = PlayQueue()
    queue.set_queue([
        QueueItem("same", "Song", "Artist", "", 1000, "", context_type="playlist", context_id="first"),
        QueueItem("same", "Song", "Artist", "Album", 2000, "art", is_local=True,
                  local_path="/tmp/track.ogg", context_type="album", context_id="second"),
    ])
    window = SimpleNamespace(statusBar=Mock(), playback_controller=Mock())
    controller = QueueController(window, queue, Mock(), Mock())
    vm = NowPlayingViewModel()
    vm.set_queue(queue.items, set(), 0)
    vm.queue_copy_requested.connect(controller.requeue_occurrence)
    vm.queue_action(1, "add_to_queue")
    copied = queue.items[-1]
    assert copied is not queue.items[1]
    assert (copied.context_type, copied.context_id, copied.local_path) == ("album", "second", "/tmp/track.ogg")
    assert copied.duration_ms == 2000
    before = len(queue.items)
    controller.requeue_occurrence(-1, True)
    controller.requeue_occurrence(before, True)
    assert len(queue.items) == before


def test_command_palette_keyboard_focus_navigation_escape_and_enter(qapp):
    from doremi.ui.controllers.command_controller import CommandController
    from doremi.ui.theme_bridge import theme_bridge
    folder = Path("src/doremi/ui/qml").resolve()
    owner = QObject()
    owner._navigate_to = Mock()
    owner._on_play_pause = Mock()
    owner._on_next = Mock()
    owner._on_prev = Mock()
    owner.search_bar = SimpleNamespace(focus_search=Mock())
    owner.now_playing_screen = SimpleNamespace(_vm=Mock())
    owner.sidebar = SimpleNamespace(playlists=[])
    controller = CommandController(owner)
    engine = QQmlEngine()
    engine.addImportPath(str(folder))
    engine.rootContext().setContextProperty("themeBridge", theme_bridge())
    engine.rootContext().setContextProperty("testCommands", controller)
    component = QQmlComponent(engine)
    component.setData(b'import QtQuick\nimport QtQuick.Controls\nimport "."\n'
                      b'ApplicationWindow { width: 640; height: 520; visible: true; '
                      b'CommandPalette { controller: testCommands } }',
                      QUrl.fromLocalFile(str(folder / "KeyboardTest.qml")))
    assert component.isReady(), [e.toString() for e in component.errors()]
    window = component.create()
    assert window is not None
    try:
        palette = window.findChild(QObject, "commandPalette")
        query = window.findChild(QObject, "commandQuery")
        results = window.findChild(QObject, "commandResults")
        QMetaObject.invokeMethod(palette, "open")
        qapp.processEvents()
        assert query.property("activeFocus")
        QTest.keyClick(window, Qt.Key_Down)
        assert results.property("currentIndex") == 1
        QTest.keyClick(window, Qt.Key_Up)
        assert results.property("currentIndex") == 0
        QTest.keyClick(window, Qt.Key_Escape)
        assert not palette.property("visible")
        QMetaObject.invokeMethod(palette, "open")
        qapp.processEvents()
        for character in "estadisticas":
            QTest.keyClick(window, Qt.Key(ord(character.upper())))
        assert controller.results[0]["id"] == "stats"
        QTest.keyClick(window, Qt.Key_Return)
        owner._navigate_to.assert_called_once_with("stats")
        assert not palette.property("visible")
    finally:
        window.close()
        window.deleteLater()
        component.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


@pytest.mark.parametrize("module,name", [
    ("playlist_vm", "PlaylistTrackModel"), ("album_vm", "DetailTrackModel"),
    ("artist_vm", "ArtistSongModel"), ("library_vm", "LibrarySongModel"),
    ("search_vm", "SearchSongModel"), ("stats_vm", "TopSongsModel"),
    ("home_vm", "SongGridModel"), ("history_vm", "HistoryListModel"),
    ("now_playing_vm", "NowPlayingQueueModel"),
    ("home_vm", "TileModel"), ("now_playing_vm", "RelatedModel"),
    ("downloads_vm", "DownloadSongModel"),
])
def test_favorite_updates_all_occurrences_without_reset(qapp, module, name):
    from importlib import import_module
    from doremi.services.experience_events import events
    model = getattr(import_module("doremi.ui.viewmodels." + module), name)()
    model.set_items([{"videoId": "same"}, {"videoId": "other"}, {"videoId": "same"}])
    resets, changed = [], []
    model.modelReset.connect(lambda: resets.append(True))
    model.dataChanged.connect(lambda first, last, roles: changed.append(first.row()))
    events.liked_changed.emit("same", True)
    assert [model.get(i).get("is_liked", False) for i in range(3)] == [True, False, True]
    assert changed == [0, 2]
    assert not resets
    events.liked_changed.emit("same", True)
    assert changed == [0, 2]
    model.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_action_metadata_preserves_unplayed_search_result(qapp):
    from doremi.ui.controllers.track_action_data import capture_track_metadata
    from doremi.ui.viewmodels.search_vm import SearchViewModel
    vm = SearchViewModel()
    vm.set_songs([dict(videoId="v", title="Known title", artist="Artist", duration_ms=120000,
                       thumbnail_url="art")])
    window = SimpleNamespace(_current_route="search", search_screen=SimpleNamespace(_vm=vm), queue=None)
    captured = capture_track_metadata(window, "v")
    vm.set_songs([])
    assert captured == dict(title="Known title", artist="Artist", album="", duration_ms=120000, thumbnail_url="art")


@pytest.mark.asyncio
async def test_pin_feedback_reverts_after_write_failure(qapp, monkeypatch):
    from unittest.mock import AsyncMock
    from doremi.db.experience_repository import ExperienceRepository
    from doremi.ui.controllers.navigation_controller import NavigationController
    from doremi.ui.widgets.nav_sidebar_qml import NavSidebarQml
    sidebar = NavSidebarQml(None)
    sidebar.set_playlists([dict(title="Gym", navigate="playlist?id=p")])
    states = []
    sidebar.playlists_changed.connect(lambda: states.append(sidebar.playlists[0]["pinned"]))
    monkeypatch.setattr(ExperienceRepository, "is_pinned", AsyncMock(return_value=False))

    async def failing_write(*args, **kwargs):
        assert sidebar.playlists[0]["pinned"]  # Feedback precedes persistence.
        raise OSError("disk unavailable")

    monkeypatch.setattr(ExperienceRepository, "set_pin", failing_write)
    window = SimpleNamespace(show_notification=Mock())
    await NavigationController(window, Mock())._toggle_pin("p", "Gym", "")
    assert states == [True, False]
    window.show_notification.assert_called_once_with("No se pudo cambiar el acceso fijado", "error")
    sidebar.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


@pytest.mark.parametrize("video_id", ["remote", "local:123"])
def test_shared_track_actions_keep_local_and_remote_operations_distinct(video_id):
    from doremi.ui.viewmodels.track_actions import dispatch_track_action
    names = ("like_requested", "download_requested", "delete_download_requested", "artist_clicked",
             "album_clicked", "copy_link_requested", "add_to_queue_requested", "play_next_requested", "add_to_playlist_requested")
    vm = SimpleNamespace(**{name: Mock() for name in names})
    item = dict(videoId=video_id, title="Song", artist="Artist", album="Album", thumbnail_url="art")
    for action in ("like", "download", "delete_download", "go_artist", "go_album", "copy_link", "add_to_queue", "play_next", "add_to_playlist"):
        assert dispatch_track_action(vm, item, action)
    vm.like_requested.emit.assert_called_once_with(video_id, None)
    vm.add_to_playlist_requested.emit.assert_called_once_with(video_id, "Song")
    vm.add_to_queue_requested.emit.assert_called_once_with(video_id, "Song", "Artist", "art")
    for name in ("download_requested", "delete_download_requested", "artist_clicked", "album_clicked", "copy_link_requested"):
        assert getattr(vm, name).emit.call_count == (0 if video_id.startswith("local:") else 1)
    assert not dispatch_track_action(vm, {}, "like")
    assert not dispatch_track_action(vm, item, "invalid")


@pytest.mark.asyncio
async def test_playlist_picker_ignores_stale_responses(qapp, monkeypatch):
    import asyncio
    from doremi.db.local_library_repository import LocalLibraryRepository
    from doremi.ui.controllers.desktop_controller import DesktopController
    started, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def playlists(_self):
        nonlocal calls
        calls += 1
        if calls == 1:
            started.set()
            await release.wait()
            return [dict(id="local-list:old", title="Old")]
        return [dict(id="local-list:new", title="New")]

    monkeypatch.setattr(LocalLibraryRepository, "playlists", playlists)
    window = QObject()
    controller = DesktopController(window)
    first = asyncio.create_task(controller.show_picker("local:first", "First"))
    await started.wait()
    await controller.show_picker("local:second", "Second")
    release.set()
    await first
    assert controller.playlists == [dict(id="local-list:new", title="New")]
    assert controller._video_id == "local:second"
    assert not controller.busy
    controller.deleteLater()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
