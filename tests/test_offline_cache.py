from __future__ import annotations

from pathlib import Path

import pytest

from doremi.config.settings import AppSettings
from doremi.services.offline_cache import OfflineCacheManager


def _manager(tmp_path: Path) -> OfflineCacheManager:
    manager = OfflineCacheManager()
    manager.root = tmp_path / "offline"
    manager.audio_dir = manager.root / "audio"
    manager.artwork_dir = manager.root / "artwork"
    manager.feed_path = manager.root / "home.json"
    manager.manifest_path = manager.root / "manifest.json"
    manager._setup()
    return manager


def test_settings_define_bounded_offline_cache():
    settings = AppSettings()
    assert settings.offline.enabled is True
    assert settings.offline.song_limit == 25
    with pytest.raises(ValueError):
        AppSettings(offline={"song_limit": 101})


def test_load_home_only_exposes_playable_cached_tracks(tmp_path):
    manager = _manager(tmp_path)
    audio = manager.audio_dir / "cached01.m4a"
    audio.write_bytes(b"audio")
    manager._write_json(manager.feed_path, {
        "tiles": [
            {"videoId": "cached01", "title": "Guardada", "artist": "A"},
            {"videoId": "missing1", "title": "No disponible", "artist": "B"},
        ],
        "songs": [],
        "horizontal": [{"navigate": "playlist?id=online"}],
    })
    manager._write_json(manager.manifest_path, {
        "cached01": {"audio_path": str(audio), "title": "Guardada", "artist": "A"},
        "missing1": {"audio_path": str(manager.audio_dir / "missing.m4a")},
    })

    home = manager.load_home()

    assert home["_source"] == "cache"
    assert [item["videoId"] for item in home["tiles"]] == ["cached01"]
    assert home["horizontal"] == []
    assert home["sections"] == []
    assert home["spotlight"][0]["navigate"] == "play:cached01"
    assert manager.local_path("cached01") == str(audio)
    assert manager.local_path("missing1") is None


@pytest.mark.asyncio
async def test_sync_rotates_old_tracks_and_respects_limit(tmp_path, monkeypatch):
    manager = _manager(tmp_path)
    old_audio = manager.audio_dir / "old0001.m4a"
    old_audio.write_bytes(b"old")
    manager._write_json(manager.manifest_path, {
        "old0001": {
            "audio_path": str(old_audio), "cached_at": 1, "last_seen": 1,
        }
    })

    async def fake_download(video_id: str):
        path = manager.audio_dir / f"{video_id}.m4a"
        path.write_bytes(video_id.encode())
        return path

    async def no_artwork(video_id: str, url: str):
        return None

    monkeypatch.setattr(manager, "_download_track", fake_download)
    monkeypatch.setattr(manager, "_cache_artwork", no_artwork)
    feed = {"tiles": [], "songs": [
        {"videoId": "new0001", "title": "Uno", "artist": "A"},
        {"videoId": "new0002", "title": "Dos", "artist": "B"},
        {"videoId": "new0003", "title": "Tres", "artist": "C"},
    ]}

    await manager.sync_from_feed(feed, limit=2)

    manifest = manager._manifest()
    assert set(manifest) == {"new0001", "new0002"}
    assert not old_audio.exists()


@pytest.mark.asyncio
async def test_download_track_falls_back_to_combined_format(tmp_path, monkeypatch):
    manager = _manager(tmp_path)
    captured: list[str] = []

    class Process:
        returncode = 0

        async def communicate(self):
            (manager.audio_dir / "video01.mp4").write_bytes(b"audio")
            return b"", b""

    async def create_process(*args, **_kwargs):
        captured.extend(args)
        return Process()

    monkeypatch.setattr("asyncio.create_subprocess_exec", create_process)

    result = await manager._download_track("video01")

    assert result == manager.audio_dir / "video01.mp4"
    assert captured[captured.index("-f") + 1].endswith("/best")


@pytest.mark.asyncio
async def test_download_track_passes_keyring_credentials(tmp_path, monkeypatch):
    """La descarga pasa la cookie del llavero como header al CLI de yt-dlp."""
    manager = _manager(tmp_path)
    captured: list[str] = []

    class Process:
        returncode = 0

        async def communicate(self):
            (manager.audio_dir / "video02.m4a").write_bytes(b"audio")
            return b"", b""

    async def create_process(*args, **_kwargs):
        captured.extend(args)
        return Process()

    from doremi.utils.secure_storage import SecureStorage
    monkeypatch.setattr(
        SecureStorage,
        "load_youtube_headers",
        classmethod(lambda cls: {"cookie": "sid=abc", "user-agent": "UA-Test"}),
    )
    monkeypatch.setattr("asyncio.create_subprocess_exec", create_process)

    result = await manager._download_track("video02")

    assert result == manager.audio_dir / "video02.m4a"
    assert captured[captured.index("--add-headers") + 1] == "Cookie:sid=abc"
    assert captured[captured.index("--user-agent") + 1] == "UA-Test"


@pytest.mark.asyncio
async def test_gather_home_uses_cache_when_network_returns_nothing(tmp_path, monkeypatch):
    manager = _manager(tmp_path)
    audio = manager.audio_dir / "cached02.webm"
    audio.write_bytes(b"audio")
    manager._write_json(manager.manifest_path, {
        "cached02": {
            "audio_path": str(audio), "title": "Offline", "artist": "Artista",
        }
    })
    monkeypatch.setattr(OfflineCacheManager, "_instance", manager)

    class EmptyClient:
        async def get_home(self):
            return []

        async def get_charts(self):
            return []

    from doremi.ui.screens.home_data import gather_home
    home = await gather_home(EmptyClient())

    assert home["_source"] == "cache"
    assert [item["videoId"] for item in home["songs"]] == ["cached02"]
