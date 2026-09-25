from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_header_places_profile_next_to_notifications(qapp):
    from doremi.ui.widgets.global_search_qml import GlobalSearchBarQml

    header = GlobalSearchBarQml(None, lambda *_args: None)
    opened: list[bool] = []
    header.profile_requested.connect(lambda: opened.append(True))
    header.update_profile(True, "Doremi", "")

    assert header.is_ok
    assert header._vm.profileLabel == "Doremi"
    header._vm.requestProfile()
    assert opened == [True]


def test_header_keeps_history_and_deep_link_suggestions(qapp):
    from doremi.ui.widgets.global_search_qml import GlobalSearchBarQml

    header = GlobalSearchBarQml(None, lambda *_args: None)
    header._vm._history = ["Doremi", "Otra búsqueda"]
    header.set_query("dore", fetch=False)

    assert [row["title"] for row in header._vm.suggestions] == ["Doremi"]

    submitted: list[str] = []
    header.search_submitted.connect(submitted.append)
    header._vm._suggestions = [{
        "title": "Artista", "subtitle": "Artista", "icon": "", "route": "artist?id=ABC",
        "deletable": False,
    }]
    header._vm.selectSuggestion(0)

    assert submitted == ["artist?id=ABC"]
