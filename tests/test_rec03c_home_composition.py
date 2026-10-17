"""REC-03C.1: composición Home pura (focalizados).

Cubre compose_home/diverse_tracks/identity sin DB, sin red, sin Qt y sin
datos reales del usuario. personalized_home con DB se verifica en REC-03C.2
cuando exista ListeningPeriods; aquí solo se exige importación limpia.
"""
from __future__ import annotations

import socket
import urllib.request
from pathlib import Path

import pytest


def test_rec03c1_imports_without_network_or_qt(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    monkeypatch.setattr(socket, "create_connection",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    import doremi.services.home_composer as hc
    assert callable(hc.identity) and callable(hc.diverse_tracks)
    assert callable(hc.compose_home) and callable(hc.personalized_home)
    source = Path(hc.__file__).read_text(encoding="utf-8")
    assert "import PySide" not in source and "from PySide" not in source
    assert "urlopen" not in source and "http.client" not in source
    assert "urllib.request" not in source


def test_rec03c1_no_qt_controllers_in_module():
    text = (Path("src/doremi/services/home_composer.py")).read_text(encoding="utf-8")
    assert "QThread" not in text and "controllers" not in text
    assert "viewmodel" not in text.lower() or "viewmodels" not in text


def test_rec03c1_identity_prefers_videoid_and_play_route():
    from doremi.services.home_composer import identity
    assert identity(dict(videoId="v1", navigate="album?id=A")) == "track:v1"
    assert identity(dict(navigate="play:abc")) == "track:abc"
    assert identity(dict(navigate="playlist?id=PL1")) == "playlist?id=PL1"
    # resume/position/next/autoplay no distinguen la misma colección.
    a = identity(dict(navigate="playlist?id=p&resume=v&position=3&next=1&autoplay=1"))
    b = identity(dict(navigate="playlist?id=p"))
    assert a == b == "playlist?id=p"
    # Params ordenados -> determinista.
    c = identity(dict(navigate="playlist?id=p&b=2&a=1"))
    assert c == "playlist?a=1&b=2&id=p"


def test_rec03c1_diverse_tracks_caps_same_artist_and_dedups():
    from doremi.services.home_composer import diverse_tracks
    frequent = [dict(videoId=str(i), title=str(i), artist="Same artist") for i in range(6)]
    alternatives = [dict(videoId="other" + str(i), title=str(i), artist="Artist " + str(i)) for i in range(4)]
    result = diverse_tracks(frequent + alternatives, limit=6)
    assert len(result) == 6
    assert sum(item["artist"] == "Same artist" for item in result) <= 2
    # Dedup por videoId.
    dupes = [dict(videoId="v", title="T"), dict(videoId="v", title="T"), dict(videoId="w", title="W")]
    assert [d["videoId"] for d in diverse_tracks(dupes, limit=6)] == ["v", "w"]
    # Sin artista no aplica el cap.
    no_artist = [dict(videoId=str(i), title=str(i)) for i in range(6)]
    assert len(diverse_tracks(no_artist, limit=6)) == 6


def test_rec03c1_compose_home_empty():
    from doremi.services.home_composer import compose_home
    result = compose_home(dict(tiles=[], songs=[], horizontal=[], spotlight=[]), [], [])
    assert result["personal"] == []
    assert result["tiles"] == [] and result["songs"] == []
    assert result["horizontal"] == [] and result["spotlight"] == []
    assert result["sections"] == []


def test_rec03c1_compose_home_priority_dedup_and_empty_sections():
    from doremi.services.home_composer import compose_home
    album = dict(title="Album", navigate="album?id=A")
    track = dict(videoId="v", title="Track")
    result = compose_home(dict(spotlight=[album], tiles=[track, track], horizontal=[album], songs=[track]),
                          [dict(title="Continue", items=[album]), dict(title="Empty", items=[])], [track])
    assert len(result["personal"]) == 1
    assert result["personal"][0]["title"] == "Continue"
    assert not result["spotlight"] and not result["horizontal"] and not result["songs"]
    assert result["tiles"] == [track]


def test_rec03c1_compose_home_limits_and_order():
    from doremi.services.home_composer import compose_home
    tiles = [dict(videoId=f"t{i}", title=f"T{i}", artist=f"A{i}") for i in range(20)]
    songs = [dict(videoId=f"s{i}", title=f"S{i}") for i in range(40)]
    horizontal = [dict(navigate=f"playlist?id=P{i}", section_title="Sec", title=f"P{i}") for i in range(100)]
    spotlight = [dict(navigate=f"album?id=A{i}", title=f"A{i}") for i in range(5)]
    personal = [dict(title="P", items=[dict(videoId=f"p{i}", title=f"p{i}") for i in range(20)])]
    result = compose_home(dict(tiles=tiles, songs=songs, horizontal=horizontal, spotlight=spotlight),
                          personal, [])
    assert len(result["tiles"]) <= 6
    assert len(result["songs"]) <= 16
    assert len(result["horizontal"]) <= 45
    assert len(result["spotlight"]) <= 1
    assert len(result["personal"][0]["items"]) <= 6
    assert result["sections"] and result["sections"][0]["title"] == "Sec"


def test_rec03c1_compose_home_offline_keeps_songs_over_spotlight():
    from doremi.services.home_composer import compose_home
    song = dict(videoId="v", title="T")
    remote = dict(_source="offline", tiles=[], songs=[song], horizontal=[], spotlight=[song])
    result = compose_home(remote, [], [])
    # En offline/cache la canción playable sobrevive aunque duplique spotlight.
    assert result["songs"] == [song]
    assert result["spotlight"] == []


def test_rec03c1_compose_home_does_not_mutate_input_and_is_deterministic():
    from doremi.services.home_composer import compose_home
    remote = dict(tiles=[dict(videoId="v", title="T")], songs=[], horizontal=[], spotlight=[])
    snapshot = repr(remote)
    first = compose_home(remote, [], [dict(videoId="w", title="W", artist="A")])
    second = compose_home(remote, [], [dict(videoId="w", title="W", artist="A")])
    assert repr(remote) == snapshot
    assert first == second


def test_rec03c1_personalized_home_is_lazy_and_needs_no_network_on_import():
    import doremi.services.home_composer as hc
    import inspect
    source = inspect.getsource(hc.personalized_home)
    # ListeningPeriods y DownloadRepository son imports perezosos: el módulo
    # se importa sin exigir todavía REC-03C.2.
    assert "from doremi.services.listening_periods import ListeningPeriods" in source
    assert "from doremi.db.repository import DownloadRepository" in source
    # Seis reglas inteligentes acotadas (limit=100) + recent(limit=3).
    assert "smart_tracks(rule, limit=100" in source
    assert "recent(limit=3)" in source
