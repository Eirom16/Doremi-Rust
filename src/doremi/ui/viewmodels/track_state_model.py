"""Small shared mutation contract for song models, without resetting lists."""
from PySide6.QtCore import QAbstractListModel, Slot

from doremi.services.experience_events import events


class TrackStateModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        events.liked_changed.connect(self.set_liked_state)
        events.downloaded_changed.connect(self.set_downloaded_state)

    @Slot(int, result="QVariantMap")
    def track_info(self, row):
        return dict(self._items[row]) if 0 <= row < len(self._items) else {}

    @Slot(str, bool)
    def set_downloaded_state(self, video_id, downloaded):
        role = next((key for key, name in self.roleNames().items() if name == b"isDownloaded"), None)
        for row, item in enumerate(self._items):
            if item.get("videoId") == video_id and bool(item.get("is_downloaded", False)) != downloaded:
                item["is_downloaded"] = downloaded
                index = self.index(row, 0)
                self.dataChanged.emit(index, index, [role] if role is not None else [])

    @Slot(str, bool)
    def set_liked_state(self, video_id, liked):
        role = next((key for key, name in self.roleNames().items() if name == b"isLiked"), None)
        if role is None:
            return
        for row, item in enumerate(self._items):
            if item.get("videoId") == video_id and bool(item.get("is_liked", False)) != liked:
                item["is_liked"] = liked
                index = self.index(row, 0)
                self.dataChanged.emit(index, index, [role])
