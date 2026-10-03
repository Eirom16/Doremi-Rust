"""Desktop library interactions and a QML playlist picker."""
import asyncio
import json
from urllib.parse import parse_qs, urlsplit

from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl
from loguru import logger

from doremi.db.local_library_repository import LocalLibraryRepository
from doremi.db.repository import SongRepository
from doremi.services.experience_events import events


class DesktopController(QObject):
    changed = Signal()
    opened = Signal()
    closed = Signal()

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self._items = []
        self._error = ""
        self._busy = False
        self._video_id = ""
        self._title = ""
        self._metadata = {}
        self._picker_generation = 0

    @Property("QVariantList", notify=changed)
    def playlists(self):
        return self._items

    @Property(str, notify=changed)
    def errorText(self):
        return self._error

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    async def show_picker(self, video_id, title, metadata=None):
        self._picker_generation += 1
        generation = self._picker_generation
        self._video_id, self._title = video_id, title
        self._metadata = dict(metadata or {})
        self._error = ""
        self._busy = True
        self.changed.emit()
        self.opened.emit()
        try:
            items = await LocalLibraryRepository().playlists()
            if not video_id.startswith("local:") and self.window.yt.is_authenticated:
                remote = await self.window.yt.get_library_playlists()
                items += [dict(id=p["playlistId"], title=p.get("title", ""), subtitle="YouTube Music") for p in remote if p.get("playlistId")]
            if generation == self._picker_generation:
                self._items = items
        except Exception as exc:
            logger.warning(f"Playlist picker: {exc}")
            if generation == self._picker_generation:
                self._error = "No se pudieron cargar las playlists"
        finally:
            if generation == self._picker_generation:
                self._busy = False
                self.changed.emit()

    async def _append(self, identity, video_id, title, metadata=None):
        if identity.startswith("local-list:"):
            repo = SongRepository()
            if not await repo.get_song(video_id):
                from doremi.ui.controllers.track_action_data import song_fields
                fields = song_fields(metadata or {})
                fields["title"] = fields["title"] or title
                await repo.upsert_song(video_id=video_id, **fields)
            await LocalLibraryRepository().append(identity, [video_id])
            events.changed.emit()
            events.collections_changed.emit()
        elif not video_id.startswith("local:") and self.window.yt.is_authenticated:
            response = await self.window.yt.add_playlist_items(identity, [video_id])
            if not response or not (response.get("status") == "STATUS_SUCCEEDED" or "playlistItemId" in response):
                raise RuntimeError("YouTube Music rechazó el cambio")
        else:
            raise ValueError("Los archivos locales necesitan una playlist local")

    @Slot(str)
    def choose(self, identity):
        if self._busy or not any(p["id"] == identity for p in self._items):
            return
        if not self._video_id:
            self.closed.emit()
            self.window._navigate_to("playlist?id=" + identity)
            return
        self._busy = True
        self.changed.emit()
        video_id, title, metadata = self._video_id, self._title, dict(self._metadata)
        async def add():
            try:
                await self._append(identity, video_id, title, metadata)
                self.closed.emit()
                self.window.show_notification("Añadida a la playlist", "success")
            except Exception as exc:
                self._error = str(exc)
            finally:
                self._busy = False
                self.changed.emit()
        self.window._run_async(add())

    @Slot()
    def new_playlist(self):
        self.window._run_async(self.show_picker("", ""))

    @Slot(str)
    def create(self, title):
        if self._busy or not title.strip():
            return
        self._busy = True
        self.changed.emit()
        video_id, track_title, metadata = self._video_id, self._title, dict(self._metadata)
        async def create():
            try:
                identity = await LocalLibraryRepository().create_playlist(title)
                self._items = await LocalLibraryRepository().playlists()
                events.changed.emit()
                events.collections_changed.emit()
                if video_id:
                    await self._append(identity, video_id, track_title, metadata)
                    self.closed.emit()
                    self.window.show_notification("Añadida a la playlist", "success")
                else:
                    self.closed.emit()
                    self.window._navigate_to("playlist?id=" + identity)
            except Exception as exc:
                self._error = str(exc)
            finally:
                self._busy = False
                self.changed.emit()
        self.window._run_async(create())

    @Slot("QVariantList")
    def import_files(self, urls):
        paths = [QUrl(url).toLocalFile() for url in urls if QUrl(url).isLocalFile()]
        async def run():
            try:
                count = await LocalLibraryRepository().import_files(paths)
                events.changed.emit()
                self.window.library_screen.force_reload()
                self.window.show_notification(f"{count} archivos añadidos a tu biblioteca", "success")
            except Exception as exc:
                logger.warning(f"Local import: {exc}")
                self.window.show_notification("No se pudieron importar los archivos", "error")
        self.window._run_async(run())

    @Slot(str)
    def copy_track_link(self, video_id):
        if not video_id or video_id == "local" or video_id.startswith("local:"):
            return
        from urllib.parse import urlencode
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText("https://music.youtube.com/watch?" + urlencode({"v": video_id}))

    @Slot(str, str)
    def drop_track(self, payload, destination):
        try:
            track = json.loads(payload)
            identity = track["videoId"]
            if not isinstance(identity, str) or not identity or len(identity) > 200:
                return
            title = str(track.get("title", ""))[:500]
        except (ValueError, KeyError, TypeError):
            return
        if destination == "queue":
            self.window.queue_controller.on_add_to_queue_requested(identity, title, str(track.get("artist", ""))[:500], str(track.get("thumbnail", "")))
            return
        playlist_id = parse_qs(urlsplit(destination).query).get("id", [""])[-1]
        if not any(p["navigate"] == destination for p in self.window.sidebar.playlists):
            return
        async def add():
            try:
                await self._append(playlist_id, identity, title, track)
                self.window.show_notification("Añadida a la playlist", "success")
            except Exception as exc:
                self.window.show_notification(str(exc), "error")
        self.window._run_async(add())
