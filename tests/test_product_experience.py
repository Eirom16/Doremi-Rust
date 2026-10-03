from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio

from doremi.audio.queue import PlayQueue, QueueItem
from doremi.db.experience_repository import ExperienceRepository, period_bounds
from doremi.db.repository import SongRepository, HistoryRepository
from doremi.services.playback_context import playback_context


@pytest_asyncio.fixture
async def experience(monkeypatch):
    import doremi.db.database as db
    await db.close_db()
    monkeypatch.setattr(db, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    await db.init_db()
    yield ExperienceRepository()
    await db.close_db()


@pytest.mark.parametrize("route,kind,identity", [("playlist?id=PL123", "playlist", "PL123"), ("album?id=MPRE", "album", "MPRE"), ("search?query=a%26b", "search", "a&b"), ("now_playing", "queue", ""), ("playlist?id=smart:repeat", "smart", "smart:repeat"), ("downloads", "downloads", "")])
def test_origin_capture(route, kind, identity):
    result = playback_context(SimpleNamespace(_current_path=route))
    assert (result["context_type"], result["context_id"]) == (kind, identity)


def test_local_library_origin_is_distinct_from_remote_library():
    window = SimpleNamespace(_current_path="library", library_screen=SimpleNamespace(_vm=SimpleNamespace(tab="local")))
    assert playback_context(window)["context_type"] == "local"


def test_queue_origin_survives_shuffle_move_restore():
    queue = PlayQueue()
    queue.set_queue([QueueItem("v", "Song", "Artist", "", 100000, "", context_type="playlist", context_id="p", context_title="Gym"), QueueItem("local:1", "Local", "", "", 100, "", is_local=True, context_type="local")])
    queue.toggle_shuffle()
    restored = PlayQueue.from_dict(queue.to_dict())
    restored.move_item(0, 1)
    restored.toggle_shuffle()
    assert restored.current.context_title == "Gym"
    assert restored.items[1].context_type == "local"


@pytest.mark.asyncio
async def test_pins_ranking_and_order_persist(experience):
    await experience.remember_collections([dict(title="Fallback", navigate="playlist?id=f"), dict(title="Frequent", navigate="playlist?id=r"), dict(title="Album", navigate="album?id=a")])
    await HistoryRepository().add_entry("v", "Song", "Artist", 100000, context_type="playlist", context_id="r", context_title="Frequent", listen_time_ms=50000)
    await experience.set_pin("p", "Pinned")
    assert [i["title"] for i in await ExperienceRepository().quick_access()] == ["Pinned", "Frequent", "Fallback"]
    await experience.set_pin("f", "Fallback")
    assert await experience.reorder_pins(["playlist?id=f", "playlist?id=p"])
    assert not await experience.reorder_pins(["playlist?id=f", "playlist?id=f"])
    assert (await experience.quick_access())[0]["title"] == "Fallback"
    await experience.set_pin("f", "Fallback", pinned=False)
    assert (await experience.quick_access())[0]["title"] == "Pinned"


@pytest.mark.asyncio
async def test_replayed_music_session_is_not_a_user_playlist(experience):
    await HistoryRepository().add_entry("v", "Song", "Artist", 100000,
        context_type="playlist", context_id="session:1:2", context_title="Anoche",
        listen_time_ms=50000, was_played=True)
    assert await experience.quick_access() == []
    assert (await experience.stats())["top_collections"] == []
    await HistoryRepository().add_entry("v", "Song", "Artist", 100000,
        context_type="playlist", context_id="real", context_title="Gym",
        listen_time_ms=50000, was_played=True)
    stats = await experience.stats()
    assert stats["total_plays"] == 2
    assert [c["title"] for c in stats["top_collections"]] == ["Gym"]
    with pytest.raises(ValueError):
        await experience.set_pin("session:1:2", "Anoche")


@pytest.mark.asyncio
async def test_context_resume_has_no_invented_progress(experience):
    await HistoryRepository().add_entry("v", "Song", "Artist", 100000, context_type="album", context_id="a", context_title="Album", listen_time_ms=40000, position_ms=42000)
    card = (await experience.continue_listening())[0]
    assert card["position_ms"] == 42000
    assert card["navigate"] == "album?id=a"
    assert "progress" not in card
    await HistoryRepository().add_entry("v", "Song", "Artist", 100000, context_type="album", context_id="a", was_played=False, skip_count=1)
    assert not await experience.continue_listening()


@pytest.mark.asyncio
async def test_continue_uses_event_time_not_import_order_and_excludes_valid_skip(experience):
    from doremi.db.database import get_session
    from doremi.db.models import PlayHistory
    await experience.remember_collections([dict(title="Album", navigate="album?id=a")])
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with get_session() as session:
        session.add_all([
            PlayHistory(video_id="new", title="New", artist="", played_at=now,
                        context_type="album", context_id="a", was_played=True, position_ms=30000),
            PlayHistory(video_id="old", title="Old", artist="", played_at=now - timedelta(hours=1),
                        context_type="album", context_id="a", was_played=True, position_ms=10000),
        ])
        await session.commit()
    assert (await experience.continue_listening())[0]["video_id"] == "new"
    # A long-enough play is valid for stats, but deliberately skipping it is
    # not an invitation to resume it from the beginning.
    await HistoryRepository().add_entry("skipped", "Skipped", "", 100000, context_type="album",
                                       context_id="a", was_played=True, listen_time_ms=50000, skip_count=1)
    assert not await experience.continue_listening()


@pytest.mark.asyncio
async def test_continue_restores_queue_origin_seek_and_does_not_replay_completed_tail():
    from unittest.mock import AsyncMock
    from doremi.ui.controllers.navigation_controller import NavigationController
    tracks = [dict(videoId="a", title="A", duration_ms=100000), dict(videoId="b", title="B", duration_ms=100000)]
    queue = PlayQueue()

    async def play(_video_id, _title, _artist, _album, _duration, _thumb, items, index):
        queue.set_queue(items, index)

    window = SimpleNamespace(_current_path="playlist?id=p", _current_route="playlist", queue=queue,
        playlist_screen=SimpleNamespace(_vm=SimpleNamespace(title="Playlist", tracks=SimpleNamespace(all_items=lambda: tracks))),
        playback_controller=SimpleNamespace(_play_song=AsyncMock(side_effect=play)), player=SimpleNamespace(seek=AsyncMock()))
    controller = NavigationController(window, None)
    await controller._resume_collection("playlist", {"resume": "a", "position": "42000"})
    assert queue.current.video_id == "a"
    assert queue.current.context_id == "p"
    window.player.seek.assert_awaited_once_with(42000)
    window.player.seek.reset_mock()
    await controller._resume_collection("playlist", {"resume": "a", "position": "0", "next": "1"})
    assert queue.current.video_id == "b"
    window.playback_controller._play_song.reset_mock()
    await controller._resume_collection("playlist", {"resume": "b", "next": "1"})
    window.playback_controller._play_song.assert_not_awaited()
    window.player.seek.assert_not_awaited()


@pytest.mark.asyncio
async def test_smart_rules_exclude_skips_and_seek_affinity(experience):
    for vid in ["heard", "skip", "seek"]:
        await SongRepository().upsert_song(video_id=vid, title=vid, artist="Artist")
    await HistoryRepository().add_entry("heard", "heard", "Artist", 100000, listen_time_ms=90000, completion_ratio=.9)
    await HistoryRepository().add_entry("skip", "skip", "Artist", 100000, listen_time_ms=1000, skip_count=1, was_played=False)
    await HistoryRepository().add_entry("seek", "seek", "Artist", 100000, listen_time_ms=1000, completion_ratio=1.0)
    assert [t["videoId"] for t in await experience.smart_tracks("repeat")] == ["heard", "seek"]
    assert [t["videoId"] for t in await experience.smart_tracks("discoveries")] == ["heard"]


@pytest.mark.asyncio
async def test_stats_aggregate_more_than_500_attempts(experience):
    from doremi.db.database import get_session
    from doremi.db.models import PlayHistory
    async with get_session() as session:
        session.add_all([PlayHistory(video_id="v", title="Song", artist="Artist", listen_time_ms=1000, was_played=True) for _ in range(510)])
        session.add(PlayHistory(video_id="old", title="Old", artist="Other", played_at=datetime(2000, 1, 1), listen_time_ms=10000, was_played=True))
        await session.commit()
    assert (await experience.stats("all"))["total_plays"] == 511
    stats = await experience.stats("today")
    assert stats["total_plays"] == 510
    assert stats["listen_time_ms"] == 510000
    assert stats["unique_songs"] == 1
    assert stats["chart_days"] == 1
    assert stats["chart"][0]["count"] == 510
    assert stats["peak_hour"]["plays"] == 510


@pytest.mark.asyncio
async def test_stats_unknown_artist_and_duration_do_not_invent_metrics(experience):
    await HistoryRepository().add_entry("local:1", "Local", "", 0, listen_time_ms=1000)
    stats = await experience.stats("all")
    assert stats["unique_artists"] == 0
    assert stats["completion_rate"] is None
    assert stats["top_artists"] == []
    assert len(stats["chart"]) == 31
    assert sum(day["count"] for day in stats["chart"]) == 1
    assert stats["active_day"]["plays"] == 1


def test_period_boundaries_are_calendar_and_half_open():
    now = datetime(2026, 9, 29, 12, tzinfo=timezone(timedelta(hours=-4)))
    start, end = period_bounds("month", now)
    assert start == datetime(2026, 9, 1, 4)
    assert end == datetime(2026, 9, 29, 16)


def test_upgrade_preserves_existing_history(tmp_path):
    from alembic.config import Config
    from alembic import command
    from sqlalchemy import create_engine, text
    config = Config("alembic.ini")
    config.set_main_option("script_location", "src/doremi/db/migrations")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path / 'old.db'}")
    command.upgrade(config, "20260926_0002")
    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO play_history(video_id,title,artist,listen_time_ms) VALUES ('v','Keep me','Artist',12345)"))
    command.upgrade(config, "head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT title,listen_time_ms,position_ms FROM play_history")).one() == ("Keep me", 12345, 0)
    engine.dispose()


def test_home_composer_priority_dedup_and_empty_sections():
    from doremi.services.home_composer import compose_home
    album = dict(title="Album", navigate="album?id=A")
    track = dict(videoId="v", title="Track")
    result = compose_home(dict(spotlight=[album], tiles=[track, track], horizontal=[album], songs=[track]),
                          [dict(title="Continue", items=[album]), dict(title="Empty", items=[])], [track])
    assert len(result["personal"]) == 1
    assert not result["spotlight"] and not result["horizontal"] and not result["songs"]
    assert result["tiles"] == [track]


def test_home_diversity_and_play_route_identity():
    from doremi.services.home_composer import compose_home
    frequent = [dict(videoId=str(i), title=str(i), artist="Same artist") for i in range(6)]
    alternatives = [dict(videoId="other" + str(i), title=str(i), artist="Artist " + str(i)) for i in range(4)]
    result = compose_home(dict(tiles=alternatives, spotlight=[dict(navigate="play:0")]), [], frequent)
    assert len(result["tiles"]) == 6
    assert sum(item["artist"] == "Same artist" for item in result["tiles"]) == 2
    assert result["spotlight"] == []
    fallback = compose_home({}, [], frequent)
    assert len(fallback["tiles"]) == 6


def test_explore_combines_provider_and_stable_categories_without_duplicates():
    from doremi.services.explore import compose_categories
    categories = compose_categories([dict(title="Electrónica"), dict(title="electronica"), dict(title="Focus"), dict(title="")])
    assert [item["name"] for item in categories[:2]] == ["Electrónica", "Focus"]
    assert sum(item["query"] == "electronic" for item in categories) == 0
    assert any(item["name"] == "Anime" for item in categories)
    assert len(categories) <= 14


@pytest.mark.asyncio
async def test_explore_offline_does_not_request_provider(monkeypatch):
    from unittest.mock import AsyncMock
    from doremi.services.explore import explore_categories
    from doremi.system.network import NetworkMonitor
    monkeypatch.setattr(NetworkMonitor, "current_connectivity", lambda: False)
    client = SimpleNamespace(get_explore=AsyncMock())
    assert await explore_categories(client) == []
    client.get_explore.assert_not_called()


@pytest.mark.asyncio
async def test_import_and_mix_local_remote_playlist(experience, tmp_path):
    from doremi.db.local_library_repository import LocalLibraryRepository, local_identity
    local = LocalLibraryRepository()
    audio = tmp_path / "Imported.flac"
    audio.write_bytes(b"fLaC")
    ignored = tmp_path / "ignore.txt"
    ignored.write_text("ignore")
    assert await local.import_files([str(audio), str(ignored)]) == 1
    identity = local_identity(audio)
    assert (await local.search("Imported"))[0]["videoId"] == identity
    await SongRepository().upsert_song(video_id="remote", title="Stream", artist="Artist")
    playlist = await local.create_playlist("Mi mezcla")
    await local.append(playlist, [identity, "remote"])
    title, tracks = await local.tracks(playlist)
    assert title == "Mi mezcla"
    assert [t["videoId"] for t in tracks] == [identity, "remote"]
    assert tracks[0]["local_path"] == str(audio)
    assert tracks[1]["local_path"] is None


@pytest.mark.asyncio
async def test_music_sessions_group_gap_and_save_as_playlist(experience):
    from doremi.db.database import get_session
    from doremi.db.models import PlayHistory
    from doremi.services.listening_periods import ListeningPeriods
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with get_session() as session:
        # Import order deliberately differs from chronological order.
        session.add_all([PlayHistory(video_id="a", title="A", artist="Artist", played_at=now - timedelta(minutes=90), listen_time_ms=60000, was_played=True),
                         PlayHistory(video_id="c", title="C", artist="Artist", played_at=now, listen_time_ms=60000, was_played=True),
                         PlayHistory(video_id="b", title="B", artist="Artist", played_at=now - timedelta(minutes=80), listen_time_ms=60000, was_played=True)])
        await session.commit()
    periods = await ListeningPeriods().recent()
    assert [p["track_count"] for p in periods] == [1, 2]
    playlist_id = await ListeningPeriods().save_as_playlist(periods[1]["first_id"], periods[1]["last_id"], "Saved")
    title, tracks = await __import__("doremi.db.local_library_repository", fromlist=["LocalLibraryRepository"]).LocalLibraryRepository().tracks(playlist_id)
    assert title == "Saved"
    assert [t["videoId"] for t in tracks] == ["a", "b"]


@pytest.mark.asyncio
async def test_music_session_route_preserves_cutoff_membership(experience):
    from doremi.db.database import get_session
    from doremi.db.models import PlayHistory
    from doremi.services.listening_periods import ListeningPeriods
    from doremi.ui.screens.playlist_data import gather_playlist
    now = datetime.now(timezone.utc).replace(microsecond=0)
    cutoff = (now - timedelta(days=90)).replace(tzinfo=None)
    async with get_session() as session:
        session.add_all([
            PlayHistory(video_id="outside", title="Old", artist="Artist", played_at=cutoff - timedelta(minutes=5), was_played=True),
            PlayHistory(video_id="inside", title="Recent", artist="Artist", played_at=cutoff + timedelta(minutes=5), was_played=True),
        ])
        await session.commit()
    periods = await ListeningPeriods().recent(now=now)
    identity = periods[0]["navigate"].split("id=", 1)[1]
    args = ListeningPeriods.parse_identity(identity)
    assert [t["videoId"] for t in await ListeningPeriods().tracks(*args)] == ["inside"]
    assert [t["videoId"] for t in (await gather_playlist(None, identity))["tracks"]] == ["inside"]
    playlist_id = await ListeningPeriods().save_as_playlist(args[0], args[1], "At boundary", args[2])
    from doremi.db.local_library_repository import LocalLibraryRepository
    assert [t["videoId"] for t in (await LocalLibraryRepository().tracks(playlist_id))[1]] == ["inside"]


@pytest.mark.asyncio
async def test_music_session_card_remains_valid_when_period_grows(experience):
    from doremi.db.database import get_session
    from doremi.db.models import PlayHistory
    from doremi.services.listening_periods import ListeningPeriods
    from doremi.db.local_library_repository import LocalLibraryRepository
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with get_session() as session:
        session.add(PlayHistory(video_id="first", title="First", artist="Artist",
                               played_at=now - timedelta(minutes=5), was_played=True))
        await session.commit()
    service = ListeningPeriods()
    identity = (await service.recent())[0]["navigate"].split("id=", 1)[1]
    args = service.parse_identity(identity)
    async with get_session() as session:
        session.add(PlayHistory(video_id="next", title="Next", artist="Artist",
                               played_at=now, was_played=True))
        await session.commit()
    assert [t["videoId"] for t in await service.tracks(*args)] == ["first", "next"]
    playlist_id = await service.save_as_playlist(args[0], args[1], "Still listening", args[2])
    assert [t["videoId"] for t in (await LocalLibraryRepository().tracks(playlist_id))[1]] == ["first", "next"]


@pytest.mark.asyncio
async def test_wrapped_uses_calendar_summary(experience):
    from doremi.db.database import get_session
    from doremi.db.models import PlayHistory
    from doremi.services.listening_periods import Wrapped
    local_now = datetime.now().astimezone()
    now = local_now.astimezone(timezone.utc).replace(tzinfo=None)
    async with get_session() as session:
        session.add(PlayHistory(video_id="v", title="Song", artist="Artist", played_at=now,
                                listen_time_ms=120000, was_played=True))
        await session.commit()
    wrapped = await Wrapped().summary(local_now.year, local_now.month)
    assert wrapped["minutes"] == 2
    assert wrapped["top_artist"] == "Artist"
    assert wrapped["top_song"] == "Song"


@pytest.mark.asyncio
async def test_smart_playlist_uses_existing_collection_contract(experience):
    from doremi.ui.screens.playlist_data import gather_playlist
    await SongRepository().upsert_song(video_id="v", title="Favorite", artist="Artist", is_liked=True)
    data = await gather_playlist(None, "smart:liked")
    assert data["title"] == "Favoritas"
    assert data["tracks"][0]["videoId"] == "v"
    assert not data["is_local"]  # virtual does not imply every file is offline


@pytest.mark.asyncio
async def test_available_download_query_checks_only_candidates_and_real_files(experience, tmp_path):
    from doremi.db.repository import DownloadRepository
    repo = DownloadRepository()
    audio = tmp_path / "song.ogg"
    audio.write_bytes(b"OggS")
    await repo.add_download(video_id="present", title="Present", artist="", file_path=str(audio))
    await repo.add_download(video_id="missing", title="Missing", artist="", file_path=str(tmp_path / "missing.ogg"))
    assert await repo.get_available_video_ids(["present", "missing", "unrecorded"]) == {"present"}
    assert not await repo.get_available_video_ids(["missing"])
    assert not await repo.get_available_video_ids([])


@pytest.mark.asyncio
async def test_stats_do_not_rank_missing_artist_placeholders(experience):
    for i, artist in enumerate(("", "Unknown", "Unknown Artist", "Known")):
        await HistoryRepository().add_entry(str(i), "Song", artist, 1000)
    data = await experience.stats()
    assert data["unique_artists"] == 1
    assert data["top_artists"] == [dict(title="Known", plays=1)]


@pytest.mark.asyncio
async def test_local_playlist_batch_append_is_atomic(experience):
    from doremi.db.local_library_repository import LocalLibraryRepository
    repo = LocalLibraryRepository()
    identity = await repo.create_playlist("Batch")
    await SongRepository().upsert_song(video_id="known", title="Known", artist="")
    with pytest.raises(ValueError, match="metadatos"):
        await repo.append(identity, ["known", "absent"])
    assert (await repo.tracks(identity))[1] == []
    await repo.append(identity, ["known"] * 600)
    assert len((await repo.tracks(identity))[1]) == 600


@pytest.mark.asyncio
async def test_local_playlist_edits_preserve_files_history_and_duplicate_occurrences(experience, tmp_path):
    from doremi.db.local_library_repository import LocalLibraryRepository, local_identity
    repo = LocalLibraryRepository()
    path = tmp_path / "Track.ogg"
    path.write_bytes(b"OggS")
    await repo.import_files([str(path)])
    video_id = local_identity(path)
    playlist = await repo.create_playlist("Original")
    await repo.append(playlist, [video_id, video_id, video_id])
    await experience.set_pin(playlist, "Original")
    await repo.rename_playlist(playlist, "Renamed")
    await HistoryRepository().add_entry(video_id, "Track", "", 1000, context_type="playlist",
                                       context_id=playlist, context_title="Original", listen_time_ms=1000)
    assert (await experience.quick_access())[0]["title"] == "Renamed"
    assert not await repo.remove_occurrence(playlist, 1, "wrong-id")
    assert await repo.remove_occurrence(playlist, 1, video_id)
    title, tracks = await repo.tracks(playlist)
    assert title == "Renamed"
    assert [track["local_position"] for track in tracks] == [0, 2]
    await repo.delete_playlist(playlist)
    assert path.is_file()
    assert await SongRepository().get_song(video_id)
    assert len(await HistoryRepository().get_history()) == 1
    await HistoryRepository().add_entry(video_id, "Track", "", 1000, context_type="playlist",
                                       context_id=playlist, context_title="Renamed", listen_time_ms=1000)
    assert await repo.playlists() == []
    assert await experience.quick_access() == []


@pytest.mark.asyncio
async def test_offline_home_and_mixed_playlist_offer_available_music(experience, tmp_path, monkeypatch):
    from doremi.db.local_library_repository import LocalLibraryRepository, local_identity
    from doremi.services.home_composer import personalized_home
    from doremi.ui.screens.playlist_data import gather_playlist
    from doremi.system.network import NetworkMonitor
    monkeypatch.setattr(NetworkMonitor, "current_connectivity", lambda: False)
    path = tmp_path / "Offline.flac"
    path.write_bytes(b"fLaC")
    local = LocalLibraryRepository()
    await local.import_files([str(path)])
    identity = local_identity(path)
    await SongRepository().upsert_song(video_id=identity, title="Offline", artist="", is_liked=True)
    await SongRepository().upsert_song(video_id="remote", title="Online", artist="Artist", is_liked=True)
    playlist = await local.create_playlist("Mixed")
    await local.append(playlist, [identity, "remote"])
    await experience.set_pin("remote-playlist", "Remote")
    for video_id in [identity, "remote"]:
        await HistoryRepository().add_entry(video_id, video_id, "Artist", 100000, listen_time_ms=90000,
                                           context_type="playlist", context_id=playlist, context_title="Mixed")
    home = await personalized_home(dict(_source="offline", tiles=[], songs=[], horizontal=[], spotlight=[]))
    assert [item["videoId"] for item in home["tiles"]] == [identity]
    assert all(item.get("navigate") != "playlist?id=remote-playlist" for section in home["personal"] for item in section["items"])
    data = await gather_playlist(None, playlist)
    assert data["track_count"] == 1
    assert data["tracks"][0]["videoId"] == identity
