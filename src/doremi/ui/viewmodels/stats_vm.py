from __future__ import annotations

from PySide6.QtCore import (
    QAbstractListModel, Property, QModelIndex, QObject, Qt, Signal, Slot,
)


from doremi.ui.viewmodels.track_state_model import TrackStateModel


class TopSongsModel(TrackStateModel):
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
    error_changed = Signal()
    period_changed = Signal()
    wrapped_changed = Signal()
    wrapped_requested = Signal(str)

    # Mismas señales que StatsScreen (QtWidgets)
    download_requested = Signal(str, str, str, str)
    copy_link_requested = Signal(str)
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    like_requested = Signal(str, object)
    add_to_playlist_requested = Signal(str, str)
    delete_download_requested = Signal(str)
    artist_clicked = Signal(str)
    play_requested = Signal(str, str, str, int, str)
    retry_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._top_songs = TopSongsModel(self)
        self._chart = ChartModel(self)
        self._loading = True
        self._time_listened = "0m"
        self._total_plays = 0
        self._unique_artists = 0
        self._error_text = ""
        self._period = "all"
        self._insights = {}
        self._wrapped = {}

    @Property("QVariantMap", notify=wrapped_changed)
    def wrapped(self):
        return self._wrapped

    def set_wrapped(self, data):
        self._wrapped = data
        self.wrapped_changed.emit()

    @Slot(str)
    def request_wrapped(self, kind):
        if kind in {"month", "year"}:
            self.wrapped_requested.emit(kind)

    @Property(str, notify=period_changed)
    def period(self):
        return self._period

    @Property("QVariantMap", notify=summary_changed)
    def insights(self):
        return self._insights

    @Slot(str)
    def select_period(self, period):
        if period in {"today", "week", "month", "year", "all"} and period != self._period:
            self._period = period
            self.period_changed.emit()
            self.retry_requested.emit()

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

    @Property(str, notify=error_changed)
    def errorText(self) -> str:
        return self._error_text

    # ── Mutators ───────────────────────────────────────────────────────────

    def set_loading(self, value: bool) -> None:
        if self._loading != value:
            self._loading = value
            self.loading_changed.emit()

    def set_data(self, data: dict) -> None:
        self._insights = data
        self._time_listened = data.get("time_listened", "0m")
        self._total_plays = data.get("total_plays", 0)
        self._unique_artists = data.get("unique_artists", 0)
        self._top_songs.set_items(data.get("top_songs", []))
        self._chart.set_items(data.get("chart", []))
        self.summary_changed.emit()

    def set_error(self, message: str) -> None:
        message = str(message or "")
        if self._error_text != message:
            self._error_text = message
            self.error_changed.emit()

    # ── Slots called from QML ──────────────────────────────────────────────

    @Slot()
    def retry(self) -> None:
        self.retry_requested.emit()

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
        if action == "play":
            self.play_at(index)
            return
        from doremi.ui.viewmodels.track_actions import dispatch_track_action
        dispatch_track_action(self, item, action)
