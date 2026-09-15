"""Tests de la isla QML — Playlist."""
from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def qapp():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


REMOTE = {
    "playlist_id": "PL1", "title": "Mi Playlist", "author": "Yo", "track_count": 3,
    "thumbnail_url": "https://x/pl.jpg",
    "tracks": [
        {"videoId": f"v{i}", "title": f"Canción {i}", "artist": "Artista",
         "duration": "3:00", "duration_ms": 180000, "thumbnail_url": "",
         "is_liked": False, "is_downloaded": i == 0, "setVideoId": f"sv{i}"}
        for i in range(3)
    ],
    "downloaded_count": 1, "is_fully_downloaded": False,
    "is_local": False, "local_meta": [],
}

LOCAL = {
    "playlist_id": "local_pl9", "title": "Local PL", "author": "Biblioteca Local",
    "track_count": 2, "thumbnail_url": "",
    "tracks": [
        {"videoId": f"L{i}", "title": f"Local {i}", "artist": "A", "duration": "2:00",
         "duration_ms": 120000, "thumbnail_url": "", "is_liked": False,
         "is_downloaded": True, "setVideoId": ""}
        for i in range(2)
    ],
    "downloaded_count": 2, "is_fully_downloaded": True,
    "is_local": True,
    "local_meta": [
        {"video_id": f"L{i}", "title": f"Local {i}", "artist": "A", "thumbnail_url": "",
         "file_path": f"/tmp/{i}.opus", "duration_ms": 120000}
        for i in range(2)
    ],
}


class TestPlaylistViewModel:
    def test_remote_header_and_meta(self, qapp):
        from doremi.ui.viewmodels.playlist_vm import PlaylistViewModel

        vm = PlaylistViewModel(qapp)
        vm.set_data(REMOTE)
        assert vm.title == "Mi Playlist"
        assert vm.meta == "Yo • 3 canciones"
        assert vm.isLocal is False
        assert vm.hasTracks
        assert vm.tracks.data(vm.tracks.index(2, 0), vm.tracks.SetVideoIdRole) == "sv2"

    def test_remote_play_queue(self, qapp):
        from doremi.ui.viewmodels.playlist_vm import PlaylistViewModel

        vm = PlaylistViewModel(qapp)
        vm.set_data(REMOTE)
        calls: list[tuple] = []
        vm.play_queue_requested.connect(lambda items, idx: calls.append((items, idx)))
        vm.play_at(2)
        vm.play_all()
        vm.play_shuffle()
        assert calls[0][1] == 2 and len(calls[0][0]) == 3
        assert calls[1][1] == 0
        assert sorted(t["videoId"] for t in calls[2][0]) == ["v0", "v1", "v2"]

    def test_local_play_uses_local_meta(self, qapp):
        from doremi.ui.viewmodels.playlist_vm import PlaylistViewModel

        vm = PlaylistViewModel(qapp)
        vm.set_data(LOCAL)
        locals_: list[tuple] = []
        queues: list[tuple] = []
        vm.play_local_requested.connect(lambda meta, idx: locals_.append((meta, idx)))
        vm.play_queue_requested.connect(lambda *a: queues.append(a))
        vm.play_at(1)
        vm.play_all()
        vm.play_shuffle()
        assert locals_[0][1] == 1 and len(locals_[0][0]) == 2
        assert locals_[0][0][1]["file_path"] == "/tmp/1.opus"
        assert queues == []  # nunca cola remota en local

    def test_remove_only_with_set_video_id_remote(self, qapp):
        from doremi.ui.viewmodels.playlist_vm import PlaylistViewModel

        vm = PlaylistViewModel(qapp)
        vm.set_data(REMOTE)
        removed: list[tuple] = []
        vm.remove_track_requested.connect(lambda *a: removed.append(a))
        vm.track_action(1, "remove")
        assert removed == [("v1", "sv1", "Canción 1")]
        # Local: remove no disponible
        vm.set_data(LOCAL)
        vm.track_action(0, "remove")
        assert len(removed) == 1

    def test_download_states(self, qapp):
        from doremi.ui.viewmodels.playlist_vm import PlaylistViewModel

        vm = PlaylistViewModel(qapp)
        vm.set_data(REMOTE)
        vm.set_download_state(PlaylistViewModel.DL_PARTIAL)
        assert vm.dlText == "Descargar restantes (1/3)"
        vm.set_download_state(PlaylistViewModel.DL_ACTIVE, 30)
        assert vm.dlText == "Descargando… 30%"
        vm.refresh_counters(3, True)
        assert vm.dlState == "full"


class TestPlaylistScreenQml:
    def test_qml_loads(self, qapp):
        from doremi.ui.screens.playlist_qml import PlaylistScreenQml

        screen = PlaylistScreenQml(None, lambda *a: None, lambda *a: None, lambda: None)
        assert screen.is_ok
        assert screen._qml_island is True

    def test_play_queue_converts_to_queue_items(self, qapp):
        from doremi.ui.screens.playlist_qml import PlaylistScreenQml

        calls: list[tuple] = []
        screen = PlaylistScreenQml(None, lambda *a: calls.append(a), None, lambda: None)
        screen._vm.set_data(REMOTE)
        screen._vm.play_at(1)
        args = calls[0]
        assert args[0] == "v1"            # video_id
        assert args[3] == ""              # album vacío (paridad widgets)
        assert len(args[6]) == 3          # queue_items
        assert args[7] == 1               # queue_index

    def test_play_local_passthrough(self, qapp):
        from doremi.ui.screens.playlist_qml import PlaylistScreenQml

        locals_: list[tuple] = []
        screen = PlaylistScreenQml(None, lambda *a: None,
                                   lambda meta, idx: locals_.append((meta, idx)), lambda: None)
        screen._vm.set_data(LOCAL)
        screen._vm.play_at(0)
        assert locals_ == [(LOCAL["local_meta"], 0)]
