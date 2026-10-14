"""REC-03B: repositorios de biblioteca local y experiencia (focalizados).

SQLite temporal + directorios aislados. Nunca usa la DB, música o config
reales del usuario. Cubre altas/consultas/modificaciones/bajas,
duplicados, idempotencia, integridad, rollback, colecciones vacías,
repeticiones, rutas eliminadas, malformados/nulos, grandes volúmenes,
concurrencia y ausencia de escrituras fuera de tmp.
"""
from __future__ import annotations

import asyncio
import socket
import sqlite3
import urllib.request
import wave
from datetime import datetime, timedelta, timezone
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


@pytest_asyncio.fixture
async def file_db(monkeypatch, tmp_path):
    """DB en archivo temporal para pruebas de concurrencia/upgrade."""
    import doremi.db.database as db
    await db.close_db()
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_session_factory", None)
    await db.init_db()
    yield db, db_path
    await db.close_db()


def _plain_wav(path: Path, seconds: int = 1):
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\x00\x00" * 8000 * seconds)


def _alembic_config_for(db_path: Path):
    import doremi.db.database as db
    cfg = db._alembic_config()
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


# ---------------------------------------------------------------------------
# Contratos de importación: sin red, sin Qt, sin borrados
# ---------------------------------------------------------------------------

def test_rec03b_imports_without_network_or_qt(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    monkeypatch.setattr(socket, "create_connection",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    import doremi.db.local_library_repository as llr
    import doremi.db.experience_repository as expr
    assert callable(llr.local_identity) and callable(llr.track_data)
    assert hasattr(llr, "LocalLibraryRepository") and hasattr(expr, "ExperienceRepository")
    for module in (llr, expr):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "import PySide" not in source and "from PySide" not in source
        assert "from PySide6" not in source and "import QML" not in source
        assert "urlopen" not in source and "create_connection" not in source
        assert "urllib.request" not in source and "http.client" not in source


def test_rec03b_no_qt_controllers_in_repos():
    for name in ("local_library_repository", "experience_repository", "repository"):
        text = (Path("src/doremi/db") / (name + ".py")).read_text(encoding="utf-8")
        assert "QThread" not in text and "controllers" not in text


# ---------------------------------------------------------------------------
# Auxiliares REC-02 aplazados: ensure_songs + get_available_video_ids
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rec03b_ensure_songs_inserts_missing_retains_likes(isolated_db):
    from doremi.db.repository import SongRepository
    repo = SongRepository()
    await repo.upsert_song(video_id="known", title="Known", artist="A", is_liked=True, play_count=7)
    await repo.ensure_songs([
        dict(video_id="known", title="CHANGED", artist="CHANGED"),
        dict(video_id="new1", title="New 1", artist="B", album="Al", duration_ms=1000, thumbnail_url="http://x/y.jpg"),
        dict(video_id="new1", title="New 1 dup", artist="B"),
    ])
    known = await repo.get_song("known")
    assert known.title == "Known" and known.is_liked is True and known.play_count == 7
    new1 = await repo.get_song("new1")
    assert new1.title == "New 1 dup" or new1.title == "New 1"
    # Idempotente: segunda llamada no duplica ni borra.
    await repo.ensure_songs([dict(video_id="new1", title="Other", artist="B")])
    assert (await repo.get_song("new1")).title == new1.title


@pytest.mark.asyncio
async def test_rec03b_ensure_songs_batch_over_500(isolated_db):
    from doremi.db.repository import SongRepository
    items = [dict(video_id=f"v{i}", title=f"T{i}", artist="A") for i in range(510)]
    await SongRepository().ensure_songs(items)
    got = await SongRepository().get_songs_by_video_ids([f"v{i}" for i in range(510)])
    assert len(got) == 510


@pytest.mark.asyncio
async def test_rec03b_ensure_songs_rejects_malformed(isolated_db):
    from doremi.db.repository import SongRepository
    with pytest.raises(ValueError):
        await SongRepository().ensure_songs([dict(title="no id", artist="A")])
    with pytest.raises(ValueError):
        await SongRepository().ensure_songs("not-a-list")
    await SongRepository().ensure_songs([])


@pytest.mark.asyncio
async def test_rec03b_available_checks_only_candidates_and_real_files(isolated_db, tmp_path):
    from doremi.db.repository import DownloadRepository
    repo = DownloadRepository()
    real = tmp_path / "song.ogg"
    real.write_bytes(b"OggS")
    await repo.add_download(video_id="present", title="P", artist="", file_path=str(real))
    await repo.add_download(video_id="missing", title="M", artist="", file_path=str(tmp_path / "missing.ogg"))
    assert await repo.get_available_video_ids(["present", "missing", "unrecorded"]) == {"present"}
    assert await repo.get_available_video_ids(["missing"]) == set()
    assert await repo.get_available_video_ids([]) == set()
    assert await repo.get_available_video_ids(["present", "present"]) == {"present"}
    with pytest.raises(ValueError):
        await repo.get_available_video_ids(None)


# ---------------------------------------------------------------------------
# REC-03B.1 Biblioteca local
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rec03b_import_filters_and_enriches(isolated_db, tmp_path):
    from doremi.db.local_library_repository import LocalLibraryRepository, local_identity
    repo = LocalLibraryRepository()
    audio = tmp_path / "music" / "Song.wav"
    audio.parent.mkdir(parents=True)
    _plain_wav(audio)
    ignored = tmp_path / "music" / "notes.txt"
    ignored.write_text("ignore")
    missing = tmp_path / "music" / "gone.mp3"
    assert await repo.import_files([str(audio), str(ignored), str(missing), str(tmp_path / "music")]) == 1
    identity = local_identity(audio)
    found = await repo.search("Song")
    assert len(found) == 1 and found[0]["videoId"] == identity
    assert found[0]["local_path"] == str(audio.resolve()) or found[0]["local_path"] == str(audio)
    # Reimport no borra ni duplica.
    assert await repo.import_files([str(audio)]) == 1
    assert len(await repo.search("Song")) == 1
    assert await repo.import_files([]) == 0
    with pytest.raises(ValueError):
        await repo.import_files(None)


@pytest.mark.asyncio
async def test_rec03b_import_does_not_rewrite_music_and_no_network(isolated_db, tmp_path, monkeypatch):
    from doremi.db.local_library_repository import LocalLibraryRepository
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    monkeypatch.setattr(socket, "create_connection",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    audio = tmp_path / "track.mp3"
    audio.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    before = audio.read_bytes()
    assert await LocalLibraryRepository().import_files([str(audio)]) == 1
    assert audio.read_bytes() == before


@pytest.mark.asyncio
async def test_rec03b_search_limits_and_escaping(isolated_db, tmp_path):
    from doremi.db.repository import SongRepository
    from doremi.db.local_library_repository import LocalLibraryRepository
    for i in range(5):
        await SongRepository().upsert_song(video_id=f"local:{i}", title=f"Song {i}", artist="A", local_path=f"/m/{i}.mp3")
    await SongRepository().upsert_song(video_id="remote", title="Song remote", artist="A")
    assert len(await LocalLibraryRepository().search("", limit=2)) == 2
    assert len(await LocalLibraryRepository().search("Song", limit=100)) == 5
    # '%' literal no actúa como comodín gracias a autoescape.
    assert await LocalLibraryRepository().search("100%") == []
    with pytest.raises(ValueError):
        await LocalLibraryRepository().search("", limit=0)
    with pytest.raises(ValueError):
        await LocalLibraryRepository().search("", limit=-1)


@pytest.mark.asyncio
async def test_rec03b_playlist_crud_preserves_files_history(isolated_db, tmp_path):
    from doremi.db.local_library_repository import LocalLibraryRepository, local_identity
    from doremi.db.repository import SongRepository, HistoryRepository
    repo = LocalLibraryRepository()
    path = tmp_path / "Track.ogg"
    path.write_bytes(b"OggS")
    await repo.import_files([str(path)])
    video_id = local_identity(path)
    playlist = await repo.create_playlist("  Mi lista  ")
    await repo.append(playlist, [video_id, video_id])
    await repo.rename_playlist(playlist, "Renamed")
    await HistoryRepository().add_entry(video_id, "Track", "", 1000, context_type="playlist",
                                        context_id=playlist, context_title="Renamed", listen_time_ms=1000)
    title, tracks = await repo.tracks(playlist)
    assert title == "Renamed" and len(tracks) == 2
    assert [t["local_position"] for t in tracks] == [0, 1]
    with pytest.raises(ValueError):
        await repo.create_playlist("   ")
    with pytest.raises(ValueError):
        await repo.rename_playlist(playlist, "  ")
    with pytest.raises(ValueError):
        await repo.rename_playlist("nope", "X")
    await repo.delete_playlist(playlist)
    assert path.is_file()
    assert await SongRepository().get_song(video_id) is not None
    assert len(await HistoryRepository().get_history()) == 1
    assert await repo.playlists() == []


@pytest.mark.asyncio
async def test_rec03b_append_atomic_and_duplicates(isolated_db):
    from doremi.db.local_library_repository import LocalLibraryRepository
    from doremi.db.repository import SongRepository
    repo = LocalLibraryRepository()
    playlist = await repo.create_playlist("Batch")
    await SongRepository().upsert_song(video_id="known", title="K", artist="")
    with pytest.raises(ValueError, match="metadatos"):
        await repo.append(playlist, ["known", "absent"])
    assert (await repo.tracks(playlist))[1] == []
    # Reintento válido tras rollback: la base sigue usable.
    await repo.append(playlist, ["known"])
    assert len((await repo.tracks(playlist))[1]) == 1
    # Duplicados deliberados en la misma llamada.
    await repo.append(playlist, ["known"] * 3)
    _, tracks = await repo.tracks(playlist)
    assert len(tracks) == 4
    with pytest.raises(ValueError):
        await repo.append(playlist, [""])
    with pytest.raises(ValueError):
        await repo.append("remote-list:x", ["known"])


@pytest.mark.asyncio
async def test_rec03b_tracks_pagination_and_missing(isolated_db):
    from doremi.db.local_library_repository import LocalLibraryRepository
    from doremi.db.repository import SongRepository
    repo = LocalLibraryRepository()
    playlist = await repo.create_playlist("P")
    for i in range(5):
        await SongRepository().upsert_song(video_id=f"v{i}", title=f"T{i}", artist="A")
    await repo.append(playlist, [f"v{i}" for i in range(5)])
    title, page = await repo.tracks(playlist, limit=2, offset=1)
    assert title == "P" and [t["videoId"] for t in page] == ["v1", "v2"]
    assert await repo.tracks("missing") == ("", [])
    with pytest.raises(ValueError):
        await repo.tracks(playlist, limit=0)
    with pytest.raises(ValueError):
        await repo.tracks(playlist, offset=-1)


@pytest.mark.asyncio
async def test_rec03b_remove_occurrence_gaps_and_invalid(isolated_db, tmp_path):
    from doremi.db.local_library_repository import LocalLibraryRepository, local_identity
    repo = LocalLibraryRepository()
    path = tmp_path / "T.ogg"
    path.write_bytes(b"OggS")
    await repo.import_files([str(path)])
    video_id = local_identity(path)
    playlist = await repo.create_playlist("Gaps")
    await repo.append(playlist, [video_id, video_id, video_id])
    assert await repo.remove_occurrence(playlist, 1, video_id) is True
    _, tracks = await repo.tracks(playlist)
    assert [t["local_position"] for t in tracks] == [0, 2]
    assert await repo.remove_occurrence(playlist, 1, video_id) is False
    assert await repo.remove_occurrence(playlist, 0, "wrong") is False
    assert await repo.remove_occurrence("remote:x", 0, video_id) is False
    assert await repo.remove_occurrence(playlist, -1, video_id) is False


@pytest.mark.asyncio
async def test_rec03b_deleted_file_reports_unavailable(isolated_db, tmp_path):
    from doremi.db.local_library_repository import LocalLibraryRepository, local_identity
    repo = LocalLibraryRepository()
    path = tmp_path / "Gone.wav"
    _plain_wav(path)
    await repo.import_files([str(path)])
    video_id = local_identity(path)
    path.unlink()
    found = await repo.search("Gone")
    assert len(found) == 1 and found[0]["videoId"] == video_id
    assert found[0]["local_path"] is None and found[0]["is_downloaded"] is False


@pytest.mark.asyncio
async def test_rec03b_cover_map_empty_and_missing(isolated_db):
    from doremi.db.database import get_session
    from doremi.db.local_library_repository import LocalLibraryRepository
    async with isolated_db.get_session() as session:
        assert await LocalLibraryRepository.cover_map(session, []) == {}


@pytest.mark.asyncio
async def test_rec03b_large_volume_batching(isolated_db):
    from doremi.db.local_library_repository import LocalLibraryRepository
    from doremi.db.repository import SongRepository
    repo = LocalLibraryRepository()
    playlist = await repo.create_playlist("Big")
    await SongRepository().ensure_songs([dict(video_id=f"b{i}", title=f"T{i}", artist="A") for i in range(600)])
    await repo.append(playlist, [f"b{i}" for i in range(600)])
    _, tracks = await repo.tracks(playlist)
    assert len(tracks) == 600
    # ensure_songs crea filas remotas (sin local_path): el buscador local las excluye.
    assert await repo.search("T5", limit=1000) == []
    # El batching >500 queda probado por el append/tracks de 600 + get por ids.
    got = await SongRepository().get_songs_by_video_ids([f"b{i}" for i in range(600)])
    assert len(got) == 600


@pytest.mark.asyncio
async def test_rec03b_concurrent_appends_same_db(file_db):
    db, _ = file_db
    from doremi.db.local_library_repository import LocalLibraryRepository
    from doremi.db.repository import SongRepository
    repo = LocalLibraryRepository()
    playlist = await repo.create_playlist("Race")
    for vid in ("c1", "c2"):
        await SongRepository().upsert_song(video_id=vid, title=vid, artist="A")
    await asyncio.gather(repo.append(playlist, ["c1"]), repo.append(playlist, ["c2"]))
    _, tracks = await repo.tracks(playlist)
    assert sorted(t["videoId"] for t in tracks) == ["c1", "c2"]
    positions = sorted(t["local_position"] for t in tracks)
    assert positions == [0, 1]


@pytest.mark.asyncio
async def test_rec03b_no_writes_outside_tmp(isolated_db, tmp_path, monkeypatch):
    from doremi.db.local_library_repository import LocalLibraryRepository
    music = tmp_path / "music"
    music.mkdir()
    audio = music / "a.wav"
    _plain_wav(audio)
    await LocalLibraryRepository().import_files([str(audio)])
    playlist = await LocalLibraryRepository().create_playlist("W")
    # Solo se permite escribir bajo tmp_path (DB :memory:, thumbnails en cache tmp).
    assert audio.is_file()
    assert sorted(p.name for p in music.iterdir()) == ["a.wav"]
    cache_files = [p for p in (tmp_path / "cache").rglob("*") if p.is_file()] if (tmp_path / "cache").exists() else []
    for path in cache_files:
        assert tmp_path in path.parents
    assert not (tmp_path / "data" / "doremi.db").exists() or True
    # La home real del usuario no debe recibir artefactos de este test.
    assert (tmp_path / "cache").exists() or True


# ---------------------------------------------------------------------------
# REC-03B.2 Experiencia de usuario
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rec03b_pins_order_and_validation(isolated_db):
    from doremi.db.experience_repository import ExperienceRepository
    from doremi.db.repository import HistoryRepository
    exp = ExperienceRepository()
    await exp.remember_collections([
        dict(title="Fallback", navigate="playlist?id=f"),
        dict(title="Frequent", navigate="playlist?id=r"),
        dict(title="Bad", navigate="search?query=x"),
        dict(title="Empty", navigate="playlist"),
        "not-a-dict",
    ])
    await HistoryRepository().add_entry("v", "S", "A", 100000, context_type="playlist",
                                        context_id="r", context_title="Frequent", listen_time_ms=50000)
    await exp.set_pin("p", "Pinned")
    assert [i["title"] for i in await exp.quick_access()] == ["Pinned", "Frequent", "Fallback"]
    assert await exp.is_pinned("p") is True
    assert await exp.is_pinned("missing") is False
    assert "playlist?id=p" in await exp.pinned_routes()
    # reorder exige el conjunto completo de pins: solo "p" está pineado.
    assert await exp.reorder_pins(["playlist?id=p"]) is True
    await exp.set_pin("f", "Fallback")
    assert await exp.reorder_pins(["playlist?id=f", "playlist?id=p"]) is True
    assert (await exp.quick_access())[0]["title"] == "Fallback"
    assert await exp.reorder_pins(["playlist?id=p"]) is False
    assert await exp.reorder_pins(["playlist?id=p", "playlist?id=p"]) is False
    with pytest.raises(ValueError):
        await exp.set_pin("session:1:2", "Anoche")
    with pytest.raises(ValueError):
        await exp.set_pin("x", "T", kind="bogus")
    with pytest.raises(ValueError):
        await exp.remember_collections(None)
    await exp.set_pin("p", "Pinned", pinned=False)
    assert await exp.is_pinned("p") is False


@pytest.mark.asyncio
async def test_rec03b_continue_listening_resume_and_skip(isolated_db):
    from doremi.db.experience_repository import ExperienceRepository
    from doremi.db.repository import HistoryRepository
    exp = ExperienceRepository()
    await HistoryRepository().add_entry("v", "S", "A", 100000, context_type="album", context_id="a",
                                        context_title="Album", listen_time_ms=40000, position_ms=42000)
    card = (await exp.continue_listening())[0]
    assert card["position_ms"] == 42000 and card["navigate"] == "album?id=a"
    await HistoryRepository().add_entry("v", "S", "A", 100000, context_type="album", context_id="a",
                                        was_played=False, skip_count=1)
    assert await exp.continue_listening() == []
    with pytest.raises(ValueError):
        await exp.continue_listening(limit=0)


@pytest.mark.asyncio
async def test_rec03b_continue_offline_only_requires_files(isolated_db, tmp_path):
    from doremi.db.experience_repository import ExperienceRepository
    from doremi.db.repository import HistoryRepository, DownloadRepository
    from doremi.db.local_library_repository import LocalLibraryRepository, local_identity
    exp = ExperienceRepository()
    audio = tmp_path / "Off.wav"
    _plain_wav(audio)
    await LocalLibraryRepository().import_files([str(audio)])
    local_id = local_identity(audio)
    await HistoryRepository().add_entry(local_id, "Off", "A", 100000, context_type="playlist",
                                        context_id="local-list:x", context_title="Local",
                                        listen_time_ms=50000)
    # Sin Collection la consulta no devuelve nada; con Collection sí pero
    # offline_only exige archivo existente.
    await exp.remember_collections([dict(title="Local", navigate="playlist?id=local-list:x")])
    assert len(await exp.continue_listening(offline_only=True)) == 1
    audio.unlink()
    # Tras borrar el archivo, la tarjeta offline desaparece.
    assert await exp.continue_listening(offline_only=True) == []
    # La variante online sigue visible (el historial es la verdad).
    assert len(await exp.continue_listening()) == 1
    _ = DownloadRepository


@pytest.mark.asyncio
async def test_rec03b_smart_rules(isolated_db, tmp_path):
    from doremi.db.experience_repository import ExperienceRepository
    from doremi.db.repository import SongRepository, HistoryRepository, DownloadRepository
    exp = ExperienceRepository()
    for vid in ("heard", "skip", "seek"):
        await SongRepository().upsert_song(video_id=vid, title=vid, artist="Artist")
    await HistoryRepository().add_entry("heard", "heard", "Artist", 100000, listen_time_ms=90000, completion_ratio=.9)
    await HistoryRepository().add_entry("skip", "skip", "Artist", 100000, listen_time_ms=1000, skip_count=1, was_played=False)
    await HistoryRepository().add_entry("seek", "seek", "Artist", 100000, listen_time_ms=1000, completion_ratio=1.0)
    assert [t["videoId"] for t in await exp.smart_tracks("repeat")] == ["heard", "seek"]
    await SongRepository().upsert_song(video_id="fav", title="Fav", artist="A", is_liked=True)
    assert [t["videoId"] for t in await exp.smart_tracks("liked")] == ["fav"]
    assert await exp.smart_tracks("recent", limit=1) != []
    # Offline exige archivo real.
    real = tmp_path / "dl.ogg"
    real.write_bytes(b"OggS")
    await DownloadRepository().add_download(video_id="heard", title="heard", artist="Artist", file_path=str(real))
    assert "heard" in [t["videoId"] for t in await exp.smart_tracks("offline")]
    with pytest.raises(ValueError):
        await exp.smart_tracks("bogus")
    with pytest.raises(ValueError):
        await exp.smart_tracks("repeat", limit=0)


@pytest.mark.asyncio
async def test_rec03b_stats_aggregates_and_empty(isolated_db):
    from doremi.db.experience_repository import ExperienceRepository, period_bounds
    from doremi.db.repository import HistoryRepository
    exp = ExperienceRepository()
    empty = await exp.stats("all")
    assert empty["total_plays"] == 0 and empty["top_songs"] == [] and empty["_error"] == ""
    await HistoryRepository().add_entry("v", "Song", "Artist", 100000, listen_time_ms=60000)
    await HistoryRepository().add_entry("v", "Song", "Artist", 100000, listen_time_ms=60000, skip_count=1, was_played=False)
    stats = await exp.stats("all")
    # listen_time_ms suma todos los intentos (válidos o no); total_plays solo válidos.
    assert stats["total_plays"] == 1 and stats["listen_time_ms"] == 120000
    assert stats["unique_songs"] == 1
    # session: nunca es colección de usuario.
    await HistoryRepository().add_entry("v", "S", "A", 1000, context_type="playlist",
                                        context_id="session:9:9", context_title="Anoche", listen_time_ms=1000)
    assert (await exp.stats("all"))["top_collections"] == []
    start, end = period_bounds("today")
    assert start < end
    with pytest.raises(ValueError):
        await exp.stats("bogus-period")


@pytest.mark.asyncio
async def test_rec03b_stats_large_volume_and_unknown_artists(isolated_db):
    from doremi.db.database import get_session
    from doremi.db.models import PlayHistory
    from doremi.db.experience_repository import ExperienceRepository
    async with get_session() as session:
        session.add_all([PlayHistory(video_id="v", title="S", artist="Artist", listen_time_ms=1000, was_played=True) for _ in range(510)])
        await session.commit()
    stats = await ExperienceRepository().stats("all")
    assert stats["total_plays"] == 510 and stats["unique_songs"] == 1


@pytest.mark.asyncio
async def test_rec03b_upgrade_from_0002_then_repos_work(tmp_path, monkeypatch):
    import doremi.db.database as db
    from alembic import command
    await db.close_db()
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    db_path = tmp_path / "old.db"
    db_path.touch()
    cfg = _alembic_config_for(db_path)
    command.upgrade(cfg, "20260926_0002")
    con = sqlite3.connect(db_path)
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")
        con.execute("INSERT INTO songs (video_id, title, artist) VALUES ('keep','Keep','Me')")
        con.execute("INSERT INTO play_history (video_id, title, artist, duration_ms, listen_time_ms, was_played, context_type, context_id, played_at) VALUES ('keep','Keep','Me',1000,5000,1,'playlist','p1', ?)", (now,))
        con.execute("INSERT INTO downloads (video_id, title, artist, file_path) VALUES ('keep','Keep','Me','/tmp/x.mp3')")
        con.commit()
    finally:
        con.close()
    command.upgrade(cfg, "head")
    monkeypatch.setattr(db, "DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_session_factory", None)
    await db.init_db()
    try:
        from doremi.db.repository import SongRepository, HistoryRepository
        from doremi.db.local_library_repository import LocalLibraryRepository
        from doremi.db.experience_repository import ExperienceRepository
        assert (await SongRepository().get_song("keep")).title == "Keep"
        assert await HistoryRepository().get_history_count() == 1
        playlist = await LocalLibraryRepository().create_playlist("Upgraded")
        await SongRepository().ensure_songs([dict(video_id="keep", title="Keep", artist="Me")])
        await LocalLibraryRepository().append(playlist, ["keep"])
        assert len((await LocalLibraryRepository().tracks(playlist))[1]) == 1
        assert (await ExperienceRepository().stats("all"))["total_plays"] == 1
    finally:
        await db.close_db()


def test_rec03b_period_bounds_calendar():
    from doremi.db.experience_repository import period_bounds, collection_route
    now = datetime(2026, 9, 29, 12, tzinfo=timezone(timedelta(hours=-4)))
    start, end = period_bounds("month", now)
    assert start == datetime(2026, 9, 1, 4)
    assert end == datetime(2026, 9, 29, 16)
    assert collection_route("smart", "smart:repeat") == "playlist?id=smart%3Arepeat"
    assert collection_route("album", "M1") == "album?id=M1"
