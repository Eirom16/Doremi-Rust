import asyncio
from enum import Enum
from dataclasses import dataclass
from typing import Callable
from loguru import logger

# Lazy loading of vlc library to prevent DLL import errors during startup
_vlc = None
def get_vlc():
    global _vlc
    if _vlc is None:
        import vlc
        _vlc = vlc
    return _vlc


class PlayerState(Enum):
    IDLE = "idle"
    LOADING = "loading"
    PLAYING = "playing"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class PlayerStatus:
    state: PlayerState = PlayerState.IDLE
    position_ms: int = 0
    duration_ms: int = 0
    volume: int = 80
    speed: float = 1.0
    current_video_id: str | None = None
    error_msg: str | None = None


class MusicPlayer:
    END_REACHED_DURATION_TOLERANCE_MS = 1500

    def __init__(self):
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = None
            
        vlc_lib = get_vlc()
        self._instance = vlc_lib.Instance(
            "--no-video",
            "--quiet",
            "--audio-resampler=soxr",
            "--network-caching=3000",
            "--live-caching=3000",
        )
        self._player = self._instance.media_player_new()
        self._eq = None
        self.status = PlayerStatus()
        self._callbacks: dict[str, list[Callable]] = {
            "state_changed": [],
            "position_changed": [],
            "track_ended": [],
            "error": [],
            "buffering": [],
        }
        self._poll_task: asyncio.Task | None = None
        self._play_lock = asyncio.Lock()
        self._playback_ready: asyncio.Event = asyncio.Event()

        em = self._player.event_manager()
        em.event_attach(vlc_lib.EventType.MediaPlayerEndReached, self._on_ended)
        em.event_attach(vlc_lib.EventType.MediaPlayerEncounteredError, self._on_error)
        em.event_attach(vlc_lib.EventType.MediaPlayerPlaying, self._on_playing)
        em.event_attach(vlc_lib.EventType.MediaPlayerPaused, self._on_paused)
        em.event_attach(vlc_lib.EventType.MediaPlayerBuffering, self._on_buffering)

    # ─── REPRODUCCIÓN ─────────────────────────────────────────────────

    async def play_url(self, stream_url: str, video_id: str) -> bool:
        async with self._play_lock:
            self._playback_ready.clear()
            try:
                self.status.state = PlayerState.LOADING
                self.status.current_video_id = video_id
                self.status.position_ms = 0
                self.status.duration_ms = 0
                self._notify("state_changed", self.status)

                self._player.stop()
                
                media = self._instance.media_new(stream_url)
                media.add_option(
                    ":http-user-agent=Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                )
                self._player.set_media(media)
                self._player.play()
                
                # Wait for VLC to confirm playback started via event, with timeout
                try:
                    await asyncio.wait_for(self._playback_ready.wait(), timeout=10.0)
                except asyncio.TimeoutError:
                    logger.error(f"Timeout waiting for playback to start: {video_id}")
                    self.status.state = PlayerState.ERROR
                    self.status.error_msg = "Timeout al iniciar reproducción"
                    self._notify("error", self.status)
                    return False
                
                if self._poll_task and not self._poll_task.done():
                    self._poll_task.cancel()
                self._poll_task = asyncio.create_task(self._poll_position())
                
                return True
            except Exception as e:
                logger.error(f"play_url error: {e}")
                self.status.state = PlayerState.ERROR
                self.status.error_msg = str(e)
                self._notify("error", self.status)
                return False

    async def pause(self) -> None:
        async with self._play_lock:
            logger.debug(f"pause() called, vlc_state={self._player.get_state()}, is_playing={self._player.is_playing()}")
            self._player.set_pause(1)
            # Immediately update state - don't wait for VLC event thread
            self.status.state = PlayerState.PAUSED
            self._notify("state_changed", self.status)
            logger.debug("pause() completed, state set to PAUSED")

    async def resume(self) -> None:
        async with self._play_lock:
            state = self._player.get_state()
            logger.debug(f"resume() called, vlc_state={state}")
            vlc_lib = get_vlc()
            if state == vlc_lib.State.Paused:
                self._player.set_pause(0)
            elif state == vlc_lib.State.Ended or state == vlc_lib.State.Stopped:
                self._player.play()
            else:
                # Try unpause regardless
                self._player.set_pause(0)
            # Immediately update state
            self.status.state = PlayerState.PLAYING
            self._notify("state_changed", self.status)
            logger.debug("resume() completed, state set to PLAYING")

    async def stop(self) -> None:
        async with self._play_lock:
            self._player.stop()
            self.status.state = PlayerState.IDLE
            self.status.position_ms = 0
            self._playback_ready.clear()
            if self._poll_task:
                self._poll_task.cancel()
            self._notify("state_changed", self.status)

    async def seek(self, position_ms: int) -> None:
        async with self._play_lock:
            if self._player.get_length() > 0:
                self._player.set_time(max(0, position_ms))

    # ─── CONTROLES ────────────────────────────────────────────────────

    def set_volume(self, volume: int) -> None:
        clamped = max(0, min(200, volume))
        self._player.audio_set_volume(clamped)
        self.status.volume = clamped

    def set_muted(self, muted: bool) -> None:
        self._player.audio_set_mute(muted)

    def set_speed(self, speed: float) -> None:
        self._player.set_rate(max(0.25, min(4.0, speed)))
        self.status.speed = speed

    def apply_equalizer(self, preamp: float, bands: list[float]) -> None:
        try:
            vlc_lib = get_vlc()
            eq = vlc_lib.libvlc_audio_equalizer_new()
            vlc_lib.libvlc_audio_equalizer_set_preamp(eq, preamp)
            for i, gain in enumerate(bands[:10]):
                vlc_lib.libvlc_audio_equalizer_set_amp_at_index(eq, gain, i)
            self._player.set_equalizer(eq)
            self._eq = eq
            logger.debug(f"EQ applied: preamp={preamp}, bands={bands}")
        except Exception as e:
            logger.warning(f"Equalizer not available: {e}")

    def reset_equalizer(self) -> None:
        try:
            self._player.set_equalizer(None)
            self._eq = None
        except Exception as e:
            logger.warning(f"Could not reset equalizer: {e}")

    # ─── CALLBACKS ────────────────────────────────────────────────────

    def on(self, event: str, callback: Callable) -> None:
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def off(self, event: str, callback: Callable) -> None:
        if event in self._callbacks:
            try:
                self._callbacks[event].remove(callback)
            except ValueError:
                pass

    def _notify(self, event: str, data=None) -> None:
        for cb in self._callbacks.get(event, []):
            try:
                cb(data)
            except Exception as e:
                logger.error(f"Player callback error [{event}]: {e}")

    async def _poll_position(self) -> None:
        vlc_lib = get_vlc()
        while True:
            await asyncio.sleep(0.5)
            if self._player.is_playing():
                if self.status.state != PlayerState.PLAYING:
                    logger.debug(f"Self-correcting player state from {self.status.state} to PLAYING")
                    self.status.state = PlayerState.PLAYING
                    self._notify("state_changed", self.status)
                pos = self._player.get_time()
                dur = self._player.get_length()
                if pos >= 0:
                    self.status.position_ms = pos
                    if dur > 0:
                        self.status.duration_ms = dur
                    self._notify("position_changed", self.status)
            elif self._player.get_state() == vlc_lib.State.Paused:
                if self.status.state != PlayerState.PAUSED:
                    logger.debug(f"Self-correcting player state from {self.status.state} to PAUSED")
                    self.status.state = PlayerState.PAUSED
                    self._notify("state_changed", self.status)

    def _schedule(self, func, *args):
        try:
            if hasattr(self, '_loop') and self._loop and not self._loop.is_closed():
                self._loop.call_soon_threadsafe(func, *args)
            else:
                loop = asyncio.get_event_loop()
                loop.call_soon_threadsafe(func, *args)
        except Exception as e:
            logger.error(f"Failed to schedule callback: {e}")

    def _refresh_timing_from_player(self) -> None:
        pos = self._player.get_time()
        dur = self._player.get_length()
        if pos >= 0:
            self.status.position_ms = pos
        if dur > 0:
            self.status.duration_ms = dur

    def _complete_position(self) -> None:
        self._refresh_timing_from_player()
        if self.status.duration_ms > 0:
            remaining_ms = self.status.duration_ms - self.status.position_ms
            if self.status.position_ms > self.status.duration_ms:
                self.status.duration_ms = self.status.position_ms
            elif (
                self.status.position_ms > 0
                and remaining_ms > self.END_REACHED_DURATION_TOLERANCE_MS
            ):
                self.status.duration_ms = self.status.position_ms
            self.status.position_ms = self.status.duration_ms
        elif self.status.position_ms > 0:
            self.status.duration_ms = self.status.position_ms

    def _on_ended(self, event):
        def _handle():
            self._complete_position()
            self._notify("position_changed", self.status)
            self.status.state = PlayerState.IDLE
            self._notify("state_changed", self.status)
            self._playback_ready.clear()
            self._notify("track_ended", self.status)
        self._schedule(_handle)

    def _on_error(self, event):
        def _handle():
            self.status.state = PlayerState.ERROR
            self.status.error_msg = "Error de reproducción"
            self._notify("error", self.status)
            self._playback_ready.set()
        self._schedule(_handle)

    def _on_playing(self, event):
        def _handle():
            self.status.state = PlayerState.PLAYING
            self._notify("state_changed", self.status)
            self._playback_ready.set()
        self._schedule(_handle)

    def _on_paused(self, event):
        def _handle():
            self.status.state = PlayerState.PAUSED
            self._notify("state_changed", self.status)
        self._schedule(_handle)

    def _on_buffering(self, event):
        def _handle():
            self._notify("buffering", event.u.new_cache)
        self._schedule(_handle)

    def release(self) -> None:
        if self._poll_task:
            self._poll_task.cancel()
        self._player.release()
        self._instance.release()
