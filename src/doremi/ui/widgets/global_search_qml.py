"""QML implementation of the global search header and its suggestion popover."""

from __future__ import annotations

import asyncio
from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from doremi.services.search_history import SearchHistory
from doremi.ui.design.icons import CODEPOINTS


class _HeaderViewModel(QObject):
    changed = Signal()
    query_changed = Signal()
    focus_requested_changed = Signal()
    search_submitted = Signal(str)
    notifications_requested = Signal()
    profile_requested = Signal()

    def __init__(self, yt_client, parent: QObject) -> None:
        super().__init__(parent)
        self.yt = yt_client
        self._history_store = SearchHistory()
        self._history = self._history_store.load()
        self._query = ""
        self._suggestions: list[dict[str, object]] = []
        self._has_unread = False
        self._notifications_open = False
        self._profile_label = "Iniciar sesión"
        self._avatar_url = ""
        self._focus_request = 0
        self._suggestion_timer = QTimer(self)
        self._suggestion_timer.setSingleShot(True)
        self._suggestion_timer.setInterval(250)
        self._suggestion_timer.timeout.connect(self._fetch_suggestions)

    @Property(str, notify=query_changed)
    def query(self) -> str:
        return self._query

    @Property("QVariantList", notify=changed)
    def suggestions(self) -> list[dict[str, object]]:
        return self._suggestions

    @Property(bool, notify=changed)
    def hasUnread(self) -> bool:
        return self._has_unread

    @Property(bool, notify=changed)
    def notificationsOpen(self) -> bool:
        return self._notifications_open

    @Property(str, notify=changed)
    def profileLabel(self) -> str:
        return self._profile_label

    @Property(str, notify=changed)
    def avatarUrl(self) -> str:
        return self._avatar_url

    @Property(int, notify=focus_requested_changed)
    def focusRequested(self) -> int:
        return self._focus_request

    @Slot(str)
    def setQuery(self, query: str) -> None:
        self.set_query(query)

    def set_query(self, query: str, *, fetch: bool = True) -> None:
        query = query.strip()
        if self._query != query:
            self._query = query
            self.query_changed.emit()
        self._suggestion_timer.stop()
        if not query:
            self._suggestions = []
            self.changed.emit()
            return
        self._suggestions = self._history_rows(query)
        self.changed.emit()
        if fetch:
            self._suggestion_timer.start()

    @Slot()
    def clearQuery(self) -> None:
        self.clear_query()

    def clear_query(self) -> None:
        self.set_query("", fetch=False)
        self.request_focus()

    def request_focus(self) -> None:
        self._focus_request += 1
        self.focus_requested_changed.emit()

    @Slot()
    def submit(self) -> None:
        self._commit_query(self._query)

    @Slot(int)
    def selectSuggestion(self, index: int) -> None:
        if not 0 <= index < len(self._suggestions):
            return
        selected = self._suggestions[index]
        route = str(selected.get("route", ""))
        if route:
            self.search_submitted.emit(route)
            self._suggestions = []
            self.changed.emit()
            return
        self._commit_query(str(selected.get("title", "")))

    @Slot(str)
    def removeHistory(self, query: str) -> None:
        self._history = self._history_store.remove(self._history, query)
        self._suggestions = self._history_rows(self._query)
        self.changed.emit()

    @Slot()
    def requestNotifications(self) -> None:
        self.notifications_requested.emit()

    @Slot()
    def requestProfile(self) -> None:
        self.profile_requested.emit()

    def set_unread(self, has_unread: bool) -> None:
        has_unread = bool(has_unread)
        if self._has_unread != has_unread:
            self._has_unread = has_unread
            self.changed.emit()

    def set_notifications_open(self, is_open: bool) -> None:
        is_open = bool(is_open)
        if self._notifications_open != is_open:
            self._notifications_open = is_open
            self.changed.emit()

    def update_profile(self, is_authenticated: bool, name: str = "", avatar_url: str = "") -> None:
        label = name or ("Mi cuenta" if is_authenticated else "Iniciar sesión")
        avatar = avatar_url if is_authenticated else ""
        if self._profile_label != label or self._avatar_url != avatar:
            self._profile_label = label
            self._avatar_url = avatar
            self.changed.emit()

    def _commit_query(self, query: str) -> None:
        query = query.strip()
        if not query:
            return
        self._history = self._history_store.commit(self._history, query)
        self._suggestions = []
        self.changed.emit()
        self.search_submitted.emit(query)

    def _history_rows(self, query: str) -> list[dict[str, object]]:
        lowered = query.casefold()
        return [
            {
                "title": item,
                "subtitle": "",
                "icon": CODEPOINTS["history"],
                "route": "",
                "deletable": True,
            }
            for item in self._history
            if lowered in item.casefold()
        ][:5]

    def _fetch_suggestions(self) -> None:
        query = self._query
        if query and self.yt:
            asyncio.ensure_future(self._fetch_suggestions_async(query))

    async def _fetch_suggestions_async(self, query: str) -> None:
        try:
            response = await self.yt.search_suggestions(query)
        except Exception:
            return
        if query != self._query:
            return
        rows = self._history_rows(query)
        rows.extend(self._suggestion_rows(response, rows))
        self._suggestions = rows
        self.changed.emit()

    @staticmethod
    def _suggestion_rows(response, existing: list[dict[str, object]]) -> list[dict[str, object]]:
        if not isinstance(response, dict):
            return [
                {
                    "title": str(item), "subtitle": "", "icon": CODEPOINTS["search"],
                    "route": "", "deletable": False,
                }
                for item in (response or [])[:6]
            ]

        existing_titles = {str(item["title"]).casefold() for item in existing}
        rows: list[dict[str, object]] = []

        def append(items, title_key: str, subtitle: str, icon: str, route_key: str = "") -> None:
            for item in items[:3]:
                title = str(item.get(title_key, "")).strip()
                if not title or title.casefold() in existing_titles:
                    continue
                route_id = str(item.get(route_key, "")) if route_key else ""
                rows.append({
                    "title": title,
                    "subtitle": subtitle,
                    "icon": CODEPOINTS[icon],
                    "route": route_id,
                    "deletable": False,
                })
                existing_titles.add(title.casefold())

        append(response.get("artists", []), "name", "Artista", "artist", "browseId")
        for row in rows:
            if row["route"]:
                row["route"] = f"artist?id={row['route']}"

        album_rows_start = len(rows)
        append(response.get("albums", []), "title", "Álbum", "album", "browseId")
        for row in rows[album_rows_start:]:
            if row["route"]:
                row["route"] = f"album?id={row['route']}"

        append(response.get("songs", []), "title", "Canción", "music_note")
        for item in response.get("text", [])[:5]:
            title = str(item.get("text", item) if isinstance(item, dict) else item).strip()
            if title and title.casefold() not in existing_titles:
                rows.append({
                    "title": title, "subtitle": "", "icon": CODEPOINTS["search"],
                    "route": "", "deletable": False,
                })
                existing_titles.add(title.casefold())
        return rows[:10]


class GlobalSearchBarQml(QObject):
    """Header presenter rendered by MainShell.qml."""

    search_submitted = Signal(str)
    notifications_requested = Signal()
    profile_requested = Signal()

    def __init__(self, yt_client, on_play_song, parent=None) -> None:
        super().__init__(parent)
        self.yt = yt_client
        self.on_play_song = on_play_song
        self._load_ok = True
        self._vm = _HeaderViewModel(yt_client, self)
        self._vm.search_submitted.connect(self.search_submitted)
        self._vm.notifications_requested.connect(self.notifications_requested)
        self._vm.profile_requested.connect(self.profile_requested)

    @property
    def is_ok(self) -> bool:
        return self._load_ok

    @property
    def yt(self):
        return self._vm.yt

    @yt.setter
    def yt(self, value) -> None:
        if hasattr(self, "_vm"):
            self._vm.yt = value

    def focus_search(self) -> None:
        self._vm.request_focus()

    def clear_query(self) -> None:
        self._vm.clear_query()

    def set_query(self, query: str, *, fetch: bool = True) -> None:
        self._vm.set_query(query, fetch=fetch)

    def _hide_dropdown(self) -> None:
        self._vm._suggestion_timer.stop()

    def update_profile(self, is_authenticated: bool, name: str = "", avatar_url: str = "") -> None:
        self._vm.update_profile(is_authenticated, name, avatar_url)

    def set_unread(self, has_unread: bool) -> None:
        self._vm.set_unread(has_unread)

    def set_panel_open(self, is_open: bool) -> None:
        self._vm.set_notifications_open(is_open)
