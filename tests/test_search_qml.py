"""Tests de la isla QML — Búsqueda."""
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
    {"videoId": f"s{i}", "title": f"Canción {i}", "artist": "Artista A",
     "duration": "3:00", "duration_ms": 180000 + i, "thumbnail_url": "https://x/1.jpg",
     "is_liked": i % 2 == 0, "result_type": "song"}
    for i in range(1, 9)  # 8 resultados: top + 4 featured + 3 rest
]

ALBUMS = [{"title": "Álbum X", "artist": "Artista A", "thumbnail_url": "",
           "navigate": "album?id=A1"}]

PLAYLISTS = [{"title": "PL X", "subtitle": "5 canciones", "thumbnail_url": "",
              "is_downloaded": True, "navigate": "playlist?id=P1"}]

PODCASTS = [{"title": "Podcast X", "artist": "Podcast", "thumbnail_url": "",
             "navigate": "podcast?id=MPSPX"}]


class TestSearchViewModel:
    def test_split_top_featured_rest(self, qapp):
        from doremi.ui.viewmodels.search_vm import SearchViewModel

        vm = SearchViewModel(qapp)
        vm.set_songs(SONGS)
        assert vm.hasTop is True
        assert vm.topTitle == "Canción 1"
        assert vm.topArtist == "Artista A"
        assert vm.topType == "Canción"
        assert vm.featured.rowCount() == 4
        assert vm.rest.rowCount() == 3
        assert vm.featured.data(vm.featured.index(0, 0), vm.featured.VideoIdRole) == "s2"
        assert vm.rest.data(vm.rest.index(2, 0), vm.rest.VideoIdRole) == "s8"

    def test_empty_songs_resets_top(self, qapp):
        from doremi.ui.viewmodels.search_vm import SearchViewModel

        vm = SearchViewModel(qapp)
        vm.set_songs(SONGS)
        vm.set_songs([])
        assert vm.hasTop is False
        assert vm.topTitle == ""
        assert vm.featured.rowCount() == 0
        assert vm.rest.rowCount() == 0

    def test_category_guard(self, qapp):
        from doremi.ui.viewmodels.search_vm import SearchViewModel

        vm = SearchViewModel(qapp)
        fired: list[str] = []
        vm.category_changed.connect(lambda: fired.append(vm.category))
        vm.set_category("album")
        vm.set_category("album")    # misma: no re-emite
        vm.set_category("podcast")
        vm.set_category("artist")   # no soportada: ignora
        assert vm.category == "podcast"
        assert fired == ["album", "podcast"]

    def test_play_and_actions(self, qapp):
        from doremi.ui.viewmodels.search_vm import SearchViewModel

        vm = SearchViewModel(qapp)
        vm.set_songs(SONGS)
        plays: list[tuple] = []
        vm.play_requested.connect(lambda *a: plays.append(a))

        vm.play_top()
        vm.play_featured(1)
        vm.play_rest(0)
        assert [p[0] for p in plays] == ["s1", "s3", "s6"]
        assert plays[0] == ("s1", "Canción 1", "Artista A", 180001, "https://x/1.jpg")

        got: dict[str, list] = {"dl": [], "next": [], "like": [], "del": []}
        vm.download_requested.connect(lambda *a: got["dl"].append(a))
        vm.play_next_requested.connect(lambda *a: got["next"].append(a))
        vm.like_requested.connect(lambda *a: got["like"].append(a))
        vm.delete_download_requested.connect(lambda *a: got["del"].append(a))

        vm.top_action("download")
        vm.featured_action(0, "play_next")
        vm.rest_action(1, "like")
        vm.top_action("delete_download")
        vm.top_action("inexistente")

        assert got["dl"] == [("s1", "Canción 1", "Artista A", "https://x/1.jpg")]
        assert got["next"] == [("s2", "Canción 2", "Artista A", "https://x/1.jpg")]
        assert got["like"] == [("s7", None)]
        assert got["del"] == [("s1",)]

    def test_albums_playlists_models(self, qapp):
        from doremi.ui.viewmodels.search_vm import SearchViewModel

        vm = SearchViewModel(qapp)
        vm.set_albums(ALBUMS)
        vm.set_playlists(PLAYLISTS)
        assert vm.albums.rowCount() == 1
        assert vm.albums.data(vm.albums.index(0, 0), vm.albums.SubtitleRole) == "Artista A"
        assert vm.playlists.data(vm.playlists.index(0, 0), vm.playlists.IsDownloadedRole) is True

    @pytest.mark.asyncio
    async def test_podcast_search_uses_own_route(self, qapp):
        from doremi.ui.screens.search_data import gather_search

        class SearchClient:
            async def search(self, query, filter=None, limit=40):
                assert filter == "podcasts"
                return [
                    {"title": "Podcast X", "browseId": "MPSPX", "thumbnails": []},
                    {"title": "Álbum infiltrado", "browseId": "MPREA", "thumbnails": []},
                ]

        items = await gather_search(SearchClient(), "podcast", "podcast")
        assert items == PODCASTS

    def test_error_and_retry(self, qapp):
        from doremi.ui.viewmodels.search_vm import SearchViewModel

        vm = SearchViewModel(qapp)
        retries: list[str] = []
        vm.retry_requested.connect(lambda: retries.append("retry"))
        vm.set_error("No se pudieron cargar los resultados")
        assert vm.errorText.startswith("No se pudieron")
        vm.retry()
        vm.set_error("")
        assert retries == ["retry"]
        assert vm.errorText == ""


class TestSearchScreenQml:
    def test_qml_loads(self, qapp):
        from doremi.ui.screens.search_qml import SearchScreenQml

        screen = SearchScreenQml(None, lambda *a: None, lambda r: None)
        assert screen.is_ok
        assert screen._qml_island is True

    def test_play_reaches_callback(self, qapp):
        from doremi.ui.screens.search_qml import SearchScreenQml

        played: list[tuple] = []
        screen = SearchScreenQml(None, lambda *a: played.append(a), lambda r: None)
        assert screen.is_ok
        screen._vm.set_songs(SONGS)
        screen._vm.play_rest(2)
        assert played == [("s8", "Canción 8", "Artista A", "", 180008, "https://x/1.jpg")]

    def test_navigate_passthrough(self, qapp):
        from doremi.ui.screens.search_qml import SearchScreenQml

        routes: list[str] = []
        screen = SearchScreenQml(None, lambda *a: None, routes.append)
        assert screen.is_ok
        screen._vm.navigate("album?id=A1")
        assert routes == ["album?id=A1"]

    def test_search_empty_query_clears(self, qapp):
        import asyncio
        from doremi.ui.screens.search_qml import SearchScreenQml

        screen = SearchScreenQml(None, lambda *a: None, lambda r: None)
        screen._current_query = "x"
        screen._vm.set_query("x")
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(screen.search(""))
        finally:
            loop.close()
        assert screen._current_query == ""
        assert screen._vm.query == ""
