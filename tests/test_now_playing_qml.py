"""Tests de la isla QML — Now Playing."""
from __future__ import annotations

import pytest

from doremi.audio.queue import PlayQueue, QueueItem, RepeatMode
from doremi.config.settings import AppSettings


@pytest.fixture(scope="module")
def qapp():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


class _FakeStatus:
    current_video_id = "v1"
    position_ms = 0
    duration_ms = 200000


class _FakePlayer:
    status = _FakeStatus()


def _make_queue() -> PlayQueue:
    q = PlayQueue()
    for i in range(3):
        q.add_to_end(QueueItem(video_id=f"v{i}", title=f"C{i}", artist="A",
                               album="Alb", duration_ms=200000 + i, thumbnail_url=""))
    return q


class TestLyricsParsing:
    def test_lrc_timestamps(self):
        from doremi.ui.viewmodels.now_playing_vm import parse_lyrics
        lines = parse_lyrics("[00:10.50]Hola\n[01:02.00]Mundo\nTexto sin ts")
        assert lines[0]["ts_ms"] == 10500
        assert lines[1]["ts_ms"] == 62000
        assert lines[0]["text"] == "Hola"
        # línea sin ts en medio queda con -1
        assert lines[2]["ts_ms"] == -1

    def test_plain_text_is_static(self):
        from doremi.ui.viewmodels.now_playing_vm import parse_lyrics
        lines = parse_lyrics("Verse one\nVerse two")
        assert all(l["ts_ms"] == -2 for l in lines)

    def test_empty(self):
        from doremi.ui.viewmodels.now_playing_vm import parse_lyrics
        assert parse_lyrics(None) == []
        assert parse_lyrics("") == []

    def test_instrumental_tag(self):
        from doremi.ui.viewmodels.now_playing_vm import parse_lyrics
        lines = parse_lyrics("[00:05.00]\n[00:20.00]Cantada")
        assert lines[0]["text"] == "♪"
        assert lines[0]["ts_ms"] == 5000


class TestNowPlayingViewModel:
    def test_track_and_position(self, qapp):
        from doremi.ui.viewmodels.now_playing_vm import NowPlayingViewModel

        vm = NowPlayingViewModel(qapp)
        vm.set_track_info("Midnight City", "M83", "https://x/a.jpg", album="Hurry Up", video_id="v1")
        assert vm.trackTitle == "Midnight City"
        assert vm.artistName == "M83"
        assert vm.albumName == "Hurry Up"
        assert vm.artworkUrl == "https://x/a.jpg"
        assert vm.videoId == "v1"

        vm.set_artwork("file:///tmp/midnight-city.jpg")
        assert vm.artworkUrl == "file:///tmp/midnight-city.jpg"

        vm.set_position(65000, 200000)
        assert abs(vm.progress - 0.325) < 0.001
        assert vm.timeCurrent == "1:05"
        assert vm.timeTotal == "3:20"

    def test_active_lyric_tracking(self, qapp):
        from doremi.ui.viewmodels.now_playing_vm import NowPlayingViewModel

        vm = NowPlayingViewModel(qapp)
        vm.set_lyrics("[00:10.00]L1\n[00:20.00]L2\n[00:30.00]L3")
        idx = lambda: next(
            (i for i in range(vm.lyrics.rowCount())
             if vm.lyrics.data(vm.lyrics.index(i, 0), vm.lyrics.ActiveRole)),
            -1,
        )
        vm.set_position(0, 60000)
        assert idx() == -1          # 0+400ms < 10s
        vm.set_position(20500, 60000)
        assert idx() == 1           # 21s > ts L2, < L3
        vm.set_position(59000, 60000)
        assert idx() == 2

    def test_queue_and_current_flag(self, qapp):
        from doremi.ui.viewmodels.now_playing_vm import NowPlayingViewModel

        vm = NowPlayingViewModel(qapp)
        vm._video_id = "v1"
        vm.set_queue(_make_queue().items, set())
        assert vm.queueModel.rowCount() == 3
        assert vm.queueModel.data(vm.queueModel.index(1, 0), vm.queueModel.IsCurrentRole) is True
        assert vm.queueModel.data(vm.queueModel.index(0, 0), vm.queueModel.IsCurrentRole) is False

    def test_like_toggle_emits_and_wraps_request(self, qapp):
        from doremi.ui.viewmodels.now_playing_vm import NowPlayingViewModel

        vm = NowPlayingViewModel(qapp)
        vm.set_track_info("X", "Y", "", "", "v9")
        likes: list[tuple] = []
        vm.like_requested.connect(lambda *a: likes.append(a))
        vm.toggle_like_current()
        assert vm.liked is False  # Espera la confirmación del repositorio.
        assert likes == [("v9", None)]
        vm.set_liked(True)
        vm.toggle_like_current()
        assert vm.liked is True
        assert likes == [("v9", None), ("v9", None)]
        vm.set_liked(False)
        assert vm.liked is False

    def test_current_track_action(self, qapp):
        from doremi.ui.viewmodels.now_playing_vm import NowPlayingViewModel

        vm = NowPlayingViewModel(qapp)
        vm.set_track_info("T", "A", "thumb", "Alb", "v1")
        got: dict[str, list] = {"pn": [], "artist": [], "album": [], "copy": [], "dl": []}
        vm.play_next_requested.connect(lambda *a: got["pn"].append(a))
        vm.artist_clicked.connect(lambda *a: got["artist"].append(a))
        vm.album_clicked.connect(lambda *a: got["album"].append(a))
        vm.copy_link_requested.connect(lambda *a: got["copy"].append(a))
        vm.download_requested.connect(lambda *a: got["dl"].append(a))

        vm.current_track_action("play_next")
        vm.current_track_action("go_artist")
        vm.current_track_action("go_album")
        vm.current_track_action("copy_link")
        vm.current_track_action("download")
        assert got["pn"][0][:3] == ("v1", "T", "A")
        assert got["artist"] == [("A",)]
        assert got["album"] == [("Alb",)]
        assert got["copy"] == [("v1",)]
        assert got["dl"] == [("v1", "T", "A", "thumb")]

    def test_queue_move_bounds(self, qapp):
        from doremi.ui.viewmodels.now_playing_vm import NowPlayingViewModel

        vm = NowPlayingViewModel(qapp)
        vm.set_queue(_make_queue().items, set())
        moves: list[tuple] = []
        vm.queue_move_requested.connect(lambda a, b: moves.append((a, b)))
        vm.move_queue_item(0, "up")     # fuera de rango: no emite
        vm.move_queue_item(1, "up")
        vm.move_queue_item(2, "down")   # fuera
        vm.move_queue_item(1, "down")
        assert moves == [(1, 0), (1, 2)]

    def test_seek_guard(self, qapp):
        from doremi.ui.viewmodels.now_playing_vm import NowPlayingViewModel

        vm = NowPlayingViewModel(qapp)
        seeks: list[int] = []
        vm.seek_ms_requested.connect(seeks.append)
        vm.seek(0.5)   # sin duración: ignora
        vm.set_position(0, 200000)
        vm.seek(0.5)
        vm.seek(9.9)   # clamp a 1.0
        assert seeks == [100000, 200000]

    def test_track_details_only_expose_source_metadata(self, qapp):
        from doremi.ui.viewmodels.now_playing_vm import NowPlayingViewModel

        vm = NowPlayingViewModel(qapp)
        vm.set_track_info("T", "A", "", "", "v1")
        requests: list[str] = []
        vm.details_requested.connect(requests.append)
        vm.request_track_details()
        assert vm.detailsLoading is True
        assert requests == ["v1"]

        vm.set_track_details({"artist": "Autor publicado", "album": "Álbum", "uploader": "Canal"})
        assert vm.detailsLoading is False
        assert vm.detailArtist == "Autor publicado"
        assert vm.detailAlbum == "Álbum"
        assert vm.detailUploader == "Canal"
        assert vm.detailLicense == ""

    def test_video_clip_request_uses_the_current_video_id(self, qapp):
        from doremi.ui.viewmodels.now_playing_vm import NowPlayingViewModel

        vm = NowPlayingViewModel(qapp)
        requested: list[str] = []
        vm.video_requested.connect(requested.append)
        vm.request_video_clip()  # sin pista: no abre ningún visor
        vm.set_track_info("T", "A", "", "", "video-123")
        vm.request_video_clip()
        assert requested == ["video-123"]

    def test_audio_video_pill_closes_the_clip_when_returning_to_audio(self, qapp):
        from doremi.ui.viewmodels.now_playing_vm import NowPlayingViewModel

        vm = NowPlayingViewModel(qapp)
        vm.set_track_info("T", "A", "", "", "video-123")
        requested: list[str] = []
        closed: list[bool] = []
        vm.video_requested.connect(requested.append)
        vm.video_closed_requested.connect(lambda: closed.append(True))

        vm.set_media_mode("video")
        assert vm.mediaMode == "video"
        assert requested == ["video-123"]
        vm.set_media_mode("audio")
        assert vm.mediaMode == "audio"
        assert closed == [True]

    def test_video_state_exposes_loading_stream_and_error(self, qapp):
        from doremi.ui.viewmodels.now_playing_vm import NowPlayingViewModel

        vm = NowPlayingViewModel(qapp)
        vm.set_track_info("T", "A", "", "", "video-123")
        vm.set_position(42000, 180000)

        vm.begin_video_loading()
        assert vm.videoLoading is True
        assert vm.videoStreamUrl == ""
        assert vm.positionMs == 42000

        vm.set_video_stream("https://cdn.example/video.mp4")
        assert vm.videoLoading is False
        assert vm.videoStreamUrl.endswith("video.mp4")
        assert vm.videoError == ""

        vm.report_video_error("Decoder no disponible")
        assert vm.videoStreamUrl.endswith("video.mp4")
        assert vm.videoError == ""  # aún está en modo audio

        vm.request_video_clip()
        assert vm.mediaMode == "video"
        vm.report_video_error("Decoder no disponible")
        assert vm.videoError == "Decoder no disponible"
        vm.set_media_mode("audio")
        vm.clear_video()
        assert vm.videoError == ""


class TestNowPlayingScreenQml:
    def test_qml_loads(self, qapp):
        from doremi.ui.screens.now_playing_qml import NowPlayingScreenQml

        screen = NowPlayingScreenQml(_FakePlayer(), _make_queue(), None,
                                     lambda i: None, AppSettings(), lambda: None)
        assert screen.is_ok
        assert screen._qml_island is True

    def test_external_api_surface(self, qapp):
        """Los métodos que los controllers invocan existen y actualizan el VM."""
        from doremi.audio.player import PlayerState
        from doremi.ui.screens.now_playing_qml import NowPlayingScreenQml

        screen = NowPlayingScreenQml(_FakePlayer(), _make_queue(), None,
                                     lambda i: None, AppSettings(), lambda: None)
        player = screen.player
        screen.update_track_info("Midnight City", "M83", "")
        assert screen._vm.trackTitle == "Midnight City"
        assert screen._vm.videoId == "v1"

        class S: state = PlayerState.PLAYING
        screen.update_state(S())
        assert screen._vm.playing is True

        screen.update_position(65000, 200000)
        assert abs(screen._vm.progress - 0.325) < 0.001

        screen.set_lyrics_loading()
        assert screen._vm.lyrics.rowCount() == 0
        screen.set_lyrics("[00:01.00]Hola")
        assert screen._vm.lyrics.rowCount() == 1

        screen.set_related([{"videoId": "r1", "title": "R", "artists": [{"name": "N"}],
                             "thumbnails": [{"url": ""}]}], None)
        assert screen._vm.related.rowCount() == 1

        screen.set_liked_state(True)
        assert screen._vm.liked is True

        screen.update_shuffle_repeat_state()

    def test_queue_tab_shim(self, qapp):
        from doremi.ui.screens.now_playing_qml import NowPlayingScreenQml

        screen = NowPlayingScreenQml(_FakePlayer(), _make_queue(), None,
                                     lambda i: None, AppSettings(), lambda: None)
        assert hasattr(screen, "queue_tab")
        screen.queue_tab.set_queue(_make_queue().items, {"v1"})
        assert screen._vm.queueModel.rowCount() == 3
        assert screen._vm.queueModel.data(screen._vm.queueModel.index(1, 0),
                                          screen._vm.queueModel.IsLikedRole) is True

        # señales del shim conectables (paridad con QueuePanel)
        calls: list[tuple] = []
        screen.queue_tab.queue_move_requested.connect(lambda a, b: calls.append((a, b)))
        screen._vm.move_queue_item(1, "up")
        assert calls == [(1, 0)]

    @pytest.mark.asyncio
    async def test_thumbnail_cache_updates_current_track_only(self, qapp, monkeypatch, tmp_path):
        """La descarga asíncrona no debe fallar ni pisar una pista posterior."""
        from doremi.ui.screens import now_playing_qml
        from doremi.ui.screens.now_playing_qml import NowPlayingScreenQml

        screen = NowPlayingScreenQml(_FakePlayer(), _make_queue(), None,
                                     lambda i: None, AppSettings(), lambda: None)
        image_path = tmp_path / "cover.jpg"
        image_path.touch()

        async def download(url):
            return image_path

        monkeypatch.setattr(type(now_playing_qml._image_cache), "download", lambda self, url: download(url))
        screen._vm.set_track_info("T", "A", "https://img/current.jpg")
        await screen._load_thumbnail("https://img/current.jpg")
        assert screen._vm.artworkUrl.endswith("cover.jpg")

        screen._vm.set_track_info("Nueva", "B", "https://img/new.jpg")
        await screen._load_thumbnail("https://img/current.jpg")
        assert screen._vm.artworkUrl == "https://img/new.jpg"

    @pytest.mark.asyncio
    async def test_video_stream_result_is_applied_only_to_current_track(self, qapp):
        from doremi.ui.screens.now_playing_qml import NowPlayingScreenQml

        screen = NowPlayingScreenQml(_FakePlayer(), _make_queue(), None,
                                     lambda i: None, AppSettings(), lambda: None)

        class Extractor:
            async def get_video_stream_info(self, video_id):
                return {"url": f"https://cdn.example/{video_id}.mp4"}

        screen._vm.set_track_info("T", "A", "", "", "v1")
        screen._vm.set_media_mode("video")
        generation = screen._video_request_generation
        await screen._load_video_stream("v1", Extractor(), generation)
        assert screen._vm.videoStreamUrl.endswith("v1.mp4")

        screen._cancel_video_request()
        screen._vm.set_track_info("Nueva", "B", "", "", "v2")
        screen._vm.begin_video_loading()
        await screen._load_video_stream("v1", Extractor(), generation)
        assert screen._vm.videoStreamUrl == ""
        assert screen._vm.videoLoading is True

    def test_video_position_sync_uses_qt_methods(self, qapp):
        from doremi.ui.screens.now_playing_qml import NowPlayingScreenQml

        screen = NowPlayingScreenQml(_FakePlayer(), _make_queue(), None,
                                     lambda i: None, AppSettings(), lambda: None)
        screen._vm.set_track_info("T", "A", "", "", "v1")
        screen._vm.set_media_mode("video")
        screen._vm.set_position(42000, 180000)

        class FakeVideoPlayer:
            def __init__(self):
                self.seeked_to = None

            def duration(self):
                return 180000

            def position(self):
                return 0

            def setPosition(self, position):
                self.seeked_to = position

        player = FakeVideoPlayer()
        screen._video_player = player
        screen._sync_video_position()
        assert player.seeked_to == 42000
