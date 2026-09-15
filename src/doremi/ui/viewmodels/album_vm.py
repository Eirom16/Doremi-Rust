from __future__ import annotations

import random

from PySide6.QtCore import (
    QAbstractListModel, Property, QModelIndex, QObject, Qt, Signal, Slot,
)


class DetailTrackModel(QAbstractListModel):
    """Tracks de un álbum/playlist. Compartido por las islas de detalle."""

    TitleRole = Qt.UserRole + 1
    ArtistRole = Qt.UserRole + 2
    DurationRole = Qt.UserRole + 3
    DurationMsRole = Qt.UserRole + 4
    ThumbnailRole = Qt.UserRole + 5
    VideoIdRole = Qt.UserRole + 6
    IsLikedRole = Qt.UserRole + 7
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
        }

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def get(self, row: int) -> dict | None:
        return self._items[row] if 0 <= row < len(self._items) else None

    def all_items(self) -> list[dict]:
        return list(self._items)


class AlbumViewModel(QObject):
    """Puente Python → QML para la pantalla Álbum (isla QML)."""

    loading_changed = Signal()
    header_changed = Signal()
    dl_state_changed = Signal()

    # Mismas señales que AlbumScreen (QtWidgets)
    download_requested = Signal(str, str, str, str)
    download_album_requested = Signal(str, str, str)  # browse_id, title, thumbnail_url
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    like_requested = Signal(str, object)
    add_to_playlist_requested = Signal(str, str)
    delete_download_requested = Signal(str)
    play_queue_requested = Signal(list, int)  # queue dicts, index
    back_requested = Signal()

    DL_NONE = ""            # sin descargas/counter
    DL_PARTIAL = "partial"  # descarga parcial
    DL_FULL = "full"        # todo descargado
    DL_ACTIVE = "active"    # descarga en curso

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tracks = DetailTrackModel(self)
        self._loading = True
        self._found = True
        self._browse_id = ""
        self._type = "ÁLBUM"
        self._title = ""
        self._meta = ""
        self._thumbnail = ""
        self._dl_state = self.DL_NONE
        self._dl_text = ""
        self._dl_percent = 0
        self._downloaded_count = 0
        self._track_count = 0

    # ── Properties ─────────────────────────────────────────────────────────

    @Property(QObject, constant=True)
    def tracks(self) -> DetailTrackModel:
        return self._tracks

    @Property(bool, notify=loading_changed)
    def loading(self) -> bool:
        return self._loading

    @Property(bool, notify=header_changed)
    def found(self) -> bool:
        return self._found

    @Property(str, notify=header_changed)
    def typeLabel(self) -> str:
        return self._type

    @Property(str, notify=header_changed)
    def title(self) -> str:
        return self._title

    @Property(str, notify=header_changed)
    def meta(self) -> str:
        return self._meta

    @Property(str, notify=header_changed)
    def thumbnail(self) -> str:
        return self._thumbnail

    @Property(str, notify=dl_state_changed)
    def dlState(self) -> str:
        return self._dl_state

    @Property(str, notify=dl_state_changed)
    def dlText(self) -> str:
        return self._dl_text

    @Property(int, notify=dl_state_changed)
    def dlPercent(self) -> int:
        return self._dl_percent

    @Property(bool, notify=header_changed)
    def hasTracks(self) -> bool:
        return self._tracks.rowCount() > 0

    # ── Mutators (Python side) ─────────────────────────────────────────────

    def set_loading(self, value: bool) -> None:
        if self._loading != value:
            self._loading = value
            self.loading_changed.emit()

    def set_data(self, data: dict) -> None:
        self._found = bool(data.get("title"))
        self._browse_id = data.get("browse_id", "")
        self._type = data.get("type", "ÁLBUM")
        self._title = data.get("title", "")
        self._meta = data.get("meta", "")
        self._thumbnail = data.get("thumbnail_url", "")
        self._tracks.set_items(data.get("tracks", []))
        self._downloaded_count = data.get("downloaded_count", 0)
        self._track_count = data.get("track_count", 0)
        self.header_changed.emit()

    def set_download_state(self, state: str, percent: int = 0) -> None:
        """Actualiza el bloque de descarga del header."""
        if state == self.DL_FULL:
            text = ""
        elif state == self.DL_ACTIVE:
            text = f"Descargando… {percent}%"
        elif state == self.DL_PARTIAL:
            text = f"Descargar restantes ({self._downloaded_count}/{self._track_count})"
        else:
            text = "Descargar álbum"
        changed = (
            self._dl_state != state or self._dl_text != text or self._dl_percent != percent
        )
        self._dl_state, self._dl_text, self._dl_percent = state, text, percent
        if changed:
            self.dl_state_changed.emit()

    @Slot()
    def mark_downloader_feedback(self) -> None:
        """Tras emitir download_album_requested: feedback inmediato en el header."""
        self.set_download_state(self.DL_ACTIVE, 0)

    def refresh_counters(self, downloaded_count: int, fully: bool) -> None:
        self._downloaded_count = downloaded_count
        if fully:
            self.set_download_state(self.DL_FULL)
        elif self._dl_state != self.DL_ACTIVE:
            self.set_download_state(self.DL_PARTIAL if downloaded_count else self.DL_NONE)

    # ── Queue helpers ──────────────────────────────────────────────────────

    def _queue_payload(self, start: int = 0) -> tuple[list, int]:
        items = self._tracks.all_items()
        return items, max(0, min(start, max(0, len(items) - 1)))

    # ── Slots called from QML ──────────────────────────────────────────────

    @Slot()
    def play_all(self) -> None:
        if not self._tracks.rowCount():
            return
        items, idx = self._queue_payload(0)
        self.play_queue_requested.emit(items, idx)

    @Slot()
    def play_shuffle(self) -> None:
        n = self._tracks.rowCount()
        if not n:
            return
        items = self._tracks.all_items()
        random.shuffle(items)
        self.play_queue_requested.emit(items, 0)

    @Slot(int)
    def play_at(self, index: int) -> None:
        if self._tracks.get(index) is None:
            return
        items, idx = self._queue_payload(index)
        self.play_queue_requested.emit(items, idx)

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

    @Slot()
    def download_album(self) -> None:
        self.download_album_requested.emit(
            self._browse_id, self._title, self._thumbnail,
        )

    @Slot()
    def go_back(self) -> None:
        self.back_requested.emit()
