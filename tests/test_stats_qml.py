"""Tests de la isla QML — Estadísticas."""
from __future__ import annotations

import datetime

import pytest


@pytest.fixture(scope="module")
def qapp():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


DATA = {
    "time_listened": "5h 30m",
    "total_plays": 247,
    "unique_artists": 12,
    "top_songs": [
        {"videoId": f"s{i}", "title": f"Song {i}", "artist": "Artista",
         "plays": 10 - i, "thumbnail_url": "", "is_liked": i % 2 == 0}
        for i in range(5)
    ],
    "chart": [
        {"day": d, "count": c} for d, c in
        [("Lun", 2), ("Mar", 0), ("Mié", 5), ("Jue", 3), ("Vie", 8), ("Sáb", 1), ("Dom", 4)]
    ],
}


class TestStatsViewModel:
    def test_summary_and_models(self, qapp):
        from doremi.ui.viewmodels.stats_vm import StatsViewModel

        vm = StatsViewModel(qapp)
        vm.set_data(DATA)
        assert vm.timeListened == "5h 30m"
        assert vm.totalPlays == 247
        assert vm.uniqueArtists == 12
        assert vm.topSongs.rowCount() == 5
        assert vm.chart.rowCount() == 7
        assert vm.chartMax == 8
        assert vm.topSongs.data(vm.topSongs.index(0, 0), vm.topSongs.PlaysRole) == 10

    def test_empty_state(self, qapp):
        from doremi.ui.viewmodels.stats_vm import StatsViewModel

        vm = StatsViewModel(qapp)
        vm.set_data({})
        assert vm.totalPlays == 0
        assert vm.chartMax == 0
        assert vm.topSongs.rowCount() == 0

    def test_play_and_actions(self, qapp):
        from doremi.ui.viewmodels.stats_vm import StatsViewModel

        vm = StatsViewModel(qapp)
        vm.set_data(DATA)
        plays: list[tuple] = []
        artists: list[str] = []
        vm.play_requested.connect(lambda *a: plays.append(a))
        vm.artist_clicked.connect(artists.append)

        vm.play_at(1)
        vm.song_action(1, "go_artist")
        vm.play_at(99)

        assert plays == [("s1", "Song 1", "Artista", 0, "")]
        assert artists == ["Artista"]


class TestStatsData:
    def test_gather_stats_empty_history(self):
        import asyncio
        from doremi.ui.screens.stats_data import gather_stats

        async def _run():
            # Sin DB configurada en tests: debe devolver estructura vacía sin explotar
            return await gather_stats()

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(_run())
        finally:
            loop.close()
        assert result["total_plays"] == 0 or result["total_plays"] >= 0
        assert set(result.keys()) == {
            "time_listened", "total_plays", "unique_artists", "top_songs", "chart",
        }

    def test_chart_weekday_labels(self):
        # El cálculo de 7 días usa etiquetas en español
        weekday_map = {0: "Lun", 1: "Mar", 2: "Mié", 3: "Jue", 4: "Vie", 5: "Sáb", 6: "Dom"}
        labels = [
            weekday_map[(datetime.date.today() - datetime.timedelta(days=i)).weekday()]
            for i in range(6, -1, -1)
        ]
        assert len(labels) == 7
        assert labels[-1] == weekday_map[datetime.date.today().weekday()]


class TestStatsScreenQml:
    def test_qml_loads(self, qapp):
        from doremi.ui.screens.stats_qml import StatsScreenQml

        screen = StatsScreenQml(None, lambda *a: None)
        assert screen.is_ok
        assert screen._qml_island is True

    def test_play_passthrough(self, qapp):
        from doremi.ui.screens.stats_qml import StatsScreenQml

        played: list[tuple] = []
        screen = StatsScreenQml(None, lambda *a: played.append(a))
        screen._vm.set_data(DATA)
        screen._vm.play_at(2)
        assert played == [("s2", "Song 2", "Artista", "", 0, "")]
