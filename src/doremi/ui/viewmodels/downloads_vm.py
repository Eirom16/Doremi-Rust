from __future__ import annotations

from PySide6.QtCore import (
    QAbstractListModel, Property, QModelIndex, QObject, Qt, Signal, Slot,
)


class DownloadSongModel(QAbstractListModel):
    """Canciones descargadas + tareas activas. Soporta updates por video_id."""

    VideoIdRole = Qt.UserRole + 1
    TitleRole = Qt.UserRole + 2
    ArtistRole = Qt.UserRole + 3
    PlaylistTitleRole = Qt.UserRole + 4
    ThumbnailRole = Qt.UserRole + 5
    StatusRole = Qt.UserRole + 6      # queued|downloading|completed|error|paused
    ProgressRole = Qt.UserRole + 7    # 0-100
    SpeedRole = Qt.UserRole + 8
    IsLikedRole = Qt.UserRole + 9
    SelectedRole = Qt.UserRole + 10

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
            return item.get("videoId", "")
        if role == self.TitleRole:
            return item.get("title", "")
        if role == self.ArtistRole:
            return item.get("artist", "")
        if role == self.PlaylistTitleRole:
            return item.get("playlist_title", "")
        if role == self.ThumbnailRole:
            return item.get("thumbnail_url", "")
        if role == self.StatusRole:
            return item.get("status", "")
        if role == self.ProgressRole:
            return item.get("progress", 0.0)
        if role == self.SpeedRole:
            return item.get("speed", "")
        if role == self.IsLikedRole:
            return item.get("is_liked", False)
        if role == self.SelectedRole:
            return item.get("selected", False)
        return None

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.VideoIdRole: b"videoId",
            self.TitleRole: b"title",
            self.ArtistRole: b"artist",
            self.PlaylistTitleRole: b"playlistTitle",
            self.ThumbnailRole: b"thumbnail",
            self.StatusRole: b"status",
            self.ProgressRole: b"progress",
            self.SpeedRole: b"speed",
            self.IsLikedRole: b"isLiked",
            self.SelectedRole: b"selected",
        }

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def get(self, row: int) -> dict | None:
        return self._items[row] if 0 <= row < len(self._items) else None

    def find_row(self, video_id: str) -> int:
        for i, it in enumerate(self._items):
            if it.get("videoId") == video_id:
                return i
        return -1

    def update_item(self, video_id: str, **fields) -> bool:
        row = self.find_row(video_id)
        if row < 0:
            return False
        self._items[row].update(fields)
        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx)
        return True

    def prepend_item(self, item: dict) -> None:
        self.beginInsertRows(QModelIndex(), 0, 0)
        self._items.insert(0, item)
        self.endInsertRows()

    def set_all_selected(self, selected: bool) -> None:
        changed = False
        for it in self._items:
            if it.get("selected", False) != selected:
                it["selected"] = selected
                changed = True
        if changed and self._items:
            self.dataChanged.emit(
                self.index(0, 0), self.index(len(self._items) - 1, 0),
                [self.SelectedRole],
            )


class DownloadGroupModel(QAbstractListModel):
    """Grupos (playlists/álbumes) de descargas."""

    PlaylistIdRole = Qt.UserRole + 1
    TitleRole = Qt.UserRole + 2
    SubtitleRole = Qt.UserRole + 3
    ThumbnailRole = Qt.UserRole + 4
    NavigateRole = Qt.UserRole + 5
    SelectedRole = Qt.UserRole + 6

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[dict] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        item = self._items[index.row()]
        if role == self.PlaylistIdRole:
            return item.get("playlist_id", "")
        if role == self.TitleRole:
            return item.get("title", "")
        if role == self.SubtitleRole:
            return item.get("subtitle", "")
        if role == self.ThumbnailRole:
            return item.get("thumbnail_url", "")
        if role == self.NavigateRole:
            return item.get("navigate", "")
        if role == self.SelectedRole:
            return item.get("selected", False)
        return None

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.PlaylistIdRole: b"playlistId",
            self.TitleRole: b"title",
            self.SubtitleRole: b"subtitle",
            self.ThumbnailRole: b"thumbnail",
            self.NavigateRole: b"navigate",
            self.SelectedRole: b"selected",
        }

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def get(self, row: int) -> dict | None:
        return self._items[row] if 0 <= row < len(self._items) else None

    def set_all_selected(self, selected: bool) -> None:
        changed = False
        for it in self._items:
            if it.get("selected", False) != selected:
                it["selected"] = selected
                changed = True
        if changed and self._items:
            self.dataChanged.emit(
                self.index(0, 0), self.index(len(self._items) - 1, 0),
                [self.SelectedRole],
            )


class DownloadsViewModel(QObject):
    """Puente Python → QML para la pantalla Descargas (isla QML).

    Mismas señales que DownloadsScreen (QtWidgets). La selección vive en los
    modelos (rol `selected`) y los borrados batch se delegan al wrapper vía
    `batch_delete_requested`.
    """

    loading_changed = Signal()
    tab_changed = Signal()
    status_filter_changed = Signal()
    selection_mode_changed = Signal()
    selected_count_changed = Signal()

    # Mismas señales que DownloadsScreen (QtWidgets)
    like_requested = Signal(str, object)
    delete_download_requested = Signal(str)
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    add_to_playlist_requested = Signal(str, str)
    play_local_requested = Signal(str, dict)      # file_path, metadata
    navigate_requested = Signal(str)
    batch_delete_requested = Signal(list, bool)   # ids, es_grupo

    TABS = ("songs", "albums", "playlists")
    STATUS_FILTERS = ("all", "completed", "active", "error")

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._songs = DownloadSongModel(self)
        self._groups = DownloadGroupModel(self)
        self._tab = "songs"
        self._status_filter = "all"
        self._loading = False
        self._selection_mode = False

    # ── Properties ─────────────────────────────────────────────────────────

    @Property(QObject, constant=True)
    def songs(self) -> DownloadSongModel:
        return self._songs

    @Property(QObject, constant=True)
    def groups(self) -> DownloadGroupModel:
        return self._groups

    @Property(str, notify=tab_changed)
    def tab(self) -> str:
        return self._tab

    @Property(str, notify=status_filter_changed)
    def statusFilter(self) -> str:
        return self._status_filter

    @Property(bool, notify=loading_changed)
    def loading(self) -> bool:
        return self._loading

    @Property(bool, notify=selection_mode_changed)
    def selectionMode(self) -> bool:
        return self._selection_mode

    @Property(int, notify=selected_count_changed)
    def selectedCount(self) -> int:
        model = self._songs if self._tab == "songs" else self._groups
        return sum(1 for i in range(model.rowCount())
                   if (model.get(i) or {}).get("selected"))

    # ── Mutators (Python side) ─────────────────────────────────────────────

    def set_loading(self, value: bool) -> None:
        if self._loading != value:
            self._loading = value
            self.loading_changed.emit()

    def set_songs(self, items: list[dict]) -> None:
        self._songs.set_items(items)
        self.selected_count_changed.emit()

    def set_groups(self, items: list[dict]) -> None:
        self._groups.set_items(items)
        self.selected_count_changed.emit()

    # ── Slots called from QML ──────────────────────────────────────────────

    @Slot(str)
    def set_tab(self, tab: str) -> None:
        if tab in self.TABS and tab != self._tab:
            self._tab = tab
            self.tab_changed.emit()

    @Slot(str)
    def set_status_filter(self, value: str) -> None:
        if value in self.STATUS_FILTERS and value != self._status_filter:
            self._status_filter = value
            self.status_filter_changed.emit()

    @Slot()
    def toggle_selection_mode(self) -> None:
        self._selection_mode = not self._selection_mode
        if not self._selection_mode:
            self._songs.set_all_selected(False)
            self._groups.set_all_selected(False)
            self.selected_count_changed.emit()
        self.selection_mode_changed.emit()

    @Slot(int)
    def toggle_item_selected(self, index: int) -> None:
        item = self._songs.get(index)
        if item is None:
            return
        self._songs.update_item(item["videoId"], selected=not item.get("selected", False))
        self.selected_count_changed.emit()

    @Slot(int)
    def toggle_group_selected(self, index: int) -> None:
        item = self._groups.get(index)
        if item is None:
            return
        row = index
        item["selected"] = not item.get("selected", False)
        idx = self._groups.index(row, 0)
        self._groups.dataChanged.emit(idx, idx)
        self.selected_count_changed.emit()

    @Slot()
    def select_all(self) -> None:
        model = self._songs if self._tab == "songs" else self._groups
        all_sel = model.rowCount() > 0 and all(
            (model.get(i) or {}).get("selected") for i in range(model.rowCount())
        )
        model.set_all_selected(not all_sel)
        self.selected_count_changed.emit()

    @Slot()
    def delete_selected(self) -> None:
        is_group = self._tab in ("albums", "playlists")
        model = self._groups if is_group else self._songs
        key = "playlist_id" if is_group else "videoId"
        ids = [
            model.get(i)[key]
            for i in range(model.rowCount())
            if (model.get(i) or {}).get("selected")
        ]
        if ids:
            self.batch_delete_requested.emit(ids, is_group)

    @Slot()
    def delete_all(self) -> None:
        # ids vacíos = todos los del tab actual (lo resuelve el wrapper)
        self.batch_delete_requested.emit([], self._tab in ("albums", "playlists"))

    @Slot(int)
    def play_at(self, index: int) -> None:
        item = self._songs.get(index)
        if item is None or item.get("status") != "completed":
            return
        self.play_local_requested.emit(item.get("file_path", ""), {
            "video_id": item.get("videoId", ""),
            "title": item.get("title", ""),
            "artist": item.get("artist", ""),
            "thumbnail_url": item.get("thumbnail_url", ""),
        })

    @Slot(int, str)
    def item_action(self, index: int, action: str) -> None:
        item = self._songs.get(index)
        if item is None:
            return
        vid = item.get("videoId", "")
        title = item.get("title", "")
        artist = item.get("artist", "")
        thumb = item.get("thumbnail_url", "")
        if action == "play_next":
            self.play_next_requested.emit(vid, title, artist, thumb)
        elif action == "add_to_queue":
            self.add_to_queue_requested.emit(vid, title, artist, thumb)
        elif action == "add_to_playlist":
            self.add_to_playlist_requested.emit(vid, title)
        elif action == "delete":
            self.delete_download_requested.emit(vid)
        elif action == "like":
            self.like_requested.emit(vid, None)

    @Slot(int)
    def group_navigate(self, index: int) -> None:
        item = self._groups.get(index)
        if item is None:
            return
        route = item.get("navigate", "")
        if route:
            self.navigate_requested.emit(route)

    # ── Live updates desde DownloadManager ─────────────────────────────────

    def upsert_task(self, item: dict) -> None:
        """Inserta al inicio o actualiza la fila de una tarea activa."""
        if self._songs.find_row(item.get("videoId", "")) >= 0:
            self._songs.update_item(item["videoId"], **item)
        else:
            self._songs.prepend_item(item)

    def update_progress(self, video_id: str, percent: float, speed: str) -> None:
        self._songs.update_item(video_id, progress=percent, speed=speed, status="downloading")

    def update_status(self, video_id: str, status: str) -> None:
        self._songs.update_item(video_id, status=status)
