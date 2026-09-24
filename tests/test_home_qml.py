"""Tests de la isla QML — Inicio.

Valida el view-model (modelos, señales, slots) y que HomeScreenQml cargue
el QML correctamente en modo offscreen (con fallback si falla).
"""
from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def qapp():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


TILES = [
    {"videoId": "t1", "title": "Tile Uno", "artist": "Artista A",
     "duration_ms": 200000, "thumbnail_url": "https://x/t1.jpg"},
    {"videoId": "t2", "title": "Tile Dos", "artist": "Artista B",
     "duration_ms": 180000, "thumbnail_url": ""},
]

SONGS = [
    {"videoId": "s1", "title": "Canción Uno", "artist": "Artista A",
     "duration": "3:20", "duration_ms": 200000, "thumbnail_url": "https://x/s1.jpg",
     "is_liked": True},
    {"videoId": "s2", "title": "Canción Dos", "artist": "Artista B",
     "duration": "4:00", "duration_ms": 240000, "thumbnail_url": "",
     "is_liked": False},
]

HORIZONTAL = [
    {"section_title": "Mixes", "type": "playlist", "item_title": "Daily Mix 1",
     "subtitle": "YouTube Music", "thumbnail_url": "", "navigate": "playlist?id=PL1",
     "is_downloaded": False},
    {"section_title": "Mixes", "type": "playlist", "item_title": "Daily Mix 2",
     "subtitle": "YouTube Music", "thumbnail_url": "", "navigate": "playlist?id=PL2",
     "is_downloaded": False},
    {"section_title": "Artistas", "type": "artist", "item_title": "Artista X",
     "subtitle": "", "thumbnail_url": "", "navigate": "artist?id=UC1",
     "is_downloaded": False},
]


def test_home_routes_podcasts_separately_from_albums():
    from doremi.ui.screens.home_data import _extract_navigate

    assert _extract_navigate({"browseId": "MPSPpodcast1"}) == "podcast?id=MPSPpodcast1"
    assert _extract_navigate({"playlistId": "MPSPpodcast2"}) == "podcast?id=MPSPpodcast2"
    assert _extract_navigate({"browseId": "MPREalbum1"}) == "album?id=MPREalbum1"


class TestHomeViewModel:
    def test_models_and_roles(self, qapp):
        from doremi.ui.viewmodels.home_vm import HomeViewModel

        vm = HomeViewModel(qapp)
        vm.set_tiles(TILES)
        vm.set_songs(SONGS)
        vm.set_horizontal(HORIZONTAL)
        vm.set_spotlight([{"title": "Spot", "subtitle": "De X",
                           "thumbnail_url": "", "navigate": "playlist?id=P"}])

        assert vm.tiles.rowCount() == 2
        assert vm.songs.rowCount() == 2
        assert vm.horizontal.rowCount() == 3
        assert vm.spotlight.rowCount() == 1
        assert vm.genres.rowCount() == 12

        idx = vm.songs.index(1, 0)
        assert vm.songs.data(idx, vm.songs.TitleRole) == "Canción Dos"
        assert vm.songs.data(idx, vm.songs.VideoIdRole) == "s2"
        assert vm.tiles.roleNames()[vm.tiles.VideoIdRole] == b"videoId"
        assert vm.genres.roleNames()[vm.genres.QueryRole] == b"query"

    def test_play_at_emits_request(self, qapp):
        from doremi.ui.viewmodels.home_vm import HomeViewModel

        vm = HomeViewModel(qapp)
        vm.set_songs(SONGS)
        captured: list[tuple] = []
        vm.play_requested.connect(lambda *args: captured.append(args))
        vm.play_at(0)
        assert captured == [("s1", "Canción Uno", "Artista A", 200000, "https://x/s1.jpg")]
        vm.play_at(99)  # fuera de rango: no emite
        assert len(captured) == 1

    def test_play_tile_emits_request(self, qapp):
        from doremi.ui.viewmodels.home_vm import HomeViewModel

        vm = HomeViewModel(qapp)
        vm.set_tiles(TILES)
        captured: list[tuple] = []
        vm.play_requested.connect(lambda *args: captured.append(args))
        vm.play_tile(1)
        assert captured == [("t2", "Tile Dos", "Artista B", 180000, "")]
        vm.play_tile(-1)  # fuera de rango: no emite
        assert len(captured) == 1

    def test_actions_map_signals(self, qapp):
        from doremi.ui.viewmodels.home_vm import HomeViewModel

        vm = HomeViewModel(qapp)
        vm.set_tiles(TILES)
        vm.set_songs(SONGS)
        got: dict[str, list] = {"download": [], "queue": [], "like": [],
                                "playlist": [], "next": [], "artist": []}
        vm.download_requested.connect(lambda *a: got["download"].append(a))
        vm.add_to_queue_requested.connect(lambda *a: got["queue"].append(a))
        vm.like_requested.connect(lambda *a: got["like"].append(a))
        vm.add_to_playlist_requested.connect(lambda *a: got["playlist"].append(a))
        vm.play_next_requested.connect(lambda *a: got["next"].append(a))
        vm.artist_clicked.connect(lambda *a: got["artist"].append(a))

        vm.tile_action(0, "download")
        vm.song_action(0, "add_to_queue")
        vm.song_action(0, "like")
        vm.song_action(0, "add_to_playlist")
        vm.song_action(1, "play_next")
        vm.song_action(1, "go_artist")
        vm.song_action(0, "inexistente")

        assert got["download"] == [("t1", "Tile Uno", "Artista A", "https://x/t1.jpg")]
        assert got["queue"] == [("s1", "Canción Uno", "Artista A", "https://x/s1.jpg")]
        assert got["like"] == [("s1", None)]
        assert got["playlist"] == [("s1", "https://x/s1.jpg")]
        assert got["next"] == [("s2", "Canción Dos", "Artista B", "")]
        assert got["artist"] == [("Artista B",)]

    def test_navigation_slots(self, qapp):
        from doremi.ui.viewmodels.home_vm import HomeViewModel

        vm = HomeViewModel(qapp)
        nav: list[str] = []
        vm.navigate_requested.connect(nav.append)
        vm.search_navigate.connect(nav.append)

        vm.navigate("playlist?id=PL1")
        vm.navigate_genre("rock")

        assert nav == ["playlist?id=PL1", "search?query=rock"]

    def test_horizontal_show_header(self, qapp):
        from doremi.ui.viewmodels.home_vm import HomeViewModel

        vm = HomeViewModel(qapp)
        vm.set_horizontal(HORIZONTAL)
        headers = [
            vm.horizontal.data(vm.horizontal.index(i, 0), vm.horizontal.ShowHeaderRole)
            for i in range(3)
        ]
        assert headers == [True, False, True]

    def test_greeting_and_loading(self, qapp):
        from doremi.ui.viewmodels.home_vm import HomeViewModel

        vm = HomeViewModel(qapp)
        events: list[str] = []
        vm.loading_changed.connect(lambda: events.append("loading"))
        vm.greeting_changed.connect(lambda: events.append("greeting"))

        vm.set_loading(False)
        vm.set_loading(False)  # sin cambio: no emite
        vm.set_greeting("¡Buenas noches!")

        assert vm.loading is False
        assert vm.greeting == "¡Buenas noches!"
        assert events == ["loading", "greeting"]


class TestHomeScreenQml:
    def test_qml_loads(self, qapp):
        """HomeScreenQml carga el QML sin errores (offscreen)."""
        from doremi.ui.screens.home_qml import HomeScreenQml

        screen = HomeScreenQml(None, lambda *a: None, lambda r: None)
        assert screen.is_ok
        assert screen._qml_island is True

    def test_play_request_reaches_callback(self, qapp):
        from doremi.ui.screens.home_qml import HomeScreenQml

        played: list[tuple] = []
        screen = HomeScreenQml(None, lambda *a: played.append(a), lambda r: None)
        assert screen.is_ok
        screen._vm.set_songs(SONGS)
        screen._vm.play_at(1)
        assert played == [("s2", "Canción Dos", "Artista B", "", 240000, "")]

    def test_play_route_fallback_uses_models(self, qapp):
        """Ruta 'play:<vid>' desde cards horizontales resuelve metadata en modelos."""
        from doremi.ui.screens.home_qml import HomeScreenQml

        played: list[tuple] = []
        screen = HomeScreenQml(None, lambda *a: played.append(a), lambda r: None)
        assert screen.is_ok
        screen._vm.set_songs(SONGS)
        screen._vm.navigate_requested.emit("play:s1")
        # videoId desconocido: igual emite play con metadata vacía
        screen._vm.navigate_requested.emit("play:unknown")
        assert played == [
            ("s1", "Canción Uno", "Artista A", "", 200000, "https://x/s1.jpg"),
            ("unknown", "", "", "", 0, ""),
        ]

    def test_navigate_passthrough(self, qapp):
        from doremi.ui.screens.home_qml import HomeScreenQml

        routes: list[str] = []
        screen = HomeScreenQml(None, lambda *a: None, routes.append)
        assert screen.is_ok
        screen._vm.navigate("playlist?id=PL1")
        screen._vm.navigate_genre("jazz")
        assert routes == ["playlist?id=PL1", "search?query=jazz"]
