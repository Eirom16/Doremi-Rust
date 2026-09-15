from __future__ import annotations

import datetime
from PySide6.QtCore import (
    QAbstractListModel, Property, QModelIndex, QObject, Qt, Signal, Slot,
)


# ── Modelos QML ──────────────────────────────────────────────────────────

class SpotlightModel(QAbstractListModel):
    """Modelo de un solo item spotlight para el banner hero."""

    TitleRole = Qt.UserRole + 1
    SubtitleRole = Qt.UserRole + 2
    ThumbnailRole = Qt.UserRole + 3
    NavigateRole = Qt.UserRole + 4  # ruta de navegación (playlist/artist/album)

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
        if role == self.SubtitleRole:
            return item.get("subtitle", "")
        if role == self.ThumbnailRole:
            return item.get("thumbnail_url", "")
        if role == self.NavigateRole:
            return item.get("navigate", "")
        return None

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.TitleRole: b"title",
            self.SubtitleRole: b"subtitle",
            self.ThumbnailRole: b"thumbnail",
            self.NavigateRole: b"navigate",
        }

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()


class TileModel(QAbstractListModel):
    """Modelo de tiles de acceso rápido (QuickAccessGrid)."""

    TitleRole = Qt.UserRole + 1
    ArtistRole = Qt.UserRole + 2
    ThumbnailRole = Qt.UserRole + 3
    VideoIdRole = Qt.UserRole + 4
    DurationMsRole = Qt.UserRole + 5

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
        if role == self.ThumbnailRole:
            return item.get("thumbnail_url", "")
        if role == self.VideoIdRole:
            return item.get("videoId", "")
        if role == self.DurationMsRole:
            return item.get("duration_ms", 0)
        return None

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.TitleRole: b"title",
            self.ArtistRole: b"artist",
            self.ThumbnailRole: b"thumbnail",
            self.VideoIdRole: b"videoId",
            self.DurationMsRole: b"durationMs",
        }

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def get(self, row: int) -> dict | None:
        return self._items[row] if 0 <= row < len(self._items) else None


class HomeSectionsModel(QAbstractListModel):
    """Secciones con items agrupados (rails horizontales en QML)."""

    TitleRole = Qt.UserRole + 1
    ItemsRole = Qt.UserRole + 2

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
        if role == self.ItemsRole:
            return item.get("items", [])
        return None

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.TitleRole: b"sectionTitle",
            self.ItemsRole: b"items",
        }

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()


class HorizontalSectionModel(QAbstractListModel):

    TitleRole = Qt.UserRole + 1
    TypeRole = Qt.UserRole + 2       # "playlist" | "album" | "artist"
    ItemTitleRole = Qt.UserRole + 3
    SubtitleRole = Qt.UserRole + 4
    ThumbnailRole = Qt.UserRole + 5
    NavigateRole = Qt.UserRole + 6   # ruta de navegación
    IsDownloadedRole = Qt.UserRole + 7
    ShowHeaderRole = Qt.UserRole + 8  # primera card de cada sección

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
            return item.get("section_title", "")
        if role == self.TypeRole:
            return item.get("type", "")
        if role == self.ItemTitleRole:
            return item.get("item_title", "")
        if role == self.SubtitleRole:
            return item.get("subtitle", "")
        if role == self.ThumbnailRole:
            return item.get("thumbnail_url", "")
        if role == self.NavigateRole:
            return item.get("navigate", "")
        if role == self.IsDownloadedRole:
            return item.get("is_downloaded", False)
        if role == self.ShowHeaderRole:
            return item.get("show_header", False)
        return None

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.TitleRole: b"sectionTitle",
            self.TypeRole: b"itemType",
            self.ItemTitleRole: b"itemTitle",
            self.SubtitleRole: b"subtitle",
            self.ThumbnailRole: b"thumbnail",
            self.NavigateRole: b"navigate",
            self.IsDownloadedRole: b"isDownloaded",
            self.ShowHeaderRole: b"showHeader",
        }

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        prev_title: str | None = None
        for it in items:
            title = it.get("section_title", "")
            it["show_header"] = title != prev_title
            prev_title = title
        self._items = items
        self.endResetModel()


class SongGridModel(QAbstractListModel):
    """Modelo de canciones en grid (2 columnas)."""

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


class GenreModel(QAbstractListModel):
    """Modelo de botones de género."""

    NameRole = Qt.UserRole + 1
    QueryRole = Qt.UserRole + 2

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[tuple[str, str]] = [
            ("Rock", "rock"), ("Pop", "pop"), ("Reggaeton", "reggaeton"),
            ("Salsa", "salsa"), ("Clasica", "classical"), ("Electronica", "electronic"),
            ("Jazz", "jazz"), ("R&B", "r&b"), ("Reggae", "reggae"),
            ("Hip Hop", "hip hop"), ("Latina", "latin music"), ("Colombia", "colombian music"),
        ]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        name, query = self._items[index.row()]
        if role == self.NameRole:
            return name
        if role == self.QueryRole:
            return query
        return None

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.NameRole: b"name",
            self.QueryRole: b"query",
        }


# ── ViewModel principal ──────────────────────────────────────────────────

class HomeViewModel(QObject):
    """Puente Python → QML para la pantalla Inicio (isla QML).

    Expone los modelos a QML y re-emite las mismas señales que HomeScreen (QtWidgets).
    """

    loading_changed = Signal()
    greeting_changed = Signal()
    spotlight_changed = Signal()

    # Señales de contexto (mismas que HomeScreen QtWidgets)
    download_requested = Signal(str, str, str, str)
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    like_requested = Signal(str, object)
    add_to_playlist_requested = Signal(str, str)
    delete_download_requested = Signal(str)
    artist_clicked = Signal(str)
    album_clicked = Signal(str)
    play_requested = Signal(str, str, str, int, str)  # videoId, title, artist, duration_ms, thumb
    navigate_requested = Signal(str)  # navegación interna (playlist/artist/album)
    search_navigate = Signal(str)     # navegación a buscar con query

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._loading = True
        self._greeting = ""
        self._spotlight = SpotlightModel(self)
        self._spot_title = ""
        self._spot_subtitle = ""
        self._spot_thumbnail = ""
        self._spot_navigate = ""
        self._tiles = TileModel(self)
        self._horizontal = HorizontalSectionModel(self)
        self._sections = HomeSectionsModel(self)
        self._songs = SongGridModel(self)
        self._genres = GenreModel(self)

    # ── Properties ─────────────────────────────────────────────────────────

    @Property(QObject, constant=True)
    def spotlight(self) -> SpotlightModel:
        return self._spotlight

    @Property(QObject, constant=True)
    def tiles(self) -> TileModel:
        return self._tiles

    @Property(QObject, constant=True)
    def horizontal(self) -> HorizontalSectionModel:
        return self._horizontal

    @Property(QObject, constant=True)
    def sections(self) -> HomeSectionsModel:
        return self._sections

    @Property(QObject, constant=True)
    def songs(self) -> SongGridModel:
        return self._songs

    @Property(QObject, constant=True)
    def genres(self) -> GenreModel:
        return self._genres

    @Property(str, notify=greeting_changed)
    def greeting(self) -> str:
        return self._greeting

    @Property(bool, notify=loading_changed)
    def loading(self) -> bool:
        return self._loading

    # Spotlight como properties notificadas (los bindings de texto QML no se
    # re-evalúan con modelos constantes + métodos data() sin NOTIFY).
    @Property(bool, notify=spotlight_changed)
    def hasSpotlight(self) -> bool:
        return self._spot_title != ""

    @Property(str, notify=spotlight_changed)
    def spotTitle(self) -> str:
        return self._spot_title

    @Property(str, notify=spotlight_changed)
    def spotSubtitle(self) -> str:
        return self._spot_subtitle

    @Property(str, notify=spotlight_changed)
    def spotThumbnail(self) -> str:
        return self._spot_thumbnail

    @Property(str, notify=spotlight_changed)
    def spotNavigate(self) -> str:
        return self._spot_navigate

    # ── Mutators ───────────────────────────────────────────────────────────

    def set_loading(self, value: bool) -> None:
        if self._loading != value:
            self._loading = value
            self.loading_changed.emit()

    def set_greeting(self, value: str) -> None:
        if self._greeting != value:
            self._greeting = value
            self.greeting_changed.emit()

    def set_spotlight(self, items: list[dict]) -> None:
        self._spotlight.set_items(items)
        item = items[0] if items else {}
        self._spot_title = item.get("title", "")
        self._spot_subtitle = item.get("subtitle", "")
        self._spot_thumbnail = item.get("thumbnail_url", "")
        self._spot_navigate = item.get("navigate", "")
        self.spotlight_changed.emit()

    def set_tiles(self, items: list[dict]) -> None:
        self._tiles.set_items(items)

    def set_horizontal(self, items: list[dict]) -> None:
        self._horizontal.set_items(items)
        sections: dict[str, list] = {}
        for it in items:
            sections.setdefault(it.get("section_title", ""), []).append(it)
        self._sections.set_items(
            [{"title": t, "items": its} for t, its in sections.items() if t]
        )

    def set_songs(self, items: list[dict]) -> None:
        self._songs.set_items(items)

    # ── Slots called from QML ──────────────────────────────────────────────

    @Slot(int)
    def play_tile(self, index: int) -> None:
        item = self._tiles.get(index)
        if item is None:
            return
        self.play_requested.emit(
            item.get("videoId", ""), item.get("title", ""), item.get("artist", ""),
            item.get("duration_ms", 0), item.get("thumbnail_url", ""),
        )

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
    def tile_action(self, index: int, action: str) -> None:
        item = self._tiles.get(index)
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
    def navigate_genre(self, query: str) -> None:
        self.search_navigate.emit(f"search?query={query}")

    @Slot(str)
    def navigate(self, route: str) -> None:
        self.navigate_requested.emit(route)
