"""Tests de la isla QML — Álbum."""
from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def qapp():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


DATA = {
    "browse_id": "b1", "type": "ÁLBUM", "title": "Thriller",
    "meta": "MJ • 1982 • 3 canciones", "thumbnail_url": "https://x/c.jpg",
    "tracks": [
        {"videoId": "t0", "title": "Wanna Be", "artist": "MJ", "duration": "3:02",
         "duration_ms": 182000, "thumbnail_url": "", "is_liked": True, "is_downloaded": True},
        {"videoId": "t1", "title": "Thriller", "artist": "MJ", "duration": "5:57",
         "duration_ms": 357000, "thumbnail_url": "", "is_liked": False, "is_downloaded": False},
        {"videoId": "t2", "title": "Beat It", "artist": "MJ", "duration": "4:18",
         "duration_ms": 258000, "thumbnail_url": "", "is_liked": False, "is_downloaded": True},
    ],
    "downloaded_count": 2, "track_count": 3, "is_fully_downloaded": False,
}


class TestAlbumViewModel:
    def test_header_and_tracks(self, qapp):
        from doremi.ui.viewmodels.album_vm import AlbumViewModel

        vm = AlbumViewModel(qapp)
        vm.set_data(DATA)
        assert vm.title == "Thriller"
        assert vm.typeLabel == "ÁLBUM"
        assert vm.meta == "MJ • 1982 • 3 canciones"
        assert vm.found is True
        assert vm.hasTracks is True
        assert vm.tracks.rowCount() == 3
        assert vm.tracks.data(vm.tracks.index(0, 0), vm.tracks.IsDownloadedRole) is True

    def test_play_with_queue(self, qapp):
        from doremi.ui.viewmodels.album_vm import AlbumViewModel

        vm = AlbumViewModel(qapp)
        vm.set_data(DATA)
        calls: list[tuple] = []
        vm.play_queue_requested.connect(lambda items, idx: calls.append((items, idx)))

        vm.play_at(1)
        assert calls[0][1] == 1
        assert [t["videoId"] for t in calls[0][0]] == ["t0", "t1", "t2"]

        vm.play_all()
        assert calls[1][1] == 0

        vm.play_shuffle()
        assert sorted(t["videoId"] for t in calls[2][0]) == ["t0", "t1", "t2"]  # misma colección

        vm.play_at(99)  # fuera de rango: no emite
        assert len(calls) == 3

    def test_download_states(self, qapp):
        from doremi.ui.viewmodels.album_vm import AlbumViewModel

        vm = AlbumViewModel(qapp)
        vm.set_data(DATA)
        vm.set_download_state(AlbumViewModel.DL_NONE)
        assert vm.dlText == "Descargar álbum"
        vm.set_download_state(AlbumViewModel.DL_PARTIAL)
        assert vm.dlText == "Descargar restantes (2/3)"
        vm.set_download_state(AlbumViewModel.DL_ACTIVE, 65)
        assert vm.dlText == "Descargando… 65%"
        vm.mark_downloader_feedback()
        assert vm.dlState == "active"
        vm.refresh_counters(3, True)
        assert vm.dlState == "full"

    def test_track_actions_and_download_album(self, qapp):
        from doremi.ui.viewmodels.album_vm import AlbumViewModel

        vm = AlbumViewModel(qapp)
        vm.set_data(DATA)
        got: dict[str, list] = {"dl_track": [], "dl_album": [], "like": [], "del": []}
        vm.download_requested.connect(lambda *a: got["dl_track"].append(a))
        vm.download_album_requested.connect(lambda *a: got["dl_album"].append(a))
        vm.like_requested.connect(lambda *a: got["like"].append(a))
        vm.delete_download_requested.connect(lambda *a: got["del"].append(a))

        vm.track_action(0, "download")
        vm.track_action(0, "like")
        vm.track_action(0, "delete_download")
        vm.download_album()

        assert got["dl_track"] == [("t0", "Wanna Be", "MJ", "")]
        assert got["dl_album"] == [("b1", "Thriller", "https://x/c.jpg")]
        assert got["like"] == [("t0", None)]
        assert got["del"] == [("t0",)]


class TestAlbumScreenQml:
    def test_qml_loads(self, qapp):
        from doremi.ui.screens.album_qml import AlbumScreenQml

        screen = AlbumScreenQml(None, lambda *a: None, lambda: None)
        assert screen.is_ok
        assert screen._qml_island is True

    def test_play_queue_builds_8arg_call(self, qapp):
        from doremi.ui.screens.album_qml import AlbumScreenQml

        calls: list[tuple] = []
        screen = AlbumScreenQml(None, lambda *a: calls.append(a), lambda: None)
        screen._vm.set_data(DATA)
        screen._vm.play_at(2)
        assert len(calls) == 1
        args = calls[0]
        assert args[0] == "t2"              # video_id
        assert args[1] == "Beat It"         # title
        assert args[3] == "Thriller"        # album (del header)
        assert args[4] == 258000            # duration_ms
        assert len(args[6]) == 3            # queue_items
        assert args[7] == 2                 # queue_index
