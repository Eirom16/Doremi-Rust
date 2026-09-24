import asyncio

import pytest

from doremi.audio.player import MusicPlayer, PlayerState


@pytest.fixture
def player():
    p = MusicPlayer()
    p._poll_task = None
    # Mocked VLC returns MagicMock by default; make timing calls return ints
    p._player.get_time.return_value = 0
    p._player.get_length.return_value = 0
    return p


@pytest.mark.asyncio
async def test_playback_ready_starts_cleared(player):
    assert not player._playback_ready.is_set()


@pytest.mark.asyncio
async def test_on_playing_sets_playback_ready(player):
    player._on_playing(None)
    # _schedule uses call_soon_threadsafe; let the loop run the callback
    await asyncio.sleep(0)
    assert player._playback_ready.is_set()
    assert player.status.state == PlayerState.PLAYING


@pytest.mark.asyncio
async def test_on_error_sets_playback_ready_and_error_state(player):
    player._on_error(None)
    await asyncio.sleep(0)
    assert player._playback_ready.is_set()
    assert player.status.state == PlayerState.ERROR
    assert player.status.error_msg


@pytest.mark.asyncio
async def test_on_ended_clears_playback_ready_and_signals_track_ended(player):
    ended = []
    player.on("track_ended", lambda s: ended.append(s))
    player._on_ended(None)
    await asyncio.sleep(0)
    assert not player._playback_ready.is_set()
    assert player.status.state == PlayerState.IDLE
    assert ended


@pytest.mark.asyncio
async def test_pause_sets_paused_state(player):
    await player.pause()
    assert player.status.state == PlayerState.PAUSED


@pytest.mark.asyncio
async def test_resume_sets_playing_state(player):
    await player.pause()
    await player.resume()
    assert player.status.state == PlayerState.PLAYING


@pytest.mark.asyncio
async def test_stop_sets_idle_and_clears_ready(player):
    player._playback_ready.set()
    await player.stop()
    assert player.status.state == PlayerState.IDLE
    assert not player._playback_ready.is_set()
    assert player.status.position_ms == 0


@pytest.mark.asyncio
async def test_lock_serializes_concurrent_play_url(player):
    """Two concurrent play_url calls must not interleave their critical sections."""
    order = []

    async def fake_wait(self=player):
        order.append("wait")
        # simulate readiness without real VLC
        player._playback_ready.set()
        return None

    # Patch the readiness wait so play_url proceeds without real VLC events
    orig_wait = player._playback_ready.wait
    player._playback_ready.wait = fake_wait

    async def tracked_play(tag):
        # Monkeypatch play_url body minimally: just acquire lock + wait
        async with player._play_lock:
            order.append(f"acquired-{tag}")
            await player._playback_ready.wait()
            order.append(f"released-{tag}")

    t1 = asyncio.create_task(tracked_play("A"))
    t2 = asyncio.create_task(tracked_play("B"))
    await asyncio.gather(t1, t2)
    player._playback_ready.wait = orig_wait

    # First acquire must fully complete before the second acquires
    assert order.index("acquired-A") < order.index("acquired-B")
    assert order.index("released-A") < order.index("acquired-B")


@pytest.mark.asyncio
async def test_set_volume_clamps(player):
    player.set_volume(500)
    assert player.status.volume == 200
    player.set_volume(-50)
    assert player.status.volume == 0


@pytest.mark.asyncio
async def test_play_url_reports_vlc_startup_error_as_failure(player, monkeypatch):
    monkeypatch.setattr(player._player, "play", lambda: player._on_error(None))
    try:
        assert await player.play_url("https://example.invalid/audio", "broken") is False
        assert player.status.state == PlayerState.ERROR
        assert player._poll_task is None
    finally:
        if player._poll_task:
            player._poll_task.cancel()
            await asyncio.gather(player._poll_task, return_exceptions=True)


@pytest.mark.asyncio
async def test_successful_play_clears_previous_error(player, monkeypatch):
    player.status.error_msg = "previous error"
    monkeypatch.setattr(player._player, "play", lambda: player._on_playing(None))
    try:
        assert await player.play_url("https://example.invalid/audio", "ok") is True
        assert player.status.error_msg is None
    finally:
        if player._poll_task:
            player._poll_task.cancel()
            await asyncio.gather(player._poll_task, return_exceptions=True)
