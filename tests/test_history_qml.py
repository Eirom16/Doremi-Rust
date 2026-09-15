"""Tests del piloto QML — Historial.

Requieren Qt offscreen. Valida el view-model (modelo, señales) y que el
Theme.qml generado esté en sync con tokens.py.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def qapp():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


class TestHistoryViewModel:
    ITEMS = [
        {"videoId": "v1", "title": "Canción Uno", "artist": "Artista A",
         "duration": "3:24", "duration_ms": 204000, "thumbnail_url": "https://x/1.jpg"},
        {"videoId": "v2", "title": "Canción Dos", "artist": "Artista B",
         "duration": "4:00", "duration_ms": 240000, "thumbnail_url": ""},
    ]

    def test_model_roles_and_rows(self, qapp):
        from doremi.ui.viewmodels.history_vm import HistoryViewModel

        vm = HistoryViewModel(qapp)
        vm.set_items(self.ITEMS)
        model = vm.model
        assert model.rowCount() == 2
        roles = model.roleNames()
        assert roles[model.TitleRole] == b"title"
        idx = model.index(1, 0)
        assert model.data(idx, model.ArtistRole) == "Artista B"
        assert vm.empty is False

    def test_play_at_emits_request(self, qapp):
        from doremi.ui.viewmodels.history_vm import HistoryViewModel

        vm = HistoryViewModel(qapp)
        vm.set_items(self.ITEMS)
        captured: list[tuple] = []
        vm.play_requested.connect(lambda *args: captured.append(args))
        vm.play_at(1)
        assert captured == [("v2", "Canción Dos", "Artista B", 240000, "")]
        vm.play_at(99)  # fuera de rango: no emite
        assert len(captured) == 1

    def test_action_at_maps_signals(self, qapp):
        from doremi.ui.viewmodels.history_vm import HistoryViewModel

        vm = HistoryViewModel(qapp)
        vm.set_items(self.ITEMS)
        got: dict[str, list] = {"download": [], "queue": [], "like": [], "playlist": []}
        vm.download_requested.connect(lambda *a: got["download"].append(a))
        vm.add_to_queue_requested.connect(lambda *a: got["queue"].append(a))
        vm.like_requested.connect(lambda *a: got["like"].append(a))
        vm.add_to_playlist_requested.connect(lambda *a: got["playlist"].append(a))

        vm.action_at(0, "download")
        vm.action_at(0, "add_to_queue")
        vm.action_at(0, "like")
        vm.action_at(0, "add_to_playlist")
        vm.action_at(0, "inexistente")

        assert got["download"] == [("v1", "Canción Uno", "Artista A", "https://x/1.jpg")]
        assert got["queue"] == [("v1", "Canción Uno", "Artista A", "https://x/1.jpg")]
        assert got["like"] == [("v1", None)]
        assert got["playlist"] == [("v1", "https://x/1.jpg")]

    def test_empty_toggle(self, qapp):
        from doremi.ui.viewmodels.history_vm import HistoryViewModel

        vm = HistoryViewModel(qapp)
        vm.set_items([])
        assert vm.empty is True
        vm.set_items(self.ITEMS)
        assert vm.empty is False


class TestThemeQmlSync:
    def test_theme_qml_matches_tokens(self):
        import sys
        result = subprocess.run(
            [sys.executable, "tools/generate_theme_qml.py", "--check"],
            capture_output=True, text=True, cwd=ROOT,
        )
        assert result.returncode == 0, result.stdout + result.stderr
