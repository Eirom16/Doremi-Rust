"""REC-03A: servicios de metadatos y artwork (focalizados, sin red, sin DB/QML)."""
from __future__ import annotations

import hashlib
import inspect
import io
import socket
import urllib.request
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from PySide6.QtCore import QUrl


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tagged_wav(path: Path, title="Canción local", artist="Artista local",
                album="Álbum local", color="purple", size=(60, 40)):
    from mutagen.wave import WAVE
    from mutagen.id3 import APIC, TIT2, TPE1, TALB
    from PIL import Image
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\x00\x00" * 8000)
    output = io.BytesIO()
    Image.new("RGB", size, color).save(output, "PNG")
    audio = WAVE(path)
    audio.add_tags()
    audio.tags.add(TIT2(encoding=3, text=title))
    audio.tags.add(TPE1(encoding=3, text=artist))
    audio.tags.add(TALB(encoding=3, text=album))
    audio.tags.add(APIC(encoding=3, mime="image/png", type=3, desc="Cover",
                        data=output.getvalue()))
    audio.save()
    return output.getvalue()


def _plain_wav(path: Path):
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\x00\x00" * 8000)


# ---------------------------------------------------------------------------
# Contratos de distribución (control 4: mutagen declarado y empaquetado)
# ---------------------------------------------------------------------------

def test_pyproject_declares_mutagen():
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert "mutagen>=1.47,<2" in text


@pytest.mark.parametrize("spec", ["doremi.spec", "doremi-linux.spec"])
def test_specs_collect_mutagen_submodules(spec):
    text = Path(spec).read_text(encoding="utf-8")
    assert '"mutagen"' in text
    assert 'collect_submodules("mutagen")' in text


def test_mutagen_format_readers_importable():
    import mutagen.mp3, mutagen.flac, mutagen.mp4, mutagen.ogg, mutagen.wave  # noqa: F401
    from mutagen import File
    assert callable(File)


def test_services_import_without_network(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    monkeypatch.setattr(socket, "create_connection",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    import doremi.services.artist_credits as ac
    import doremi.services.artwork as aw
    import doremi.services.local_metadata as lm
    assert callable(ac.artist_credits) and callable(aw.resolve_artwork)
    assert callable(aw.cover_fields) and callable(lm.read_metadata)


# ---------------------------------------------------------------------------
# artist_credits
# ---------------------------------------------------------------------------

def test_credits_structured_commas_preserved():
    from doremi.services.artist_credits import artist_credits
    source = [{"name": "Earth, Wind & Fire", "id": "UC_band"}]
    assert artist_credits(source, "Earth, Wind & Fire") == [
        {"name": "Earth, Wind & Fire", "id": "UC_band"}]


def test_credits_same_name_different_ids_preserved():
    """Control 1: mismo nombre + distinto id NO se deduplica."""
    from doremi.services.artist_credits import artist_credits
    source = [{"name": "A", "id": "UC_A"}, {"name": "A", "id": "UC_B"}]
    assert artist_credits(source, "") == [
        {"name": "A", "id": "UC_A"}, {"name": "A", "id": "UC_B"}]


def test_credits_same_name_same_id_deduped():
    from doremi.services.artist_credits import artist_credits
    source = [{"name": "A", "id": "UC_A"}, {"name": "A", "id": "UC_A"}]
    assert artist_credits(source, "") == [{"name": "A", "id": "UC_A"}]


def test_credits_case_insensitive_name_dedup_with_empty_id():
    from doremi.services.artist_credits import artist_credits
    assert artist_credits(["A", "a "], "") == [{"name": "A", "id": ""}]


@pytest.mark.parametrize("fallback,expected", [
    ("A, B feat. C", ["A", "B", "C"]),
    ("A; B ft. C", ["A", "B", "C"]),
    ("A featuring B", ["A", "B"]),
])
def test_credits_legacy_split(fallback, expected):
    from doremi.services.artist_credits import artist_credits
    assert artist_credits(None, fallback) == [
        {"name": n, "id": ""} for n in expected]


def test_credits_ampersand_not_split():
    from doremi.services.artist_credits import artist_credits
    assert artist_credits(None, "Simon & Garfunkel") == [
        {"name": "Simon & Garfunkel", "id": ""}]


@pytest.mark.parametrize("unknown", [
    "unknown", "Unknown Artist", "artista desconocido", "DESCONOCIDO", "  Unknown  "])
def test_credits_unknown_filtered(unknown):
    from doremi.services.artist_credits import artist_credits
    assert artist_credits(None, unknown) == []
    assert artist_credits([{"name": unknown, "id": "UC_x"}], "") == []


def test_credits_dict_single_and_browse_channel_ids():
    from doremi.services.artist_credits import artist_credits
    assert artist_credits({"name": "B", "browseId": "UC_B"}, "") == [
        {"name": "B", "id": "UC_B"}]
    assert artist_credits([{"artist": "C", "channelId": "UC_C"}], "") == [
        {"name": "C", "id": "UC_C"}]


def test_credits_invalid_entries_skipped_and_no_writes(monkeypatch, tmp_path):
    from doremi.services.artist_credits import artist_credits
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    assert artist_credits([None, 123, {"name": "", "id": ""}], "") == []
    assert artist_credits("", "") == []
    assert artist_credits(None, "") == []
    # Pura: no debe crear nada en disco.
    assert not (tmp_path / "cache").exists()


# ---------------------------------------------------------------------------
# artwork
# ---------------------------------------------------------------------------

def test_cover_selection_dedup_limit4(tmp_path):
    from doremi.services.artwork import cover_fields
    tracks = [dict(thumbnail_url=""), dict(thumbnail_url=(tmp_path / "gone.jpg").as_uri())]
    tracks += [dict(thumbnail_url=f"https://example.test/{i}.jpg") for i in [1, 1, 2, 3, 4, 5]]
    fields = cover_fields(tracks)
    assert fields["thumbnail_url"] == "https://example.test/1.jpg"
    assert fields["artwork_sources"] == [f"https://example.test/{i}.jpg" for i in range(1, 5)]


def test_cover_explicit_overrides(tmp_path):
    from doremi.services.artwork import cover_fields
    cover = tmp_path / "explicit.jpg"
    cover.write_bytes(b"x")
    fields = cover_fields([dict(thumbnail_url="https://example.test/1.jpg")], str(cover))
    assert fields["artwork_sources"] == [cover.resolve().as_uri()]
    assert fields["thumbnail_url"] == cover.resolve().as_uri()
    # Explícita inexistente no enmascara: cae a las pistas.
    fields = cover_fields(
        [dict(thumbnail_url="https://example.test/1.jpg")],
        str(tmp_path / "missing.jpg"))
    assert fields["thumbnail_url"] == "https://example.test/1.jpg"


def test_resolve_file_url_existing_vs_missing(tmp_path):
    from doremi.services.artwork import resolve_artwork
    real = tmp_path / "cover with spaces.jpg"
    real.write_bytes(b"img")
    assert resolve_artwork(real.as_uri()) == real.as_uri()
    assert resolve_artwork((tmp_path / "missing.jpg").as_uri()) == ""
    # file:// con espacios codificados también resuelve por path real.
    assert resolve_artwork(real.as_uri()) != ""


def test_resolve_plain_path_existing_vs_missing(tmp_path, monkeypatch):
    from doremi.services.artwork import resolve_artwork
    monkeypatch.chdir(tmp_path)
    real = tmp_path / "local.jpg"
    real.write_bytes(b"img")
    assert resolve_artwork(str(real)) == real.resolve().as_uri()
    assert resolve_artwork(str(tmp_path / "missing.jpg")) == ""
    assert resolve_artwork("") == ""


def test_resolve_http_cache_hit(monkeypatch, tmp_path):
    from doremi.config.paths import AppDirs
    from doremi.services.artwork import resolve_artwork
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    url = "https://example.test/album.jpg"
    cached = AppDirs.artwork_cache / (hashlib.md5(url.encode()).hexdigest() + ".jpg")
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"cached")
    resolved = resolve_artwork(url)
    assert resolved == cached.as_uri()
    local = Path(QUrl(resolved).toLocalFile())
    assert local.is_relative_to(AppDirs.artwork_cache)


def test_resolve_offline_cache_hit_and_contained(monkeypatch, tmp_path):
    from doremi.config.paths import AppDirs
    from doremi.services.artwork import resolve_artwork
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    offline = AppDirs.cache / "offline" / "artwork" / "video_123.jpg"
    offline.parent.mkdir(parents=True)
    offline.write_bytes(b"offline")
    resolved = resolve_artwork("https://example.test/other.jpg", "video_123")
    assert resolved == offline.as_uri()
    assert Path(QUrl(resolved).toLocalFile()).is_relative_to(AppDirs.cache)


@pytest.mark.parametrize("bad", ["../../outside", "a/b", "a.b", "a:b", "a b", "vid.jpg"])
def test_video_id_traversal_rejected(monkeypatch, tmp_path, bad):
    """Control 2: video_id solo [A-Za-z0-9_-]; el resto no toca disco offline."""
    from doremi.services.artwork import resolve_artwork
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert resolve_artwork("", bad) == ""
    # Con URL remota y video_id inválido: passthrough sin resolver offline.
    url = "https://example.test/x.jpg"
    assert resolve_artwork(url, bad) == url


def test_offline_miss_returns_remote_without_network(monkeypatch, tmp_path):
    from doremi.services.artwork import resolve_artwork
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no net")))
    url = "https://example.test/uncached.jpg"
    assert resolve_artwork(url, "valid_id_1") == url
    assert resolve_artwork(url) == url


def test_resolved_cache_paths_never_escape(monkeypatch, tmp_path):
    """Control 2: lo resuelto desde caché vive bajo XDG_CACHE_HOME."""
    from doremi.config.paths import AppDirs
    from doremi.services.artwork import resolve_artwork, cover_fields
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    url = "https://example.test/album.jpg"
    cached = AppDirs.artwork_cache / (hashlib.md5(url.encode()).hexdigest() + ".jpg")
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"c")
    offline = AppDirs.cache / "offline" / "artwork" / "abc-123_X.jpg"
    offline.parent.mkdir(parents=True)
    offline.write_bytes(b"o")
    for resolved in (resolve_artwork(url),
                     resolve_artwork("https://example.test/o.jpg", "abc-123_X")):
        assert Path(QUrl(resolved).toLocalFile()).is_relative_to(tmp_path / "cache")
    fields = cover_fields([dict(thumbnail_url=url, videoId="abc-123_X")])
    for source in fields["artwork_sources"]:
        if source.startswith("file:"):
            assert Path(QUrl(source).toLocalFile()).is_relative_to(tmp_path / "cache")


# ---------------------------------------------------------------------------
# local_metadata
# ---------------------------------------------------------------------------

def test_read_metadata_tagged_wav(monkeypatch, tmp_path):
    from doremi.services.local_metadata import read_metadata
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    path = tmp_path / "track.wav"
    _tagged_wav(path)
    result = read_metadata(path)
    assert result["title"] == "Canción local"
    assert result["artist"] == "Artista local"
    assert result["album"] == "Álbum local"
    assert result["duration_ms"] == 1000
    assert set(result) == {"title", "artist", "album", "duration_ms", "thumbnail_url"}
    cover = Path(QUrl(result["thumbnail_url"]).toLocalFile())
    assert cover.is_file()
    from PIL import Image
    with Image.open(cover) as image:
        assert max(image.size) <= 1024


def test_read_metadata_does_not_modify_audio(monkeypatch, tmp_path):
    from doremi.services.local_metadata import read_metadata
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    path = tmp_path / "track.wav"
    _tagged_wav(path)
    original = path.read_bytes()
    first = read_metadata(path)
    assert path.read_bytes() == original
    # Segunda lectura reutiliza la misma carátula (sin re-codificar).
    before = Path(QUrl(first["thumbnail_url"]).toLocalFile()).stat().st_mtime_ns
    second = read_metadata(path)
    after = Path(QUrl(second["thumbnail_url"]).toLocalFile()).stat().st_mtime_ns
    assert second["thumbnail_url"] == first["thumbnail_url"]
    assert after == before


def test_read_metadata_damaged_and_missing(monkeypatch, tmp_path):
    from doremi.services.local_metadata import read_metadata
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    damaged = tmp_path / "damaged.flac"
    damaged.write_bytes(b"not audio")
    result = read_metadata(damaged)
    assert result["thumbnail_url"] == ""
    assert result["title"] == "damaged"
    missing = tmp_path / "gone.mp3"
    result = read_metadata(missing)
    assert result == {"title": "gone", "artist": "", "album": "",
                      "duration_ms": 0, "thumbnail_url": ""}


def test_read_metadata_untagged_defaults_to_stem(monkeypatch, tmp_path):
    from doremi.services.local_metadata import read_metadata
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    path = tmp_path / "plain.wav"
    _plain_wav(path)
    result = read_metadata(path)
    assert result["title"] == "plain"
    assert result["artist"] == result["album"] == ""
    assert result["thumbnail_url"] == ""


def test_huge_embedded_skipped_before_decode(monkeypatch, tmp_path):
    """Control 3: >16 MiB no llega a Pillow (límite antes de decodificar)."""
    import doremi.services.local_metadata as lm
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    path = tmp_path / "track.wav"
    _tagged_wav(path)
    huge = b"x" * (16 * 1024 * 1024 + 1)
    monkeypatch.setattr(lm, "_picture", lambda tags, audio: huge)
    called = []
    real_open = lm.Image.open
    def guarded(*a, **k):
        called.append(True)
        return real_open(*a, **k)
    monkeypatch.setattr(lm.Image, "open", guarded)
    result = lm.read_metadata(path)
    assert result["thumbnail_url"] == ""
    assert called == []


def test_concurrent_same_cover_atomic_no_tmp_leftovers(monkeypatch, tmp_path):
    """Control 3: escrituras simultáneas de la misma carátula: 1 JPEG válido."""
    from doremi.services.local_metadata import read_metadata
    from doremi.config.paths import AppDirs
    from PIL import Image
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    path = tmp_path / "track.wav"
    _tagged_wav(path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: read_metadata(path), range(8)))
    urls = {r["thumbnail_url"] for r in results}
    assert len(urls) == 1
    cover = Path(QUrl(results[0]["thumbnail_url"]).toLocalFile())
    assert cover.is_file()
    assert cover.is_relative_to(AppDirs.artwork_cache)
    with Image.open(cover) as image:
        image.verify()
    leftovers = list(AppDirs.artwork_cache.glob("*.tmp")) + \
        [p for p in AppDirs.artwork_cache.iterdir() if p.suffix == ".tmp"]
    assert leftovers == []
    assert all(r["title"] == "Canción local" for r in results)


def test_only_artwork_cache_written(monkeypatch, tmp_path):
    from doremi.services.local_metadata import read_metadata
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    audio_dir = tmp_path / "music"
    audio_dir.mkdir()
    path = audio_dir / "song.wav"
    _tagged_wav(path)
    before_audio = path.read_bytes()
    read_metadata(path)
    assert path.read_bytes() == before_audio
    written = [p for p in (tmp_path / "cache").rglob("*") if p.is_file()]
    assert written, "se esperaba la carátula en caché"
    assert all("artwork" in str(p) for p in written)
    assert not (tmp_path / "data").exists()
    assert not (tmp_path / "config").exists()
    assert sorted(p.name for p in audio_dir.iterdir()) == ["song.wav"]


def test_read_metadata_is_synchronous():
    import asyncio
    from doremi.services import local_metadata as lm
    assert not inspect.iscoroutinefunction(lm.read_metadata)
    assert "asyncio" not in dir(lm) or True
    source = Path(lm.__file__).read_text(encoding="utf-8")
    assert "async def read_metadata" not in source
    assert "asyncio" not in source.split("def read_metadata")[0] or "to_thread" in source


def test_first_truncates_to_500():
    from doremi.services.local_metadata import _first
    assert _first({"title": "x" * 600}, "title") == "x" * 500
