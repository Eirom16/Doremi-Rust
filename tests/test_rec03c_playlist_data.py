"""REC-03C.3: datos de playlists locales, inteligentes y mixtas (focalizados).

SQLite temporal + XDG aislados + mocks. Nunca usa DB, música o config
reales ni descargas remotas. Cubre ramas session:/local-list:/smart:,
paginación explícita sin truncado silencioso, orden y duplicados, huecos
de posición, identidad local:, offline real/desaparecido, carátulas
faltantes, N+1, importación sin red/Qt y QML-independencia.
"""
from __future__ import annotations

import socket
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

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


@pytest_asyncio.fixture
async def online(monkeypatch):
    from doremi.system.network import NetworkMonitor
    monkeypatch.setattr(NetworkMonitor, "current_connectivity", lambda: True)
    yield


@pytest_asyncio.fixture
async def offline(monkeypatch):
    from doremi.system.network import NetworkMonitor
    monkeypatch.setattr(NetworkMonitor, "current_connectivity", lambda: False)
    yield


def test_rec03c3_imports_without_network_or_qt(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    monkeypatch.setattr(socket, "create_connection",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    import doremi.ui.screens.playlist_data as pd
    assert callable(pd.gather_playlist)
    source = Path(pd.__file__).read_text(encoding="utf-8")
    assert "import PySide" not in source and "from PySide" not in source
    assert "urlopen" not in source and "http.client" not in source
    assert "urllib.request" not in source and "controllers" not in source
    assert ".is_file()" not in source


@pytest.mark.asyncio
async def test_rec03c3_empty_and_invalid_ids(isolated_db, online):
    from doremi.ui.screens.playlist_data import gather_playlist
    empty = await gather_playlist(None, "")
    assert empty["tracks"] == [] and empty["track_count"] == 0
    bad_session = await gather_playlist(None, "session:bogus")
    assert bad_session["tracks"] == [] and bad_session["title"] == "Sesión musical"
    missing_local = await gather_playlist(None, "local-list:missing")
    assert missing_local["tracks"] == [] and missing_local["title"] == ""
    with pytest.raises(ValueError):
        await gather_playlist(None, "smart:bogus")
    with pytest.raises(ValueError):
        await gather_playlist(None, "local-list:x", limit=0)
    with pytest.raises(ValueError):
        await gather_playlist(None, "local-list:x", offset=-1)


@pytest.mark.asyncio
async def test_rec03c3_smart_uses_collection_contract(isolated_db, online):
    from doremi.db.repository import SongRepository
    from doremi.ui.screens.playlist_data import gather_playlist
    await SongRepository().upsert_song(video_id="v", title="Favorite", artist="Artist", is_liked=True)
    data = await gather_playlist(None, "smart:liked")
    assert data["title"] == "Favoritas"
    assert data["author"] == "Doremi · Colección inteligente"
    assert data["tracks"][0]["videoId"] == "v"
    assert data["track_count"] == 1 and data["has_more"] is False
    assert not data["is_local"]


@pytest.mark.asyncio
async def test_rec03c3_session_branch_matches_period_tracks(isolated_db, online):
    from doremi.db.repository import HistoryRepository
    from doremi.services.listening_periods import ListeningPeriods
    from doremi.ui.screens.playlist_data import gather_playlist
    await HistoryRepository().add_entry("a", "A", "Ar", 100000, listen_time_ms=60000)
    await HistoryRepository().add_entry("b", "B", "Ar", 100000, listen_time_ms=60000)
    periods = await ListeningPeriods().recent()
    identity = periods[0]["navigate"].split("id=", 1)[1]
    data = await gather_playlist(None, identity)
    assert data["title"] == "Sesión musical" and data["author"] == "Tu historial"
    assert [t["videoId"] for t in data["tracks"]] == ["a", "b"]
    assert "thumbnail_url" in data


@pytest.mark.asyncio
async def test_rec03c3_local_list_order_duplicates_and_gaps(isolated_db, online):
    from doremi.db.local_library_repository import LocalLibraryRepository
    from doremi.db.repository import SongRepository
    from doremi.ui.screens.playlist_data import gather_playlist
    for vid in ("k1", "k2"):
        await SongRepository().upsert_song(video_id=vid, title=vid, artist="A")
    repo = LocalLibraryRepository()
    pid = await repo.create_playlist("Gaps")
    await repo.append(pid, ["k1", "k1", "k2"])
    assert await repo.remove_occurrence(pid, 1, "k1") is True
    data = await gather_playlist(None, pid)
    assert data["title"] == "Gaps"
    assert [t["videoId"] for t in data["tracks"]] == ["k1", "k2"]
    assert [t["local_position"] for t in data["tracks"]] == [0, 2]


@pytest.mark.asyncio
async def test_rec03c3_local_identity_never_becomes_youtube_id(isolated_db, online, tmp_path):
    from doremi.db.local_library_repository import LocalLibraryRepository, local_identity
    from doremi.ui.screens.playlist_data import gather_playlist
    audio = tmp_path / "Track.ogg"
    audio.write_bytes(b"OggS")
    await LocalLibraryRepository().import_files([str(audio)])
    identity = local_identity(audio)
    assert identity.startswith("local:")
    pid = await LocalLibraryRepository().create_playlist("Local")
    await LocalLibraryRepository().append(pid, [identity])
    data = await gather_playlist(None, pid)
    assert data["tracks"][0]["videoId"] == identity
    assert data["tracks"][0]["videoId"].startswith("local:")


@pytest.mark.asyncio
async def test_rec03c3_disappeared_files_not_available(isolated_db, online, tmp_path):
    from doremi.db.local_library_repository import LocalLibraryRepository, local_identity
    from doremi.ui.screens.playlist_data import gather_playlist
    audio = tmp_path / "Gone.wav"
    audio.write_bytes(b"\x00" * 100)
    await LocalLibraryRepository().import_files([str(audio)])
    identity = local_identity(audio)
    pid = await LocalLibraryRepository().create_playlist("P")
    await LocalLibraryRepository().append(pid, [identity])
    audio.unlink()
    data = await gather_playlist(None, pid)
    assert data["tracks"][0]["local_path"] is None
    assert data["tracks"][0]["is_downloaded"] is False


@pytest.mark.asyncio
async def test_rec03c3_offline_filters_to_available(isolated_db, offline, tmp_path):
    from doremi.db.local_library_repository import LocalLibraryRepository, local_identity
    from doremi.db.repository import SongRepository, HistoryRepository
    from doremi.ui.screens.playlist_data import gather_playlist
    audio = tmp_path / "Off.flac"
    audio.write_bytes(b"fLaC")
    await LocalLibraryRepository().import_files([str(audio)])
    identity = local_identity(audio)
    await SongRepository().upsert_song(video_id=identity, title="Off", artist="", is_liked=True)
    await SongRepository().upsert_song(video_id="remote", title="On", artist="A", is_liked=True)
    pid = await LocalLibraryRepository().create_playlist("Mixed")
    await LocalLibraryRepository().append(pid, [identity, "remote"])
    data = await gather_playlist(None, pid)
    assert [t["videoId"] for t in data["tracks"]] == [identity]
    smart = await gather_playlist(None, "smart:liked")
    assert [t["videoId"] for t in smart["tracks"]] == [identity]


@pytest.mark.asyncio
async def test_rec03c3_large_playlist_explicit_pagination(isolated_db, online):
    from doremi.db.local_library_repository import LocalLibraryRepository
    from doremi.db.repository import SongRepository
    from doremi.ui.screens.playlist_data import gather_playlist
    await SongRepository().ensure_songs([dict(video_id=f"b{i}", title=f"T{i}", artist="A") for i in range(10)])
    pid = await LocalLibraryRepository().create_playlist("Big")
    await LocalLibraryRepository().append(pid, [f"b{i}" for i in range(10)])
    first = await gather_playlist(None, pid, limit=4, offset=0)
    second = await gather_playlist(None, pid, limit=4, offset=4)
    third = await gather_playlist(None, pid, limit=4, offset=8)
    assert [t["videoId"] for t in first["tracks"]] == [f"b{i}" for i in range(4)]
    assert first["has_more"] is True and first["limit"] == 4 and first["offset"] == 0
    assert [t["videoId"] for t in second["tracks"]] == [f"b{i}" for i in range(4, 8)]
    assert [t["videoId"] for t in third["tracks"]] == ["b8", "b9"]
    assert third["has_more"] is False
    assert first["tracks"] + second["tracks"] + third["tracks"] == (await gather_playlist(None, pid))["tracks"][:10]


@pytest.mark.asyncio
async def test_rec03c3_missing_covers_do_not_break(isolated_db, online):
    from doremi.db.local_library_repository import LocalLibraryRepository
    from doremi.db.repository import SongRepository
    from doremi.ui.screens.playlist_data import gather_playlist
    await SongRepository().upsert_song(video_id="nocover", title="N", artist="A")
    pid = await LocalLibraryRepository().create_playlist("C")
    await LocalLibraryRepository().append(pid, ["nocover"])
    data = await gather_playlist(None, pid)
    assert data["tracks"][0]["thumbnail_url"] == ""
    assert data["thumbnail_url"] == ""


@pytest.mark.asyncio
async def test_rec03c3_remote_preserves_artists_and_marks_downloads(isolated_db, online):
    from doremi.db.repository import DownloadRepository, SongRepository
    from doremi.ui.screens.playlist_data import gather_playlist
    await SongRepository().upsert_song(video_id="v1", title="T1", artist="A", is_liked=True)
    await DownloadRepository().add_download(video_id="v1", title="T1", artist="A", file_path="/tmp/x.mp3")

    async def fake_get_playlist(pid):
        assert pid == "PL123"
        return dict(title="Remote", author=dict(name="Author"), trackCount=2, tracks=[
            dict(videoId="v1", title="T1", artists=[dict(name="A")], duration="3:00",
                 thumbnails=[dict(url="http://img/1")], setVideoId="s1"),
            dict(videoId="v2", title="T2", artists=[dict(name="B")], duration="",
                 thumbnails=[], setVideoId=""),
        ])
    data = await gather_playlist(SimpleNamespace(get_playlist=fake_get_playlist), "PL123")
    assert data["title"] == "Remote" and data["track_count"] == 2
    assert data["tracks"][0]["artists"] == [dict(name="A")]
    assert data["tracks"][0]["is_liked"] is True and data["tracks"][0]["is_downloaded"] is True
    assert data["tracks"][1]["is_downloaded"] is False
    assert data["downloaded_count"] == 1 and data["is_fully_downloaded"] is False


@pytest.mark.asyncio
async def test_rec03c3_remote_failure_returns_empty_without_network_calls(isolated_db, online, monkeypatch):
    import urllib.request as urlreq
    monkeypatch.setattr(urlreq, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    from doremi.ui.screens.playlist_data import gather_playlist

    async def boom(pid):
        raise RuntimeError("down")
    data = await gather_playlist(SimpleNamespace(get_playlist=boom), "PLX")
    assert data["tracks"] == [] and data["title"] == ""


@pytest.mark.asyncio
async def test_rec03c3_deleted_songs_kept_as_history_not_autodeleted(isolated_db, online):
    from doremi.db.local_library_repository import LocalLibraryRepository
    from doremi.db.repository import HistoryRepository, SongRepository
    from doremi.ui.screens.playlist_data import gather_playlist
    await SongRepository().upsert_song(video_id="gone", title="G", artist="A")
    pid = await LocalLibraryRepository().create_playlist("P")
    await LocalLibraryRepository().append(pid, ["gone"])
    assert await SongRepository().delete_song("gone") is True
    # Playlist row references a missing Song: underlying tracks() inner-joins,
    # so the occurrence disappears from the view but history is preserved.
    data = await gather_playlist(None, pid)
    assert data["tracks"] == []
    await HistoryRepository().add_entry("gone", "G", "A", 1000, context_type="playlist",
                                        context_id=pid, context_title="P", listen_time_ms=1000)
    assert await HistoryRepository().get_history_count() == 1


@pytest.mark.asyncio
async def test_rec03c3_smart_pagination_beyond_1000(isolated_db, online):
    # >1000 canciones elegibles: la página offset>0 por recorte Python sobre
    # un tope de 1000 no puede recorrerlas; la paginación real viaja en SQL.
    from doremi.db.database import get_session
    from doremi.db.models import Song
    from doremi.ui.screens.playlist_data import gather_playlist
    async with get_session() as session:
        session.add_all([Song(video_id=f"v{i:04d}", title=f"T{i}", artist="A", is_liked=True)
                         for i in range(1200)])
        await session.commit()
    expected = [f"v{i:04d}" for i in range(1200)]
    first = await gather_playlist(None, "smart:liked", limit=600, offset=0)
    second = await gather_playlist(None, "smart:liked", limit=600, offset=600)
    # Las 1200 comparten puntaje (sin historial): el empate se resuelve por
    # videoId de forma determinista, así páginas consecutivas no omiten ni
    # repiten canciones.
    assert [t["videoId"] for t in first["tracks"]] == expected[:600]
    assert first["has_more"] is True
    assert [t["videoId"] for t in second["tracks"]] == expected[600:]
    assert second["has_more"] is False
    tail = await gather_playlist(None, "smart:liked", limit=600, offset=1200)
    assert tail["tracks"] == [] and tail["has_more"] is False


@pytest.mark.asyncio
async def test_rec03c3_no_n_plus_1_single_repo_call(isolated_db, online, monkeypatch):
    from doremi.db import local_library_repository as llr
    from doremi.ui.screens.playlist_data import gather_playlist
    calls = []
    orig = llr.LocalLibraryRepository.tracks

    async def counting(self, identity, limit=None, offset=0):
        calls.append((identity, limit, offset))
        return await orig(self, identity, limit=limit, offset=offset)
    monkeypatch.setattr(llr.LocalLibraryRepository, "tracks", counting)
    from doremi.db.repository import SongRepository
    await SongRepository().ensure_songs([dict(video_id=f"w{i}", title=f"T{i}", artist="A") for i in range(6)])
    pid = await llr.LocalLibraryRepository().create_playlist("P")
    await llr.LocalLibraryRepository().append(pid, [f"w{i}" for i in range(6)])
    await gather_playlist(None, pid)
    assert len(calls) == 1
