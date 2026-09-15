from __future__ import annotations

import random

from PySide6.QtCore import (
    QAbstractListModel, Property, QModelIndex, QObject, Qt, Signal, Slot,
)


class ArtistSongModel(QAbstractListModel):
    """Top canciones del artista."""

    TitleRole = Qt.UserRole + 1
    ArtistRole = Qt.UserRole + 2
    DurationRole = Qt.UserRole + 3
    DurationMsRole = Qt.UserRole + 4
    ThumbnailRole = Qt.UserRole + 5
    VideoIdRole = Qt.UserRole + 6
    IsLikedRole = Qt.UserRole + 7

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[dict] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        item = self._items[index.row()]
        if role == self.TitleRole:
            return item.get("title", "")
        if role == self.ArtistRole:
            return item.get("artist", "")
        if role == self.DurationRole:
            return item.get("duration", "")
        if role == self.DurationMsRole:
            return item.get("duration_ms", 0)
        if role == self.ThumbnailRole:
            return item.get("thumbnail_url", "")
        if role == self.VideoIdRole:
            return item.get("videoId", "")
        if role == self.IsLikedRole:
            return item.get("is_liked", False)
        return None

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.TitleRole: b"title",
            self.ArtistRole: b"artist",
            self.DurationRole: b"duration",
            self.DurationMsRole: b"durationMs",
            self.ThumbnailRole: b"thumbnail",
            self.VideoIdRole: b"videoId",
            self.IsLikedRole: b"isLiked",
        }

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def get(self, row: int) -> dict | None:
        return self._items[row] if 0 <= row < len(self._items) else None


class ArtistCardModel(QAbstractListModel):
    """Cards de álbumes y artistas similares (roles uniformes)."""

    TitleRole = Qt.UserRole + 1
    SubtitleRole = Qt.UserRole + 2
    ThumbnailRole = Qt.UserRole + 3
    NavigateRole = Qt.UserRole + 4
    RoundRole = Qt.UserRole + 5  # True → crop circular (artistas)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[dict] = []
        self._round = False

    def set_round(self, value: bool) -> None:
        self._round = value

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        item = self._items[index.row()]
        if role == self.TitleRole:
            return item.get("title", "") or item.get("name", "")
        if role == self.SubtitleRole:
            return item.get("year", "") or item.get("artist", "")
        if role == self.ThumbnailRole:
            return item.get("thumbnail_url", "")
        if role == self.NavigateRole:
            return item.get("navigate", "")
        if role == self.RoundRole:
            return self._round
        return None

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.TitleRole: b"title",
            self.SubtitleRole: b"subtitle",
            self.ThumbnailRole: b"thumbnail",
            self.NavigateRole: b"navigate",
            self.RoundRole: b"roundCrop",
        }

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def get(self, row: int) -> dict | None:
        return self._items[row] if 0 <= row < len(self._items) else None


class ArtistViewModel(QObject):
    """Puente Python → QML para la pantalla Artista (isla QML)."""

    loading_changed = Signal()
    header_changed = Signal()

    # Mismas señales que ArtistScreen (QtWidgets)
    download_requested = Signal(str, str, str, str)
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    like_requested = Signal(str, object)
    add_to_playlist_requested = Signal(str, str)
    delete_download_requested = Signal(str)
    play_requested = Signal(str, str, str, int, str)  # videoId, title, artist, duration_ms, thumb
    navigate_requested = Signal(str)
    back_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._songs = ArtistSongModel(self)
        self._albums = ArtistCardModel(self)
        self._related = ArtistCardModel(self)
        self._related.set_round(True)
        self._loading = True
        self._found = True
        self._name = ""
        self._subscribers = ""
        self._thumbnail = ""

    # ── Properties ─────────────────────────────────────────────────────────

    @Property(QObject, constant=True)
    def songs(self) -> ArtistSongModel:
        return self._songs

    @Property(QObject, constant=True)
    def albums(self) -> ArtistCardModel:
        return self._albums

    @Property(QObject, constant=True)
    def related(self) -> ArtistCardModel:
        return self._related

    @Property(bool, notify=loading_changed)
    def loading(self) -> bool:
        return self._loading

    @Property(bool, notify=header_changed)
    def found(self) -> bool:
        return self._found

    @Property(str, notify=header_changed)
    def artistName(self) -> str:
        return self._name

    @Property(str, notify=header_changed)
    def subscribers(self) -> str:
        return self._subscribers

    @Property(str, notify=header_changed)
    def thumbnail(self) -> str:
        return self._thumbnail

    @Property(bool, notify=header_changed)
    def hasSongs(self) -> bool:
        return self._songs.rowCount() > 0

    # ── Mutators (Python side) ─────────────────────────────────────────────

    def set_loading(self, value: bool) -> None:
        if self._loading != value:
            self._loading = value
            self.loading_changed.emit()

    def set_data(self, data: dict) -> None:
        self._found = bool(data.get("name"))
        self._name = data.get("name", "")
        self._subscribers = data.get("subscribers", "")
        self._thumbnail = data.get("thumbnail_url", "")
        self._songs.set_items(data.get("songs", []))
        self._albums.set_items(data.get("albums", []))
        self._related.set_items(data.get("related", []))
        self.header_changed.emit()

    # ── Slots called from QML ──────────────────────────────────────────────

    @Slot()
    def play_all(self) -> None:
        if self._songs.rowCount() > 0:
            self.play_at(0)

    @Slot()
    def play_shuffle(self) -> None:
        n = self._songs.rowCount()
        if n > 0:
            self.play_at(random.randrange(n))

    @Slot(int)
    def play_at(self, index: int) -> None:
        item = self._songs.get(index)
        if item is None:
            return
        self.play_requested.emit(
            item.get("videoId", ""), item.get("title", ""), item.get("artist", ""),
            item.get("duration_ms", 0), item.get("thumbnail_url", ""),
        )

    @Slot(int, str)
    def song_action(self, index: int, action: str) -> None:
        item = self._songs.get(index)
        if item is None:
            return
        vid = item.get("videoId", "")
        title = item.get("title", "")
        artist = item.get("artist", "")
        thumb = item.get("thumbnail_url", "")
        if action == "download":
            self.download_requested.emit(vid, title, artist, thumb)
        elif action == "play_next":
            self.play_next_requested.emit(vid, title, artist, thumb)
        elif action == "add_to_queue":
            self.add_to_queue_requested.emit(vid, title, artist, thumb)
        elif action == "like":
            self.like_requested.emit(vid, None)
        elif action == "add_to_playlist":
            self.add_to_playlist_requested.emit(vid, thumb)

    @Slot(str)
    def navigate(self, route: str) -> None:
        if route:
            self.navigate_requested.emit(route)

    @Slot()
    def go_back(self) -> None:
        self.back_requested.emit()
