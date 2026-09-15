import asyncio
import json
import time
import pylast
from loguru import logger
from doremi.config.paths import AppDirs


class LastFmScrobbler:

    def __init__(
        self, api_key: str, api_secret: str, session_key: str
    ):
        self._network = pylast.LastFMNetwork(
            api_key=api_key,
            api_secret=api_secret,
            session_key=session_key,
        )
        self._pending_file = AppDirs.data / "lastfm_scrobbles.json"

    def _now_playing(self, artist: str, title: str, album: str = "") -> None:
        try:
            self._network.update_now_playing(artist, title, album=album)
        except Exception as e:
            logger.warning(f"Last.fm now-playing failed: {e}")

    def _scrobble(self, artist: str, title: str, timestamp: int, album: str = "") -> bool:
        try:
            self._network.scrobble(artist, title, timestamp, album=album)
            return True
        except Exception as e:
            logger.warning(f"Last.fm scrobble failed: {e}")
            return False

    def _load_pending(self) -> list[dict]:
        try:
            if not self._pending_file.exists():
                return []
            with open(self._pending_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.warning(f"Failed to load pending Last.fm scrobbles: {e}")
            return []

    def _save_pending(self, items: list[dict]) -> None:
        try:
            self._pending_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._pending_file, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save pending Last.fm scrobbles: {e}")

    @staticmethod
    def _pending_key(item: dict) -> tuple[str, str, int]:
        return (
            str(item.get("artist", "")),
            str(item.get("title", "")),
            int(item.get("timestamp", 0)),
        )

    def _enqueue_pending(
        self, artist: str, title: str, timestamp: int, album: str = ""
    ) -> None:
        pending = self._load_pending()
        entry = {
            "artist": artist,
            "title": title,
            "album": album,
            "timestamp": timestamp,
        }
        key = self._pending_key(entry)
        if any(self._pending_key(item) == key for item in pending):
            return
        pending.append(entry)
        self._save_pending(pending)

    async def update_now_playing(
        self, artist: str, title: str, album: str = ""
    ) -> None:
        # Use asyncio.to_thread instead of loop.run_in_executor to avoid qasync cancellation SIGSEGV bugs
        await asyncio.to_thread(self._now_playing, artist, title, album)
        await self.flush_pending()

    async def scrobble(
        self, artist: str, title: str, album: str = "", timestamp: int | None = None
    ) -> bool:
        # Use asyncio.to_thread instead of loop.run_in_executor to avoid qasync cancellation SIGSEGV bugs
        timestamp = timestamp or int(time.time())
        success = await asyncio.to_thread(
            self._scrobble, artist, title, timestamp or int(time.time()), album
        )
        if not success:
            self._enqueue_pending(artist, title, timestamp, album)
        return success

    async def flush_pending(self) -> None:
        pending = self._load_pending()
        if not pending:
            return

        remaining = []
        for item in pending:
            artist = str(item.get("artist", ""))
            title = str(item.get("title", ""))
            album = str(item.get("album", ""))
            timestamp = int(item.get("timestamp", 0))
            if not artist or not title or not timestamp:
                continue
            success = await asyncio.to_thread(
                self._scrobble, artist, title, timestamp, album
            )
            if not success:
                remaining.append(item)

        if len(remaining) != len(pending):
            self._save_pending(remaining)
