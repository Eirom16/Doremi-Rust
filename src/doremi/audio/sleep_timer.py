import asyncio
from typing import Callable
from loguru import logger


class SleepTimer:

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._callback: Callable | None = None

    async def start(self, seconds: int, callback: Callable) -> None:
        if self._task and not self._task.done():
            self._task.cancel()

        self._callback = callback
        logger.info(f"Sleep timer started for {seconds}s")

        async def _countdown():
            await asyncio.sleep(seconds)
            logger.info("Sleep timer expired")
            if self._callback:
                self._callback()

        self._task = asyncio.create_task(_countdown())

    def cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("Sleep timer cancelled")

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()
