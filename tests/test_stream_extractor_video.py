"""Pruebas de extracción del stream visual para Now Playing."""
from __future__ import annotations

import pytest

from doremi.api.stream_extractor import StreamExtractor
from types import SimpleNamespace


@pytest.fixture(autouse=True)
def _avoid_host_keyring_for_stream_extractor_tests(monkeypatch, request):
    """Video-format tests must not contact the user's desktop keyring."""
    if request.node.name != "test_get_stream_info_includes_stored_cookies":
        monkeypatch.setattr(StreamExtractor, "_load_cookie_opts", staticmethod(lambda: {}))


class _FakeYoutubeDL:
    last_options = None

    def __init__(self, options):
        type(self).last_options = options

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def extract_info(self, url, download=False):
        assert url == "https://www.youtube.com/watch?v=video-123"
        assert download is False
        return {
            "url": "https://cdn.example/video.mp4",
            "ext": "mp4",
            "vcodec": "avc1.640028",
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "duration": 213.5,
        }


class _AltStreamFakeYoutubeDL(_FakeYoutubeDL):
    def extract_info(self, _url, download=False):
        return {
            "formats": [
                {"url": "https://cdn.example/video-only.mp4", "vcodec": "avc1.4d401f"},
                {"url": "https://cdn.example/audio.m4a", "vcodec": "none"},
            ]
        }


@pytest.mark.asyncio
async def test_get_alternative_stream_prefers_audio_only(monkeypatch):
    """El fallback alimenta el motor de audio: no debe devolver video-only."""
    monkeypatch.setattr("doremi.api.stream_extractor.yt_dlp.YoutubeDL", _AltStreamFakeYoutubeDL)
    extractor = StreamExtractor()

    url = await extractor.get_alternative_stream("video-123")

    assert url == "https://cdn.example/audio.m4a"


@pytest.mark.asyncio
async def test_get_alternative_stream_falls_back_to_video_only(monkeypatch):
    """Sin formatos de audio puros, el último recurso sigue funcionando."""
    class OnlyVideoFake(_FakeYoutubeDL):
        def extract_info(self, _url, download=False):
            return {
                "formats": [
                    {"url": "https://cdn.example/video-only.mp4", "vcodec": "avc1.4d401f"},
                ]
            }

    monkeypatch.setattr("doremi.api.stream_extractor.yt_dlp.YoutubeDL", OnlyVideoFake)
    extractor = StreamExtractor()

    url = await extractor.get_alternative_stream("video-123")

    assert url == "https://cdn.example/video-only.mp4"


@pytest.mark.asyncio
async def test_get_stream_info_includes_stored_cookies(monkeypatch):
    """Las credenciales del llavero deben llegar a las opciones de yt-dlp."""
    monkeypatch.setattr(
        "doremi.utils.secure_storage.SecureStorage.load_youtube_headers",
        classmethod(lambda cls: {"cookie": "sid=abc", "user-agent": "UA-Test"}),
    )
    monkeypatch.setattr("doremi.api.stream_extractor.yt_dlp.YoutubeDL", _FakeYoutubeDL)
    extractor = StreamExtractor()

    await extractor.get_stream_info("video-123")

    headers = _FakeYoutubeDL.last_options.get("headers", {})
    assert headers.get("Cookie") == "sid=abc"
    assert headers.get("User-Agent") == "UA-Test"


@pytest.mark.asyncio
async def test_stream_quality_and_proxy_are_applied(monkeypatch):
    class FormatsFake(_FakeYoutubeDL):
        def extract_info(self, _url, download=False):
            return {
                "formats": [
                    {"url": "https://cdn.example/64.m4a", "vcodec": "none", "ext": "m4a", "abr": 64},
                    {"url": "https://cdn.example/192.m4a", "vcodec": "none", "ext": "m4a", "abr": 192},
                ]
            }

    monkeypatch.setattr("doremi.api.stream_extractor.yt_dlp.YoutubeDL", FormatsFake)
    settings = SimpleNamespace(network=SimpleNamespace(stream_quality="low", proxy_url="http://proxy.test:8080"))
    info = await StreamExtractor(settings).get_stream_info("video-123")

    assert info["url"].endswith("64.m4a")
    assert info["quality"] == 64
    assert FormatsFake.last_options["proxy"] == "http://proxy.test:8080"
