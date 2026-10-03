"""Product listening periods and calendar summaries derived from PlayHistory."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text, select

from doremi.db.database import get_session
from doremi.db.models import PlayHistory as H, Song, Download
from doremi.db.experience_repository import ExperienceRepository
from doremi.db.local_library_repository import LocalLibraryRepository, track_data


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
        now = now or datetime.now(timezone.utc)
        # Carry the query boundary in the route: opening an older card must
        # group exactly the same events, including a period crossing 90 days.
        cutoff_epoch = int((now - timedelta(days=90)).timestamp())
        cutoff = datetime.fromtimestamp(cutoff_epoch, timezone.utc).replace(tzinfo=None).isoformat(sep=" ")
        # A new period begins when more than 30 minutes elapse between
        # completed listening attempts. Counts and durations are never capped.
        sql = text("""
            WITH ordered AS (
                SELECT id, played_at, listen_time_ms,
                       lag(played_at) OVER (ORDER BY played_at, id) AS previous
                FROM play_history WHERE was_played = 1 AND played_at >= :cutoff
            ), marks AS (
                SELECT *, CASE WHEN previous IS NULL OR
                    (julianday(played_at)-julianday(previous))*1440 > 30 THEN 1 ELSE 0 END AS starts
                FROM ordered
            ), groups AS (
                SELECT *, sum(starts) OVER (ORDER BY played_at, id ROWS UNBOUNDED PRECEDING) AS period FROM marks
            )
            SELECT min(id), max(id), min(played_at), max(played_at), count(*),
                   sum(coalesce(listen_time_ms,0)) FROM groups GROUP BY period
            ORDER BY max(played_at) DESC LIMIT :limit
        """)
        async with get_session() as session:
            rows = (await session.execute(sql, {"cutoff": cutoff, "limit": limit})).all()
        return [dict(first_id=r[0], last_id=r[1], first_at=r[2], last_at=r[3],
                     track_count=r[4], listen_time_ms=r[5], title=f"{r[4]} canciones · {int(r[5] or 0)//60000} min",
                     subtitle=str(r[2])[:16] + " – " + str(r[3])[11:16],
                     navigate=f"playlist?id=session:{r[0]}:{r[1]}:{cutoff_epoch}") for r in rows]

    async def tracks(self, first_id, last_id, cutoff=None):
        if first_id < 1 or last_id < first_id:
            return []
        async with get_session() as session:
            # IDs are stable route markers, not a chronological range: imported
            # history can interleave the IDs of two different periods.
            member_ids = (await session.execute(text("""
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
                    SELECT id, sum(starts) OVER
                        (ORDER BY played_at, id ROWS UNBOUNDED PRECEDING) AS period FROM marks
                ), bounds AS (
                    SELECT period, min(id) AS first_id, max(id) AS last_id
                    FROM groups GROUP BY period
                )
                SELECT id FROM groups WHERE period IN (
                    SELECT period FROM bounds WHERE first_id = :first AND last_id = :last
                )
            """), {"first": first_id, "last": last_id,
                    "cutoff": cutoff.isoformat(sep=" ") if cutoff else None})).scalars().all()
            if not member_ids:
                return []
            rows = (await session.execute(select(H, Song, Download.file_path)
                .outerjoin(Song, Song.video_id == H.video_id)
                .outerjoin(Download, Download.video_id == H.video_id)
                .where(H.id.in_(member_ids))
                .order_by(H.played_at, H.id))).all()
        tracks = []
        for history, song, download_path in rows:
            if song:
                track = track_data(song, download_path)
            else:
                track = dict(videoId=history.video_id, title=history.title, artist=history.artist,
                             duration_ms=history.duration_ms, duration="", thumbnail_url="",
                             is_liked=False, is_downloaded=False, local_path=None)
            tracks.append(track)
        return tracks

    async def save_as_playlist(self, first_id, last_id, title, cutoff=None):
        tracks = await self.tracks(first_id, last_id, cutoff)
        if not tracks:
            raise ValueError("La sesión está vacía")
        from doremi.db.repository import SongRepository
        repo = SongRepository()
        for track in tracks:
            if not await repo.get_song(track["videoId"]):
                await repo.upsert_song(video_id=track["videoId"], title=track["title"], artist=track["artist"])
        local = LocalLibraryRepository()
        playlist_id = await local.create_playlist(title)
        await local.append(playlist_id, [t["videoId"] for t in tracks])
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
                    discoveries=data["discoveries"], plays=data["total_plays"])
