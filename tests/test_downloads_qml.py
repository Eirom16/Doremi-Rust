"""Tests de la isla QML — Descargas."""
from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def qapp():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


SONGS = [
    {"videoId": "d1", "title": "Song A", "artist": "Artista A", "playlist_title": "",
     "thumbnail_url": "", "status": "completed", "progress": 100.0, "speed": "",
     "file_path": "/tmp/a.opus", "is_liked": True},
    {"videoId": "d2", "title": "Song B", "artist": "Artista B", "playlist_title": "Mix",
     "thumbnail_url": "", "status": "downloading", "progress": 40.0, "speed": "1MB/s",
     "file_path": "", "is_liked": False},
    {"videoId": "d3", "title": "Song C", "artist": "Artista C", "playlist_title": "",
     "thumbnail_url": "", "status": "error", "progress": 0.0, "speed": "",
     "file_path": "", "is_liked": False},
]

GROUPS = [
    {"playlist_id": "pl1", "title": "Mi Playlist", "subtitle": "3 canciones",
     "thumbnail_url": "", "navigate": "playlist?id=local_pl1"},
    {"playlist_id": "album_x", "title": "Álbum Local", "subtitle": "8 canciones",
     "thumbnail_url": "", "navigate": "album?id=x"},
]


class TestDownloadsViewModel:
    def test_models_roles(self, qapp):
        from doremi.ui.viewmodels.downloads_vm import DownloadsViewModel

        vm = DownloadsViewModel(qapp)
        vm.set_songs(SONGS)
        vm.set_groups(GROUPS)
        assert vm.songs.rowCount() == 3
        assert vm.groups.rowCount() == 2
        assert vm.songs.data(vm.songs.index(1, 0), vm.songs.StatusRole) == "downloading"
        assert vm.songs.data(vm.songs.index(1, 0), vm.songs.ProgressRole) == 40.0
        assert vm.groups.data(vm.groups.index(1, 0), vm.groups.NavigateRole) == "album?id=x"

    def test_play_at_only_completed(self, qapp):
        from doremi.ui.viewmodels.downloads_vm import DownloadsViewModel

        vm = DownloadsViewModel(qapp)
        vm.set_songs(SONGS)
        played: list[tuple] = []
        vm.play_local_requested.connect(lambda p, m: played.append((p, m)))
        vm.play_at(0)
        vm.play_at(1)  # downloading: no reproduce
        vm.play_at(2)  # error: no reproduce
        vm.play_at(99)
        assert played == [("/tmp/a.opus", {"video_id": "d1", "title": "Song A",
                                           "artist": "Artista A", "thumbnail_url": ""})]

    def test_item_actions(self, qapp):
        from doremi.ui.viewmodels.downloads_vm import DownloadsViewModel

        vm = DownloadsViewModel(qapp)
        vm.set_songs(SONGS)
        got: dict[str, list] = {"next": [], "queue": [], "pl": [], "del": [], "like": []}
        vm.play_next_requested.connect(lambda *a: got["next"].append(a))
        vm.add_to_queue_requested.connect(lambda *a: got["queue"].append(a))
        vm.add_to_playlist_requested.connect(lambda *a: got["pl"].append(a))
        vm.delete_download_requested.connect(lambda *a: got["del"].append(a))
        vm.like_requested.connect(lambda *a: got["like"].append(a))

        vm.item_action(0, "play_next")
        vm.item_action(0, "add_to_queue")
        vm.item_action(0, "add_to_playlist")
        vm.item_action(1, "delete")
        vm.item_action(0, "like")

        assert got["next"] == [("d1", "Song A", "Artista A", "")]
        assert got["queue"] == [("d1", "Song A", "Artista A", "")]
        assert got["pl"] == [("d1", "Song A")]
        assert got["del"] == [("d2",)]
        assert got["like"] == [("d1", None)]

    def test_selection_flow(self, qapp):
        from doremi.ui.viewmodels.downloads_vm import DownloadsViewModel

        vm = DownloadsViewModel(qapp)
        vm.set_songs(SONGS)
        vm.toggle_selection_mode()
        assert vm.selectionMode is True

        vm.toggle_item_selected(0)
        vm.toggle_item_selected(2)
        assert vm.selectedCount == 2

        batches: list[tuple] = []
        vm.batch_delete_requested.connect(lambda ids, g: batches.append((ids, g)))
        vm.delete_selected()
        assert batches == [(["d1", "d3"], False)]

        # select_all alterna todos/ninguno
        vm.select_all()
        assert vm.selectedCount == 3
        vm.select_all()
        assert vm.selectedCount == 0

        # salir del modo selección limpia las marcas
        vm.toggle_item_selected(0)
        vm.toggle_selection_mode()
        assert vm.selectedCount == 0

    def test_delete_selection_groups(self, qapp):
        from doremi.ui.viewmodels.downloads_vm import DownloadsViewModel

        vm = DownloadsViewModel(qapp)
        vm.set_groups(GROUPS)
        vm.set_tab("playlists")
        vm.toggle_group_selected(1)
        batches: list[tuple] = []
        vm.batch_delete_requested.connect(lambda ids, g: batches.append((ids, g)))
        vm.delete_selected()
        assert batches == [(["album_x"], True)]

    def test_live_task_updates(self, qapp):
        from doremi.ui.viewmodels.downloads_vm import DownloadsViewModel

        vm = DownloadsViewModel(qapp)
        vm.set_songs(SONGS[:1])
        vm.upsert_task({"videoId": "d9", "title": "Nueva", "artist": "X",
                        "playlist_title": "", "thumbnail_url": "", "status": "queued",
                        "progress": 0.0, "speed": "", "file_path": "", "is_liked": False})
        assert vm.songs.find_row("d9") == 0  # prepend
        vm.update_progress("d9", 55.0, "2MB/s")
        row = vm.songs.find_row("d9")
        assert vm.songs.data(vm.songs.index(row, 0), vm.songs.ProgressRole) == 55.0
        assert vm.songs.data(vm.songs.index(row, 0), vm.songs.StatusRole) == "downloading"
        vm.update_status("d9", "error")
        assert vm.songs.data(vm.songs.index(row, 0), vm.songs.StatusRole) == "error"

    def test_navigate_groups(self, qapp):
        from doremi.ui.viewmodels.downloads_vm import DownloadsViewModel

        vm = DownloadsViewModel(qapp)
        vm.set_groups(GROUPS)
        routes: list[str] = []
        vm.navigate_requested.connect(routes.append)
        vm.group_navigate(0)
        assert routes == ["playlist?id=local_pl1"]


class TestDownloadsData:
    def test_task_matches_filter(self):
        from doremi.ui.screens.downloads_data import task_matches_filter

        assert task_matches_filter("downloading", "all")
        assert task_matches_filter("queued", "active")
        assert task_matches_filter("paused", "active")
        assert not task_matches_filter("completed", "active")
        assert task_matches_filter("error", "error")
        assert not task_matches_filter("downloading", "error")


class TestDownloadsScreenQml:
    def test_qml_loads(self, qapp):
        from doremi.ui.screens.downloads_qml import DownloadsScreenQml

        screen = DownloadsScreenQml(None, lambda *a: None, lambda *a: None, lambda r: None)
        assert screen.is_ok
        assert screen._qml_island is True
        assert screen._current_tab == "songs"

    def test_play_local_passthrough(self, qapp):
        from doremi.ui.screens.downloads_qml import DownloadsScreenQml

        played: list[tuple] = []
        screen = DownloadsScreenQml(None, lambda p, m: played.append((p, m)),
                                    lambda *a: None, lambda r: None)
        assert screen.is_ok
        screen._vm.set_songs(SONGS)
        screen._vm.play_at(0)
        assert played == [("/tmp/a.opus", {"video_id": "d1", "title": "Song A",
                                           "artist": "Artista A", "thumbnail_url": ""})]
