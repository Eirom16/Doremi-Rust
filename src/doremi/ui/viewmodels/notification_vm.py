from __future__ import annotations

from PySide6.QtCore import (
    QAbstractListModel, Property, QModelIndex, QObject, Qt, Signal, Slot,
)


class NotificationListModel(QAbstractListModel):
    """Filas del panel de notificaciones (activas, historial o lanzamientos)."""

    KindRole = Qt.UserRole + 1
    TitleRole = Qt.UserRole + 2
    ArtistRole = Qt.UserRole + 3
    VideoIdRole = Qt.UserRole + 4
    ArtistIdRole = Qt.UserRole + 5
    ThumbRole = Qt.UserRole + 6
    TimeRole = Qt.UserRole + 7
    ProgressRole = Qt.UserRole + 8
    SpeedRole = Qt.UserRole + 9

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[dict] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        item = self._items[index.row()]
        if role == self.KindRole:
            return item.get("kind", "")
        if role == self.TitleRole:
            return item.get("title", "")
        if role == self.ArtistRole:
            return item.get("artist", "")
        if role == self.VideoIdRole:
            return item.get("video_id", "")
        if role == self.ArtistIdRole:
            return item.get("artist_id", "")
        if role == self.ThumbRole:
            return item.get("thumbnail_url", "")
        if role == self.TimeRole:
            return item.get("time", "")
        if role == self.ProgressRole:
            return item.get("progress", 0.0)
        if role == self.SpeedRole:
            return item.get("speed", "")
        return None

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.KindRole: b"kind",
            self.TitleRole: b"title",
            self.ArtistRole: b"artist",
            self.VideoIdRole: b"videoId",
            self.ArtistIdRole: b"artistId",
            self.ThumbRole: b"thumbnail",
            self.TimeRole: b"timeAgo",
            self.ProgressRole: b"progress",
            self.SpeedRole: b"speed",
        }

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def append(self, item: dict) -> None:
        row = len(self._items)
        self.beginInsertRows(QModelIndex(), row, row)
        self._items.append(item)
        self.endInsertRows()

    def find_row(self, video_id: str) -> int:
        for i, it in enumerate(self._items):
            if it.get("video_id") == video_id:
                return i
        return -1

    def get(self, row: int) -> dict | None:
        return self._items[row] if 0 <= row < len(self._items) else None

    def update_item(self, video_id: str, **fields) -> bool:
        row = self.find_row(video_id)
        if row < 0:
            return False
        self._items[row].update(fields)
        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx)
        return True

    def remove_by_video_id(self, video_id: str) -> bool:
        row = self.find_row(video_id)
        if row < 0:
            return False
        self.beginRemoveRows(QModelIndex(), row, row)
        del self._items[row]
        self.endRemoveRows()
        return True


class NotificationViewModel(QObject):
    """Puente Python → QML para el panel de notificaciones (isla QML)."""

    state_changed = Signal()
    loading_changed = Signal()

    # Señales out (observadas por el wrapper)
    song_clicked = Signal(str, str, str, str)      # videoId, title, artist, thumb
    artist_clicked = Signal(str, str)              # artist name, artist id
    cancel_download_requested = Signal(str)        # videoId
    clear_history_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._active = NotificationListModel(self)
        self._history = NotificationListModel(self)
        self._releases = NotificationListModel(self)
        self._loading = False

    # ── Properties ─────────────────────────────────────────────────────────

    @Property(QObject, constant=True)
    def active(self) -> NotificationListModel:
        return self._active

    @Property(QObject, constant=True)
    def history(self) -> NotificationListModel:
        return self._history

    @Property(QObject, constant=True)
    def releases(self) -> NotificationListModel:
        return self._releases

    @Property(bool, notify=state_changed)
    def hasActive(self) -> bool:
        return self._active.rowCount() > 0

    @Property(bool, notify=state_changed)
    def hasHistory(self) -> bool:
        return self._history.rowCount() > 0

    @Property(bool, notify=state_changed)
    def hasReleases(self) -> bool:
        return self._releases.rowCount() > 0

    @Property(bool, notify=state_changed)
    def isEmpty(self) -> bool:
        return (
            self._active.rowCount() == 0
            and self._history.rowCount() == 0
            and self._releases.rowCount() == 0
        )

    @Property(bool, notify=loading_changed)
    def loading(self) -> bool:
        return self._loading

    # ── Mutators (desde wrapper) ───────────────────────────────────────────

    def set_loading(self, value: bool) -> None:
        if self._loading != value:
            self._loading = value
            self.loading_changed.emit()

    def add_active_download(self, video_id: str, title: str, artist: str) -> None:
        self._active.append({
            "video_id": video_id, "title": title, "artist": artist,
            "progress": 0.0, "speed": "", "kind": "download",
        })
        self.state_changed.emit()

    def update_active_progress(self, video_id: str, progress: float, speed: str) -> None:
        if self._active.update_item(video_id, progress=progress, speed=speed):
            pass  # dataChanged llevado por update_item

    def finish_active_download(self, video_id: str) -> None:
        self._active.remove_by_video_id(video_id)
        self.state_changed.emit()

    def add_history(self, message: str, kind: str) -> None:
        self._history.append({"title": message, "kind": kind})
        self.state_changed.emit()

    def clear_history(self) -> None:
        self._history.set_items([])
        self.state_changed.emit()

    def set_releases(self, items: list[dict]) -> None:
        self._releases.set_items(items)
        self.state_changed.emit()

    # ── Slots from QML ─────────────────────────────────────────────────────

    @Slot(str)
    def cancel_download(self, video_id: str) -> None:
        self.cancel_download_requested.emit(video_id)

    @Slot(str, str, str)
    def open_artist(self, name: str, artist_id: str) -> None:
        self.artist_clicked.emit(name, artist_id)

    @Slot(str, str, str, str)
    def play_release(self, video_id: str, title: str, artist: str, thumb: str) -> None:
        self.song_clicked.emit(video_id, title, artist, thumb)

    @Slot()
    def clear_all(self) -> None:
        self.clear_history_requested.emit()
