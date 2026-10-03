"""Local identities and playlists; never send a local ID to YouTube."""
import asyncio
import hashlib
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select, func, delete

from doremi.db.database import get_session
from doremi.db.models import Song, Collection, LocalPlaylistTrack, Download

EXTENSIONS = frozenset({".mp3", ".flac", ".ogg", ".opus", ".m4a", ".wav"})


def local_identity(path):
    return "local:" + hashlib.sha256(str(Path(path).resolve()).encode()).hexdigest()


def track_data(song, downloaded_path=None):
    path = song.local_path or downloaded_path
    available = bool(path and Path(path).is_file())
    return dict(videoId=song.video_id, title=song.title, artist=song.artist, album=song.album or "",
                thumbnail_url=song.thumbnail_url or "", duration_ms=song.duration_ms or 0,
                duration=f"{(song.duration_ms or 0)//60000}:{(song.duration_ms or 0)//1000%60:02d}",
                local_path=path if available else None, is_liked=bool(song.is_liked),
                is_downloaded=available, result_type="local" if song.local_path else "song")


class LocalLibraryRepository:
    _write_lock = None

    async def import_files(self, paths):
        # No recursive directory traversal. Explicit regular audio files only.
        def inspect():
            result = {}
            for raw in paths[:1000]:
                path = Path(raw).resolve()
                if path.suffix.lower() in EXTENSIONS and path.is_file():
                    result[local_identity(path)] = path
            return result
        files = await asyncio.to_thread(inspect)
        async with get_session() as session:
            identities = list(files)
            existing = set()
            for offset in range(0, len(identities), 500):
                existing.update((await session.scalars(select(Song.video_id).where(
                    Song.video_id.in_(identities[offset:offset + 500])))).all())
            for identity, path in files.items():
                if identity not in existing:
                    session.add(Song(video_id=identity, title=path.stem, artist="", local_path=str(path)))
            await session.commit()
        return len(files)

    async def search(self, query="", limit=100):
        async with get_session() as session:
            songs = (await session.scalars(select(Song).where(Song.local_path.is_not(None),
                Song.title.icontains(query, autoescape=True) | Song.artist.icontains(query, autoescape=True))
                .order_by(Song.title).limit(limit))).all()
        return [track_data(song) for song in songs]

    async def create_playlist(self, title):
        title = title.strip()
        if not title:
            raise ValueError("Escribe un nombre para la playlist")
        identity = "local-list:" + uuid4().hex
        async with get_session() as session:
            session.add(Collection(context_type="playlist", context_id=identity, title=title[:200]))
            await session.commit()
        return identity

    async def playlists(self):
        async with get_session() as session:
            rows = (await session.scalars(select(Collection).where(Collection.context_type == "playlist", Collection.context_id.startswith("local-list:")).order_by(Collection.title))).all()
        return [dict(id=r.context_id, title=r.title, navigate="playlist?id=" + r.context_id, thumbnail_url=r.thumbnail_url, subtitle="Playlist local") for r in rows]

    async def rename_playlist(self, identity, title):
        title = title.strip()
        if not title:
            raise ValueError("Escribe un nombre para la playlist")
        async with get_session() as session:
            collection = await session.get(Collection, ("playlist", identity))
            if not collection or not identity.startswith("local-list:"):
                raise ValueError("Playlist local inexistente")
            collection.title = title[:200]
            await session.commit()

    async def delete_playlist(self, identity):
        if not identity.startswith("local-list:"):
            raise ValueError("Solo se pueden eliminar playlists locales")
        if self.__class__._write_lock is None:
            self.__class__._write_lock = asyncio.Lock()
        async with self.__class__._write_lock:
            async with get_session() as session:
                await session.execute(delete(LocalPlaylistTrack).where(LocalPlaylistTrack.playlist_id == identity))
                await session.execute(delete(Collection).where(Collection.context_type == "playlist", Collection.context_id == identity))
                await session.commit()

    async def remove_occurrence(self, identity, position, video_id):
        if not identity.startswith("local-list:") or position < 0:
            return False
        async with get_session() as session:
            result = await session.execute(delete(LocalPlaylistTrack).where(
                LocalPlaylistTrack.playlist_id == identity, LocalPlaylistTrack.position == position,
                LocalPlaylistTrack.video_id == video_id))
            await session.commit()
            return result.rowcount == 1

    async def append(self, playlist_id, video_ids):
        # Serialize max(position)+insert within this process. SQLite commits the
        # complete append, retaining duplicate occurrences deliberately.
        if self.__class__._write_lock is None:
            self.__class__._write_lock = asyncio.Lock()
        async with self.__class__._write_lock:
            async with get_session() as session:
                collection = await session.get(Collection, ("playlist", playlist_id))
                if not collection or not playlist_id.startswith("local-list:"):
                    raise ValueError("Playlist local inexistente")
                unique_ids = list(dict.fromkeys(video_ids))
                known_ids = set()
                for offset in range(0, len(unique_ids), 500):
                    known_ids.update((await session.scalars(select(Song.video_id).where(
                        Song.video_id.in_(unique_ids[offset:offset + 500])))).all())
                if set(unique_ids) != known_ids:
                    raise ValueError("Faltan los metadatos de la canción")
                maximum = await session.scalar(select(func.max(LocalPlaylistTrack.position)).where(LocalPlaylistTrack.playlist_id == playlist_id))
                position = maximum + 1 if maximum is not None else 0
                for identity in video_ids:
                    session.add(LocalPlaylistTrack(playlist_id=playlist_id, position=position, video_id=identity))
                    position += 1
                await session.commit()

    async def tracks(self, identity):
        async with get_session() as session:
            collection = await session.get(Collection, ("playlist", identity))
            if collection is None:
                return "", []
            rows = (await session.execute(select(Song, Download.file_path, LocalPlaylistTrack.position).join(LocalPlaylistTrack, LocalPlaylistTrack.video_id == Song.video_id)
                .outerjoin(Download, Download.video_id == Song.video_id).where(LocalPlaylistTrack.playlist_id == identity)
                .order_by(LocalPlaylistTrack.position))).all()
            title = collection.title
        return title, [dict(track_data(song, path), local_position=position) for song, path, position in rows]
