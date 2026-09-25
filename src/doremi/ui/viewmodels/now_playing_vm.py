from __future__ import annotations

from doremi.utils.i18n import _

import re

from PySide6.QtCore import (
    QAbstractListModel, Property, QModelIndex, QObject, Qt, Signal, Slot,
)

_LRC_TS = re.compile(r"^((?:\[\d{1,}:\d{2}(?:\.\d+)?\])+)(.*)$")
_LRC_TAG = re.compile(r"\[(\d{1,}):(\d{2}(?:\.\d+)?)\]")


def parse_lyrics(lyrics) -> list[dict]:
    """Parsea texto/LRC a líneas normalizadas [{text, ts_ms}]. Igual que widgets."""
    if not lyrics:
        return []
    lines = lyrics.strip().split("\n") if isinstance(lyrics, str) else list(lyrics)
    out: list[dict] = []
    for raw in lines:
        clean = str(raw).strip()
        ts_ms = -1
        m = _LRC_TS.match(clean)
        if m:
            clean = m.group(2).strip()
            tag = _LRC_TAG.search(m.group(1))
            if tag:
                ts_ms = int((int(tag.group(1)) * 60 + float(tag.group(2))) * 1000)
        if not clean:
            if ts_ms != -1:
                clean = "♪"
            else:
                continue
        out.append({"text": clean, "ts_ms": ts_ms})
    if out and not any(l["ts_ms"] != -1 for l in out):
        # sin timestamps: modo estático (widget las activa todas)
        for l in out:
            l["ts_ms"] = -2
    return out


class NowPlayingQueueModel(QAbstractListModel):
    TitleRole = Qt.UserRole + 1
    ArtistRole = Qt.UserRole + 2
    DurationRole = Qt.UserRole + 3
    ThumbnailRole = Qt.UserRole + 4
    VideoIdRole = Qt.UserRole + 5
    IsLikedRole = Qt.UserRole + 6
    IsCurrentRole = Qt.UserRole + 7

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
        if role == self.ThumbnailRole:
            return item.get("thumbnail_url", "")
        if role == self.VideoIdRole:
            return item.get("videoId", "")
        if role == self.IsLikedRole:
            return item.get("is_liked", False)
        if role == self.IsCurrentRole:
            return item.get("is_current", False)
        return None

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.TitleRole: b"title", self.ArtistRole: b"artist",
            self.DurationRole: b"duration", self.ThumbnailRole: b"thumbnail",
            self.VideoIdRole: b"videoId", self.IsLikedRole: b"isLiked",
            self.IsCurrentRole: b"isCurrent",
        }

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def get(self, row: int) -> dict | None:
        return self._items[row] if 0 <= row < len(self._items) else None


class LyricsModel(QAbstractListModel):
    TextRole = Qt.UserRole + 1
    TsMsRole = Qt.UserRole + 2
    ActiveRole = Qt.UserRole + 3

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._lines: list[dict] = []
        self._active_index = -1

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._lines)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._lines):
            return None
        line = self._lines[index.row()]
        if role == self.TextRole:
            return line.get("text", "")
        if role == self.TsMsRole:
            return line.get("ts_ms", -1)
        if role == self.ActiveRole:
            return index.row() == self._active_index
        return None

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.TextRole: b"lineText",
            self.TsMsRole: b"tsMs",
            self.ActiveRole: b"active",
        }

    def set_lines(self, lines: list[dict]) -> None:
        self.beginResetModel()
        self._lines = lines
        self._active_index = -1
        self.endResetModel()

    def set_active(self, index: int) -> bool:
        if index == self._active_index:
            return False
        old, new = self._active_index, index
        self._active_index = index
        if 0 <= old < len(self._lines):
            idx = self.index(old, 0)
            self.dataChanged.emit(idx, idx, [self.ActiveRole])
        if 0 <= new < len(self._lines):
            idx = self.index(new, 0)
            self.dataChanged.emit(idx, idx, [self.ActiveRole])
        return True


class RelatedModel(QAbstractListModel):
    TitleRole = Qt.UserRole + 1
    ArtistRole = Qt.UserRole + 2
    DurationRole = Qt.UserRole + 3
    ThumbnailRole = Qt.UserRole + 4
    VideoIdRole = Qt.UserRole + 5

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
        if role == self.ThumbnailRole:
            return item.get("thumbnail_url", "")
        if role == self.VideoIdRole:
            return item.get("videoId", "")
        return None

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.TitleRole: b"title", self.ArtistRole: b"artist",
            self.DurationRole: b"duration", self.ThumbnailRole: b"thumbnail",
            self.VideoIdRole: b"videoId",
        }

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def get(self, row: int) -> dict | None:
        return self._items[row] if 0 <= row < len(self._items) else None


class NowPlayingViewModel(QObject):
    """Puente Python → QML para Now Playing (isla QML).

    El wrapper traduce las llamadas de los controllers (update_track_info,
    update_state, update_position, set_lyrics, set_related, set_liked_state)
    a propiedades; las señales se re-emiten tal cual las de QtWidgets.
    """

    track_changed = Signal()
    playing_changed = Signal()
    like_changed = Signal()
    position_changed = Signal()
    control_changed = Signal()      # shuffle / repeat
    lyrics_style_changed = Signal()
    lyric_index_changed = Signal()
    tab_changed = Signal()
    details_changed = Signal()
    media_mode_changed = Signal()
    video_changed = Signal()

    # Intenciones de la UI (el wrapper las enruta a MainWindow)
    toggle_play_requested = Signal()
    prev_requested = Signal()
    next_requested = Signal()
    seek_ms_requested = Signal(int)
    shuffle_toggled = Signal()
    repeat_cycled = Signal()
    minimize_requested = Signal()
    artist_pressed = Signal(str)
    queue_play_at = Signal(int)
    queue_move_requested = Signal(int, int)
    copy_link_requested = Signal(str)
    details_requested = Signal(str)
    video_requested = Signal(str)
    video_closed_requested = Signal()

    # Mismas señales que NowPlayingScreen (QtWidgets)
    download_requested = Signal(str, str, str, str)
    play_next_requested = Signal(str, str, str, str)
    add_to_queue_requested = Signal(str, str, str, str)
    add_to_playlist_requested = Signal(str, str)
    like_requested = Signal(str, object)
    delete_download_requested = Signal(str)
    artist_clicked = Signal(str)
    album_clicked = Signal(str)
    play_related_requested = Signal(str, str, str, int, str)

    TABS = ("queue", "lyrics", "related")

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._queue_model = NowPlayingQueueModel(self)
        self._lyrics = LyricsModel(self)
        self._related = RelatedModel(self)
        self._video_player = None
        self._video_sink = None

        self._title = "No hay canción"
        self._artist_name = ""
        self._album = ""
        self._artwork_url = ""
        self._video_id = ""
        self._playing = False
        self._liked = False
        self._position_ms = 0
        self._duration_ms = 0
        self._shuffle = False
        self._repeat = "off"
        self._tab = "queue"
        # estilo de letras (desde settings.subtitles)
        self._lyric_font_size = 26
        self._lyric_align = "center"
        self._lyric_glow = True
        self._lyric_auto_scroll = True
        self._lyric_delay_ms = 0
        self._details_loading = False
        self._detail_artist = ""
        self._detail_album = ""
        self._detail_uploader = ""
        self._detail_release_date = ""
        self._detail_license = ""
        self._details_error = ""
        self._media_mode = "audio"
        self._video_stream_url = ""
        self._video_loading = False
        self._video_error = ""

    # ── Properties ─────────────────────────────────────────────────────────

    @Property(QObject, constant=True)
    def queueModel(self):
        return self._queue_model

    @Property(QObject, constant=True)
    def lyrics(self):
        return self._lyrics

    @Property(QObject, constant=True)
    def related(self):
        return self._related

    @Property(str, notify=track_changed)
    def trackTitle(self) -> str:
        return self._title

    @Property(str, notify=track_changed)
    def artistName(self) -> str:
        return self._artist_name

    @Property(str, notify=track_changed)
    def albumName(self) -> str:
        return self._album

    @Property(str, notify=track_changed)
    def artworkUrl(self) -> str:
        return self._artwork_url

    @Property(str, notify=track_changed)
    def videoId(self) -> str:
        return self._video_id

    @Property(bool, notify=playing_changed)
    def playing(self) -> bool:
        return self._playing

    @Property(bool, notify=like_changed)
    def liked(self) -> bool:
        return self._liked

    @Property(float, notify=position_changed)
    def progress(self) -> float:
        if self._duration_ms <= 0:
            return 0.0
        return min(1.0, max(0.0, self._position_ms / self._duration_ms))

    @Property(str, notify=position_changed)
    def timeCurrent(self) -> str:
        return _fmt_ms(self._position_ms)

    @Property(str, notify=position_changed)
    def timeTotal(self) -> str:
        return _fmt_ms(self._duration_ms)

    @Property(bool, notify=control_changed)
    def shuffle(self) -> bool:
        return self._shuffle

    @Property(str, notify=control_changed)
    def repeatMode(self) -> str:
        return self._repeat

    @Property(str, notify=tab_changed)
    def tab(self) -> str:
        return self._tab

    @Property(int, notify=lyrics_style_changed)
    def lyricFontSize(self) -> int:
        return self._lyric_font_size

    @Property(str, notify=lyrics_style_changed)
    def lyricAlign(self) -> str:
        return self._lyric_align

    @Property(bool, notify=lyrics_style_changed)
    def lyricGlow(self) -> bool:
        return self._lyric_glow

    @Property(bool, notify=lyrics_style_changed)
    def lyricAutoScroll(self) -> bool:
        return self._lyric_auto_scroll

    @Property(bool, notify=lyric_index_changed)
    def hasLyrics(self) -> bool:
        return self._lyrics.rowCount() > 0

    @Property(bool, notify=details_changed)
    def detailsLoading(self) -> bool:
        return self._details_loading

    @Property(str, notify=details_changed)
    def detailArtist(self) -> str:
        return self._detail_artist

    @Property(str, notify=details_changed)
    def detailAlbum(self) -> str:
        return self._detail_album

    @Property(str, notify=details_changed)
    def detailUploader(self) -> str:
        return self._detail_uploader

    @Property(str, notify=details_changed)
    def detailReleaseDate(self) -> str:
        return self._detail_release_date

    @Property(str, notify=details_changed)
    def detailLicense(self) -> str:
        return self._detail_license

    @Property(str, notify=details_changed)
    def detailsError(self) -> str:
        return self._details_error

    @Property(str, notify=media_mode_changed)
    def mediaMode(self) -> str:
        return self._media_mode

    @Property(str, notify=video_changed)
    def videoStreamUrl(self) -> str:
        return self._video_stream_url

    @Property(QObject, notify=video_changed)
    def videoPlayer(self):
        return self._video_player

    @Property(bool, notify=video_changed)
    def videoLoading(self) -> bool:
        return self._video_loading

    @Property(str, notify=video_changed)
    def videoError(self) -> str:
        return self._video_error

    @Property(str, constant=True)
    def videoRetryText(self) -> str:
        return _("Reintentar")

    def set_video_player(self, player) -> None:
        self._video_player = player
        if self._video_sink is not None:
            player.setVideoSink(self._video_sink)
        self.video_changed.emit()

    @Slot(QObject)
    def setVideoSink(self, sink) -> None:
        self._video_sink = sink
        if self._video_player is not None:
            self._video_player.setVideoSink(sink)

    @Property(int, notify=position_changed)
    def positionMs(self) -> int:
        return self._position_ms

    # ── Mutators llamados por el wrapper (paridad con widgets) ────────────

    def set_track_info(self, title: str, artist: str, thumbnail_url: str,
                       album: str = "", video_id: str = "") -> None:
        self._title = title or "No hay canción"
        self._artist_name = artist or ""
        self._artwork_url = thumbnail_url or ""
        self._album = album or ""
        self._video_id = video_id or ""
        self.track_changed.emit()

    def set_artwork(self, artwork_url: str) -> None:
        """Actualiza la carátula ya resuelta por la caché local."""
        if self._artwork_url != artwork_url:
            self._artwork_url = artwork_url
            self.track_changed.emit()

    def set_track_details(self, details: dict) -> None:
        self._details_loading = False
        self._detail_artist = str(details.get("artist", "") or "")
        self._detail_album = str(details.get("album", "") or "")
        self._detail_uploader = str(details.get("uploader", "") or "")
        self._detail_release_date = str(details.get("release_date", "") or "")
        self._detail_license = str(details.get("license", "") or "")
        self._details_error = ""
        self.details_changed.emit()

    def set_details_error(self, message: str) -> None:
        self._details_loading = False
        self._details_error = message
        self.details_changed.emit()

    def begin_video_loading(self) -> None:
        self._video_stream_url = ""
        self._video_loading = True
        self._video_error = ""
        self.video_changed.emit()

    def set_video_stream(self, stream_url: str) -> None:
        self._video_stream_url = stream_url or ""
        self._video_loading = False
        self._video_error = "" if stream_url else _("No se pudo cargar el videoclip.")
        self.video_changed.emit()

    def set_video_error(self, message: str) -> None:
        self._video_stream_url = ""
        self._video_loading = False
        self._video_error = message or _("No se pudo reproducir el videoclip.")
        self.video_changed.emit()

    def clear_video(self) -> None:
        if self._video_stream_url or self._video_loading or self._video_error:
            self._video_stream_url = ""
            self._video_loading = False
            self._video_error = ""
            self.video_changed.emit()

    def set_playing(self, playing: bool) -> None:
        if self._playing != playing:
            self._playing = playing
            self.playing_changed.emit()

    def set_liked(self, liked: bool) -> None:
        if self._liked != liked:
            self._liked = liked
            self.like_changed.emit()

    def set_position(self, position_ms: int, duration_ms: int) -> None:
        self._position_ms = position_ms
        self._duration_ms = duration_ms
        self.position_changed.emit()
        self._update_active_lyric()

    def set_shuffle_repeat(self, shuffle: bool, repeat_mode: str) -> None:
        if shuffle != self._shuffle or repeat_mode != self._repeat:
            self._shuffle, self._repeat = shuffle, repeat_mode
            self.control_changed.emit()

    def set_lyrics_loading(self) -> None:
        self._lyrics.set_lines([])
        self.lyric_index_changed.emit()

    def set_lyrics(self, data) -> None:
        self._lyrics.set_lines(parse_lyrics(data))
        self.lyric_index_changed.emit()

    def set_related(self, tracks: list[dict]) -> None:
        self._related.set_items(tracks)

    def set_queue(self, items: list, liked_ids: set) -> None:
        from doremi.utils.time_utils import format_duration_short
        rows = []
        for it in items:
            vid = getattr(it, "video_id", "") or ""
            dur_ms = getattr(it, "duration_ms", 0) or 0
            rows.append({
                "title": getattr(it, "title", "") or "",
                "artist": getattr(it, "artist", "") or "",
                "duration": format_duration_short(dur_ms) if dur_ms else "",
                "thumbnail_url": getattr(it, "thumbnail_url", "") or "",
                "videoId": vid,
                "is_liked": vid in liked_ids,
                "is_current": vid == self._video_id,
            })
        self._queue_model.set_items(rows)

    def set_lyrics_style(self, font_size: int, alignment: str, glow: bool,
                         auto_scroll: bool, delay_ms: int) -> None:
        self._lyric_font_size = int(font_size)
        self._lyric_align = alignment
        self._lyric_glow = bool(glow)
        self._lyric_auto_scroll = bool(auto_scroll)
        self._lyric_delay_ms = int(delay_ms)
        self.lyrics_style_changed.emit()

    def _update_active_lyric(self) -> None:
        adjusted = self._position_ms + 400 + self._lyric_delay_ms
        active = -1
        for i in range(self._lyrics.rowCount()):
            ts = self._lyrics._lines[i].get("ts_ms", -1)
            if ts == -2:  # modo estático: no resaltar nada especial
                continue
            if ts != -1 and adjusted >= ts:
                active = i
        if self._lyrics.set_active(active):
            self.lyric_index_changed.emit()

    # ── Slots called from QML ──────────────────────────────────────────────

    @Slot()
    def toggle_play(self) -> None:
        self.toggle_play_requested.emit()

    @Slot()
    def prev(self) -> None:
        self.prev_requested.emit()

    @Slot()
    def next(self) -> None:
        self.next_requested.emit()

    @Slot(float)
    def seek(self, fraction: float) -> None:
        if self._duration_ms > 0:
            self.seek_ms_requested.emit(int(max(0.0, min(1.0, fraction)) * self._duration_ms))

    @Slot()
    def toggle_shuffle(self) -> None:
        self.shuffle_toggled.emit()

    @Slot()
    def cycle_repeat(self) -> None:
        self.repeat_cycled.emit()

    @Slot()
    def minimize(self) -> None:
        self.minimize_requested.emit()

    @Slot()
    def press_artist(self) -> None:
        if self._artist_name:
            self.artist_pressed.emit(self._artist_name)
            self.artist_clicked.emit(self._artist_name)

    @Slot(int)
    def play_queue_index(self, index: int) -> None:
        if 0 <= index < self._queue_model.rowCount():
            self.queue_play_at.emit(index)

    @Slot(int, str)
    def move_queue_item(self, index: int, direction: str) -> None:
        target = index - 1 if direction == "up" else index + 1
        if 0 <= index < self._queue_model.rowCount() and 0 <= target < self._queue_model.rowCount():
            self.queue_move_requested.emit(index, target)

    @Slot(str)
    def set_tab(self, tab: str) -> None:
        if tab in self.TABS and tab != self._tab:
            self._tab = tab
            self.tab_changed.emit()

    @Property(str, notify=like_changed)
    def favoriteActionText(self) -> str:
        return _("Quitar de Favoritas") if self._liked else _("Añadir a Favoritas")

    @Slot()
    def toggle_like_current(self) -> None:
        if not self._video_id:
            return
        self.like_requested.emit(self._video_id, None)

    @Slot(str)
    def current_track_action(self, action: str) -> None:
        if not self._video_id:
            return
        vid, title, artist, thumb = self._video_id, self._title, self._artist_name, self._artwork_url
        if action == "play_next":
            self.play_next_requested.emit(vid, title, artist, thumb)
        elif action == "add_to_queue":
            self.add_to_queue_requested.emit(vid, title, artist, thumb)
        elif action == "add_to_playlist":
            self.add_to_playlist_requested.emit(vid, title)
        elif action == "download":
            self.download_requested.emit(vid, title, artist, thumb)
        elif action == "go_artist" and artist:
            self.artist_clicked.emit(artist)
        elif action == "go_album" and self._album:
            self.album_clicked.emit(self._album)
        elif action == "copy_link":
            self.copy_link_requested.emit(vid)

    @Slot()
    def request_track_details(self) -> None:
        if not self._video_id:
            return
        self._details_loading = True
        self._details_error = ""
        self.details_changed.emit()
        self.details_requested.emit(self._video_id)

    @Slot()
    def request_video_clip(self) -> None:
        """Solicita el stream visual asociado sin alterar la cola de audio."""
        if not self._video_id:
            return
        if self._media_mode != "video":
            self._media_mode = "video"
            self.media_mode_changed.emit()
        self.video_requested.emit(self._video_id)

    @Slot(str)
    def report_video_error(self, message: str) -> None:
        if self._media_mode == "video":
            self.set_video_error(message)

    @Slot(str)
    def set_media_mode(self, mode: str) -> None:
        if mode not in ("audio", "video") or mode == self._media_mode:
            return
        self._media_mode = mode
        self.media_mode_changed.emit()
        if mode == "video":
            self.request_video_clip()
        else:
            self.video_closed_requested.emit()

    @Slot(int, str)
    def queue_action(self, index: int, action: str) -> None:
        item = self._queue_model.get(index)
        if item is None:
            return
        vid = item.get("videoId", "")
        title = item.get("title", "")
        artist = item.get("artist", "")
        thumb = item.get("thumbnail_url", "")
        if action == "play":
            self.play_queue_index(index)
        elif action == "play_next":
            self.play_next_requested.emit(vid, title, artist, thumb)
        elif action == "add_to_queue":
            self.add_to_queue_requested.emit(vid, title, artist, thumb)
        elif action == "like":
            self.like_requested.emit(vid, None)
        elif action == "add_to_playlist":
            self.add_to_playlist_requested.emit(vid, thumb)
        elif action == "download":
            self.download_requested.emit(vid, title, artist, thumb)
        elif action == "delete_download":
            self.delete_download_requested.emit(vid)
        elif action == "go_artist" and artist:
            self.artist_clicked.emit(artist)

    @Slot(int, str)
    def related_action(self, index: int, action: str) -> None:
        item = self._related.get(index)
        if item is None:
            return
        if action == "play":
            self.play_related_requested.emit(
                item.get("videoId", ""), item.get("title", ""), item.get("artist", ""),
                0, item.get("thumbnail_url", ""),
            )
            return
        vid = item.get("videoId", "")
        title = item.get("title", "")
        artist = item.get("artist", "")
        thumb = item.get("thumbnail_url", "")
        if action == "play_next":
            self.play_next_requested.emit(vid, title, artist, thumb)
        elif action == "add_to_queue":
            self.add_to_queue_requested.emit(vid, title, artist, thumb)
        elif action == "like":
            self.like_requested.emit(vid, None)
        elif action == "add_to_playlist":
            self.add_to_playlist_requested.emit(vid, thumb)
        elif action == "download":
            self.download_requested.emit(vid, title, artist, thumb)
        elif action == "go_artist" and artist:
            self.artist_clicked.emit(artist)


def _fmt_ms(ms: int) -> str:
    if not ms or ms <= 0:
        return "0:00"
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"
