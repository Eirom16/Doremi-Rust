from __future__ import annotations

from PySide6.QtCore import (
    QAbstractListModel, Property, QModelIndex, QObject, Qt, Signal, Slot,
)


class _BaseModel(QAbstractListModel):
    """Base con set_items/get comunes."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[dict] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._items)

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def get(self, row: int) -> dict | None:
        return self._items[row] if 0 <= row < len(self._items) else None


class LibrarySongModel(_BaseModel):
    TitleRole = Qt.UserRole + 1
    ArtistRole = Qt.UserRole + 2
    DurationRole = Qt.UserRole + 3
    DurationMsRole = Qt.UserRole + 4
    ThumbnailRole = Qt.UserRole + 5
    VideoIdRole = Qt.UserRole + 6
    IsLikedRole = Qt.UserRole + 7

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


class LibraryAlbumModel(_BaseModel):
    TitleRole = Qt.UserRole + 1
    ArtistRole = Qt.UserRole + 2
    YearRole = Qt.UserRole + 3
    ThumbnailRole = Qt.UserRole + 4
    NavigateRole = Qt.UserRole + 5
    NameRole = Qt.UserRole + 6
    SubtitleRole = Qt.UserRole + 7
    IsDownloadedRole = Qt.UserRole + 8

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        item = self._items[index.row()]
        if role in (self.TitleRole, self.NameRole):
            return item.get("title", "")
        if role == self.ArtistRole:
            return item.get("artist", "")
        if role == self.YearRole:
            return item.get("year", "")
        if role == self.SubtitleRole:
            artist = item.get("artist", "")
            year = item.get("year", "")
            return f"{artist} · {year}" if artist and year else (artist or year)
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
            self.ArtistRole: b"artist",
            self.YearRole: b"year",
            self.SubtitleRole: b"subtitle",
            self.ThumbnailRole: b"thumbnail",
            self.NavigateRole: b"navigate",
            self.IsDownloadedRole: b"isDownloaded",
        }


class LibraryArtistModel(_BaseModel):
    NameRole = Qt.UserRole + 1
    ThumbnailRole = Qt.UserRole + 2
    NavigateRole = Qt.UserRole + 3
    TitleRole = Qt.UserRole + 4
    ArtistRole = Qt.UserRole + 5
    YearRole = Qt.UserRole + 6
    SubtitleRole = Qt.UserRole + 7
    IsDownloadedRole = Qt.UserRole + 8

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        item = self._items[index.row()]
        if role in (self.NameRole, self.TitleRole):
            return item.get("name", "")
        if role == self.ArtistRole:
            return ""
        if role == self.YearRole:
            return ""
        if role == self.SubtitleRole:
            return ""
        if role == self.ThumbnailRole:
            return item.get("thumbnail_url", "")
        if role == self.NavigateRole:
            return item.get("navigate", "")
        if role == self.IsDownloadedRole:
            return False
        return None

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.NameRole: b"name",
            self.TitleRole: b"title",
            self.ArtistRole: b"artist",
            self.YearRole: b"year",
            self.SubtitleRole: b"subtitle",
            self.ThumbnailRole: b"thumbnail",
            self.NavigateRole: b"navigate",
            self.IsDownloadedRole: b"isDownloaded",
        }


class LibraryPlaylistModel(_BaseModel):
    TitleRole = Qt.UserRole + 1
    SubtitleRole = Qt.UserRole + 2
    ThumbnailRole = Qt.UserRole + 3
    IsDownloadedRole = Qt.UserRole + 4
    NavigateRole = Qt.UserRole + 5
    NameRole = Qt.UserRole + 6
    ArtistRole = Qt.UserRole + 7
    YearRole = Qt.UserRole + 8

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        item = self._items[index.row()]
        if role in (self.TitleRole, self.NameRole):
            return item.get("title", "")
        if role == self.SubtitleRole:
            return item.get("subtitle", "")
        if role == self.ArtistRole:
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


class LibraryViewModel(QObject):
    """Puente Python → QML para la pantalla Biblioteca (isla QML).

    Re-emite las mismas señales que LibraryScreen (QtWidgets). Filtrado y
    ordenación se aplican en Python (testeable) sobre copias crudas por tab.
    """

    loading_changed = Signal()
    tab_changed = Signal()
    filter_changed = Signal()
    sort_changed = Signal()
    auth_required_changed = Signal()

    # Mismas señales que LibraryScreen (QtWidgets)
    download_requested = Signal(str, str, str, str)
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    like_requested = Signal(str, object)
    add_to_playlist_requested = Signal(str, str)
    delete_download_requested = Signal(str)
    artist_clicked = Signal(str)
    album_clicked = Signal(str)
    play_requested = Signal(str, str, str, int, str)  # videoId, title, artist, duration_ms, thumb
    navigate_requested = Signal(str)
    create_playlist_requested = Signal(str, str)  # title, description

    TABS = ("songs", "albums", "artists", "playlists")

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._songs = LibrarySongModel(self)
        self._albums = LibraryAlbumModel(self)
        self._artists = LibraryArtistModel(self)
        self._playlists = LibraryPlaylistModel(self)
        self._tab = "songs"
        self._loading = True
        self._filter = ""
        self._sort = "recent"
        self._auth_required = False
        self._raw: dict[str, list[dict]] = {}

    # ── Properties ─────────────────────────────────────────────────────────

    @Property(QObject, constant=True)
    def songs(self) -> LibrarySongModel:
        return self._songs

    @Property(QObject, constant=True)
    def albums(self) -> LibraryAlbumModel:
        return self._albums

    @Property(QObject, constant=True)
    def artists(self) -> LibraryArtistModel:
        return self._artists

    @Property(QObject, constant=True)
    def playlists(self) -> LibraryPlaylistModel:
        return self._playlists

    @Property(str, notify=tab_changed)
    def tab(self) -> str:
        return self._tab

    @Property(bool, notify=loading_changed)
    def loading(self) -> bool:
        return self._loading

    @Property(str, notify=filter_changed)
    def filterText(self) -> str:
        return self._filter

    @Property(str, notify=sort_changed)
    def sortMode(self) -> str:
        return self._sort

    @Property(bool, notify=auth_required_changed)
    def authRequired(self) -> bool:
        return self._auth_required

    # ── Mutators (Python side) ─────────────────────────────────────────────

    def set_loading(self, value: bool) -> None:
        if self._loading != value:
            self._loading = value
            self.loading_changed.emit()

    def set_auth_required(self, value: bool) -> None:
        if self._auth_required != value:
            self._auth_required = value
            self.auth_required_changed.emit()

    def set_tab_data(self, tab: str, items: list[dict]) -> None:
        self._raw[tab] = items
        self._apply(tab)

    def clear_tab_data(self, tab: str) -> None:
        self._raw.pop(tab, None)

    # ── Filter / sort (aplicado sobre los datos crudos) ────────────────────

    def _apply(self, tab: str | None = None) -> None:
        tab = tab or self._tab
        items = list(self._raw.get(tab, []))
        if self._filter:
            f = self._filter
            items = [it for it in items if f in " ".join(
                str(v or "") for v in (it.get("title"), it.get("artist"),
                                       it.get("name"), it.get("year"))
            ).lower()]
        if self._sort == "title":
            items.sort(key=lambda it: str(it.get("title") or it.get("name") or "").lower())
        elif self._sort == "artist":
            items.sort(key=lambda it: str(it.get("artist") or it.get("name") or "").lower())

        model = {
            "songs": self._songs,
            "albums": self._albums,
            "artists": self._artists,
            "playlists": self._playlists,
        }[tab]
        model.set_items(items)

    # ── Slots called from QML ──────────────────────────────────────────────

    @Slot(str)
    def set_tab(self, tab: str) -> None:
        if tab not in self.TABS or tab == self._tab:
            return
        self._tab = tab
        self.tab_changed.emit()

    @Slot(str)
    def set_filter(self, text: str) -> None:
        value = (text or "").strip().lower()
        if value != self._filter:
            self._filter = value
            self.filter_changed.emit()
            self._apply()

    @Slot(str)
    def set_sort(self, mode: str) -> None:
        if mode in ("recent", "title", "artist") and mode != self._sort:
            self._sort = mode
            self.sort_changed.emit()
            self._apply()

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
        elif action == "go_artist":
            self.artist_clicked.emit(artist)

    @Slot(str)
    def navigate(self, route: str) -> None:
        if route:
            self.navigate_requested.emit(route)

    @Slot(str, str)
    def create_playlist(self, title: str, description: str) -> None:
        title = (title or "").strip()
        if title:
            self.create_playlist_requested.emit(title, (description or "").strip())
