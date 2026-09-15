import asyncio
from loguru import logger


class CrossfadeManager:

    def __init__(self, enabled: bool = True, duration_sec: int = 5):
        self.enabled = enabled
        self.duration_sec = duration_sec



    async def fade_out(self, player, duration_sec: float = 1.5) -> None:
        if not self.enabled:
            return
        steps = 15
        sleep_time = duration_sec / steps
        start_vol = player.status.volume
        logger.info(f"Crossfade: fading out from volume {start_vol} to 0 over {duration_sec}s")
        for step in range(steps):
            vol = max(0, int(start_vol * (1 - (step + 1) / steps)))
            player.set_volume(vol)
            await asyncio.sleep(sleep_time)

    async def fade_in(self, player, target_vol: int, duration_sec: float = 1.5) -> None:
        if not self.enabled:
            player.set_volume(target_vol)
            return
        steps = 15
        sleep_time = duration_sec / steps
        logger.info(f"Crossfade: fading in to target volume {target_vol} over {duration_sec}s")
        for step in range(steps):
            vol = min(target_vol, int(target_vol * ((step + 1) / steps)))
            player.set_volume(vol)
            await asyncio.sleep(sleep_time)
