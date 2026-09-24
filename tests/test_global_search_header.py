from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_header_places_profile_next_to_notifications(qapp):
    from doremi.ui.widgets.global_search import GlobalSearchBar

    header = GlobalSearchBar(None, lambda *_args: None)
    opened: list[bool] = []
    header.profile_requested.connect(lambda: opened.append(True))
    header.update_profile(True, "Doremi", "")

    assert header.profile_btn.accessibleName() == "Doremi"
    assert header.profile_btn.parentWidget() is header.bar_widget
    header.profile_btn.click()
    assert opened == [True]
