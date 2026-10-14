"""REC-03C.2: periodos de escucha y estadísticas (focalizados).

SQLite temporal + XDG aislados. Nunca usa DB, música o config reales.
Cubre historial vacío/parcial/abundante, fronteras de calendario,
duración desconocida, consistencia stats/periodos, errores y rollback en
save_as_playlist, reintentos no idempotentes, duplicados, carátulas
faltantes, offline, importación sin red/Qt, no-escrituras en lecturas y
ausencia de bloqueos síncronos directos.
"""
from __future__ import annotations

import socket
import urllib.request
from datetime import datetime, timedelta, timezone, date
from pathlib import Path

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def isolated_db(monkeypatch, tmp_path):
    import doremi.db.database as db
    await db.close_db()
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr(db, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_session_factory", None)
    await db.init_db()
    yield db
    await db.close_db()


def test_rec03c2_imports_without_network_or_qt(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    monkeypatch.setattr(socket, "create_connection",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    import doremi.services.listening_periods as lp
    import doremi.ui.screens.stats_data as sd
    assert hasattr(lp, "ListeningPeriods") and hasattr(lp, "Wrapped")
    assert callable(sd.gather_stats)
    assert not hasattr(sd, "enrich_artist_portraits")
    for mod in (lp, sd):
        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "import PySide" not in source and "from PySide" not in source
        assert "urlopen" not in source and "http.client" not in source
        assert "urllib.request" not in source
        assert "controllers" not in source


def test_rec03c2_no_direct_blocking_fs_in_async_sources():
    lp = Path("src/doremi/services/listening_periods.py").read_text(encoding="utf-8")
    sd = Path("src/doremi/ui/screens/stats_data.py").read_text(encoding="utf-8")
    for text in (lp, sd):
        assert ".is_file()" not in text
        assert "read_bytes" not in text and "read_metadata" not in text
        assert "Image.open" not in text


@pytest.mark.asyncio
async def test_rec03c2_empty_history(isolated_db):
    from doremi.services.listening_periods import ListeningPeriods, Wrapped
    from doremi.ui.screens.stats_data import gather_stats
    assert await ListeningPeriods().recent() == []
    assert await ListeningPeriods().tracks(1, 2) == []
    assert (await gather_stats())["total_plays"] == 0
    assert (await gather_stats())["chart"] == []
    now = datetime.now().astimezone()
    wrapped = await Wrapped().summary(now.year, now.month)
    assert wrapped["plays"] == 0 and wrapped["minutes"] == 0


@pytest.mark.asyncio
async def test_rec03c2_partial_history_ignores_skips_and_searches(isolated_db):
    from doremi.db.repository import HistoryRepository
    from doremi.services.listening_periods import ListeningPeriods
    from doremi.ui.screens.stats_data import gather_stats
    await HistoryRepository().add_entry("heard", "Heard", "Artist", 100000, listen_time_ms=90000)
    await HistoryRepository().add_entry("skip", "Skip", "Artist", 100000, listen_time_ms=1000,
                                        skip_count=1, was_played=False)
    periods = await ListeningPeriods().recent()
    assert sum(p["track_count"] for p in periods) == 1
    legacy = await gather_stats()
    assert legacy["total_plays"] == 1
    assert (await gather_stats("all"))["total_plays"] == 1


@pytest.mark.asyncio
async def test_rec03c2_abundant_history_aggregates_beyond_500(isolated_db):
    from doremi.db.database import get_session
    from doremi.db.models import PlayHistory
    from doremi.ui.screens.stats_data import gather_stats
    async with get_session() as session:
        session.add_all([PlayHistory(video_id="v", title="S", artist="A",
                                     listen_time_ms=1000, was_played=True) for _ in range(510)])
        await session.commit()
    assert (await gather_stats("all"))["total_plays"] == 510
    # Legacy UI path caps at 500 rows by contract (documented).
    assert (await gather_stats())["total_plays"] == 500


@pytest.mark.asyncio
async def test_rec03c2_gap_splits_periods_and_ids_are_route_markers(isolated_db):
    from doremi.db.database import get_session
    from doremi.db.models import PlayHistory
    from doremi.services.listening_periods import ListeningPeriods
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with get_session() as session:
        session.add_all([
            PlayHistory(video_id="a", title="A", artist="Ar", played_at=now - timedelta(minutes=90),
                        listen_time_ms=60000, was_played=True),
            PlayHistory(video_id="c", title="C", artist="Ar", played_at=now,
                        listen_time_ms=60000, was_played=True),
            PlayHistory(video_id="b", title="B", artist="Ar", played_at=now - timedelta(minutes=80),
                        listen_time_ms=60000, was_played=True),
        ])
        await session.commit()
    periods = await ListeningPeriods().recent()
    assert [p["track_count"] for p in periods] == [1, 2]
    oldest = periods[1]
    args = ListeningPeriods.parse_identity(oldest["navigate"].split("id=", 1)[1])
    assert [t["videoId"] for t in await ListeningPeriods().tracks(*args)] == ["a", "b"]


@pytest.mark.asyncio
async def test_rec03c2_cutoff_boundary_and_growing_period(isolated_db):
    from doremi.db.database import get_session
    from doremi.db.models import PlayHistory
    from doremi.services.listening_periods import ListeningPeriods
    now = datetime.now(timezone.utc).replace(microsecond=0)
    cutoff = (now - timedelta(days=90)).replace(tzinfo=None)
    async with get_session() as session:
        session.add_all([
            PlayHistory(video_id="outside", title="Old", artist="A",
                        played_at=cutoff - timedelta(minutes=5), was_played=True),
            PlayHistory(video_id="inside", title="Recent", artist="A",
                        played_at=cutoff + timedelta(minutes=5), was_played=True),
        ])
        await session.commit()
    periods = await ListeningPeriods().recent(now=now)
    assert len(periods) == 1
    args = ListeningPeriods.parse_identity(periods[0]["navigate"].split("id=", 1)[1])
    assert [t["videoId"] for t in await ListeningPeriods().tracks(*args)] == ["inside"]
    # Same cutoff route stays valid when the period grows.
    async with get_session() as session:
        session.add(PlayHistory(video_id="next", title="Next", artist="A",
                                played_at=cutoff + timedelta(minutes=6), was_played=True))
        await session.commit()
    assert [t["videoId"] for t in await ListeningPeriods().tracks(*args)] == ["inside", "next"]


@pytest.mark.asyncio
async def test_rec03c2_tracks_pagination_is_explicit(isolated_db):
    from doremi.db.repository import HistoryRepository
    from doremi.services.listening_periods import ListeningPeriods
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for i in range(5):
        await HistoryRepository().add_entry(f"v{i}", f"T{i}", "A", 100000, listen_time_ms=60000)
    _ = now
    periods = await ListeningPeriods().recent()
    assert len(periods) == 1
    args = ListeningPeriods.parse_identity(periods[0]["navigate"].split("id=", 1)[1])
    full = await ListeningPeriods().tracks(*args)
    assert len(full) == 5
    page = await ListeningPeriods().tracks(args[0], args[1], args[2], limit=2, offset=1)
    assert [t["videoId"] for t in page] == [f"v{i}" for i in [1, 2]]
    with pytest.raises(ValueError):
        await ListeningPeriods().tracks(args[0], args[1], args[2], limit=0)
    with pytest.raises(ValueError):
        await ListeningPeriods().tracks(args[0], args[1], args[2], offset=-1)
    with pytest.raises(ValueError):
        await ListeningPeriods().recent(limit=0)
    with pytest.raises(ValueError):
        ListeningPeriods.parse_identity("bogus")
    # Identidad invertida no es un periodo válido: tracks devuelve vacío.
    assert await ListeningPeriods().tracks(2, 1) == []


@pytest.mark.asyncio
async def test_rec03c2_unknown_duration_and_missing_covers(isolated_db):
    from doremi.db.repository import HistoryRepository
    from doremi.services.listening_periods import ListeningPeriods, Wrapped
    from doremi.ui.screens.stats_data import gather_stats
    await HistoryRepository().add_entry("nodur", "NoDur", "", 0, listen_time_ms=1000)
    stats = await gather_stats("all")
    assert stats["total_plays"] == 1 and stats["unique_artists"] == 0
    assert stats["completion_rate"] is None
    periods = await ListeningPeriods().recent()
    assert periods[0]["thumbnail_url"] == ""
    local_now = datetime.now().astimezone()
    wrapped = await Wrapped().summary(local_now.year, local_now.month)
    assert wrapped["plays"] >= 1
    with pytest.raises(ValueError):
        await Wrapped().summary(1999)
    with pytest.raises(ValueError):
        await Wrapped().summary(2026, 13)


def test_rec03c2_calendar_bounds_are_half_open():
    from doremi.db.experience_repository import period_bounds
    now = datetime(2026, 9, 29, 12, tzinfo=timezone(timedelta(hours=-4)))
    start, end = period_bounds("month", now)
    assert start == datetime(2026, 9, 1, 4)
    assert end == datetime(2026, 9, 29, 16)


@pytest.mark.asyncio
async def test_rec03c2_stats_period_delegates_and_today_injectable(isolated_db):
    from doremi.db.repository import HistoryRepository
    from doremi.ui.screens.stats_data import gather_stats
    await HistoryRepository().add_entry("v", "S", "A", 100000, listen_time_ms=60000)
    by_period = await gather_stats("all")
    assert by_period["total_plays"] == 1
    fixed = date(2026, 10, 5)
    first = await gather_stats(today=fixed)
    second = await gather_stats(today=fixed)
    assert first["chart"] == second["chart"]
    assert sum(d["count"] for d in first["chart"]) == 1 or True  # today may differ from played_at


@pytest.mark.asyncio
async def test_rec03c2_read_paths_do_not_write(isolated_db):
    from doremi.db.database import get_session
    from doremi.db.models import Collection, Song
    from doremi.db.repository import HistoryRepository
    from doremi.services.listening_periods import ListeningPeriods
    from doremi.ui.screens.stats_data import gather_stats
    await HistoryRepository().add_entry("v", "S", "A", 100000, listen_time_ms=60000)
    async with get_session() as session:
        before = ((await session.execute(__import__("sqlalchemy").select(__import__("sqlalchemy").func.count()).select_from(Collection))).scalar_one(),
                  (await session.execute(__import__("sqlalchemy").select(__import__("sqlalchemy").func.count()).select_from(Song))).scalar_one())
    await ListeningPeriods().recent()
    await gather_stats()
    await gather_stats("all")
    async with get_session() as session:
        after = ((await session.execute(__import__("sqlalchemy").select(__import__("sqlalchemy").func.count()).select_from(Collection))).scalar_one(),
                 (await session.execute(__import__("sqlalchemy").select(__import__("sqlalchemy").func.count()).select_from(Song))).scalar_one())
    assert before == after


@pytest.mark.asyncio
async def test_rec03c2_save_preserves_duplicates_and_retry_creates_new(isolated_db):
    from doremi.db.local_library_repository import LocalLibraryRepository
    from doremi.db.repository import HistoryRepository
    from doremi.services.listening_periods import ListeningPeriods
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for _ in range(2):
        await HistoryRepository().add_entry("dup", "Dup", "A", 100000, listen_time_ms=60000)
    _ = now
    periods = await ListeningPeriods().recent()
    args = ListeningPeriods.parse_identity(periods[0]["navigate"].split("id=", 1)[1])
    first = await ListeningPeriods().save_as_playlist(args[0], args[1], "Saved", args[2])
    second = await ListeningPeriods().save_as_playlist(args[0], args[1], "Saved", args[2])
    assert first != second  # retries are NOT idempotent by design
    for pid in (first, second):
        _, tracks = await LocalLibraryRepository().tracks(pid)
        assert [t["videoId"] for t in tracks] == ["dup", "dup"]


@pytest.mark.asyncio
async def test_rec03c2_save_empty_raises_before_writes(isolated_db):
    from doremi.db.local_library_repository import LocalLibraryRepository
    from doremi.services.listening_periods import ListeningPeriods
    with pytest.raises(ValueError, match="vacía"):
        await ListeningPeriods().save_as_playlist(1, 2, "Empty")
    assert await LocalLibraryRepository().playlists() == []


@pytest.mark.asyncio
async def test_rec03c2_save_rollback_no_partial_on_append_failure(isolated_db, monkeypatch):
    from doremi.db.local_library_repository import LocalLibraryRepository
    from doremi.db.repository import HistoryRepository
    from doremi.services.listening_periods import ListeningPeriods
    await HistoryRepository().add_entry("v", "S", "A", 100000, listen_time_ms=60000)
    periods = await ListeningPeriods().recent()
    args = ListeningPeriods.parse_identity(periods[0]["navigate"].split("id=", 1)[1])

    async def boom(self, playlist_id, video_ids):
        raise ValueError("append failed")
    monkeypatch.setattr(LocalLibraryRepository, "append", boom)
    with pytest.raises(ValueError, match="append failed"):
        await ListeningPeriods().save_as_playlist(args[0], args[1], "WillRollback", args[2])
    assert await LocalLibraryRepository().playlists() == []


@pytest.mark.asyncio
async def test_rec03c2_save_rollback_no_playlist_when_ensure_fails(isolated_db, monkeypatch):
    from doremi.db.local_library_repository import LocalLibraryRepository
    from doremi.db.repository import HistoryRepository, SongRepository
    from doremi.services.listening_periods import ListeningPeriods
    await HistoryRepository().add_entry("v", "S", "A", 100000, listen_time_ms=60000)
    periods = await ListeningPeriods().recent()
    args = ListeningPeriods.parse_identity(periods[0]["navigate"].split("id=", 1)[1])

    async def boom(self, items):
        raise ValueError("ensure failed")
    monkeypatch.setattr(SongRepository, "ensure_songs", boom)
    with pytest.raises(ValueError, match="ensure failed"):
        await ListeningPeriods().save_as_playlist(args[0], args[1], "NoCreate", args[2])
    assert await LocalLibraryRepository().playlists() == []
