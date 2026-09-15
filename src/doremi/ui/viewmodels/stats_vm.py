from __future__ import annotations

from PySide6.QtCore import (
    QAbstractListModel, Property, QModelIndex, QObject, Qt, Signal, Slot,
)


class TopSongsModel(QAbstractListModel):
    TitleRole = Qt.UserRole + 1
    ArtistRole = Qt.UserRole + 2
    PlaysRole = Qt.UserRole + 3
    ThumbnailRole = Qt.UserRole + 4
    VideoIdRole = Qt.UserRole + 5
    IsLikedRole = Qt.UserRole + 6

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
        if role == self.PlaysRole:
            return item.get("plays", 0)
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
            self.PlaysRole: b"plays",
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


class ChartModel(QAbstractListModel):
    """Barras de actividad diaria (últimos 7 días)."""

    DayRole = Qt.UserRole + 1
    CountRole = Qt.UserRole + 2

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[dict] = []
        self._max = 0

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        item = self._items[index.row()]
        if role == self.DayRole:
            return item.get("day", "")
        if role == self.CountRole:
            return item.get("count", 0)
        return None

    def roleNames(self) -> dict[int, bytes]:
        return {self.DayRole: b"day", self.CountRole: b"count"}

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        self._items = items
        self._max = max((it.get("count", 0) for it in items), default=0)
        self.endResetModel()

    @property
    def max_value(self) -> int:
        return self._max


class StatsViewModel(QObject):
    """Puente Python → QML para la pantalla Estadísticas (isla QML)."""

    loading_changed = Signal()
    summary_changed = Signal()

    # Mismas señales que StatsScreen (QtWidgets)
    download_requested = Signal(str, str, str, str)
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    like_requested = Signal(str, object)
    add_to_playlist_requested = Signal(str, str)
    delete_download_requested = Signal(str)
    artist_clicked = Signal(str)
    play_requested = Signal(str, str, str, int, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._top_songs = TopSongsModel(self)
        self._chart = ChartModel(self)
        self._loading = True
        self._time_listened = "0m"
        self._total_plays = 0
        self._unique_artists = 0

    # ── Properties ─────────────────────────────────────────────────────────

    @Property(QObject, constant=True)
    def topSongs(self) -> TopSongsModel:
        return self._top_songs

    @Property(QObject, constant=True)
    def chart(self) -> ChartModel:
        return self._chart

    @Property(bool, notify=loading_changed)
    def loading(self) -> bool:
        return self._loading

    @Property(str, notify=summary_changed)
    def timeListened(self) -> str:
        return self._time_listened

    @Property(int, notify=summary_changed)
    def totalPlays(self) -> int:
        return self._total_plays

    @Property(int, notify=summary_changed)
    def uniqueArtists(self) -> int:
        return self._unique_artists

    @Property(int, notify=summary_changed)
    def chartMax(self) -> int:
        return self._chart.max_value

    # ── Mutators ───────────────────────────────────────────────────────────

    def set_loading(self, value: bool) -> None:
        if self._loading != value:
            self._loading = value
            self.loading_changed.emit()

    def set_data(self, data: dict) -> None:
        self._time_listened = data.get("time_listened", "0m")
        self._total_plays = data.get("total_plays", 0)
        self._unique_artists = data.get("unique_artists", 0)
        self._top_songs.set_items(data.get("top_songs", []))
        self._chart.set_items(data.get("chart", []))
        self.summary_changed.emit()

    # ── Slots called from QML ──────────────────────────────────────────────

    @Slot(int)
    def play_at(self, index: int) -> None:
        item = self._top_songs.get(index)
        if item is None:
            return
        self.play_requested.emit(
            item.get("videoId", ""), item.get("title", ""), item.get("artist", ""),
            0, item.get("thumbnail_url", ""),
        )

    @Slot(int, str)
    def song_action(self, index: int, action: str) -> None:
        item = self._top_songs.get(index)
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
        elif action == "go_artist":
            self.artist_clicked.emit(artist)
