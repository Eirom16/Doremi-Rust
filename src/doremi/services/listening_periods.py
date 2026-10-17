"""Product listening periods and calendar summaries derived from PlayHistory.

REC-03C.2 recovery from rescue working tree
(``Doremi-Rust-Rescate`` ``src/doremi/services/listening_periods.py``,
154 lines). Adaptations vs rescue (no schema/migration changes):

- ``recent`` validates ``limit`` (1..1000, default 12); 90-day cutoff and
  30-minute gap semantics preserved; history remains source of truth.
- ``tracks`` gains optional ``limit``/``offset`` pagination (default full
  for backward compat) and batches the final ``IN`` fetch in chunks of 500
  to avoid SQLite variable limits; ordering by ``(played_at, id)`` keeps
  results deterministic.
- ``save_as_playlist`` is a write command: ``ensure_songs`` then
  ``create_playlist`` then ``append`` per their contracts. ``append`` alone
  is atomic (REC-03B); ``create`` + ``append`` are two transactions, so on
  ``append`` failure the newly created empty playlist is best-effort deleted
  to avoid orphans. Each call creates a new identity: retries are NOT
  idempotent.
- Filesystem checks (``track_data``/``cover_fields`` ``is_file``) are
  inherited from REC-03A/REC-03B and required so disappeared files are never
  reported as available; ``recent`` only resolves at most 4 covers per
  period. No new blocking calls added; no network, no Qt on import.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

from doremi.services.artwork import cover_fields

from sqlalchemy import text, select

from doremi.db.database import get_session
from doremi.db.models import PlayHistory as H, Song, Download
from doremi.db.experience_repository import ExperienceRepository
from doremi.db.local_library_repository import LocalLibraryRepository, track_data

_MAX_LIMIT = 1000
_BATCH_IDS = 500


def _coerce_limit(value, *, default, name):
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Invalid {name}")
    if value <= 0:
        raise ValueError(f"Invalid {name}")
    return min(value, _MAX_LIMIT)


def _coerce_offset(value, *, name="offset"):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"Invalid {name}")
    return value


class ListeningPeriods:
    @staticmethod
    def parse_identity(identity):
        parts = identity.split(":")
        if len(parts) not in (3, 4) or parts[0] != "session":
            raise ValueError("Invalid session")
        first, last = int(parts[1]), int(parts[2])
        cutoff = datetime.fromtimestamp(int(parts[3]), timezone.utc).replace(tzinfo=None) if len(parts) == 4 else None
        return first, last, cutoff

    async def recent(self, limit=12, now=None):
        limit = _coerce_limit(limit, default=12, name="limit")
        now = now or datetime.now(timezone.utc)
        # Carry the query boundary in the route: opening an older card must
        # retain the same boundary, including a period crossing 90 days.
        cutoff_epoch = int((now - timedelta(days=90)).timestamp())
        cutoff = datetime.fromtimestamp(cutoff_epoch, timezone.utc).replace(tzinfo=None).isoformat(sep=" ")
        # A new period begins when more than 30 minutes elapse between
        # completed listening attempts. Counts and durations are never capped.
        sql = text("""
            WITH ordered AS (
                SELECT id, video_id, played_at, listen_time_ms,
                       row_number() OVER (ORDER BY played_at, id) AS chronology,
                       lag(played_at) OVER (ORDER BY played_at, id) AS previous
                FROM play_history WHERE was_played = 1 AND played_at >= :cutoff
            ), marks AS (
                SELECT *, CASE WHEN previous IS NULL OR
                    (julianday(played_at)-julianday(previous))*1440 > 30 THEN 1 ELSE 0 END AS starts
                FROM ordered
            ), groups AS (
                SELECT *, sum(starts) OVER (ORDER BY played_at, id ROWS UNBOUNDED PRECEDING) AS period FROM marks
            ), summaries AS (
                SELECT period, min(id) AS first_id, max(id) AS last_id,
                       min(played_at) AS first_at, max(played_at) AS last_at,
                       count(*) AS tracks, sum(coalesce(listen_time_ms,0)) AS duration
                FROM groups GROUP BY period ORDER BY max(played_at) DESC LIMIT :limit
            ), covers AS (
                SELECT g.period, coalesce(nullif(s.thumbnail_url,''), d.thumbnail_url, '') AS url,
                       min(g.chronology) AS first_order, min(g.video_id) AS video_id
                FROM groups g JOIN summaries ON summaries.period = g.period
                LEFT JOIN songs s ON s.video_id = g.video_id
                LEFT JOIN downloads d ON d.video_id = g.video_id
                GROUP BY g.period, url HAVING url != ''
            ), ranked AS (
                SELECT *, row_number() OVER (PARTITION BY period ORDER BY first_order) AS rank
                FROM covers
            )
            SELECT first_id, last_id, first_at, last_at, tracks, duration,
                   (SELECT json_group_array(json_object('thumbnail_url', url, 'videoId', video_id)) FROM
                    (SELECT url, video_id FROM ranked WHERE ranked.period = summaries.period AND rank <= 4 ORDER BY rank))
            FROM summaries ORDER BY last_at DESC
        """)
        async with get_session() as session:
            rows = (await session.execute(sql, {"cutoff": cutoff, "limit": limit})).all()
        return [dict(first_id=r[0], last_id=r[1], first_at=r[2], last_at=r[3],
                     track_count=r[4], listen_time_ms=r[5], title=f"{r[4]} canciones · {int(r[5] or 0)//60000} min",
                     subtitle=str(r[2])[:16] + " – " + str(r[3])[11:16],
                     navigate=f"playlist?id=session:{r[0]}:{r[1]}:{cutoff_epoch}",
                     **cover_fields(json.loads(r[6] or "[]"))) for r in rows]

    async def tracks(self, first_id, last_id, cutoff=None, *, limit=None, offset=0):
        """Chronological tracks of a listening period with SQL page pushdown.

        Membership keeps the REC-03C.2 window-function semantics: IDs are
        stable route markers (interleaved import IDs supported), history is
        never written and the final order is ``(played_at, id)``. When a
        small page is requested, ``LIMIT :limit OFFSET :offset`` is applied
        to the period-members CTE in SQLite, so only the page's rows are
        materialized (the old implementation loaded every member's
        History/Song/Download rows and sliced in Python). ``limit=None``
        keeps the legacy full-materialize contract used by
        ``save_as_playlist``/full views; chunked IN-fetches (≤500 ids) still
        respect SQLite variable limits, and the same Python sort keeps the
        sequence identical regardless of chunk boundaries.
        """
        if first_id < 1 or last_id < first_id:
            return []
        offset = _coerce_offset(offset)
        if limit is not None:
            limit = _coerce_limit(limit, default=_MAX_LIMIT, name="limit")
        params = {"first": first_id, "last": last_id,
                  "cutoff": cutoff.isoformat(sep=" ") if cutoff else None}
        # The page cut travels in SQL; `limiter` is one of two fixed literal
        # fragments (never caller-controlled text), so the f-string stays
        # safe.
        limiter = "" if limit is None else "\n                LIMIT :limit OFFSET :offset"
        if limit is not None:
            params["limit"], params["offset"] = limit, offset
        async with get_session() as session:
            # IDs are stable route markers, not a chronological range: imported
            # history can interleave the IDs of two different periods.
            page_ids = (await session.execute(text(f"""
                WITH ordered AS (
                    SELECT id, played_at,
                           lag(played_at) OVER (ORDER BY played_at, id) AS previous
                    FROM play_history WHERE was_played = 1
                        AND (:cutoff IS NULL OR played_at >= :cutoff)
                ), marks AS (
                    SELECT *, CASE WHEN previous IS NULL OR
                        (julianday(played_at)-julianday(previous))*1440 > 30 THEN 1 ELSE 0 END AS starts
                    FROM ordered
                ), groups AS (
                    SELECT id, played_at, sum(starts) OVER
                        (ORDER BY played_at, id ROWS UNBOUNDED PRECEDING) AS period FROM marks
                )
                SELECT id FROM groups WHERE period IN (
                    SELECT period FROM groups WHERE id = :first
                ) AND period IN (
                    SELECT period FROM groups WHERE id = :last
                ) ORDER BY played_at, id{limiter}
            """), params)).scalars().all()
            if not page_ids:
                return []
            # Page rows (page-sized for limit windows, full members for the
            # legacy unlimited contract). Batch the IN fetch to stay under
            # SQLite variable limits; the same (played_at, id) sort as before
            # keeps the sequence identical regardless of chunk boundaries.
            rows = []
            for start in range(0, len(page_ids), _BATCH_IDS):
                chunk = page_ids[start:start + _BATCH_IDS]
                rows.extend((await session.execute(select(H, Song, Download.file_path, Download.thumbnail_url)
                    .outerjoin(Song, Song.video_id == H.video_id)
                    .outerjoin(Download, Download.video_id == H.video_id)
                    .where(H.id.in_(chunk)))).all())
            ordered = sorted(rows, key=lambda r: (r[0].played_at, r[0].id))
            # limit windows were already cut in SQL; only the legacy full path
            # applies the offset in Python.
            page = ordered if limit is not None else ordered[offset:None]
        tracks = []
        for history, song, download_path, downloaded_thumbnail in page:
            if song:
                track = track_data(song, download_path)
            else:
                track = dict(videoId=history.video_id, title=history.title, artist=history.artist,
                             duration_ms=history.duration_ms, duration="", thumbnail_url=downloaded_thumbnail or "",
                             is_liked=False, is_downloaded=False, local_path=None)
            if not track["thumbnail_url"]:
                track["thumbnail_url"] = downloaded_thumbnail or ""
            tracks.append(track)
        return tracks

    async def save_as_playlist(self, first_id, last_id, title, cutoff=None):
        """Write command (not idempotent): snapshot a period into a new local playlist.

        Steps per existing contracts: ``ensure_songs`` (missing metadata only,
        likes/plays of known IDs untouched) → ``create_playlist`` (new uuid)
        → ``append`` (atomic, duplicates and order preserved). Empty periods
        raise before any write. If ``append`` fails, the just-created empty
        playlist is best-effort deleted so no partial playlist remains;
        ``create`` + ``append`` are still two transactions (no cross-repo
        unit in the current architecture). Retries always create a NEW
        playlist identity.
        """
        tracks = await self.tracks(first_id, last_id, cutoff)
        if not tracks:
            raise ValueError("La sesión está vacía")
        from doremi.db.repository import SongRepository
        await SongRepository().ensure_songs([
            dict(video_id=track["videoId"], title=track["title"], artist=track["artist"],
                 album=track.get("album", ""), duration_ms=track.get("duration_ms", 0),
                 thumbnail_url=track.get("thumbnail_url", "")) for track in tracks])
        local = LocalLibraryRepository()
        playlist_id = await local.create_playlist(title)
        try:
            await local.append(playlist_id, [t["videoId"] for t in tracks])
        except Exception:
            try:
                await local.delete_playlist(playlist_id)
            except Exception:
                pass
            raise
        return playlist_id


MONTHS = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")


class Wrapped:
    async def summary(self, year, month=None):
        if not 2000 <= year <= 2100 or month is not None and not 1 <= month <= 12:
            raise ValueError("Invalid period")
        start = datetime(year, month or 1, 1).astimezone()
        end = datetime(year + 1, 1, 1).astimezone() if month is None else (
            datetime(year + 1, 1, 1).astimezone() if month == 12 else datetime(year, month + 1, 1).astimezone())
        data = await ExperienceRepository().stats(start=start.astimezone(timezone.utc).replace(tzinfo=None),
                                                  end=end.astimezone(timezone.utc).replace(tzinfo=None))
        return dict(title=f"Tu {MONTHS[month-1]} en Doremi" if month else f"Tu {year} en Doremi",
                    minutes=data["listen_time_ms"] // 60000,
                    top_artist=data["top_artists"][0]["title"] if data["top_artists"] else "",
                    top_song=data["top_songs"][0]["title"] if data["top_songs"] else "",
                    top_song_thumbnail=data["top_songs"][0]["thumbnail_url"] if data["top_songs"] else "",
                    top_artist_thumbnail=data["top_artists"][0].get("thumbnail_url", "") if data["top_artists"] else "",
                    discoveries=data["discoveries"], plays=data["total_plays"])
