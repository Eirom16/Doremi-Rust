"""Tests de la isla QML — Biblioteca.

Valida el view-model (modelos, filtro/sort, señales), la normalización de
colores rgba() del ThemeBridge para QML y la carga offscreen del QML.
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


SONGS = [
    {"videoId": "s1", "title": "Beta Song", "artist": "ZZ Top",
     "duration": "3:00", "duration_ms": 180000, "thumbnail_url": "https://x/1.jpg",
     "is_liked": True},
    {"videoId": "s2", "title": "Alpha Song", "artist": "ABBA",
     "duration": "4:00", "duration_ms": 240000, "thumbnail_url": "",
     "is_liked": True},
]

ALBUMS = [
    {"title": "Album Uno", "artist": "Artista A", "year": "2020",
     "thumbnail_url": "", "navigate": "album?id=A1"},
]

ARTISTS = [
    {"name": "Artista X", "thumbnail_url": "", "navigate": "artist?id=U1"},
]

PLAYLISTS = [
    {"title": "Mi Playlist", "subtitle": "10 canciones", "count": "10",
     "thumbnail_url": "", "is_downloaded": True, "navigate": "playlist?id=P1"},
]


class TestLibraryModels:
    def test_roles_and_rows(self, qapp):
        from doremi.ui.viewmodels.library_vm import LibraryViewModel

        vm = LibraryViewModel(qapp)
        vm.set_tab_data("songs", SONGS)
        vm.set_tab_data("albums", ALBUMS)
        vm.set_tab_data("artists", ARTISTS)
        vm.set_tab_data("playlists", PLAYLISTS)

        assert vm.songs.rowCount() == 2
        assert vm.albums.rowCount() == 1
        assert vm.artists.rowCount() == 1
        assert vm.playlists.rowCount() == 1

        assert vm.songs.data(vm.songs.index(0, 0), vm.songs.VideoIdRole) == "s1"
        assert vm.albums.data(vm.albums.index(0, 0), vm.albums.NavigateRole) == "album?id=A1"
        assert vm.artists.data(vm.artists.index(0, 0), vm.artists.NameRole) == "Artista X"
        assert vm.playlists.data(vm.playlists.index(0, 0), vm.playlists.IsDownloadedRole) is True

    def test_filter_and_sort(self, qapp):
        from doremi.ui.viewmodels.library_vm import LibraryViewModel

        vm = LibraryViewModel(qapp)
        vm.set_tab_data("songs", SONGS)

        # Filtro por título
        vm.set_filter("alpha")
        assert vm.songs.rowCount() == 1
        assert vm.songs.get(0)["videoId"] == "s2"
        vm.set_filter("")

        # Sort por título: Alpha antes que Beta
        vm.set_sort("title")
        assert vm.songs.get(0)["title"] == "Alpha Song"
        # Sort por artista: ABBA antes que ZZ Top
        vm.set_sort("artist")
        assert vm.songs.get(0)["videoId"] == "s2"
        vm.set_sort("recent")
        assert vm.songs.get(0)["videoId"] == "s1"

    def test_filter_applies_to_new_tab_data(self, qapp):
        from doremi.ui.viewmodels.library_vm import LibraryViewModel

        vm = LibraryViewModel(qapp)
        vm.set_filter("zzz-sin-match")
        vm.set_tab_data("songs", SONGS)
        assert vm.songs.rowCount() == 0
        vm.set_filter("")
        vm.set_tab_data("albums", ALBUMS)
        assert vm.albums.rowCount() == 1

    def test_tab_guard(self, qapp):
        from doremi.ui.viewmodels.library_vm import LibraryViewModel

        vm = LibraryViewModel(qapp)
        fired: list[str] = []
        vm.tab_changed.connect(lambda: fired.append(vm.tab))
        vm.set_tab("albums")
        vm.set_tab("albums")     # mismo tab: no re-emite
        vm.set_tab("invalid")    # inválido: ignora
        assert vm.tab == "albums"
        assert fired == ["albums"]


class TestLibraryViewModelSignals:
    def test_play_at(self, qapp):
        from doremi.ui.viewmodels.library_vm import LibraryViewModel

        vm = LibraryViewModel(qapp)
        vm.set_tab_data("songs", SONGS)
        captured: list[tuple] = []
        vm.play_requested.connect(lambda *a: captured.append(a))
        vm.play_at(1)
        vm.play_at(42)
        assert captured == [("s2", "Alpha Song", "ABBA", 240000, "")]

    def test_song_action_maps(self, qapp):
        from doremi.ui.viewmodels.library_vm import LibraryViewModel

        vm = LibraryViewModel(qapp)
        vm.set_tab_data("songs", SONGS)
        got: dict[str, list] = {"dl": [], "next": [], "queue": [], "like": [],
                                "pl": [], "artist": []}
        vm.download_requested.connect(lambda *a: got["dl"].append(a))
        vm.play_next_requested.connect(lambda *a: got["next"].append(a))
        vm.add_to_queue_requested.connect(lambda *a: got["queue"].append(a))
        vm.like_requested.connect(lambda *a: got["like"].append(a))
        vm.add_to_playlist_requested.connect(lambda *a: got["pl"].append(a))
        vm.artist_clicked.connect(lambda *a: got["artist"].append(a))

        vm.song_action(0, "download")
        vm.song_action(0, "play_next")
        vm.song_action(0, "add_to_queue")
        vm.song_action(0, "like")
        vm.song_action(0, "add_to_playlist")
        vm.song_action(0, "go_artist")
        vm.song_action(0, "inexistente")

        assert got["dl"] == [("s1", "Beta Song", "ZZ Top", "https://x/1.jpg")]
        assert got["next"] == [("s1", "Beta Song", "ZZ Top", "https://x/1.jpg")]
        assert got["queue"] == [("s1", "Beta Song", "ZZ Top", "https://x/1.jpg")]
        assert got["like"] == [("s1", None)]
        assert got["pl"] == [("s1", "https://x/1.jpg")]
        assert got["artist"] == [("ZZ Top",)]

    def test_navigate_and_create_playlist(self, qapp):
        from doremi.ui.viewmodels.library_vm import LibraryViewModel

        vm = LibraryViewModel(qapp)
        nav: list[str] = []
        created: list[tuple] = []
        vm.navigate_requested.connect(nav.append)
        vm.create_playlist_requested.connect(lambda t, d: created.append((t, d)))

        vm.navigate("playlist?id=P1")
        vm.navigate("")
        vm.create_playlist("  Mi Mix  ", " desc ")
        vm.create_playlist("   ", "x")  # sin título: no emite

        assert nav == ["playlist?id=P1"]
        assert created == [("Mi Mix", "desc")]


class TestThemeBridgeColors:
    def test_rgba_strings_become_qml_parseable(self, qapp):
        from PySide6.QtGui import QColor
        from doremi.ui.design import tokens
        from doremi.ui.theme_bridge import _to_qml_color

        # Tokens con sintaxis CSS rgba() deben convertirse a #AARRGGBB
        converted = _to_qml_color("rgba(167,139,250,0.5)")
        assert converted == "#80A78BFA"
        assert QColor(converted).isValid()
        # Hex y todo lo demás pasan intactos
        assert _to_qml_color("#A78BFA") == "#A78BFA"
        for value in tokens.CURRENT.__dataclass_fields__:
            color = _to_qml_color(getattr(tokens.CURRENT, value))
            assert QColor(color).isValid(), f"{value}={color} no parseable en QML"


class TestLibraryScreenQml:
    def test_qml_loads(self, qapp):
        from doremi.ui.screens.library_qml import LibraryScreenQml

        screen = LibraryScreenQml(None, lambda *a: None, lambda r: None)
        assert screen.is_ok
        assert screen._qml_island is True
        assert screen._current_tab == "songs"

    def test_play_reaches_callback(self, qapp):
        from doremi.ui.screens.library_qml import LibraryScreenQml

        played: list[tuple] = []
        screen = LibraryScreenQml(None, lambda *a: played.append(a), lambda r: None)
        assert screen.is_ok
        screen._vm.set_tab_data("songs", SONGS)
        screen._vm.play_at(0)
        assert played == [("s1", "Beta Song", "ZZ Top", "", 180000, "https://x/1.jpg")]

    def test_navigate_passthrough(self, qapp):
        from doremi.ui.screens.library_qml import LibraryScreenQml

        routes: list[str] = []
        screen = LibraryScreenQml(None, lambda *a: None, routes.append)
        assert screen.is_ok
        screen._vm.navigate("album?id=A1")
        assert routes == ["album?id=A1"]

    def test_invalidate_songs_cache(self, qapp):
        from doremi.ui.screens.library_qml import LibraryScreenQml

        screen = LibraryScreenQml(None, lambda *a: None, lambda r: None)
        screen._cache["songs"] = SONGS
        screen._cache_time["songs"] = 1.0
        screen._vm.set_tab_data("songs", SONGS)
        screen.invalidate_songs_cache()
        assert "songs" not in screen._cache
        assert "songs" not in screen._cache_time
