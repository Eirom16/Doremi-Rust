from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from doremi.db.database import get_session
from doremi.db.models import Song, PlayHistory, Download, Notification, CachedArtwork


class SongRepository:

    async def upsert_song(self, **kwargs) -> Song:
        async with get_session() as session:
            video_id = kwargs.get("video_id")
            result = await session.execute(
                select(Song).where(Song.video_id == video_id)
            )
            song = result.scalar_one_or_none()
            if song:
                for k, v in kwargs.items():
                    setattr(song, k, v)
            else:
                song = Song(**kwargs)
                session.add(song)
            await session.commit()
            await session.refresh(song)
            return song

    async def get_song(self, video_id: str) -> Song | None:
        async with get_session() as session:
            result = await session.execute(
                select(Song).where(Song.video_id == video_id)
            )
            return result.scalar_one_or_none()

    async def get_liked_songs(self) -> list[Song]:
        async with get_session() as session:
            result = await session.execute(
                select(Song).where(Song.is_liked == True).order_by(Song.last_played.desc())
            )
            return list(result.scalars().all())

    async def get_liked_video_ids(self) -> set[str]:
        """Return a set of video_ids for all liked songs (efficient for batch UI checks)."""
        async with get_session() as session:
            result = await session.execute(
                select(Song.video_id).where(Song.is_liked == True)
            )
            return set(result.scalars().all())

    async def get_all_songs(self) -> list[Song]:
        async with get_session() as session:
            result = await session.execute(
                select(Song).order_by(Song.last_played.desc())
            )
            return list(result.scalars().all())

    async def get_songs_by_video_ids(self, video_ids: list[str]) -> list[Song]:
        if not video_ids:
            return []
        async with get_session() as session:
            result = await session.execute(
                select(Song).where(Song.video_id.in_(video_ids))
            )
            return list(result.scalars().all())

    async def search_songs(self, query: str, limit: int = 100) -> list[Song]:
        pattern = f"%{query.strip()}%"
        async with get_session() as session:
            result = await session.execute(
                select(Song)
                .where(Song.title.ilike(pattern) | Song.artist.ilike(pattern) | Song.album.ilike(pattern))
                .order_by(Song.last_played.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def delete_song(self, video_id: str) -> bool:
        async with get_session() as session:
            result = await session.execute(
                delete(Song).where(Song.video_id == video_id)
            )
            await session.commit()
            return bool(result.rowcount)

    async def record_play(self, video_id: str) -> None:
        async with get_session() as session:
            result = await session.execute(
                select(Song).where(Song.video_id == video_id)
            )
            song = result.scalar_one_or_none()
            if song:
                from datetime import datetime, timezone
                song.play_count += 1
                song.last_played = datetime.now(timezone.utc)
                await session.commit()

    async def toggle_like(self, video_id: str) -> bool:
        async with get_session() as session:
            result = await session.execute(
                select(Song).where(Song.video_id == video_id)
            )
            song = result.scalar_one_or_none()
            if song:
                song.is_liked = not song.is_liked
                liked = song.is_liked
                await session.commit()
                return liked
            return False


class HistoryRepository:

    async def add_entry(self, video_id: str, title: str, artist: str, duration_ms: int) -> None:
        async with get_session() as session:
            entry = PlayHistory(
                video_id=video_id, title=title, artist=artist, duration_ms=duration_ms
            )
            session.add(entry)
            await session.commit()

    async def get_history(self, limit: int = 100) -> list[tuple[PlayHistory, str | None]]:
        async with get_session() as session:
            result = await session.execute(
                select(PlayHistory, Song.thumbnail_url)
                .outerjoin(Song, PlayHistory.video_id == Song.video_id)
                .order_by(PlayHistory.played_at.desc())
                .limit(limit)
            )
            return list(result.all())

    async def clear_history(self) -> int:
        async with get_session() as session:
            result = await session.execute(delete(PlayHistory))
            await session.commit()
            return int(result.rowcount or 0)

    async def delete_entry(self, entry_id: int) -> bool:
        async with get_session() as session:
            result = await session.execute(
                delete(PlayHistory).where(PlayHistory.id == entry_id)
            )
            await session.commit()
            return bool(result.rowcount)

    async def get_history_by_date_range(
        self, start: datetime, end: datetime, limit: int = 100
    ) -> list[tuple[PlayHistory, str | None]]:
        async with get_session() as session:
            result = await session.execute(
                select(PlayHistory, Song.thumbnail_url)
                .outerjoin(Song, PlayHistory.video_id == Song.video_id)
                .where(PlayHistory.played_at >= start, PlayHistory.played_at <= end)
                .order_by(PlayHistory.played_at.desc())
                .limit(limit)
            )
            return list(result.all())

    async def get_history_count(self) -> int:
        async with get_session() as session:
            result = await session.execute(select(func.count()).select_from(PlayHistory))
            return int(result.scalar_one() or 0)


class DownloadRepository:

    async def get_download(self, video_id: str) -> Download | None:
        async with get_session() as session:
            result = await session.execute(
                select(Download).where(Download.video_id == video_id)
            )
            return result.scalar_one_or_none()

    async def add_download(self, **kwargs) -> Download:
        async with get_session() as session:
            video_id = kwargs.get("video_id")
            result = await session.execute(
                select(Download).where(Download.video_id == video_id)
            )
            download = result.scalar_one_or_none()
            if download:
                for k, v in kwargs.items():
                    setattr(download, k, v)
            else:
                download = Download(**kwargs)
                session.add(download)
            await session.commit()
            await session.refresh(download)
            return download

    async def get_downloads(self) -> list[Download]:
        async with get_session() as session:
            result = await session.execute(select(Download).order_by(Download.downloaded_at.desc()))
            return list(result.scalars().all())

    async def get_downloads_by_playlist(self, playlist_id: str) -> list[Download]:
        async with get_session() as session:
            result = await session.execute(
                select(Download)
                .where(Download.parent_playlist_id == playlist_id)
                .order_by(Download.downloaded_at.desc())
            )
            return list(result.scalars().all())

    async def search_downloads(self, query: str, limit: int = 100) -> list[Download]:
        pattern = f"%{query.strip()}%"
        async with get_session() as session:
            result = await session.execute(
                select(Download)
                .where(
                    Download.title.ilike(pattern)
                    | Download.artist.ilike(pattern)
                    | Download.album.ilike(pattern)
                    | Download.parent_playlist_title.ilike(pattern)
                )
                .order_by(Download.downloaded_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def count_downloads(self) -> int:
        async with get_session() as session:
            result = await session.execute(select(func.count()).select_from(Download))
            return int(result.scalar_one() or 0)

    async def remove_download(self, video_id: str) -> bool:
        async with get_session() as session:
            result = await session.execute(
                select(Download).where(Download.video_id == video_id)
            )
            download = result.scalar_one_or_none()
            if download:
                await session.delete(download)
                await session.commit()
                return True
            return False

    async def remove_downloads(self, video_ids: list[str]) -> int:
        if not video_ids:
            return 0
        async with get_session() as session:
            result = await session.execute(
                delete(Download).where(Download.video_id.in_(video_ids))
            )
            await session.commit()
            return int(result.rowcount or 0)


class NotificationRepository:

    async def add_if_new(
        self,
        video_id: str,
        title: str,
        artist: str,
        thumbnail_url: str = "",
        created_at: datetime | None = None,
        artist_id: str | None = None,
    ) -> bool:
        async with get_session() as session:
            result = await session.execute(
                select(Notification).where(Notification.video_id == video_id)
            )
            if result.scalar_one_or_none():
                return False

            notification = Notification(
                video_id=video_id,
                title=title,
                artist=artist,
                artist_id=artist_id,
                thumbnail_url=thumbnail_url,
                created_at=created_at or datetime.now(timezone.utc),
                is_read=False,
            )
            session.add(notification)
            await session.commit()
            return True

    async def get_recent(self, limit: int = 20) -> list[Notification]:
        async with get_session() as session:
            result = await session.execute(
                select(Notification).order_by(Notification.created_at.desc()).limit(limit)
            )
            return list(result.scalars().all())

    async def mark_all_read(self) -> int:
        async with get_session() as session:
            result = await session.execute(
                select(Notification).where(Notification.is_read == False)
            )
            notifications = list(result.scalars().all())
            for notification in notifications:
                notification.is_read = True
            await session.commit()
            return len(notifications)

    async def has_unread(self) -> bool:
        async with get_session() as session:
            result = await session.execute(
                select(Notification.id).where(Notification.is_read == False).limit(1)
            )
            return result.scalar_one_or_none() is not None

    async def delete_old(self, days: int = 30) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        async with get_session() as session:
            result = await session.execute(
                delete(Notification).where(Notification.created_at < cutoff)
            )
            await session.commit()
            return int(result.rowcount or 0)


class CachedArtworkRepository:

    async def upsert_artwork(
        self,
        url: str,
        local_path: str,
        cached_at: datetime | None = None,
    ) -> CachedArtwork:
        async with get_session() as session:
            result = await session.execute(
                select(CachedArtwork).where(CachedArtwork.url == url)
            )
            artwork = result.scalar_one_or_none()
            if artwork:
                artwork.local_path = local_path
                artwork.cached_at = cached_at or datetime.now(timezone.utc)
            else:
                artwork = CachedArtwork(
                    url=url,
                    local_path=local_path,
                    cached_at=cached_at or datetime.now(timezone.utc),
                )
                session.add(artwork)
            await session.commit()
            await session.refresh(artwork)
            return artwork

    async def get_artwork(self, url: str) -> CachedArtwork | None:
        async with get_session() as session:
            result = await session.execute(
                select(CachedArtwork).where(CachedArtwork.url == url)
            )
            return result.scalar_one_or_none()

    async def delete_artwork(self, url: str) -> bool:
        async with get_session() as session:
            result = await session.execute(
                delete(CachedArtwork).where(CachedArtwork.url == url)
            )
            await session.commit()
            return bool(result.rowcount)

    async def delete_old(self, days: int = 30) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        async with get_session() as session:
            result = await session.execute(
                delete(CachedArtwork).where(CachedArtwork.cached_at < cutoff)
            )
            await session.commit()
            return int(result.rowcount or 0)
