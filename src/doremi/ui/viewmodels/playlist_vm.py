from __future__ import annotations

import random

from PySide6.QtCore import (
    QAbstractListModel, Property, QModelIndex, QObject, Qt, Signal, Slot,
)


class PlaylistTrackModel(QAbstractListModel):
    """Tracks de una playlist. Igual que DetailTrackModel + rol setVideoId."""

    TitleRole = Qt.UserRole + 1
    ArtistRole = Qt.UserRole + 2
    DurationRole = Qt.UserRole + 3
    DurationMsRole = Qt.UserRole + 4
    ThumbnailRole = Qt.UserRole + 5
    VideoIdRole = Qt.UserRole + 6
    IsLikedRole = Qt.UserRole + 7
    IsDownloadedRole = Qt.UserRole + 8
    SetVideoIdRole = Qt.UserRole + 9

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
        if role == self.IsDownloadedRole:
            return item.get("is_downloaded", False)
        if role == self.SetVideoIdRole:
            return item.get("setVideoId", "")
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
            self.IsDownloadedRole: b"isDownloaded",
            self.SetVideoIdRole: b"setVideoId",
        }

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def get(self, row: int) -> dict | None:
        return self._items[row] if 0 <= row < len(self._items) else None

    def all_items(self) -> list[dict]:
        return list(self._items)


class PlaylistViewModel(QObject):
    """Puente Python → QML para la pantalla Playlist (isla QML).

    Cubre playlists remotas (YouTube Music) y locales (local_<pid>): estas
    últimas reproducen vía `play_local_requested(meta_list, start_index)`.
    """

    loading_changed = Signal()
    header_changed = Signal()
    dl_state_changed = Signal()

    # Mismas señales que PlaylistScreen (QtWidgets)
    download_requested = Signal(str, str, str, str)
    download_playlist_requested = Signal(str, str, str)  # playlist_id, title, thumbnail_url
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    add_to_playlist_requested = Signal(str, str)
    like_requested = Signal(str, object)
    delete_download_requested = Signal(str)
    play_queue_requested = Signal(list, int)       # queue dicts, index (remota)
    play_local_requested = Signal(list, int)       # meta dicts, start_index (local)
    remove_track_requested = Signal(str, str, str)  # video_id, set_video_id, title
    back_requested = Signal()

    DL_NONE = ""
    DL_PARTIAL = "partial"
    DL_FULL = "full"
    DL_ACTIVE = "active"

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tracks = PlaylistTrackModel(self)
        self._loading = True
        self._found = True
        self._playlist_id = ""
        self._title = ""
        self._author = ""
        self._thumbnail = ""
        self._track_count = 0
        self._downloaded_count = 0
        self._is_local = False
        self._is_fully = False
        self._local_meta: list[dict] = []
        self._dl_state = self.DL_NONE
        self._dl_text = ""
        self._dl_percent = 0

    # ── Properties ─────────────────────────────────────────────────────────

    @Property(QObject, constant=True)
    def tracks(self) -> PlaylistTrackModel:
        return self._tracks

    @Property(bool, notify=loading_changed)
    def loading(self) -> bool:
        return self._loading

    @Property(bool, notify=header_changed)
    def found(self) -> bool:
        return self._found

    @Property(str, notify=header_changed)
    def title(self) -> str:
        return self._title

    @Property(str, notify=header_changed)
    def meta(self) -> str:
        if self._author and self._track_count:
            return f"{self._author} • {self._track_count} canciones"
        return self._author or (f"{self._track_count} canciones" if self._track_count else "")

    @Property(str, notify=header_changed)
    def thumbnail(self) -> str:
        return self._thumbnail

    @Property(bool, notify=header_changed)
    def isLocal(self) -> bool:
        return self._is_local

    @Property(bool, notify=header_changed)
    def hasTracks(self) -> bool:
        return self._tracks.rowCount() > 0

    @Property(str, notify=dl_state_changed)
    def dlState(self) -> str:
        return self._dl_state

    @Property(str, notify=dl_state_changed)
    def dlText(self) -> str:
        return self._dl_text

    @Property(int, notify=dl_state_changed)
    def dlPercent(self) -> int:
        return self._dl_percent

    # ── Mutators (Python side) ─────────────────────────────────────────────

    def set_loading(self, value: bool) -> None:
        if self._loading != value:
            self._loading = value
            self.loading_changed.emit()

    def set_data(self, data: dict) -> None:
        self._found = bool(data.get("title"))
        self._playlist_id = data.get("playlist_id", "")
        self._title = data.get("title", "")
        self._author = data.get("author", "")
        self._thumbnail = data.get("thumbnail_url", "")
        self._track_count = data.get("track_count", 0)
        self._downloaded_count = data.get("downloaded_count", 0)
        self._is_local = bool(data.get("is_local", False))
        self._is_fully = bool(data.get("is_fully_downloaded", False))
        self._local_meta = list(data.get("local_meta", []))
        self._tracks.set_items(data.get("tracks", []))
        self.header_changed.emit()

    def set_download_state(self, state: str, percent: int = 0) -> None:
        if state == self.DL_FULL:
            text = ""
        elif state == self.DL_ACTIVE:
            text = f"Descargando… {percent}%"
        elif state == self.DL_PARTIAL:
            text = f"Descargar restantes ({self._downloaded_count}/{self._track_count})"
        else:
            text = "Descargar playlist"
        changed = (
            self._dl_state != state or self._dl_text != text or self._dl_percent != percent
        )
        self._dl_state, self._dl_text, self._dl_percent = state, text, percent
        if changed:
            self.dl_state_changed.emit()

    @Slot()
    def mark_downloader_feedback(self) -> None:
        self.set_download_state(self.DL_ACTIVE, 0)

    def refresh_counters(self, downloaded_count: int, fully: bool) -> None:
        self._downloaded_count = downloaded_count
        if fully:
            self.set_download_state(self.DL_FULL)
        elif self._dl_state != self.DL_ACTIVE:
            self.set_download_state(self.DL_PARTIAL if downloaded_count else self.DL_NONE)

    # ── Slots called from QML ──────────────────────────────────────────────

    @Slot()
    def play_all(self) -> None:
        if self._is_local:
            if self._local_meta:
                self.play_local_requested.emit(list(self._local_meta), 0)
            return
        if self._tracks.rowCount():
            self.play_queue_requested.emit(self._tracks.all_items(), 0)

    @Slot()
    def play_shuffle(self) -> None:
        if self._is_local:
            if self._local_meta:
                shuffled = list(self._local_meta)
                random.shuffle(shuffled)
                self.play_local_requested.emit(shuffled, 0)
            return
        items = self._tracks.all_items()
        if items:
            random.shuffle(items)
            self.play_queue_requested.emit(items, 0)

    @Slot(int)
    def play_at(self, index: int) -> None:
        if self._tracks.get(index) is None:
            return
        if self._is_local:
            self.play_local_requested.emit(list(self._local_meta), index)
            return
        self.play_queue_requested.emit(self._tracks.all_items(), index)

    @Slot(int, str)
    def track_action(self, index: int, action: str) -> None:
        item = self._tracks.get(index)
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
        elif action == "delete_download":
            self.delete_download_requested.emit(vid)
        elif action == "remove":
            set_id = item.get("setVideoId", "")
            if set_id and not self._is_local:
                self.remove_track_requested.emit(vid, set_id, title)

    @Slot()
    def download_playlist(self) -> None:
        self.download_playlist_requested.emit(
            self._playlist_id, self._title, self._thumbnail,
        )

    @Slot()
    def go_back(self) -> None:
        self.back_requested.emit()
