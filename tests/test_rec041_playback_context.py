"""REC-04.1.1: origen de reproducción e historial contextual (focalizados).

SQLite temporal + XDG aislados + mocks mínimos. Nunca usa DB, música,
config reales ni red. Cubre el defecto D1 (persistencia con
``context_type="queue"`` fijo) y las reglas del boundary: contexto
capturado al solicitar reproducir, nunca recalculado al guardar;
procedencia conservada por QueueItem a través de avance manual, shuffle,
repeat y reemplazo de cola; autoplay diferenciado; ``position_ms``
desde ``ListenResult``; un solo registro por canción.

Nota de contrato: ``PlayHistory`` no guarda ``context_title``; el título
vive en la fila ``Collection`` que ``add_entry`` crea/actualiza cuando
``context_id`` y ``context_title`` existen (sin recrear ``local-list:``).
"""
from __future__ import annotations

import asyncio
import socket
import urllib.request
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio

from doremi.audio.listening import ListenResult, ListeningSession
from doremi.audio.queue import PlayQueue, QueueItem, RepeatMode
from doremi.config.settings import AppSettings
from doremi.db.models import Collection, PlayHistory as H
from doremi.services.playback_context import CONTEXT_TYPES, playback_context
from doremi.ui.controllers.playback_controller import PlaybackController


@pytest.fixture(scope="module")
def qapp():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


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


def _controller() -> PlaybackController:
    """PlaybackController real con dependencias inmediatas; nunca ejecuta
    VLC. Las tareas diferidas se cierran, no se programan."""
    from doremi.audio.player import PlayerState
    controller = PlaybackController(
        player=SimpleNamespace(status=SimpleNamespace(state=PlayerState.IDLE)),
        queue=PlayQueue(),
        yt=SimpleNamespace(is_authenticated=False,
                           get_watch_playlist=AsyncMock(return_value={"tracks": []})),
        settings=AppSettings(),
        extractor=SimpleNamespace(get_stream_info=AsyncMock(return_value={})),
        download_manager=SimpleNamespace(),
        run_async=lambda coro: coro.close(),
        mini_player=SimpleNamespace(update_track_info=lambda *a, **k: None),
        now_playing_screen=SimpleNamespace(update_track_info=lambda *a, **k: None),
        tray=None,
        mpris=None,
        crossfade_manager=SimpleNamespace(cancel=lambda: None),
        network_monitor=SimpleNamespace(is_connected=True),
        lyrics_client=SimpleNamespace(),
        sleep_timer=SimpleNamespace(),
        main_window=SimpleNamespace(
            _current_path="home",
            _stream_recovery_attempts=set(),
        ),
    )
    controller._update_queue_panel = lambda: None
    controller._play_current = AsyncMock(return_value=None)
    return controller


def _result(item: QueueItem, *, position_ms=0, skip=0, completed=False, played=False):
    return ListenResult(item=item, listen_time_ms=1000, completion_ratio=0.1,
                        skip_count=skip, completed=completed, was_played=played,
                        position_ms=position_ms)


async def _history_rows():
    from doremi.db.database import get_session
    from sqlalchemy import select
    async with get_session() as session:
        rows = list((await session.scalars(select(H).order_by(H.id))).all())
        collections = list((await session.scalars(select(Collection))).all())
    return rows, collections


# ── 1. Contrato del servicio de contexto ──────────────────────────────────

def test_rec041_playback_context_service_contract():
    import inspect
    from doremi.services import playback_context as module
    source = inspect.getsource(module)
    for banned in ("requests", "httpx", "aiohttp", "PySide", "QtWidgets"):
        assert banned not in source          # sin red, sin Qt en el módulo
    smart = playback_context(SimpleNamespace(_current_path="playlist?id=smart:repeat"))
    assert (smart["context_type"], smart["context_id"]) == (("smart", "smart:repeat"))
    session_ = playback_context(SimpleNamespace(_current_path="playlist?id=session:1:2:0&position=7"))
    assert (session_["context_type"], session_["context_id"]) == ("playlist", "session:1:2:0")
    downloads = playback_context(SimpleNamespace(_current_path="downloads"))
    assert downloads["context_type"] == "downloads"
    blank = playback_context(SimpleNamespace(_current_path=""))
    assert blank["context_type"] == "unknown" and blank["context_id"] == ""
    assert "autoplay" in CONTEXT_TYPES


# ── 2. Defecto D1 reproducido (regresión roja antes del fix) ──────────────

@pytest.mark.asyncio
async def test_rec041_history_preserves_playlist_album_smart(isolated_db):
    controller = _controller()
    cases = [
        (QueueItem("p1", "P", "Art", "", 0, "", context_type="playlist",
                   context_id="PLxyz", context_title="Mix"),
         ("playlist", "PLxyz", "Mix")),
        (QueueItem("a1", "A", "Art", "Alb", 0, "", context_type="album",
                   context_id="ALBxyz", context_title="Disco"),
         ("album", "ALBxyz", "Disco")),
        (QueueItem("s1", "S", "Art", "", 0, "", context_type="smart",
                   context_id="smart:repeat", context_title="En repetición"),
         ("smart", "smart:repeat", "En repetición")),
    ]
    for item, _ in cases:
        await controller._persist_listen(_result(item, position_ms=42000, played=True))
    rows, collections = await _history_rows()
    assert len(rows) == 3
    for row, (item, (kind, identity, title)) in zip(rows, cases):
        assert (row.context_type, row.context_id) == (kind, identity)
        assert row.position_ms == 42000
    saved = {(c.context_type, c.context_id): c.title for c in collections}
    assert saved == {("playlist", "PLxyz"): "Mix", ("album", "ALBxyz"): "Disco",
                     ("smart", "smart:repeat"): "En repetición"}


@pytest.mark.asyncio
async def test_rec041_missing_context_falls_back_to_queue(isolated_db):
    """Sin origen identificable: fallback 'queue' y nunca identidad inventada."""
    controller = _controller()
    await controller._persist_listen(
        _result(QueueItem("x1", "T", "Art", "", 0, "", context_type=""), played=True))
    # context_id sin título no crea una colección falsa.
    await controller._persist_listen(
        _result(QueueItem("x2", "T2", "Art", "", 0, "", context_type="search",
                          context_id="busqueda-suelta", context_title=""), played=True))
    rows, collections = await _history_rows()
    assert rows[0].context_type == "queue"       # fallback coherente
    assert rows[0].context_id == ""
    assert (rows[1].context_type, rows[1].context_id) == ("search", "busqueda-suelta")
    assert collections == []                     # título vacío ⇒ cero identidades


# ── 3. Boundary: capturar al solicitar, no al finalizar ───────────────────

def test_rec041_sync_play_captures_context_at_boundary(monkeypatch, qapp):
    """`_play_song_sync` captura el origen de la pantalla activa en el
    momento del clic; una navegación posterior no lo modifica."""
    from doremi.ui.main_window import MainWindow
    observed_paths, observed_context = [], []

    real_context = playback_context

    def watched_context(window):
        observed_paths.append(getattr(window, "_current_path", ""))
        return real_context(window)

    class StubController:
        async def _play_song(self, *args, context=None, **kwargs):
            observed_context.append(context)

    window = MainWindow.__new__(MainWindow)
    window._current_path = "album?id=ALBxyz"
    window.playback_controller = StubController()

    def fake_run_async(self, coro):
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(coro)
        finally:
            loop.close()

    monkeypatch.setattr("doremi.services.playback_context.playback_context", watched_context)
    monkeypatch.setattr(MainWindow, "_run_async", fake_run_async)
    window._play_song_sync("v1", "T", "Art", "", 0, "")
    window._current_path = "settings"        # el usuario ya navegó a otra pantalla
    assert observed_paths == ["album?id=ALBxyz"]     # capturado, no recalculado
    assert observed_context[0]["context_type"] == "album"


@pytest.mark.asyncio
async def test_rec041_fallback_context_applies_only_to_unmarked_items():
    """Los items que ya traen contexto del productor lo conservan; los
    ``unknown`` reciben el contexto capturado en el boundary."""
    from dataclasses import replace
    item = QueueItem("v1", "T", "A", "", 0, "")
    sealed = replace(item, context_type="album", context_id="X", context_title="Y")
    assert item.context_type == "unknown" and sealed.context_id == "X"
    controller = _controller()
    controller._finalize_listening = Mock()
    marked = QueueItem("p1", "P", "A", "", 0, "", context_type="playlist",
                       context_id="PLxyz", context_title="Mix")
    unmarked = QueueItem("q1", "Q", "A", "", 0, "")
    context = dict(context_type="album", context_id="ALBxyz", context_title="Disco")
    await controller._play_song("q1", "Q", "A", "", 0, "", [marked, unmarked], 1,
                                context=context)
    items = controller.queue.items
    assert (items[0].context_type, items[0].context_id) == ("playlist", "PLxyz")
    assert (items[1].context_type, items[1].context_id) == ("album", "ALBxyz")
    await controller._play_song("z1", "Z", "A", "", 0, "", None, 0, context=context)
    assert controller.queue.current.context_id == "ALBxyz"


# ── 4. Cola: cada elemento conserva su contexto ───────────────────────────

def test_rec041_manual_advance_keeps_per_item_context():
    queue = PlayQueue()
    first = QueueItem("v1", "T1", "A", "", 0, "", context_type="playlist",
                      context_id="PL1", context_title="Uno")
    second = QueueItem("v2", "T2", "A", "", 0, "", context_type="album",
                       context_id="ALB1", context_title="Dos")
    queue.set_queue([first, second])
    queue.advance()
    assert queue.current is second and queue.current.context_id == "ALB1"
    # Lo ya reproducido permanece en la cola y conserva su propia procedencia.
    assert first.context_id == "PL1"


def test_rec041_shuffle_and_repeat_preserve_provenance():
    items = [QueueItem(f"v{i}", f"T{i}", "A", "", 0, "", context_type="playlist",
                       context_id=f"PL{i}", context_title="X") for i in range(4)]
    queue = PlayQueue()
    queue.set_queue(items, 0)
    queue.toggle_shuffle()
    assert all(item.context_type == "playlist" and item.context_title == "X"
               for item in queue.items)
    queue.repeat_mode = RepeatMode.ONE
    queue.advance()
    assert queue.current.context_id.startswith("PL")


def test_rec041_queue_replacement_does_not_reuse_previous_origin():
    queue = PlayQueue()
    queue.set_queue([QueueItem("o1", "A", "Art", "", 0, "", context_type="playlist",
                               context_id="PL_old", context_title="Vieja")])
    previous = queue.current
    queue.set_queue([QueueItem("n1", "B", "Art", "", 0, "", context_type="smart",
                               context_id="smart:recent", context_title="Nueva")])
    assert queue.current.context_id == "smart:recent"
    assert previous.context_id == "PL_old"       # el item anterior no cambió


def test_rec041_queue_roundtrip_preserves_context():
    queue = PlayQueue()
    queue.set_queue([QueueItem("v1", "T", "A", "", 0, "", context_type="smart",
                               context_id="smart:repeat", context_title="En repetición")])
    restored = PlayQueue.from_dict(queue.to_dict())
    assert restored.current.context_type == "smart"
    assert restored.current.context_id == "smart:repeat"


# ── 5. Persistencia: skip, posición y unicidad ────────────────────────────

@pytest.mark.asyncio
async def test_rec041_skip_semantics_preserved(isolated_db, monkeypatch):
    recorded_play = []
    monkeypatch.setattr("doremi.db.repository.SongRepository.record_play",
                        AsyncMock(side_effect=lambda vid: recorded_play.append(vid)))
    controller = _controller()
    skipped_item = QueueItem("s1", "S", "Art", "", 60000, "", context_type="smart",
                             context_id="smart:repeat", context_title="En repetición")
    await controller._persist_listen(_result(skipped_item, skip=1, played=False))
    played_item = QueueItem("s2", "S2", "Art", "", 60000, "", context_type="playlist",
                            context_id="PL1", context_title="Mix")
    await controller._persist_listen(_result(played_item, played=True))
    rows, _ = await _history_rows()
    assert [row.skip_count for row in rows] == [1, 0]
    assert [bool(row.was_played) for row in rows] == [False, True]
    assert recorded_play == ["s2"]               # el skip no cuenta como reproducción


@pytest.mark.asyncio
async def test_rec041_position_ms_matches_listen_result(isolated_db):
    session = ListeningSession()
    session.start(QueueItem("v1", "T", "A", "", 180000, "", context_type="queue"))
    session.observe(5000, 180000, True)
    session.observe(45000, 180000, True)
    result = session.finish("skipped")
    controller = _controller()
    await controller._persist_listen(result)
    (row,), _ = await _history_rows()
    assert row.position_ms == result.position_ms == 45000


@pytest.mark.asyncio
async def test_rec041_single_record_per_song_completion(isolated_db):
    controller = _controller()
    session = ListeningSession()
    session.start(QueueItem("v1", "T", "A", "", 30000, "", context_type="playlist",
                            context_id="PL1", context_title="Mix"))
    session.observe(30000, 30000, True)
    first = session.finish("completed")
    assert session.finish("completed") is None   # la sesión ya terminó
    await controller._persist_listen(first)
    rows, _ = await _history_rows()
    assert [row.video_id for row in rows] == ["v1"]


@pytest.mark.asyncio
async def test_rec041_replacement_does_not_reattribute_previous_song(isolated_db):
    controller = _controller()
    session = ListeningSession()
    session.start(QueueItem("p1", "P", "A", "", 120000, "", context_type="playlist",
                            context_id="PL_old", context_title="Antiguo"))
    session.observe(40000, 120000, True)
    await controller._persist_listen(session.finish("replaced"))
    controller.queue.set_queue([QueueItem("n1", "N", "A", "", 180000, "",
                                          context_type="smart", context_id="smart:recent",
                                          context_title="Últimamente")])
    session2 = ListeningSession()
    session2.start(controller.queue.current)
    session2.observe(10000, 180000, True)
    await controller._persist_listen(session2.finish("replaced"))
    rows, _ = await _history_rows()
    by_video = {row.video_id: row for row in rows}
    assert (by_video["p1"].context_type, by_video["p1"].context_id) == ("playlist", "PL_old")
    assert (by_video["n1"].context_type, by_video["n1"].context_id) == ("smart", "smart:recent")


# ── 6. add_entry persiste los campos en SQLite temporal ───────────────────

@pytest.mark.asyncio
async def test_rec041_repo_persists_all_context_fields(isolated_db):
    from doremi.db.repository import HistoryRepository
    await HistoryRepository().add_entry(
        video_id="v9", title="T", artist="Art", duration_ms=120000,
        listen_time_ms=5000, completion_ratio=0.05, skip_count=0,
        completed=False, was_played=True, context_type="playlist",
        context_id="local-list:abc", context_title="Lista Local",
        position_ms=12345)
    rows, collections = await _history_rows()
    (row,) = rows
    assert (row.context_type, row.context_id, row.position_ms) == (
        "playlist", "local-list:abc", 12345)
    # `local-list:` nunca se recrea como colección.
    assert collections == []


# ── 7. Productores reales estampan su origen ──────────────────────────────

def test_rec041_playlist_screen_stamps_context(qapp):
    from doremi.ui.screens.playlist_qml import PlaylistScreenQml
    calls: list = []
    screen = PlaylistScreenQml(None, lambda *a: calls.append(a), None, lambda: None)
    screen._playlist_id = "local-list:abc"
    screen._vm.set_data({"playlist_id": "local-list:abc", "title": "Lista",
                         "tracks": [{"videoId": "v1", "title": "T", "artist": "A",
                                     "duration_ms": 10, "thumbnail_url": ""}]})
    screen._vm.play_at(0)
    item = calls[0][6][0]
    assert (item.context_type, item.context_id, item.context_title) == (
        "playlist", "local-list:abc", "Lista")
    screen._playlist_id = "smart:repeat"
    screen._vm.set_data({"playlist_id": "smart:repeat", "title": "En repetición",
                         "tracks": [{"videoId": "v2", "title": "T2", "artist": "A",
                                     "duration_ms": 10, "thumbnail_url": ""}]})
    screen._vm.play_at(0)
    smart_item = calls[1][6][0]
    assert (smart_item.context_type, smart_item.context_id) == ("smart", "smart:repeat")


def test_rec041_album_screen_stamps_context(qapp):
    from doremi.ui.screens.album_qml import AlbumScreenQml
    calls: list = []
    screen = AlbumScreenQml(None, lambda *a: calls.append(a), lambda: None)
    screen._browse_id = "ALBxyz"
    screen._vm.set_data({"browse_id": "ALBxyz", "title": "Disco",
                         "tracks": [{"videoId": "a1", "title": "T", "artist": "A",
                                     "duration_ms": 5, "thumbnail_url": ""}]})
    screen._vm.play_at(0)
    items = calls[0][6]
    assert all(item.context_type == "album" and item.context_id == "ALBxyz"
               and item.context_title == "Disco" for item in items)


def test_rec041_queue_controller_stamps_screen_context(qapp):
    from doremi.ui.controllers.queue_controller import QueueController
    window = SimpleNamespace(
        _current_path="playlist?id=PLxyz",
        statusBar=lambda: SimpleNamespace(showMessage=lambda *a, **k: None),
        playback_controller=SimpleNamespace(_update_queue_panel=lambda: None),
    )
    controller = QueueController(
        main_window=window, queue=PlayQueue(),
        extractor=SimpleNamespace(get_stream_info=AsyncMock(return_value={})),
        run_async=lambda coro: coro)
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(controller.add_to_queue_async(
            "v1", "T", "A", "t.png", add_next=True,
            context=playback_context(window)))
    finally:
        loop.close()
    (item,) = controller.queue.items
    assert (item.context_type, item.context_id) == ("playlist", "PLxyz")


def test_rec041_local_playlist_play_stamps_window_context():
    controller = _controller()
    controller.main_window = SimpleNamespace(_current_path="playlist?id=local_123")
    controller._play_local_playlist(
        [{"video_id": "v1", "title": "T", "artist": "A", "album": "", "duration_ms": 0,
          "thumbnail_url": "", "file_path": "/tmp/no-file.mp3"}],
        start_index=0)
    (item,) = controller.queue.items
    assert (item.context_type, item.context_id) == ("playlist", "local_123")
    assert item.is_local and item.local_path == "/tmp/no-file.mp3"


def test_rec041_local_single_file_capture_and_fallback(monkeypatch):
    """El wrapper captura en el boundary; sin metadata el origen es 'local'
    (nunca una colección inventada)."""
    # Sin base de datos en estas pruebas (duracion desde DownloadsRepository
    # se degrada a 0 sin tocar la DB del usuario).
    monkeypatch.setattr(
        "doremi.db.repository.DownloadRepository.get_download",
        AsyncMock(side_effect=RuntimeError("sin DB en esta prueba")))
    controller = _controller()
    controller.main_window = SimpleNamespace(_current_path="downloads")
    loop = asyncio.new_event_loop()
    pending = []
    try:
        # Las tareas diferidas se programan en el mismo loop del test
        # (paridad del _run_async real, sin loops anidados).
        controller.run_async = lambda coro: pending.append(
            asyncio.ensure_future(coro, loop=loop))
        # 1) el wrapper captura la pantalla activa en el boundary.
        controller._play_local_wrapper(
            "/tmp/a.mp3", {"title": "T", "artist": "A", "video_id": "d1"})
        loop.run_until_complete(asyncio.gather(*pending))
        (stamped,) = controller.queue.items
        assert stamped.context_type == "downloads"
        assert stamped.local_path == "/tmp/a.mp3"
        # 2) llamada directa sin metadata: fallback 'local', sin identidad
        #    de coleccion inventada.
        controller.queue.clear()
        loop.run_until_complete(controller._play_local(
            "/tmp/b.mp3", {"title": "T2", "artist": "A", "video_id": "d2"}))
        (fallback,) = controller.queue.items
        assert fallback.context_type == "local" and fallback.context_id == ""
        # 3) la metadata con playback_context manda sobre cualquier fallback.
        controller.queue.clear()
        loop.run_until_complete(controller._play_local(
            "/tmp/c.mp3",
            {"title": "T3", "artist": "A", "video_id": "d3",
             "playback_context": {"context_type": "smart",
                                  "context_id": "smart:daily",
                                  "context_title": "Diaria"}}))
        (override,) = controller.queue.items
        assert (override.context_type, override.context_id,
                override.context_title) == ("smart", "smart:daily", "Diaria")
    finally:
        loop.close()


def test_rec041_watch_expansion_stamps_autoplay():
    """La expansión automática de _advance_queue nunca hereda la colección."""
    controller = _controller()
    controller._finalize_listening = Mock()
    queue = PlayQueue()
    queue.set_queue([QueueItem("cur1", "C", "Art", "", 0, "", context_type="playlist",
                               context_id="PL1", context_title="Mix")], 0)
    controller.queue = queue
    played = []

    async def play_current():
        played.append(queue.current.video_id)

    controller._play_current = play_current

    async def watch(video_id):
        return {"tracks": [{"videoId": "cur1"},
                           {"videoId": "w2", "title": "N", "artists": [{"name": "A2"}],
                            "thumbnail": []}]}

    controller.yt = SimpleNamespace(is_authenticated=False, get_watch_playlist=watch)
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(controller._advance_queue())
    finally:
        loop.close()
    expansion = [item for item in queue.items if item.video_id == "w2"]
    assert len(expansion) == 1
    assert (expansion[0].context_type, expansion[0].context_id,
            expansion[0].context_title) == ("autoplay", "", "")
    assert expansion[0].is_local is False
    assert played == ["w2"]


def test_rec041_auto_queue_population_stamps_autoplay():
    """+_fetch_and_populate_auto_queue estampa 'autoplay', no la colección."""
    controller = _controller()
    queue = PlayQueue()
    queue.set_queue([QueueItem("abcde", "C", "Art", "", 0, "", context_type="playlist",
                               context_id="PL1", context_title="Mix")], 0)
    controller.queue = queue

    async def watch(video_id, limit=25):
        return {"tracks": [{"videoId": "abcde"},
                           {"videoId": "f2", "title": "T2", "artists": [{"name": "A2"}],
                            "thumbnail": []}]}

    controller.yt = SimpleNamespace(is_authenticated=False, get_watch_playlist=watch)
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(controller._fetch_and_populate_auto_queue("abcde"))
    finally:
        loop.close()
    added = [item for item in queue.items if item.video_id == "f2"]
    assert len(added) == 1
    assert (added[0].context_type, added[0].context_id) == ("autoplay", "")


# ── 8. Sin red durante el ejercicio ───────────────────────────────────────

def test_rec041_no_network_calls_allowed(monkeypatch):
    def deny(*a, **k):
        raise AssertionError("la prueba no debe abrir red")

    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(urllib.request, "urlopen", deny)
    assert playback_context(SimpleNamespace(_current_path="home"))["context_type"] == "home"
