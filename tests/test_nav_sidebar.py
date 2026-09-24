from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_sidebar_shows_up_to_four_playlist_shortcuts(qapp):
    from doremi.ui.widgets.nav_sidebar import NavSidebar

    sidebar = NavSidebar(lambda _route: None)
    sidebar.set_playlists([
        {
            "title": f"Playlist {i}",
            "navigate": f"playlist?id={i}",
            "thumbnail_url": f"https://img.example.test/{i}.jpg",
        }
        for i in range(6)
    ])

    assert [button.label for button in sidebar._playlist_buttons] == [
        "Playlist 0", "Playlist 1", "Playlist 2", "Playlist 3",
    ]
    assert [button.thumbnail_url for button in sidebar._playlist_buttons] == [
        f"https://img.example.test/{i}.jpg" for i in range(4)
    ]
    assert sidebar._playlist_section.isHidden() is False

    sidebar.toggle_collapse()
    assert sidebar._playlist_section.isHidden() is True
