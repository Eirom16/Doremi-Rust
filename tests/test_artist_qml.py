"""Tests de la isla QML — Artista."""
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
    "name": "Daft Punk",
    "subscribers": "5M suscriptores",
    "thumbnail_url": "https://x/cover.jpg",
    "songs": [
        {"videoId": f"s{i}", "title": f"Track {i}", "artist": "Daft Punk",
         "duration": "4:12", "duration_ms": 252000, "thumbnail_url": "", "is_liked": False}
        for i in range(5)
    ],
    "albums": [{"title": "Discovery", "artist": "Daft Punk", "year": "2001",
                "thumbnail_url": "", "navigate": "album?id=A1"}],
    "related": [{"name": "Justice", "thumbnail_url": "", "navigate": "artist?id=R1"}],
}


class TestArtistViewModel:
    def test_header_and_models(self, qapp):
        from doremi.ui.viewmodels.artist_vm import ArtistViewModel

        vm = ArtistViewModel(qapp)
        vm.set_data(DATA)
        assert vm.artistName == "Daft Punk"
        assert vm.subscribers == "5M suscriptores"
        assert vm.thumbnail == "https://x/cover.jpg"
        assert vm.found is True
        assert vm.hasSongs is True
        assert vm.songs.rowCount() == 5
        assert vm.albums.rowCount() == 1
        assert vm.related.rowCount() == 1
        # álbumes: subtitle = año; related: roundCrop = True
        assert vm.albums.data(vm.albums.index(0, 0), vm.albums.SubtitleRole) == "2001"
        assert vm.related.data(vm.related.index(0, 0), vm.related.RoundRole) is True
        assert vm.albums.data(vm.albums.index(0, 0), vm.albums.RoundRole) is False

    def test_empty_data(self, qapp):
        from doremi.ui.viewmodels.artist_vm import ArtistViewModel

        vm = ArtistViewModel(qapp)
        vm.set_data({})
        assert vm.found is False
        assert vm.hasSongs is False

    def test_play_semantics(self, qapp):
        from doremi.ui.viewmodels.artist_vm import ArtistViewModel

        vm = ArtistViewModel(qapp)
        vm.set_data(DATA)
        plays: list[tuple] = []
        vm.play_requested.connect(lambda *a: plays.append(a))

        vm.play_all()
        vm.play_at(4)
        assert plays[0] == ("s0", "Track 0", "Daft Punk", 252000, "")
        assert plays[1][0] == "s4"
        vm.play_shuffle()
        assert len(plays) == 3 and plays[2][0] in {f"s{i}" for i in range(5)}

    def test_song_actions(self, qapp):
        from doremi.ui.viewmodels.artist_vm import ArtistViewModel

        vm = ArtistViewModel(qapp)
        vm.set_data(DATA)
        got: dict[str, list] = {"dl": [], "next": [], "like": [], "pl": [], "queue": []}
        vm.download_requested.connect(lambda *a: got["dl"].append(a))
        vm.play_next_requested.connect(lambda *a: got["next"].append(a))
        vm.like_requested.connect(lambda *a: got["like"].append(a))
        vm.add_to_playlist_requested.connect(lambda *a: got["pl"].append(a))
        vm.add_to_queue_requested.connect(lambda *a: got["queue"].append(a))

        vm.song_action(0, "download")
        vm.song_action(0, "play_next")
        vm.song_action(0, "like")
        vm.song_action(0, "add_to_playlist")
        vm.song_action(0, "add_to_queue")
        vm.song_action(0, "inexistente")

        assert got["dl"] == [("s0", "Track 0", "Daft Punk", "")]
        assert got["next"] == [("s0", "Track 0", "Daft Punk", "")]
        assert got["like"] == [("s0", None)]
        assert got["pl"] == [("s0", "")]
        assert got["queue"] == [("s0", "Track 0", "Daft Punk", "")]

    def test_navigate_and_back(self, qapp):
        from doremi.ui.viewmodels.artist_vm import ArtistViewModel

        vm = ArtistViewModel(qapp)
        routes: list[str] = []
        backs: list[str] = []
        vm.navigate_requested.connect(routes.append)
        vm.back_requested.connect(lambda: backs.append("back"))
        vm.navigate("album?id=A1")
        vm.navigate("")
        vm.go_back()
        assert routes == ["album?id=A1"]
        assert backs == ["back"]


class TestArtistScreenQml:
    def test_qml_loads(self, qapp):
        from doremi.ui.screens.artist_qml import ArtistScreenQml

        screen = ArtistScreenQml(None, lambda *a: None, lambda r: None, lambda: None)
        assert screen.is_ok
        assert screen._qml_island is True

    def test_play_reaches_callback(self, qapp):
        from doremi.ui.screens.artist_qml import ArtistScreenQml

        played: list[tuple] = []
        screen = ArtistScreenQml(None, lambda *a: played.append(a), None)
        screen._vm.set_data(DATA)
        screen._vm.play_all()
        assert played == [("s0", "Track 0", "Daft Punk", "", 252000, "")]

    def test_back_and_navigate_passthrough(self, qapp):
        from doremi.ui.screens.artist_qml import ArtistScreenQml

        routes: list[str] = []
        backs: list[str] = []
        screen = ArtistScreenQml(None, lambda *a: None, routes.append, lambda: backs.append("back"))
        screen._vm.navigate("album?id=A1")
        screen._vm.go_back()
        assert routes == ["album?id=A1"]
        assert backs == ["back"]
