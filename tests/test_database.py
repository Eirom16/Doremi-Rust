import pytest
import pytest_asyncio
from sqlalchemy import text


@pytest_asyncio.fixture(autouse=True)
async def close_test_database(monkeypatch):
    yield
    from doremi.db.database import close_db
    await close_db()

@pytest.mark.asyncio
async def test_database_initialization(monkeypatch):
    import doremi.db.database as db
    
    # Override DATABASE_URL to use in-memory SQLite for isolated testing
    monkeypatch.setattr(db, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_session_factory", None)
    
    # Initialize the database
    await db.init_db()
    
    # Verify tables are created by querying sqlite_master
    async with db.get_session() as session:
        result = await session.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
        tables = [row[0] for row in result.fetchall()]
        
        assert "songs" in tables
        assert "downloads" in tables
        assert "play_history" in tables
        assert "cached_artwork" in tables


@pytest.mark.asyncio
async def test_database_initialization_uses_alembic_for_file_db(monkeypatch, tmp_path):
    import doremi.db.database as db

    db_path = tmp_path / "doremi.db"
    monkeypatch.setattr(db, "DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_session_factory", None)

    await db.init_db()

    async with db.get_session() as session:
        result = await session.execute(text("SELECT version_num FROM alembic_version;"))
        assert result.scalar_one() == "20260708_0001"

        result = await session.execute(text("PRAGMA table_info(downloads)"))
        download_columns = {row[1] for row in result.fetchall()}
        assert "parent_playlist_thumbnail_url" in download_columns

        result = await session.execute(text("PRAGMA table_info(notifications)"))
        notification_columns = {row[1] for row in result.fetchall()}
        assert "artist_id" in notification_columns


@pytest.mark.asyncio
async def test_cached_artwork_repository(monkeypatch):
    import doremi.db.database as db
    from doremi.db.repository import CachedArtworkRepository

    monkeypatch.setattr(db, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_session_factory", None)

    await db.init_db()

    repo = CachedArtworkRepository()
    artwork = await repo.upsert_artwork("https://example.test/a.jpg", "/tmp/a.jpg")
    assert artwork.local_path == "/tmp/a.jpg"

    updated = await repo.upsert_artwork("https://example.test/a.jpg", "/tmp/b.jpg")
    assert updated.id == artwork.id
    assert updated.local_path == "/tmp/b.jpg"

    found = await repo.get_artwork("https://example.test/a.jpg")
    assert found is not None
    assert found.local_path == "/tmp/b.jpg"
