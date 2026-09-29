"""State for one real listening session.

The player reports media position periodically.  A session accumulates only
small forward position deltas while playback is active, so a seek does not get
mistaken for time listened.  It is intentionally independent from Qt/VLC to
make the playback-statistics contract easy to test.
"""
from __future__ import annotations

from dataclasses import dataclass

from doremi.audio.queue import QueueItem


@dataclass(frozen=True)
class ListenResult:
    item: QueueItem
    listen_time_ms: int
    completion_ratio: float
    skip_count: int
    completed: bool
    was_played: bool


class ListeningSession:
    """Accumulate a track's actual listening time until it finishes or skips."""

    # Position poll gaps greater than this are treated as a seek/reload rather
    # than an uninterrupted listen interval.
    MAX_CONTIGUOUS_DELTA_MS = 10_000
    PLAY_THRESHOLD_MS = 30_000

    def __init__(self) -> None:
        self._item: QueueItem | None = None
        self._listen_time_ms = 0
        self._max_position_ms = 0
        self._last_position_ms: int | None = None
        self._duration_ms = 0

    @property
    def item(self) -> QueueItem | None:
        return self._item

    def start(self, item: QueueItem) -> None:
        self._item = item
        self._listen_time_ms = 0
        self._max_position_ms = 0
        self._last_position_ms = None
        self._duration_ms = max(0, int(item.duration_ms or 0))

    def observe(self, position_ms: int, duration_ms: int, is_playing: bool) -> None:
        if self._item is None:
            return
        position = max(0, int(position_ms or 0))
        duration = max(0, int(duration_ms or 0))
        if duration:
            self._duration_ms = duration
        self._max_position_ms = max(self._max_position_ms, position)
        if is_playing and self._last_position_ms is not None:
            delta = position - self._last_position_ms
            if 0 < delta <= self.MAX_CONTIGUOUS_DELTA_MS:
                self._listen_time_ms += delta
        self._last_position_ms = position

    def finish(self, reason: str) -> ListenResult | None:
        item = self._item
        if item is None:
            return None
        duration = self._duration_ms or max(0, int(item.duration_ms or 0))
        ratio = min(1.0, self._max_position_ms / duration) if duration else 0.0
        completed = reason == "completed" or ratio >= 0.9
        # A completed short song is a play even below 30 seconds.  For longer
        # tracks, require either completion or a meaningful listening interval.
        was_played = completed or self._listen_time_ms >= min(
            self.PLAY_THRESHOLD_MS,
            duration // 2 if duration else self.PLAY_THRESHOLD_MS,
        )
        result = ListenResult(
            item=item,
            listen_time_ms=self._listen_time_ms,
            completion_ratio=ratio,
            skip_count=int(reason in {"skipped", "replaced", "failed", "stopped"} and not completed),
            completed=completed,
            was_played=was_played,
        )
        self._item = None
        self._last_position_ms = None
        return result
