"""Local identities and playlists; never send a local ID to YouTube.

REC-03B recovery from rescue working tree
(``~/Proyectos/Doremi/Doremi-Rust-Rescate``,
``src/doremi/db/local_library_repository.py``, 189 lines,
sha256 e9d226e5…, untracked modifications over rescue commit
``11f15a8 feat: add playback origins, listening insights and local collections``).

Adaptations vs rescue (no schema/migration changes):
- explicit ``rollback`` on every failing write (REC-02 ``get_session`` does
  not auto-rollback);
- input validation (titles, identities, limits, video ids, paths);
- bounded limits (``search`` 1..1000, ``tracks`` optional pagination);
- early returns for empty inputs to avoid ``IN ()`` round-trips;
- ``read_metadata`` stays off the event loop via ``asyncio.to_thread``
  (REC-03A sync design: future Qt consumers must never call it on the
  Qt main thread);
- no network, no QML/Qt, no file deletes/rewrites (only reads + thumbnail
  cache writes under ``AppDirs.artwork_cache``, frozen-safe).
"""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, func, select

from doremi.db.database import get_session
from doremi.db.models import Collection, Download, LocalPlaylistTrack, Song
from doremi.services.artwork import cover_fields
from doremi.services.local_metadata import read_metadata

EXTENSIONS = frozenset({".mp3", ".flac", ".ogg", ".opus", ".m4a", ".wav"})

_MAX_IMPORT = 1000
_MAX_SEARCH = 1000
_MAX_TRACK_LIMIT = 1000
_BATCH_SONGS = 500
_BATCH_COVERS = 250


def _coerce_limit(value: int, *, default: int, maximum: int, name: str) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Invalid {name}")
    if value <= 0:
        raise ValueError(f"Invalid {name}")
    return min(value, maximum)


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
        # Synchronous tag reads run in a worker thread so future Qt callers
        # never block the Qt main thread.
        if paths is None or not isinstance(paths, (list, tuple)):
            raise ValueError("Invalid paths")
        queued = list(paths[:_MAX_IMPORT])

        def inspect():
            result = {}
            for raw in queued:
                try:
                    path = Path(raw).resolve()
                except (OSError, ValueError):
                    continue
                if path.suffix.lower() in EXTENSIONS and path.is_file():
                    try:
                        result[local_identity(path)] = (path, read_metadata(path))
                    except (OSError, ValueError):
                        continue
            return result

        files = await asyncio.to_thread(inspect)
        if not files:
            return 0
        async with get_session() as session:
            try:
                identities = list(files)
                existing = {}
                for offset in range(0, len(identities), _BATCH_SONGS):
                    existing.update({song.video_id: song for song in (await session.scalars(select(Song).where(
                        Song.video_id.in_(identities[offset:offset + _BATCH_SONGS])))).all()})
                for identity, (path, metadata) in files.items():
                    song = existing.get(identity)
                    if song is None:
                        song = Song(video_id=identity, local_path=str(path))
                        session.add(song)
                    if not isinstance(metadata, dict):
                        continue
                    for field, value in metadata.items():
                        if not hasattr(song, field):
                            continue
                        # Reimport enriches old imports without erasing useful tags.
                        if value or not getattr(song, field):
                            setattr(song, field, value)
                await session.flush()
                affected = (await session.scalars(select(LocalPlaylistTrack.playlist_id).where(
                    LocalPlaylistTrack.video_id.in_(identities)).distinct())).all()
                for playlist_id in affected:
                    await self._refresh_cover(session, playlist_id)
                await session.commit()
            except Exception:
                try:
                    await session.rollback()
                except Exception:
                    pass
                raise
        return len(files)

    async def search(self, query="", limit=100):
        if query is None:
            query = ""
        if not isinstance(query, str):
            raise ValueError("Invalid query")
        limit = _coerce_limit(limit, default=100, maximum=_MAX_SEARCH, name="limit")
        async with get_session() as session:
            songs = (await session.scalars(select(Song).where(Song.local_path.is_not(None),
                Song.title.icontains(query, autoescape=True) | Song.artist.icontains(query, autoescape=True))
                .order_by(Song.title).limit(limit))).all()
        return [track_data(song) for song in songs]

    async def create_playlist(self, title):
        if not isinstance(title, str):
            raise ValueError("Escribe un nombre para la playlist")
        title = title.strip()
        if not title:
            raise ValueError("Escribe un nombre para la playlist")
        identity = "local-list:" + uuid4().hex
        async with get_session() as session:
            try:
                session.add(Collection(context_type="playlist", context_id=identity, title=title[:200]))
                await session.commit()
            except Exception:
                try:
                    await session.rollback()
                except Exception:
                    pass
                raise
        return identity

    async def playlists(self):
        async with get_session() as session:
            rows = (await session.scalars(select(Collection).where(Collection.context_type == "playlist", Collection.context_id.startswith("local-list:")).order_by(Collection.title))).all()
            covers = await self.cover_map(session, [r.context_id for r in rows])
        return [dict(id=r.context_id, title=r.title, navigate="playlist?id=" + r.context_id,
                     **covers.get(r.context_id, cover_fields([], r.thumbnail_url)), subtitle="Playlist local") for r in rows]

    @staticmethod
    async def cover_map(session, identities):
        if not identities:
            return {}
        covers = {}
        for offset in range(0, len(identities), _BATCH_COVERS):
            unique = select(LocalPlaylistTrack.playlist_id.label("identity"),
                Song.thumbnail_url.label("url"), func.min(Song.video_id).label("video_id"),
                func.min(LocalPlaylistTrack.position).label("position")).join(
                Song, Song.video_id == LocalPlaylistTrack.video_id).where(
                LocalPlaylistTrack.playlist_id.in_(identities[offset:offset + _BATCH_COVERS]),
                Song.thumbnail_url != "").group_by(LocalPlaylistTrack.playlist_id, Song.thumbnail_url).subquery()
            ranked = select(unique, func.row_number().over(partition_by=unique.c.identity,
                order_by=(unique.c.position, unique.c.url)).label("rank")).subquery()
            rows = (await session.execute(select(ranked.c.identity, ranked.c.url, ranked.c.video_id)
                .where(ranked.c.rank <= 4).order_by(ranked.c.identity, ranked.c.rank))).all()
            tracks = {}
            for identity, url, video_id in rows:
                tracks.setdefault(identity, []).append(dict(videoId=video_id, thumbnail_url=url))
            covers.update({identity: cover_fields(items) for identity, items in tracks.items()})
        return covers

    async def rename_playlist(self, identity, title):
        if not isinstance(identity, str) or not isinstance(title, str):
            raise ValueError("Playlist local inexistente")
        title = title.strip()
        if not title:
            raise ValueError("Escribe un nombre para la playlist")
        async with get_session() as session:
            try:
                collection = await session.get(Collection, ("playlist", identity))
                if not collection or not identity.startswith("local-list:"):
                    raise ValueError("Playlist local inexistente")
                collection.title = title[:200]
                await session.commit()
            except Exception:
                try:
                    await session.rollback()
                except Exception:
                    pass
                raise

    async def delete_playlist(self, identity):
        if not isinstance(identity, str) or not identity.startswith("local-list:"):
            raise ValueError("Solo se pueden eliminar playlists locales")
        if self.__class__._write_lock is None:
            self.__class__._write_lock = asyncio.Lock()
        async with self.__class__._write_lock:
            async with get_session() as session:
                try:
                    await session.execute(delete(LocalPlaylistTrack).where(LocalPlaylistTrack.playlist_id == identity))
                    await session.execute(delete(Collection).where(Collection.context_type == "playlist", Collection.context_id == identity))
                    await session.commit()
                except Exception:
                    try:
                        await session.rollback()
                    except Exception:
                        pass
                    raise

    async def remove_occurrence(self, identity, position, video_id):
        if (not isinstance(identity, str) or not identity.startswith("local-list:")
                or isinstance(position, bool) or not isinstance(position, int)
                or position < 0 or not isinstance(video_id, str) or not video_id):
            return False
        async with get_session() as session:
            try:
                result = await session.execute(delete(LocalPlaylistTrack).where(
                    LocalPlaylistTrack.playlist_id == identity, LocalPlaylistTrack.position == position,
                    LocalPlaylistTrack.video_id == video_id))
                await self._refresh_cover(session, identity)
                await session.commit()
                return result.rowcount == 1
            except Exception:
                try:
                    await session.rollback()
                except Exception:
                    pass
                raise

    async def append(self, playlist_id, video_ids):
        # Serialize max(position)+insert within this process. SQLite commits the
        # complete append, retaining duplicate occurrences deliberately.
        if not isinstance(playlist_id, str) or not isinstance(video_ids, (list, tuple)):
            raise ValueError("Playlist local inexistente")
        for candidate in video_ids:
            if not isinstance(candidate, str) or not candidate:
                raise ValueError("Faltan los metadatos de la canción")
        if self.__class__._write_lock is None:
            self.__class__._write_lock = asyncio.Lock()
        async with self.__class__._write_lock:
            async with get_session() as session:
                try:
                    collection = await session.get(Collection, ("playlist", playlist_id))
                    if not collection or not playlist_id.startswith("local-list:"):
                        raise ValueError("Playlist local inexistente")
                    if not video_ids:
                        await session.commit()
                        return
                    unique_ids = list(dict.fromkeys(video_ids))
                    known_ids = set()
                    for offset in range(0, len(unique_ids), _BATCH_SONGS):
                        known_ids.update((await session.scalars(select(Song.video_id).where(
                            Song.video_id.in_(unique_ids[offset:offset + _BATCH_SONGS])))).all())
                    if set(unique_ids) != known_ids:
                        raise ValueError("Faltan los metadatos de la canción")
                    maximum = await session.scalar(select(func.max(LocalPlaylistTrack.position)).where(LocalPlaylistTrack.playlist_id == playlist_id))
                    position = maximum + 1 if maximum is not None else 0
                    for identity in video_ids:
                        session.add(LocalPlaylistTrack(playlist_id=playlist_id, position=position, video_id=identity))
                        position += 1
                    await session.flush()
                    await self._refresh_cover(session, playlist_id)
                    await session.commit()
                except Exception:
                    try:
                        await session.rollback()
                    except Exception:
                        pass
                    raise

    async def tracks(self, identity, limit=None, offset=0):
        if not isinstance(identity, str):
            return "", []
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("Invalid offset")
        if limit is not None:
            limit = _coerce_limit(limit, default=_MAX_TRACK_LIMIT, maximum=_MAX_TRACK_LIMIT, name="limit")
        async with get_session() as session:
            collection = await session.get(Collection, ("playlist", identity))
            if collection is None:
                return "", []
            query = (select(Song, Download.file_path, LocalPlaylistTrack.position).join(LocalPlaylistTrack, LocalPlaylistTrack.video_id == Song.video_id)
                .outerjoin(Download, Download.video_id == Song.video_id).where(LocalPlaylistTrack.playlist_id == identity)
                .order_by(LocalPlaylistTrack.position).offset(offset))
            if limit is not None:
                query = query.limit(limit)
            rows = (await session.execute(query)).all()
            title = collection.title
        return title, [dict(track_data(song, path), local_position=position) for song, path, position in rows]

    @staticmethod
    async def _refresh_cover(session, identity):
        collection = await session.get(Collection, ("playlist", identity))
        rows = (await session.execute(select(Song.video_id, Song.thumbnail_url).join(
            LocalPlaylistTrack, LocalPlaylistTrack.video_id == Song.video_id).where(
            LocalPlaylistTrack.playlist_id == identity).order_by(LocalPlaylistTrack.position))).all()
        if collection is not None:
            collection.thumbnail_url = cover_fields([
                dict(videoId=video_id, thumbnail_url=url) for video_id, url in rows])["thumbnail_url"]
