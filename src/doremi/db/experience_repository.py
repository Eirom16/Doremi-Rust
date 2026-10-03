"""Bounded, aggregated product queries; history remains the source of truth."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, parse_qs, urlsplit

from sqlalchemy import select, func, case, and_, tuple_

from doremi.db.database import get_session
from doremi.db.models import Song, PlayHistory as H, Download, Collection

SMART_TITLES = {
    "repeat": "En repetición", "recent": "Últimamente", "liked": "Favoritas",
    "discoveries": "Descubrimientos", "forgotten": "Olvidadas", "offline": "Descargadas",
}


def collection_route(kind, identity):
    return ("playlist" if kind == "smart" else kind) + "?" + urlencode({"id": identity})


def period_bounds(period, now=None):
    """Local calendar periods, half-open UTC boundaries. Week begins Monday."""
    local_calendar = now is None
    now = now or datetime.now().astimezone()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    starts = {
        "today": midnight, "week": midnight - timedelta(days=midnight.weekday()),
        "month": midnight.replace(day=1), "year": midnight.replace(month=1, day=1),
    }
    if period not in {*starts, "all"}:
        raise ValueError("Unknown period")
    start = starts.get(period)
    if start and local_calendar:
        start = start.replace(tzinfo=None).astimezone()
    return (start.astimezone(timezone.utc).replace(tzinfo=None) if start else None,
            now.astimezone(timezone.utc).replace(tzinfo=None))


class ExperienceRepository:
    async def pinned_routes(self):
        async with get_session() as session:
            rows = (await session.scalars(select(Collection).where(Collection.pinned_at.is_not(None))
                .order_by(Collection.position, Collection.pinned_at))).all()
        return [collection_route(row.context_type, row.context_id) for row in rows]

    async def is_pinned(self, identity, kind="playlist"):
        async with get_session() as session:
            entry = await session.get(Collection, (kind, identity))
            return bool(entry and entry.pinned_at is not None)

    async def remember_collections(self, items):
        candidates = {}
        for item in items:
            route = urlsplit(item.get("navigate", ""))
            identity = parse_qs(route.query).get("id", [""])[-1]
            if route.path in {"playlist", "album", "artist"} and identity:
                candidates[(route.path, identity)] = item
        keys = list(candidates)
        async with get_session() as session:
            known = {}
            for offset in range(0, len(keys), 250):
                entries = (await session.scalars(select(Collection).where(
                    tuple_(Collection.context_type, Collection.context_id).in_(keys[offset:offset + 250])))).all()
                known.update({(entry.context_type, entry.context_id): entry for entry in entries})
            for key, item in candidates.items():
                entry = known.get(key)
                if entry is None:
                    entry = Collection(context_type=key[0], context_id=key[1])
                    session.add(entry)
                entry.title = item.get("title", "")
                entry.thumbnail_url = item.get("thumbnail_url", "")
            await session.commit()

    async def set_pin(self, identity, title, thumbnail="", *, kind="playlist", pinned=True):
        if kind not in {"playlist", "album", "artist"} or not identity or identity.startswith("session:"):
            raise ValueError("Invalid collection")
        async with get_session() as session:
            entry = await session.get(Collection, (kind, identity))
            if entry is None:
                entry = Collection(context_type=kind, context_id=identity, title=title, thumbnail_url=thumbnail)
                session.add(entry)
            if pinned and entry.pinned_at is None:
                entry.pinned_at = datetime.now(timezone.utc)
                entry.position = (await session.scalar(select(func.max(Collection.position))) or 0) + 1
            elif not pinned:
                entry.pinned_at = entry.position = None
            await session.commit()

    async def reorder_pins(self, identities):
        """Require the complete current pin set to reject stale/forged drops."""
        async with get_session() as session:
            entries = list((await session.scalars(select(Collection).where(Collection.pinned_at.is_not(None)))).all())
            by_route = {collection_route(e.context_type, e.context_id): e for e in entries}
            if len(identities) != len(set(identities)) or set(identities) != set(by_route):
                return False
            for position, route in enumerate(identities):
                by_route[route].position = position
            await session.commit()
            return True

    async def quick_access(self, limit=6):
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=90)
        activity = select(
            H.context_type.label("kind"), H.context_id.label("identity"),
            func.sum(case((H.was_played.is_(True), 1), else_=0)).label("plays"),
            func.max(H.played_at).label("recent"),
        ).where(H.played_at >= cutoff).group_by(H.context_type, H.context_id).subquery()
        async with get_session() as session:
            entries = (await session.scalars(select(Collection).outerjoin(activity, and_(
                Collection.context_type == activity.c.kind, Collection.context_id == activity.c.identity,
            )).where(Collection.context_type == "playlist", ~Collection.context_id.startswith("session:"))
                .order_by(Collection.pinned_at.is_not(None).desc(), Collection.position.asc(),
                          func.coalesce(activity.c.plays, 0).desc(), activity.c.recent.desc(), Collection.title.asc())
                .limit(limit))).all()
            return [dict(title=e.title, item_title=e.title, type=e.context_type,
                         thumbnail_url=e.thumbnail_url, navigate=collection_route(e.context_type, e.context_id),
                         pinned=e.pinned_at is not None, subtitle="") for e in entries]

    async def continue_listening(self, limit=4, *, offline_only=False):
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=14)
        # The latest attempt wins, including skips. Never resume an older attempt
        # after the user has completed or deliberately skipped that collection.
        latest = select(H.id.label("id"), func.row_number().over(
            partition_by=(H.context_type, H.context_id),
            order_by=(H.played_at.desc(), H.id.desc())).label("rank")).where(
            H.context_type.in_(["playlist", "album", "smart"]), H.context_id != "",
            H.played_at >= cutoff,
        ).subquery()
        async with get_session() as session:
            query = select(H, Collection, Song.thumbnail_url, Song.local_path, Download.file_path)
            query = (query
                .join(latest, and_(latest.c.id == H.id, latest.c.rank == 1))
                .join(Collection, and_(Collection.context_type == H.context_type, Collection.context_id == H.context_id))
                .outerjoin(Song, Song.video_id == H.video_id)
                .outerjoin(Download, Download.video_id == H.video_id)
                .where(H.was_played.is_(True), (H.skip_count == 0) | H.completed.is_(True)))
            if offline_only:
                query = query.where(H.context_type.in_(["playlist", "smart"]),
                    H.context_id.startswith("local-list:") | H.context_id.startswith("local_") | H.context_id.startswith("smart:"),
                    Song.local_path.is_not(None) | Download.file_path.is_not(None))
            rows = (await session.execute(query.order_by(H.played_at.desc()).limit(limit))).all()
            return [dict(title=c.title, subtitle=h.title, thumbnail_url=c.thumbnail_url or thumb or "",
                         navigate=collection_route(h.context_type, h.context_id), video_id=h.video_id,
                         position_ms=h.position_ms if not h.completed and not h.skip_count else 0,
                         completed=bool(h.completed)) for h, c, thumb, local_path, download_path in rows
                    if not offline_only or (local_path or download_path) and Path(local_path or download_path).is_file()]

    async def smart_tracks(self, rule, limit=100, now=None, *, offline_only=False):
        if rule not in SMART_TITLES:
            raise ValueError("Unknown smart playlist")
        now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        if now.tzinfo:
            now = now.astimezone(timezone.utc).replace(tzinfo=None)
        valid = H.was_played.is_(True)
        recent = H.played_at >= now - timedelta(days=30)
        # Completion for scoring uses actual listening, so seeking to the end
        # cannot manufacture affinity. Each attempt contributes at most 1.
        completion = case((H.duration_ms > 0, func.min(1.0, H.listen_time_ms * 1.0 / H.duration_ms)), else_=0.0)
        affinity = case((and_(valid, recent), 2 + completion + func.min(H.listen_time_ms / 60000.0, 5.0)), else_=0)
        agg = select(H.video_id.label("video_id"), func.sum(affinity).label("score"),
                     func.sum(case((valid, 1), else_=0)).label("plays"),
                     func.max(case((valid, H.played_at))).label("recent"),
                     func.min(case((valid, H.played_at))).label("first")) .group_by(H.video_id).subquery()
        query = select(Song, Download.file_path, agg.c.score).outerjoin(agg, agg.c.video_id == Song.video_id).outerjoin(Download, Download.video_id == Song.video_id)
        if offline_only:
            query = query.where(Download.file_path.is_not(None) | Song.local_path.is_not(None))
        if rule == "liked":
            query = query.where(Song.is_liked.is_(True)).order_by(agg.c.recent.desc())
        elif rule == "offline":
            query = query.where(Download.file_path.is_not(None) | Song.local_path.is_not(None)).order_by(Download.downloaded_at.desc())
        elif rule == "forgotten":
            query = query.where(agg.c.plays >= 3, agg.c.recent < now - timedelta(days=60)).order_by(agg.c.plays.desc())
        elif rule == "discoveries":
            query = query.where(agg.c.first >= now - timedelta(days=30), agg.c.score >= 3).order_by(agg.c.score.desc())
        elif rule == "recent":
            query = query.where(agg.c.recent.is_not(None)).order_by(agg.c.recent.desc())
        else:
            query = query.where(agg.c.score > 0).order_by(agg.c.score.desc(), agg.c.recent.desc())
        async with get_session() as session:
            rows = (await session.execute(query.order_by(Song.video_id).limit(limit))).all()
        result = []
        for song, path, score in rows:
            path = song.local_path or path
            available = bool(path and Path(path).is_file())
            if (rule == "offline" or offline_only) and not available:
                continue
            result.append(dict(videoId=song.video_id, title=song.title, artist=song.artist, album=song.album,
                               duration_ms=song.duration_ms or 0, thumbnail_url=song.thumbnail_url or "",
                               duration=f"{(song.duration_ms or 0)//60000}:{(song.duration_ms or 0)//1000%60:02d}",
                               is_liked=bool(song.is_liked), is_downloaded=available,
                               local_path=path if available else None, score=score or 0))
        return result

    async def stats(self, period="all", *, start=None, end=None):
        if end is None:
            start, end = period_bounds(period)
        conditions = [H.played_at < end]
        if start is not None:
            conditions.append(H.played_at >= start)
        valid = H.was_played.is_(True)
        last_day = (end - timedelta(microseconds=1)).replace(tzinfo=timezone.utc).astimezone().date()
        known_artist = func.trim(H.artist).not_in(("", "Unknown", "Unknown Artist"))
        first_day = last_day - timedelta(days=30)
        if start:
            first_day = max(first_day, start.replace(tzinfo=timezone.utc).astimezone().date())
        chart_start = datetime.combine(first_day, datetime.min.time()).astimezone().astimezone(timezone.utc).replace(tzinfo=None)
        async with get_session() as session:
            row = (await session.execute(select(
                func.coalesce(func.sum(H.listen_time_ms), 0),
                func.count(case((valid, H.id))),
                func.count(func.distinct(case((valid, H.video_id)))),
                func.count(func.distinct(case((and_(valid, known_artist), H.artist)))),
                func.avg(case((H.duration_ms > 0, func.min(1.0, H.listen_time_ms * 1.0 / H.duration_ms)))),
                func.avg(case((H.skip_count > 0, 1.0), else_=0.0)),
            ).where(*conditions))).one()
            songs = (await session.execute(select(H.video_id, H.title, H.artist, func.count(H.id).label("plays"), Song.thumbnail_url, Song.is_liked)
                .outerjoin(Song, Song.video_id == H.video_id).where(*conditions, valid)
                .group_by(H.video_id).order_by(func.count(H.id).desc(), H.video_id).limit(5))).all()
            artists = (await session.execute(select(H.artist, func.count()).where(*conditions, valid, known_artist)
                .group_by(H.artist).order_by(func.count().desc()).limit(5))).all()
            collections = (await session.execute(select(H.context_type, H.context_id, Collection.title, func.count())
                .join(Collection, and_(H.context_type == Collection.context_type, H.context_id == Collection.context_id))
                .where(*conditions, valid, H.context_type.in_(["album", "playlist"]),
                       ~H.context_id.startswith("session:"))
                .group_by(H.context_type, H.context_id).order_by(func.count().desc()).limit(10))).all()
            day_expr = func.date(H.played_at, "localtime")
            days = (await session.execute(select(day_expr, func.count())
                .where(*conditions, valid, H.played_at >= chart_start).group_by(day_expr))).all()
            hour_expr = func.strftime("%H", H.played_at, "localtime")
            peak_hour = (await session.execute(select(hour_expr, func.count())
                .where(*conditions, valid).group_by(hour_expr)
                .order_by(func.count().desc(), hour_expr).limit(1))).first()
            active_day = (await session.execute(select(day_expr, func.count())
                .where(*conditions, valid).group_by(day_expr)
                .order_by(func.count().desc(), day_expr.desc()).limit(1))).first()
            firsts = select(func.min(H.played_at).label("first")).where(valid).group_by(H.video_id).subquery()
            discoveries_query = select(func.count()).select_from(firsts).where(firsts.c.first < end)
            if start is not None:
                discoveries_query = discoveries_query.where(firsts.c.first >= start)
            discoveries = await session.scalar(discoveries_query)
        minutes = int(row[0]) // 60000
        from doremi.db.repository import DownloadRepository
        available = await DownloadRepository().get_available_video_ids([s[0] for s in songs])
        day_counts = dict(days)
        chart_days = [first_day + timedelta(days=offset) for offset in range((last_day-first_day).days+1)]
        return dict(time_listened=f"{minutes//60}h {minutes%60}m" if minutes >= 60 else f"{minutes}m",
                    listen_time_ms=int(row[0]), total_plays=row[1], unique_songs=row[2], unique_artists=row[3],
                    completion_rate=row[4], skip_rate=row[5], discoveries=discoveries,
                    top_songs=[dict(videoId=s[0], title=s[1], artist=s[2], plays=s[3], thumbnail_url=s[4] or "", is_liked=bool(s[5]), is_downloaded=s[0] in available) for s in songs],
                    top_artists=[dict(title=a, plays=n) for a, n in artists],
                    top_collections=[dict(type=k, title=t, plays=n, navigate=collection_route(k, i)) for k, i, t, n in collections],
                    peak_hour=dict(hour=peak_hour[0], plays=peak_hour[1]) if peak_hour else {},
                    active_day=dict(day=active_day[0], plays=active_day[1]) if active_day else {},
                    chart_days=len(chart_days),
                    chart=[dict(day=d.strftime("%d/%m"), count=day_counts.get(d.isoformat(), 0)) for d in chart_days], _error="")
