import asyncio
from collections.abc import Callable


class CrossfadeManager:
    """Fundidos consecutivos; duración configurada para la transición completa."""

    def __init__(self, enabled: bool = True, duration_sec: int = 5):
        self.enabled = enabled
        self.duration_sec = duration_sec
        self._generation = 0

    def cancel(self) -> None:
        self._generation += 1

    async def _fade(self, player, target: int, duration_sec: float | None,
                    is_current: Callable[[], bool] | None) -> None:
        if is_current and not is_current():
            return
        self.cancel()
        generation = self._generation
        start = player.status.volume
        previous = start
        duration = self.duration_sec / 2 if duration_sec is None else duration_sec
        for step in range(1, 16):
            if generation != self._generation or (is_current and not is_current()):
                return
            # Un cambio manual de volumen tiene prioridad sobre el fundido.
            if player.status.volume != previous:
                return
            previous = round(start + (target - start) * step / 15)
            player.set_volume(previous)
            await asyncio.sleep(max(0, duration) / 15)

    async def fade_out(self, player, duration_sec: float | None = None,
                       *, is_current: Callable[[], bool] | None = None) -> None:
        if self.enabled:
            await self._fade(player, 0, duration_sec, is_current)

    async def fade_in(self, player, target_vol: int, duration_sec: float | None = None,
                      *, is_current: Callable[[], bool] | None = None) -> None:
        if is_current and not is_current():
            return
        if not self.enabled:
            player.set_volume(target_vol)
            return
        await self._fade(player, target_vol, duration_sec, is_current)
