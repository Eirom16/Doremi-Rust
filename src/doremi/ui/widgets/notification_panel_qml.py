from __future__ import annotations

import asyncio
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication
from loguru import logger

from doremi.services.download_manager import DownloadManager
from doremi.ui.viewmodels.notification_vm import NotificationViewModel

class NotificationPanelQml(QObject):
    """Isla QML del panel de notificaciones.

    Drop-in replacement de NotificationPanel (QtWidgets): mismas señales y
    métodos públicos (`toggle_panel`, `add_custom_notification`, etc.).
    La animación de ancho se hace con QPropertyAnimation como en la versión
    de widgets (compatible con `MainWindow._position_mini_player`).
    """

    unread_changed = Signal(bool)
    panel_toggled = Signal(bool)
    artist_clicked = Signal(str, str)
    song_clicked = Signal(str, str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._vm = NotificationViewModel(QApplication.instance())
        self.has_unread = False
        self._shell_managed = False
        self._shell_open = False

        self._load_ok = True

        # Señales de la VM → señales de la pantalla
        self._vm.song_clicked.connect(self.song_clicked)
        self._vm.artist_clicked.connect(self.artist_clicked)
        self._vm.cancel_download_requested.connect(
            lambda vid: DownloadManager.get_instance().cancel_download(vid)
        )
        self._vm.clear_history_requested.connect(self.clear_history)

        self._connect_download_manager()

    @property
    def is_ok(self) -> bool:
        return self._load_ok

    # ── Compat pública ─────────────────────────────────────────────────────

    def add_custom_notification(self, message: str, kind: str = "info") -> None:
        self._vm.add_history(message, kind)
        if not self._shell_open:
            self.has_unread = True
            self.unread_changed.emit(True)

    def clear_history(self) -> None:
        self._vm.clear_history()

    def toggle_panel(self) -> None:
        if self._shell_managed:
            if self._shell_open:
                self._close_anim()
            else:
                self.has_unread = False
                self.unread_changed.emit(False)
                self.load_db_notifications()
                self._open_anim()
            return
        if self._shell_open:
            self._close_anim()
        else:
            self.has_unread = False
            self.unread_changed.emit(False)
            self.load_db_notifications()
            self._open_anim()

    def _open_anim(self) -> None:
        if self._shell_managed:
            self._shell_open = True
            self.panel_toggled.emit(True)
            return
        self._shell_open = True
        self.panel_toggled.emit(True)

    def _close_anim(self) -> None:
        if self._shell_managed:
            self._shell_open = False
            self.panel_toggled.emit(False)
            return
        self._shell_open = False
        self.panel_toggled.emit(False)

    def set_shell_managed(self) -> None:
        """Delegate visibility and animation to MainShell.qml."""
        self._shell_managed = True
        return None

    def hide(self) -> None:
        self._shell_open = False

    @property
    def is_open(self) -> bool:
        return self._shell_open

    # ── Descargas activas ──────────────────────────────────────────────────

    def _connect_download_manager(self) -> None:
        mgr = DownloadManager.get_instance()
        mgr.download_queued.connect(self._on_download_queued)
        mgr.download_progress.connect(self._on_download_progress)
        mgr.download_completed.connect(self._on_download_completed)
        mgr.download_error.connect(self._on_download_error)

    def _on_download_queued(self, task) -> None:
        self._vm.add_active_download(task.video_id, task.title, task.artist)
        if not self._shell_open:
            self.has_unread = True
            self.unread_changed.emit(True)

    def _on_download_progress(self, video_id: str, percent: float, speed: str) -> None:
        self._vm.update_active_progress(video_id, percent, speed)

    def _on_download_completed(self, video_id: str, _filepath: str) -> None:
        item = self._vm._active.get(self._vm._active.find_row(video_id))
        self._vm.finish_active_download(video_id)
        if item:
            self.add_custom_notification(
                f"Descarga finalizada: {item.get('artist', '')} - {item.get('title', '')}",
                "success",
            )

    def _on_download_error(self, video_id: str, error_msg: str) -> None:
        item = self._vm._active.get(self._vm._active.find_row(video_id))
        self._vm.finish_active_download(video_id)
        title = item.get("title", video_id) if item else video_id
        self.add_custom_notification(f"Error al descargar '{title}': {error_msg}", "error")

    # ── Lanzamientos (DB) ──────────────────────────────────────────────────

    def load_db_notifications(self) -> None:
        asyncio.ensure_future(self._load_db_notifications())

    async def _load_db_notifications(self) -> None:
        self._vm.set_loading(True)
        try:
            from doremi.db.repository import NotificationRepository
            repo = NotificationRepository()
            releases = await repo.get_recent(limit=20)
            items = []
            for n in releases:
                items.append({
                    "video_id": n.video_id,
                    "title": n.title,
                    "artist": n.artist,
                    "artist_id": n.artist_id,
                    "thumbnail_url": n.thumbnail_url or "",
                    "time": self._time_ago(n.created_at),
                    "kind": "release",
                })
            self._vm.set_releases(items)
            await repo.mark_all_read()
        except Exception as e:
            logger.error(f"Error cargando notificaciones (QML): {e}")
        finally:
            self._vm.set_loading(False)

    @staticmethod
    def _time_ago(created_at) -> str:
        from datetime import datetime
        try:
            if not created_at:
                return ""
            dt = created_at
            if isinstance(dt, str):
                dt = datetime.fromisoformat(dt)
            diff = datetime.now(tz=dt.tzinfo) - dt if dt.tzinfo else datetime.now() - dt
            secs = int(diff.total_seconds())
            if secs < 60:
                return "ahora"
            if secs < 3600:
                return f"hace {secs // 60} min"
            if secs < 86400:
                return f"hace {secs // 3600} h"
            return f"hace {secs // 86400} d"
        except Exception:
            return ""
