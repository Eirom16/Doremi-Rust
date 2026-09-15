from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, Property, QModelIndex, QObject, Qt, Signal, Slot


class HistoryListModel(QAbstractListModel):
    """Modelo de la lista del historial consumido por QML ListView."""

    VideoIdRole = Qt.UserRole + 1
    TitleRole = Qt.UserRole + 2
    ArtistRole = Qt.UserRole + 3
    DurationRole = Qt.UserRole + 4
    DurationMsRole = Qt.UserRole + 5
    ThumbnailRole = Qt.UserRole + 6

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[dict] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        item = self._items[index.row()]
        if role == self.VideoIdRole:
            return item["videoId"]
        if role == self.TitleRole:
            return item["title"]
        if role == self.ArtistRole:
            return item["artist"]
        if role == self.DurationRole:
            return item["duration"]
        if role == self.DurationMsRole:
            return item.get("duration_ms", 0)
        if role == self.ThumbnailRole:
            return item["thumbnail_url"]
        return None

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.VideoIdRole: b"videoId",
            self.TitleRole: b"title",
            self.ArtistRole: b"artist",
            self.DurationRole: b"duration",
            self.DurationMsRole: b"durationMs",
            self.ThumbnailRole: b"thumbnail",
        }

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def get(self, row: int) -> dict | None:
        return self._items[row] if 0 <= row < len(self._items) else None

    def clear(self) -> None:
        self.set_items([])


class HistoryViewModel(QObject):
    """Puente Python → QML para la pantalla Historial (isla QML).

    Expone el modelo a `ListView` y re-emite las mismas señales que la
    versión QtWidgets (`HistoryScreen`), de modo que el wiring existente
    en MainWindow funcione sin cambios.
    """

    loading_changed = Signal()
    empty_changed = Signal()

    # Mismas señales que HistoryScreen (QtWidgets)
    download_requested = Signal(str, str, str, str)
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    like_requested = Signal(str, object)
    add_to_playlist_requested = Signal(str, str)
    delete_download_requested = Signal(str)
    artist_clicked = Signal(str)
    album_clicked = Signal(str)
    play_requested = Signal(str, str, str, int, str)  # videoId, title, artist, duration_ms, thumb
    clear_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._model = HistoryListModel(self)
        self._loading = False
        self._empty = False

    # ── Properties consumed by QML ────────────────────────────────────────

    @Property(QObject, constant=True)
    def model(self) -> HistoryListModel:
        return self._model

    @Property(bool, notify=loading_changed)
    def loading(self) -> bool:
        return self._loading

    @Property(bool, notify=empty_changed)
    def empty(self) -> bool:
        return self._empty

    # ── Mutators (Python side) ────────────────────────────────────────────

    def set_loading(self, value: bool) -> None:
        if self._loading != value:
            self._loading = value
            self.loading_changed.emit()

    def set_items(self, items: list[dict]) -> None:
        self._model.set_items(items)
        empty = not items
        if self._empty != empty:
            self._empty = empty
            self.empty_changed.emit()

    # ── Slots called from QML ─────────────────────────────────────────────

    @Slot(int)
    def play_at(self, index: int) -> None:
        item = self._model.get(index)
        if item is None:
            return
        self.play_requested.emit(
            item["videoId"], item["title"], item["artist"],
            item.get("duration_ms", 0), item["thumbnail_url"],
        )

    @Slot(int, str)  # index, action
    def action_at(self, index: int, action: str) -> None:
        item = self._model.get(index)
        if item is None:
            return
        video_id, title, artist = item["videoId"], item["title"], item["artist"]
        thumb = item["thumbnail_url"]
        if action == "download":
            self.download_requested.emit(video_id, title, artist, thumb)
        elif action == "play_next":
            self.play_next_requested.emit(video_id, title, artist, thumb)
        elif action == "add_to_queue":
            self.add_to_queue_requested.emit(video_id, title, artist, thumb)
        elif action == "like":
            self.like_requested.emit(video_id, None)
        elif action == "add_to_playlist":
            self.add_to_playlist_requested.emit(video_id, thumb)
        elif action == "go_artist":
            self.artist_clicked.emit(artist)

    @Slot()
    def clear(self) -> None:
        self.clear_requested.emit()
