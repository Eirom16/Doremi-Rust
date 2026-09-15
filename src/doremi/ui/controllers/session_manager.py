import asyncio
import json

from loguru import logger

from doremi.config.paths import AppDirs
from doremi.audio.queue import PlayQueue, RepeatMode


class PlaybackSessionManager:
    """Specialized controller for playback session lifecycle.

    Owns startup initialization, session restore/save and silent update checks
    previously living in MainWindow's god object. Dependencies are accessed via
    the ``main_window`` reference; ``run_async`` is a callable (MainWindow._run_async)
    used to launch coroutines as asyncio tasks.
    """

    def __init__(self, main_window, run_async):
        self.main_window = main_window
        self.run_async = run_async
        self._queue_state_file = AppDirs.data / "queue_state.json"
        self._resume_position_ms = 0

    async def initialize(self) -> None:
        self.restore_playback_session()
        await self.main_window._navigate("home")
        if self.main_window.settings.player.resume_on_startup and self.main_window.queue.current:
            self.main_window.playback_controller._update_queue_panel()
            item = self.main_window.queue.current
            self.main_window.mini_player.update_track_info(item.title, item.artist, item.thumbnail_url)
            self.main_window.now_playing_screen.update_track_info(item.title, item.artist, item.thumbnail_url)
            self.run_async(self.resume_playback_after_startup())

    async def resume_playback_after_startup(self) -> None:
        try:
            await self.main_window.playback_controller._play_current(resume=True)
            if self._resume_position_ms > 0:
                await self.main_window.player.seek(self._resume_position_ms)
        except Exception as e:
            logger.warning(f"Failed to resume playback session: {e}")

    def restore_playback_session(self) -> None:
        try:
            if not self._queue_state_file.exists():
                return
            with open(self._queue_state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            restored = PlayQueue.from_dict(data.get("queue", {}))
            if not restored.items:
                return
            self.main_window.queue = restored
            self.main_window.queue.shuffle_enabled = self.main_window.settings.player.shuffle_enabled
            try:
                self.main_window.queue.repeat_mode = RepeatMode(self.main_window.settings.player.repeat_mode)
            except ValueError:
                self.main_window.queue.repeat_mode = RepeatMode.OFF
            self.main_window.mpris.queue = self.main_window.queue
            self.main_window.mini_player.queue = self.main_window.queue
            self.main_window.now_playing_screen.queue = self.main_window.queue
            self.main_window.settings.last_video_id = (
                data.get("last_video_id") or self.main_window.queue.current.video_id
            )
            self._resume_position_ms = int(data.get("position_ms", 0))
            logger.info(f"Restored playback queue with {len(self.main_window.queue.items)} items")
        except Exception as e:
            logger.warning(f"Failed to restore playback session: {e}")

    def save_playback_session(self) -> None:
        try:
            current = self.main_window.queue.current
            self.main_window.settings.last_video_id = current.video_id if current else None
            payload = {
                "queue": self.main_window.queue.to_dict(),
                "last_video_id": self.main_window.settings.last_video_id,
                "position_ms": self.main_window.player.status.position_ms,
            }
            self._queue_state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._queue_state_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            self.main_window.settings.save(AppDirs.settings_file)
        except Exception as e:
            logger.warning(f"Failed to save playback session: {e}")

    async def check_updates(self) -> None:
        """Comprueba actualizaciones silenciosamente al arrancar."""
        from doremi.utils.updater import check_for_updates
        from doremi.ui.widgets.update_dialog import UpdateDialog

        release = await check_for_updates()
        if release:
            # Mostrar el diálogo de actualización (no bloquea la UI)
            dlg = UpdateDialog(release, parent=self.main_window)
            dlg.show()
