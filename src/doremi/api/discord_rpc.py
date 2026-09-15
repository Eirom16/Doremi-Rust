import asyncio
import time
from pypresence import AioPresence
from loguru import logger


class DiscordRPC:

    def __init__(self):
        self._rpc: AioPresence | None = None
        self._connecting = False
        self._next_retry_at = 0.0
        self._retry_delay = 5.0

    async def connect(self) -> None:
        if self._connecting:
            return
        self._connecting = True
        try:
            self._rpc = AioPresence("1395462809164263495")
            await self._rpc.connect()
            self._retry_delay = 5.0
            self._next_retry_at = 0.0
            logger.info("Discord RPC connected")
        except Exception as e:
            logger.warning(f"Discord RPC connection failed: {e}")
            self._rpc = None
            self._next_retry_at = time.time() + self._retry_delay
            self._retry_delay = min(self._retry_delay * 2, 300.0)
        finally:
            self._connecting = False

    async def disconnect(self) -> None:
        if self._rpc:
            try:
                await self._rpc.close()
                logger.info("Discord RPC disconnected")
            except Exception as e:
                logger.debug(f"Discord RPC disconnect error: {e}")
            finally:
                self._rpc = None

    async def _ensure_connected(self) -> bool:
        if self._rpc:
            return True
        if time.time() < self._next_retry_at:
            return False
        await self.connect()
        return self._rpc is not None

    async def update(
        self,
        title: str,
        artist: str,
        album: str = "",
        is_playing: bool = False,
        thumbnail_url: str = "",
    ) -> None:
        if not await self._ensure_connected():
            return
        try:
            state = f"by {artist}" if artist else "YouTube Music"
            details = f"{title}"
            large_img = thumbnail_url if (thumbnail_url and thumbnail_url.startswith("http")) else "music"
            await self._rpc.update(
                state=state,
                details=details,
                large_image=large_img,
                large_text=album if album else "Doremi",
                small_image="play" if is_playing else "pause",
                small_text="Playing" if is_playing else "Paused",
            )
        except Exception as e:
            logger.debug(f"Discord RPC update failed: {e}")
            self._rpc = None
            self._next_retry_at = time.time() + self._retry_delay
            self._retry_delay = min(self._retry_delay * 2, 300.0)
