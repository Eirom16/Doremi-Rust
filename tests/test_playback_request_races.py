import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from doremi.audio.player import PlayerState
from doremi.audio.queue import PlayQueue, QueueItem
from doremi.config.settings import AppSettings
from doremi.ui.controllers.playback_controller import PlaybackController


@pytest.mark.asyncio
@pytest.mark.parametrize("delay_at", ["download", "alternative", "extraction_error"])
async def test_late_playback_request_cannot_replace_newer_track(monkeypatch, delay_at):
    import doremi.db.repository as repositories

    started, release = asyncio.Event(), asyncio.Event()

    async def get_download(video_id):
        if video_id == "first" and delay_at == "download":
            started.set()
            await release.wait()
        return None

    monkeypatch.setattr(repositories, "DownloadRepository",
                        lambda: SimpleNamespace(get_download=get_download))
    controller = PlaybackController.__new__(PlaybackController)
    controller._current_play_id = 0
    controller.queue = PlayQueue()
    controller.settings = AppSettings()
    controller.settings.player.crossfade_enabled = False
    controller.player = SimpleNamespace(
        status=SimpleNamespace(state=PlayerState.IDLE),
        play_url=AsyncMock(side_effect=lambda url, vid: vid != "first" or delay_at != "alternative"),
    )
    async def delayed_extraction(video_id):
        started.set()
        await release.wait()
        if delay_at == "extraction_error":
            raise RuntimeError("fallo tardío")
        return "https://example.invalid/alternative"

    controller.extractor = SimpleNamespace(
        get_alternative_stream=delayed_extraction,
        get_stream_info=delayed_extraction,
    )
    controller.mini_player = MagicMock()
    controller.now_playing_screen = MagicMock()
    controller.tray = MagicMock()
    controller.main_window = MagicMock()
    controller.main_window._handle_playback_failure = AsyncMock()
    controller.scrobbler = controller.discord = controller.mpris = None
    controller.network_monitor = SimpleNamespace(is_connected=True)
    # Las tareas auxiliares no forman parte de esta carrera.
    controller.run_async = lambda coro: coro.close()
    first, second = [QueueItem(
        vid, vid, "", "", 0, "", stream_url=f"https://example.invalid/{vid}",
        stream_expires_at=time.time() + 60,
    ) for vid in ("first", "second")]
    if delay_at == "extraction_error":
        first.stream_url = None
    controller.queue.set_queue([first, second])
    pending = asyncio.create_task(controller._play_current())
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        controller.queue.jump_to(1)
        await controller._play_current()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await pending
        calls = controller.player.play_url.await_args_list
        assert calls[-1].args == (second.stream_url, "second")
        assert len(calls) == (2 if delay_at == "alternative" else 1)
        assert controller.mini_player.update_track_info.call_args.args[0] == "second"
        controller.main_window._handle_playback_failure.assert_not_awaited()
    finally:
        release.set()
        await asyncio.gather(pending, return_exceptions=True)
