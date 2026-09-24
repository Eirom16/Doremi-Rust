from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from doremi.audio.queue import PlayQueue, QueueItem
from doremi.ui.controllers.queue_controller import QueueController


@pytest.mark.asyncio
@pytest.mark.parametrize("add_next, expected", [
    (True, ["a", "new", "b", "c"]),
    (False, ["a", "b", "c", "new"]),
])
async def test_queue_actions_have_distinct_insertion_positions(add_next, expected):
    queue = PlayQueue()
    queue.set_queue([QueueItem(vid, vid, "", "", 0, "") for vid in "abc"])
    window = MagicMock()
    extractor = SimpleNamespace(get_stream_info=AsyncMock(return_value={}))
    controller = QueueController(window, queue, extractor, MagicMock())
    await controller.add_to_queue_async("new", "New", "", "", add_next=add_next)
    assert [item.video_id for item in queue.items] == expected


@pytest.fixture
def application():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.mark.asyncio
async def test_playlist_thumbnail_can_be_scaled(application, tmp_path, monkeypatch):
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QLabel
    from doremi.utils.image_cache import ImageCache

    path = tmp_path / "cover.png"
    cover = QImage(80, 80, QImage.Format.Format_RGB32)
    cover.fill(0)
    assert cover.save(str(path))
    monkeypatch.setattr(ImageCache, "download", AsyncMock(return_value=path))
    label = QLabel()
    controller = QueueController(MagicMock(), PlayQueue(), MagicMock(), MagicMock())
    await controller.load_playlist_thumb(label, "https://example.invalid/cover")
    assert not label.pixmap().isNull()
    assert label.pixmap().width() == 44


@pytest.mark.asyncio
async def test_unlike_in_widget_library_removes_card(application, monkeypatch):
    from PySide6.QtWidgets import QWidget
    import doremi.db.repository as repositories

    monkeypatch.setattr(repositories, "SongRepository", lambda: SimpleNamespace(
        get_song=AsyncMock(return_value=SimpleNamespace(is_liked=True)),
        toggle_like=AsyncMock(return_value=False),
    ))
    window = MagicMock()
    window.yt.is_authenticated = False
    window.library_screen._current_tab = "songs"
    window.stack.currentWidget.return_value = window.library_screen
    card = QWidget()
    button = MagicMock()
    button.parent.return_value = card
    button.objectName.return_value = "songLike"
    controller = QueueController(window, PlayQueue(), MagicMock(), MagicMock())
    await controller.toggle_like_async("song", button)
    window.library_screen.content_layout.removeWidget.assert_called_once_with(card)
