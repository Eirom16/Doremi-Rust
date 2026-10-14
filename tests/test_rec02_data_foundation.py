"""REC-02 data foundation: migrations 0003/0004 + minimal contracts.

Covers (on temporary SQLite files, never real user data):
1. fresh migration to head
2. upgrade from 0002 with seed data preserved
3. no data loss on upgrade
4. indexes / constraints / tables
5. read-write on new models (Song.local_path, PlayHistory.position_ms,
   Collection, LocalPlaylistTrack) via models + HistoryRepository
6. empty / duplicates / nulls
7. idempotence (re-upgrade, add_if_new)
8. guarded downgrade preserving pre-existing 0002 data
Plus minimal contract checks for playback origins (QueueItem context
fields, ListeningSession.position_ms, services.playback_context).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import text


@pytest_asyncio.fixture(autouse=True)
async def _close_db():
    yield
    from doremi.db import database as db
    await db.close_db()


def _alembic_config(db_path: Path):
    import doremi.db.database as db
    from alembic.config import Config

    # Reuse the packaged script_location resolution (frozen-safe).
    cfg = db._alembic_config()
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def _sqlite_tables(db_path: Path) -> set[str]:
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return {r[0] for r in rows}
    finally:
        con.close()


def _sqlite_indexes(db_path: Path, table: str) -> set[str]:
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(f"PRAGMA index_list('{table}')").fetchall()
        # (seq, name, unique, origin, partial)
        return {r[1] for r in rows}
    finally:
        con.close()


def _pragma_table_info(db_path: Path, table: str) -> dict[str, dict]:
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(f"PRAGMA table_info('{table}')").fetchall()
        # cid, name, type, notnull, dflt_value, pk
        return {r[1]: {"type": r[2], "notnull": r[3], "default": r[4], "pk": r[5]} for r in rows}
    finally:
        con.close()


# 1. Fresh migration ---------------------------------------------------------

@pytest.mark.asyncio
async def test_rec02_fresh_migration_reaches_head(monkeypatch, tmp_path):
    import doremi.db.database as db

    db_path = tmp_path / "fresh.db"
    monkeypatch.setattr(db, "DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_session_factory", None)

    await db.init_db()

    async with db.get_session() as session:
        version = (await session.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
        assert version == "20260929_0004"
        tables = {r[0] for r in (await session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))).fetchall()}
        assert {"songs", "play_history", "downloads", "cached_artwork", "notifications",
                "collections", "local_playlist_tracks", "alembic_version"} <= tables
        history_cols = {r[1] for r in (await session.execute(text("PRAGMA table_info(play_history)"))).fetchall()}
        assert "position_ms" in history_cols
        song_cols = {r[1] for r in (await session.execute(text("PRAGMA table_info(songs)"))).fetchall()}
        assert "local_path" in song_cols


@pytest.mark.asyncio
async def test_rec02_in_memory_create_all_includes_new_tables(monkeypatch):
    import doremi.db.database as db

    monkeypatch.setattr(db, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_session_factory", None)
    await db.init_db()

    async with db.get_session() as session:
        tables = {r[0] for r in (await session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))).fetchall()}
        assert "collections" in tables
        assert "local_playlist_tracks" in tables


# 2/3. Upgrade from 0002 with data ------------------------------------------

def test_rec02_upgrade_from_0002_preserves_data(tmp_path):
    from alembic import command

    db_path = tmp_path / "from0002.db"
    db_path.touch()
    cfg = _alembic_config(db_path)
    command.upgrade(cfg, "20260926_0002")

    con = sqlite3.connect(db_path)
    try:
        con.execute("INSERT INTO songs (video_id, title, artist, album, duration_ms, thumbnail_url, is_liked, play_count) VALUES ('v1','Song','Artist','Album',200000,'',1,3)")
        con.execute("INSERT INTO play_history (video_id, title, artist, duration_ms, listen_time_ms, completion_ratio, skip_count, completed, was_played, context_type, context_id) VALUES ('v1','Song','Artist',200000,50000,0.5,0,0,1,'playlist','p1')")
        con.execute("INSERT INTO downloads (video_id, title, artist, file_path) VALUES ('v1','Song','Artist','/tmp/x.mp3')")
        con.commit()
    finally:
        con.close()

    command.upgrade(cfg, "head")

    con = sqlite3.connect(db_path)
    try:
        version = con.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        assert version == "20260929_0004"
        song = con.execute("SELECT video_id, title, play_count, is_liked, local_path FROM songs WHERE video_id='v1'").fetchone()
        assert song[0] == "v1" and song[1] == "Song" and song[2] == 3
        assert song[3] == 1
        assert song[4] is None  # new nullable column defaults to NULL
        hist = con.execute("SELECT video_id, context_id, position_ms FROM play_history WHERE video_id='v1'").fetchone()
        assert hist[0] == "v1" and hist[1] == "p1"
        assert hist[2] == 0  # server default for existing rows
        dl = con.execute("SELECT video_id FROM downloads WHERE video_id='v1'").fetchone()
        assert dl[0] == "v1"
    finally:
        con.close()


def test_rec02_reupgrade_is_idempotent(tmp_path):
    from alembic import command

    db_path = tmp_path / "idempotent.db"
    db_path.touch()
    cfg = _alembic_config(db_path)
    command.upgrade(cfg, "head")
    # Second upgrade must be a no-op, not an error.
    command.upgrade(cfg, "head")
    con = sqlite3.connect(db_path)
    try:
        version = con.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        assert version == "20260929_0004"
    finally:
        con.close()


# 4. Indexes / constraints ----------------------------------------------------

def test_rec02_indexes_and_constraints(tmp_path):
    from alembic import command

    db_path = tmp_path / "constraints.db"
    db_path.touch()
    cfg = _alembic_config(db_path)
    command.upgrade(cfg, "head")

    # Composite context index on play_history.
    assert "ix_history_context_time" in _sqlite_indexes(db_path, "play_history")
    assert "ix_play_history_was_played" in _sqlite_indexes(db_path, "play_history")
    # Video index on local_playlist_tracks.
    assert "ix_local_playlist_tracks_video_id" in _sqlite_indexes(db_path, "local_playlist_tracks")

    info_collections = _pragma_table_info(db_path, "collections")
    assert info_collections["context_type"]["pk"] == 1
    assert info_collections["context_id"]["pk"] == 2
    assert info_collections["title"]["notnull"] == 1
    assert info_collections["thumbnail_url"]["notnull"] == 1

    info_tracks = _pragma_table_info(db_path, "local_playlist_tracks")
    assert info_tracks["playlist_id"]["pk"] == 1
    assert info_tracks["position"]["pk"] == 2
    assert info_tracks["video_id"]["notnull"] == 1

    info_songs = _pragma_table_info(db_path, "songs")
    assert "local_path" in info_songs
    assert info_songs["local_path"]["notnull"] == 0  # nullable

    info_history = _pragma_table_info(db_path, "play_history")
    assert "position_ms" in info_history

    # No FKs by design: denormalized so history/downloads survive song deletes.
    con = sqlite3.connect(db_path)
    try:
        for table in ("play_history", "downloads", "collections", "local_playlist_tracks", "songs"):
            fks = con.execute(f"PRAGMA foreign_key_list('{table}')").fetchall()
            assert fks == [], f"unexpected FK on {table}: {fks}"
    finally:
        con.close()


# 5/6. Read-write, empty / duplicates / nulls --------------------------------

@pytest.mark.asyncio
async def test_rec02_new_models_read_write(monkeypatch):
    import doremi.db.database as db
    from doremi.db.models import Song, PlayHistory, Collection, LocalPlaylistTrack
    from doremi.db.database import get_session

    monkeypatch.setattr(db, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_session_factory", None)
    await db.init_db()

    async with get_session() as session:
        # Empty start.
        from sqlalchemy import select, func
        assert (await session.scalar(select(func.count()).select_from(Collection))) == 0
        assert (await session.scalar(select(func.count()).select_from(LocalPlaylistTrack))) == 0

        session.add(Song(video_id="v1", title="T", artist="A", local_path="/music/a.mp3"))
        session.add(Song(video_id="v2", title="U", artist="B"))  # local_path NULL
        session.add(PlayHistory(video_id="v1", title="T", artist="A", duration_ms=1000, position_ms=42000,
                                context_type="album", context_id="a1"))
        session.add(Collection(context_type="playlist", context_id="p1", title="Gym"))
        session.add(LocalPlaylistTrack(playlist_id="local-list:x", position=0, video_id="v1"))
        session.add(LocalPlaylistTrack(playlist_id="local-list:x", position=1, video_id="v1"))  # duplicate video, distinct position
        await session.commit()

    async with get_session() as session:
        from sqlalchemy import select
        song = (await session.execute(select(Song).where(Song.video_id == "v1"))).scalar_one()
        assert song.local_path == "/music/a.mp3"
        null_song = (await session.execute(select(Song).where(Song.video_id == "v2"))).scalar_one()
        assert null_song.local_path is None
        hist = (await session.execute(select(PlayHistory).where(PlayHistory.video_id == "v1"))).scalar_one()
        assert hist.position_ms == 42000
        coll = await session.get(Collection, ("playlist", "p1"))
        assert coll is not None and coll.title == "Gym"
        tracks = (await session.execute(select(LocalPlaylistTrack).where(LocalPlaylistTrack.playlist_id == "local-list:x").order_by(LocalPlaylistTrack.position))).scalars().all()
        assert [t.position for t in tracks] == [0, 1]
        assert [t.video_id for t in tracks] == ["v1", "v1"]


@pytest.mark.asyncio
async def test_rec02_unique_constraints_reject_duplicates(monkeypatch):
    import doremi.db.database as db
    from doremi.db.models import Song, Collection, LocalPlaylistTrack
    from doremi.db.database import get_session
    from sqlalchemy.exc import IntegrityError

    monkeypatch.setattr(db, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_session_factory", None)
    await db.init_db()

    async with get_session() as session:
        session.add(Song(video_id="dup", title="T", artist="A"))
        await session.commit()
        session.add(Song(video_id="dup", title="T2", artist="A2"))
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

    async with get_session() as session:
        session.add(Collection(context_type="playlist", context_id="p", title="A"))
        await session.commit()
        session.add(Collection(context_type="playlist", context_id="p", title="B"))
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

    async with get_session() as session:
        session.add(LocalPlaylistTrack(playlist_id="pl", position=0, video_id="v"))
        await session.commit()
        session.add(LocalPlaylistTrack(playlist_id="pl", position=0, video_id="other"))
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


@pytest.mark.asyncio
async def test_rec02_history_repository_position_and_collection(monkeypatch):
    import doremi.db.database as db
    from doremi.db.repository import HistoryRepository
    from doremi.db.models import Collection
    from doremi.db.database import get_session

    monkeypatch.setattr(db, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_session_factory", None)
    await db.init_db()

    repo = HistoryRepository()
    await repo.add_entry("v1", "Song", "Artist", 100000, context_type="album", context_id="a1",
                         context_title="Album", position_ms=12345)
    history = await repo.get_history(limit=10)
    assert len(history) == 1
    assert history[0][0].position_ms == 12345

    async with get_session() as session:
        coll = await session.get(Collection, ("album", "a1"))
        assert coll is not None
        assert coll.title == "Album"

    # local-list origins must NOT recreate a deleted local playlist.
    await repo.add_entry("v2", "S2", "A2", 50000, context_type="playlist",
                         context_id="local-list:gone", context_title="Gone")
    async with get_session() as session:
        assert await session.get(Collection, ("playlist", "local-list:gone")) is None

    # Null/empty edge: no context -> no collection, position defaults to 0.
    await repo.add_entry("v3", "S3", "A3", 1000)
    history = await repo.get_history(limit=10)
    assert any(h.video_id == "v3" and h.position_ms == 0 for h, _ in history)


@pytest.mark.asyncio
async def test_rec02_notification_add_if_new_idempotent(monkeypatch):
    import doremi.db.database as db
    from doremi.db.repository import NotificationRepository

    monkeypatch.setattr(db, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_session_factory", None)
    await db.init_db()

    repo = NotificationRepository()
    assert await repo.add_if_new("vn", "T", "A") is True
    assert await repo.add_if_new("vn", "T", "A") is False


# 8. Guarded downgrade ----------------------------------------------------------

def test_rec02_downgrade_preserves_0002_data(tmp_path):
    from alembic import command

    db_path = tmp_path / "downgrade.db"
    db_path.touch()
    cfg = _alembic_config(db_path)
    command.upgrade(cfg, "20260926_0002")

    con = sqlite3.connect(db_path)
    try:
        con.execute("INSERT INTO songs (video_id, title, artist) VALUES ('keep','Keep','Me')")
        con.execute("INSERT INTO play_history (video_id, title, artist, duration_ms) VALUES ('keep','Keep','Me',1000)")
        con.commit()
    finally:
        con.close()

    command.upgrade(cfg, "head")
    con = sqlite3.connect(db_path)
    try:
        con.execute("INSERT INTO collections (context_type, context_id, title) VALUES ('playlist','p1','Gym')")
        con.execute("INSERT INTO local_playlist_tracks (playlist_id, position, video_id) VALUES ('pl',0,'keep')")
        con.commit()
    finally:
        con.close()

    # Downgrade one step: 0004 artifacts gone, 0003 + seed data intact.
    command.downgrade(cfg, "20260929_0003")
    tables = _sqlite_tables(db_path)
    assert "local_playlist_tracks" not in tables
    assert "collections" in tables
    con = sqlite3.connect(db_path)
    try:
        assert con.execute("SELECT title FROM songs WHERE video_id='keep'").fetchone()[0] == "Keep"
        assert con.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "20260929_0003"
    finally:
        con.close()

    # Full downgrade to 0002: REC-02 artifacts gone, seed data intact.
    command.downgrade(cfg, "20260926_0002")
    tables = _sqlite_tables(db_path)
    assert "collections" not in tables
    assert "local_playlist_tracks" not in tables
    con = sqlite3.connect(db_path)
    try:
        assert con.execute("SELECT title FROM songs WHERE video_id='keep'").fetchone()[0] == "Keep"
        assert con.execute("SELECT video_id FROM play_history WHERE video_id='keep'").fetchone()[0] == "keep"
        cols = {r[1] for r in con.execute("PRAGMA table_info(play_history)").fetchall()}
        assert "position_ms" not in cols
        song_cols = {r[1] for r in con.execute("PRAGMA table_info(songs)").fetchall()}
        assert "local_path" not in song_cols
    finally:
        con.close()

    # Re-upgrade still works after downgrade.
    command.upgrade(cfg, "head")
    con = sqlite3.connect(db_path)
    try:
        assert con.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "20260929_0004"
        assert con.execute("SELECT title FROM songs WHERE video_id='keep'").fetchone()[0] == "Keep"
    finally:
        con.close()


# Minimal playback-origin contracts --------------------------------------------

def test_rec02_playback_context_origins():
    from doremi.services.playback_context import CONTEXT_TYPES, playback_context

    assert {"playlist", "album", "smart", "queue", "local", "unknown"} <= set(CONTEXT_TYPES)
    cases = [
        ("playlist?id=PL123", "playlist", "PL123"),
        ("album?id=MPRE", "album", "MPRE"),
        ("search?query=a%26b", "search", "a&b"),
        ("now_playing", "queue", ""),
        ("playlist?id=smart:repeat", "smart", "smart:repeat"),
        ("downloads", "downloads", ""),
    ]
    for route, kind, identity in cases:
        result = playback_context(SimpleNamespace(_current_path=route))
        assert (result["context_type"], result["context_id"]) == (kind, identity)
        assert "context_title" in result

    window = SimpleNamespace(_current_path="library", library_screen=SimpleNamespace(_vm=SimpleNamespace(tab="local")))
    assert playback_context(window)["context_type"] == "local"


def test_rec02_queue_item_context_survives_serialization():
    from doremi.audio.queue import PlayQueue, QueueItem

    queue = PlayQueue()
    queue.set_queue([
        QueueItem("v", "Song", "Artist", "", 100000, "", context_type="playlist", context_id="p", context_title="Gym"),
        QueueItem("local:1", "Local", "", "", 100, "", is_local=True, context_type="local"),
    ])
    queue.toggle_shuffle()
    restored = PlayQueue.from_dict(queue.to_dict())
    restored.move_item(0, 1)
    restored.toggle_shuffle()
    assert restored.current.context_title == "Gym"
    assert restored.items[1].context_type == "local"

    # Backwards compat: payloads saved before REC-02 (no context keys) still load.
    legacy = {"items": [{"video_id": "old", "title": "T", "artist": "A", "album": "", "duration_ms": 1000, "thumbnail_url": ""}],
              "original": [], "index": 0, "repeat_mode": "off", "shuffle_enabled": False}
    assert PlayQueue.from_dict(legacy).current.video_id == "old"


def test_rec02_listening_session_reports_position():
    from doremi.audio.listening import ListeningSession
    from doremi.audio.queue import QueueItem

    session = ListeningSession()
    item = QueueItem("v", "T", "A", "", 100000, "")
    session.start(item)
    session.observe(10000, 100000, True)
    session.observe(15000, 100000, True)
    result = session.finish("completed")
    assert result is not None
    assert result.position_ms == 15000
    # Default stays zero when no position was ever observed.
    session.start(item)
    assert session.finish("stopped").position_ms == 0
