from __future__ import annotations

from PySide6.QtCore import (
    QAbstractListModel, Property, QModelIndex, QObject, Qt, Signal, Slot,
)


class SearchSongModel(QAbstractListModel):
    """Lista de canciones de búsqueda (featured o rest)."""

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


class SearchAlbumModel(QAbstractListModel):
    # roles uniformes con SearchPlaylistModel: el grid QML usa un solo delegate
    TitleRole = Qt.UserRole + 1
    SubtitleRole = Qt.UserRole + 2
    ThumbnailRole = Qt.UserRole + 3
    NavigateRole = Qt.UserRole + 4
    NameRole = Qt.UserRole + 5
    ArtistRole = Qt.UserRole + 6
    YearRole = Qt.UserRole + 7
    IsDownloadedRole = Qt.UserRole + 8

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[dict] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        item = self._items[index.row()]
        if role in (self.TitleRole, self.NameRole):
            return item.get("title", "")
        if role in (self.SubtitleRole, self.ArtistRole):
            return item.get("artist", "")
        if role == self.YearRole:
            return item.get("year", "")
        if role == self.ThumbnailRole:
            return item.get("thumbnail_url", "")
        if role == self.NavigateRole:
            return item.get("navigate", "")
        if role == self.IsDownloadedRole:
            return item.get("is_downloaded", False)
        return None

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.TitleRole: b"title",
            self.NameRole: b"name",
            self.SubtitleRole: b"subtitle",
            self.ArtistRole: b"artist",
            self.YearRole: b"year",
            self.ThumbnailRole: b"thumbnail",
            self.NavigateRole: b"navigate",
            self.IsDownloadedRole: b"isDownloaded",
        }

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()


class SearchPlaylistModel(QAbstractListModel):
    TitleRole = Qt.UserRole + 1
    SubtitleRole = Qt.UserRole + 2
    ThumbnailRole = Qt.UserRole + 3
    IsDownloadedRole = Qt.UserRole + 4
    NavigateRole = Qt.UserRole + 5
    NameRole = Qt.UserRole + 6
    ArtistRole = Qt.UserRole + 7
    YearRole = Qt.UserRole + 8

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[dict] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        item = self._items[index.row()]
        if role in (self.TitleRole, self.NameRole):
            return item.get("title", "")
        if role in (self.SubtitleRole, self.ArtistRole):
            return item.get("subtitle", "")
        if role == self.YearRole:
            return ""
        if role == self.ThumbnailRole:
            return item.get("thumbnail_url", "")
        if role == self.IsDownloadedRole:
            return item.get("is_downloaded", False)
        if role == self.NavigateRole:
            return item.get("navigate", "")
        return None

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.TitleRole: b"title",
            self.NameRole: b"name",
            self.SubtitleRole: b"subtitle",
            self.ArtistRole: b"artist",
            self.YearRole: b"year",
            self.ThumbnailRole: b"thumbnail",
            self.IsDownloadedRole: b"isDownloaded",
            self.NavigateRole: b"navigate",
        }

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()


_TYPE_LABELS = {"song": "Canción", "video": "Video", "": "Canción"}


class SearchViewModel(QObject):
    """Puente Python → QML para la pantalla Buscar (isla QML).

    Mismas señales que SearchScreen (QtWidgets). Layout de la pestaña
    canciones: resultado principal (properties topX) + 4 destacadas
    (`featured`) + el resto (`rest`).
    """

    loading_changed = Signal()
    category_changed = Signal()
    query_changed = Signal()
    top_changed = Signal()
    error_changed = Signal()

    # Mismas señales que SearchScreen (QtWidgets)
    download_requested = Signal(str, str, str, str)
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    like_requested = Signal(str, object)
    add_to_playlist_requested = Signal(str, str)
    delete_download_requested = Signal(str)
    play_requested = Signal(str, str, str, int, str)
    navigate_requested = Signal(str)
    retry_requested = Signal()  # la isla pide re-fetch de la categoría activa

    CATEGORIES = ("song", "album", "podcast", "playlist")

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._featured = SearchSongModel(self)
        self._rest = SearchSongModel(self)
        self._albums = SearchAlbumModel(self)
        self._playlists = SearchPlaylistModel(self)
        self._loading = False
        self._category = "song"
        self._query = ""
        self._error = ""
        self._top: dict | None = None

    # ── Properties ─────────────────────────────────────────────────────────

    @Property(QObject, constant=True)
    def featured(self) -> SearchSongModel:
        return self._featured

    @Property(QObject, constant=True)
    def rest(self) -> SearchSongModel:
        return self._rest

    @Property(QObject, constant=True)
    def albums(self) -> SearchAlbumModel:
        return self._albums

    @Property(QObject, constant=True)
    def playlists(self) -> SearchPlaylistModel:
        return self._playlists

    @Property(bool, notify=loading_changed)
    def loading(self) -> bool:
        return self._loading

    @Property(str, notify=category_changed)
    def category(self) -> str:
        return self._category

    @Property(str, notify=query_changed)
    def query(self) -> str:
        return self._query

    @Property(str, notify=error_changed)
    def errorText(self) -> str:
        return self._error

    @Property(bool, notify=top_changed)
    def hasTop(self) -> bool:
        return self._top is not None

    @Property(str, notify=top_changed)
    def topTitle(self) -> str:
        return self._top.get("title", "") if self._top else ""

    @Property(str, notify=top_changed)
    def topArtist(self) -> str:
        return self._top.get("artist", "") if self._top else ""

    @Property(str, notify=top_changed)
    def topThumbnail(self) -> str:
        return self._top.get("thumbnail_url", "") if self._top else ""

    @Property(str, notify=top_changed)
    def topType(self) -> str:
        if not self._top:
            return ""
        return _TYPE_LABELS.get(self._top.get("result_type", ""), "Canción")

    # ── Mutators (Python side) ─────────────────────────────────────────────

    def set_loading(self, value: bool) -> None:
        if self._loading != value:
            self._loading = value
            self.loading_changed.emit()

    def set_error(self, value: str) -> None:
        if self._error != value:
            self._error = value
            self.error_changed.emit()

    def set_query(self, value: str) -> None:
        if self._query != value:
            self._query = value
            self.query_changed.emit()

    def set_songs(self, items: list[dict]) -> None:
        self._top = items[0] if items else None
        self._featured.set_items(items[1:5])
        self._rest.set_items(items[5:])
        self.top_changed.emit()

    def set_albums(self, items: list[dict]) -> None:
        self._albums.set_items(items)

    def set_playlists(self, items: list[dict]) -> None:
        self._playlists.set_items(items)

    # ── Slots called from QML ──────────────────────────────────────────────

    @Slot(str)
    def set_category(self, category: str) -> None:
        if category in self.CATEGORIES and category != self._category:
            self._category = category
            self.category_changed.emit()

    @Slot()
    def play_top(self) -> None:
        self._emit_play(self._top)

    @Slot(str)
    def top_action(self, action: str) -> None:
        self._emit_action(self._top, action)

    @Slot(int)
    def play_featured(self, index: int) -> None:
        self._emit_play(self._featured.get(index))

    @Slot(int, str)
    def featured_action(self, index: int, action: str) -> None:
        self._emit_action(self._featured.get(index), action)

    @Slot(int)
    def play_rest(self, index: int) -> None:
        self._emit_play(self._rest.get(index))

    @Slot(int, str)
    def rest_action(self, index: int, action: str) -> None:
        self._emit_action(self._rest.get(index), action)

    @Slot(str)
    def navigate(self, route: str) -> None:
        if route:
            self.navigate_requested.emit(route)

    @Slot()
    def retry(self) -> None:
        self.retry_requested.emit()

    # ── Helpers ────────────────────────────────────────────────────────────

    def _emit_play(self, item: dict | None) -> None:
        if not item or not item.get("videoId"):
            return
        self.play_requested.emit(
            item["videoId"], item.get("title", ""), item.get("artist", ""),
            item.get("duration_ms", 0), item.get("thumbnail_url", ""),
        )

    def _emit_action(self, item: dict | None, action: str) -> None:
        if not item:
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
        elif action == "delete_download":
            self.delete_download_requested.emit(vid)
