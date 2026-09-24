import pytest
import pytest_asyncio

from doremi.db.repository import SongRepository, HistoryRepository


@pytest_asyncio.fixture
async def repo(monkeypatch):
    import doremi.db.database as db

    monkeypatch.setattr(db, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_session_factory", None)
    await db.init_db()
    yield SongRepository()
    await db.close_db()


@pytest.mark.asyncio
async def test_upsert_song_creates(repo):
    song = await repo.upsert_song(
        video_id="v1", title="Song", artist="Artist", album="Album", duration_ms=200000
    )
    assert song.id is not None
    assert song.video_id == "v1"


@pytest.mark.asyncio
async def test_upsert_song_updates_existing(repo):
    await repo.upsert_song(video_id="v1", title="Song", artist="Artist")
    updated = await repo.upsert_song(video_id="v1", title="Renamed", is_liked=True)
    assert updated.title == "Renamed"
    assert updated.is_liked is True
    # Only one row exists
    all_songs = await repo.get_all_songs()
    assert len(all_songs) == 1


@pytest.mark.asyncio
async def test_get_song(repo):
    await repo.upsert_song(video_id="v1", title="Song", artist="Artist")
    found = await repo.get_song("v1")
    assert found is not None
    assert found.title == "Song"
    missing = await repo.get_song("nope")
    assert missing is None


@pytest.mark.asyncio
async def test_liked_songs_and_ids(repo):
    await repo.upsert_song(video_id="v1", title="A", artist="X", is_liked=True)
    await repo.upsert_song(video_id="v2", title="B", artist="Y", is_liked=False)
    await repo.upsert_song(video_id="v3", title="C", artist="Z", is_liked=True)

    liked = await repo.get_liked_songs()
    assert {s.video_id for s in liked} == {"v1", "v3"}

    liked_ids = await repo.get_liked_video_ids()
    assert liked_ids == {"v1", "v3"}


@pytest.mark.asyncio
async def test_get_songs_by_video_ids(repo):
    await repo.upsert_song(video_id="v1", title="A", artist="X")
    await repo.upsert_song(video_id="v2", title="B", artist="Y")
    await repo.upsert_song(video_id="v3", title="C", artist="Z")

    songs = await repo.get_songs_by_video_ids(["v1", "v3"])
    assert {s.video_id for s in songs} == {"v1", "v3"}

    # empty input returns empty list (no query error)
    assert await repo.get_songs_by_video_ids([]) == []


@pytest.mark.asyncio
async def test_search_songs(repo):
    await repo.upsert_song(video_id="v1", title="Bohemian Rhapsody", artist="Queen")
    await repo.upsert_song(video_id="v2", title="Another One Bites", artist="Queen")
    await repo.upsert_song(video_id="v3", title="Billie Jean", artist="Michael Jackson")

    results = await repo.search_songs("queen")
    assert {s.video_id for s in results} == {"v1", "v2"}

    by_title = await repo.search_songs("billie")
    assert {s.video_id for s in by_title} == {"v3"}


@pytest.mark.asyncio
async def test_delete_song(repo):
    await repo.upsert_song(video_id="v1", title="A", artist="X")
    assert await repo.delete_song("v1") is True
    assert await repo.get_song("v1") is None
    assert await repo.delete_song("missing") is False


@pytest.mark.asyncio
async def test_record_play_updates_play_count(repo):
    await repo.upsert_song(video_id="v1", title="A", artist="X")
    await repo.record_play("v1")
    await repo.record_play("v1")
    song = await repo.get_song("v1")
    assert song.play_count == 2
    assert song.last_played is not None


@pytest.mark.asyncio
async def test_history_repository_add_entry(repo):
    history_repo = HistoryRepository()
    await history_repo.add_entry("v1", "Song", "Artist", 200000)
    history = await history_repo.get_history(limit=10)
    assert len(history) == 1
    assert history[0][0].video_id == "v1"
    assert history[0][0].title == "Song"
