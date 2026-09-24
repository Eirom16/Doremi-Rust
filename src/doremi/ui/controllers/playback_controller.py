import asyncio
import os
import time

from loguru import logger

from doremi.audio.player import MusicPlayer, PlayerState
from doremi.audio.queue import PlayQueue, QueueItem, RepeatMode
from doremi.api.youtube_music import YouTubeMusicClient
from doremi.config.settings import AppSettings
from doremi.api.stream_extractor import StreamExtractor
from doremi.services.download_manager import DownloadManager
from doremi.ui.widgets.mini_player import MiniPlayerWidget
from doremi.ui.screens.now_playing import NowPlayingScreen
from doremi.system.tray import SystemTray
from doremi.system.mpris import MprisPlayer
from doremi.api.lastfm import LastFmScrobbler
from doremi.api.discord_rpc import DiscordRPC
from doremi.audio.crossfade import CrossfadeManager
from doremi.system.network import NetworkMonitor
from doremi.api.lyrics import LyricsClient
from doremi.audio.sleep_timer import SleepTimer


class PlaybackController:
    """Specialized controller for playback logic.

    Owns the core playback methods previously living in MainWindow's god object.
    Dependencies are injected through the constructor; ``run_async`` is a callable
    (MainWindow._run_async) used to launch coroutines as asyncio tasks.
    ``main_window`` is kept as a reference for a small set of tightly-coupled
    navigation/lastfm concerns that remain on MainWindow.
    """

    def __init__(
        self,
        player: MusicPlayer,
        queue: PlayQueue,
        yt: YouTubeMusicClient,
        settings: AppSettings,
        extractor: StreamExtractor,
        download_manager: DownloadManager,
        run_async,
        mini_player: MiniPlayerWidget,
        now_playing_screen: NowPlayingScreen,
        tray: SystemTray,
        mpris: MprisPlayer,
        scrobbler: LastFmScrobbler | None,
        discord: DiscordRPC | None,
        crossfade_manager: CrossfadeManager,
        network_monitor: NetworkMonitor,
        lyrics_client: LyricsClient,
        sleep_timer: SleepTimer,
        main_window,
    ):
        self.player = player
        self.queue = queue
        self.yt = yt
        self.settings = settings
        self.extractor = extractor
        self.download_manager = download_manager
        self.run_async = run_async
        self.mini_player = mini_player
        self.now_playing_screen = now_playing_screen
        self.tray = tray
        self.mpris = mpris
        self.scrobbler = scrobbler
        self.discord = discord
        self.crossfade_manager = crossfade_manager
        self.network_monitor = network_monitor
        self.lyrics_client = lyrics_client
        self.sleep_timer = sleep_timer
        self.main_window = main_window

        # Playback identity counter (only used by moved methods).
        self._current_play_id = 0
        self._play_task = None
        self._starting_media = False
        self._recovering_id = None
        self._failed_video_ids: set[str] = set()

    async def _play_song(
        self,
        video_id: str,
        title: str,
        artist: str,
        album: str,
        duration_ms: int,
        thumbnail_url: str,
        queue_items: list[QueueItem] | None = None,
        queue_index: int = 0,
    ) -> None:
        logger.info(f"_play_song called: {title[:30]} video_id={video_id}")
        if queue_items:
            self.queue.set_queue(queue_items, queue_index)
        else:
            item = QueueItem(
                video_id=video_id, title=title, artist=artist,
                album=album, duration_ms=duration_ms,
                thumbnail_url=thumbnail_url,
            )
            self.queue.set_queue([item], 0)

        self._update_queue_panel()
        await self._play_current()

        if not queue_items:
            self.run_async(self._fetch_and_populate_auto_queue(video_id))

    async def _fetch_and_populate_auto_queue(self, video_id: str) -> None:
        """Fetch watch playlist and populate the rest of the queue automatically."""
        if not video_id or video_id == "local" or len(video_id) < 5:
            return
        if hasattr(self, 'network_monitor') and not self.network_monitor.is_connected:
            return

        expected_item = self.queue.current
        play_id = self._current_play_id
        try:
            logger.info(f"Fetching automatic watch playlist for song {video_id}")
            watch = await self.yt.get_watch_playlist(video_id, limit=25)
            tracks = watch.get('tracks', [])

            # Verify the current track hasn't changed while we were fetching
            current_item = self.queue.current
            if not current_item or current_item is not expected_item or current_item.video_id != video_id or self._current_play_id != play_id:
                logger.info("Song changed during auto queue fetch. Discarding results.")
                return

            new_items = []
            for t in tracks:
                vid = t.get("videoId")
                if not vid or vid == video_id:
                    continue

                # Check if this song is already in the queue to avoid duplication
                if any(x.video_id == vid for x in self.queue.items):
                    continue

                # Extract artist names robustly
                artists = t.get("artists", [])
                artist_name = "Unknown Artist"
                if isinstance(artists, list) and artists:
                    names = []
                    for a in artists:
                        if isinstance(a, dict):
                            names.append(a.get("name", ""))
                        else:
                            names.append(str(a))
                    artist_name = ", ".join(filter(None, names)) or artist_name
                elif artists:
                    artist_name = str(artists)

                # Extract thumbnail robustly
                t_thumbnail_url = ""
                thumbnails = t.get("thumbnail") or t.get("thumbnails")
                if isinstance(thumbnails, list) and thumbnails:
                    t_thumbnail_url = thumbnails[0].get("url", "")
                elif isinstance(thumbnails, dict):
                    t_thumbnail_url = thumbnails.get("url", "")

                # Extract album robustly
                album_name = ""
                album_data = t.get("album")
                if isinstance(album_data, dict):
                    album_name = album_data.get("name", "")
                elif album_data:
                    album_name = str(album_data)

                # Duration
                dur_ms = 0
                for key in ('duration_seconds', 'durationSeconds', 'lengthSeconds'):
                    if key in t:
                        try:
                            dur_ms = int(t.get(key)) * 1000
                            break
                        except (TypeError, ValueError):
                            pass
                # Fallback: parse duration string (e.g., "4:55")
                if dur_ms == 0 and t.get('duration'):
                    try:
                        dur_str = str(t['duration'])
                        parts = dur_str.split(':')
                        if len(parts) == 2:
                            dur_ms = (int(parts[0]) * 60 + int(parts[1])) * 1000
                        elif len(parts) == 3:
                            dur_ms = (int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])) * 1000
                    except (ValueError, IndexError):
                        pass

                new_items.append(QueueItem(
                    video_id=vid,
                    title=t.get("title", "Unknown"),
                    artist=artist_name,
                    album=album_name,
                    duration_ms=dur_ms,
                    thumbnail_url=t_thumbnail_url,
                ))

            if new_items:
                logger.info(f"Adding {len(new_items)} related items to the auto-generated queue.")
                for ni in new_items:
                    self.queue.add_to_end(ni)
                self._update_queue_panel()
        except Exception as e:
            logger.warning(f"Failed to generate automatic queue: {e}")

    async def _play_current(self, resume: bool = False, *, reset_failures: bool = True) -> None:
        task = asyncio.current_task()
        previous = getattr(self, "_play_task", None)
        if previous and previous is not task and not previous.done():
            previous.cancel()
        self._play_task = task
        if reset_failures:
            self._failed_video_ids = set()
        try:
            await self._play_current_request(resume)
        except asyncio.CancelledError:
            # Una selección más reciente o el cierre invalida esta operación.
            raise
        finally:
            if self._play_task is task:
                self._play_task = None

    async def _start_media(self, url: str, item: QueueItem) -> bool:
        play_id = self._current_play_id
        self._starting_media = True
        try:
            return await self.player.play_url(url, item.video_id)
        finally:
            if play_id == self._current_play_id:
                self._starting_media = False

    def on_player_error(self, status) -> None:
        # Los errores de inicio pertenecen al await de _start_media.
        if getattr(self, "_starting_media", False):
            return
        item = self.queue.current
        play_id = self._current_play_id
        if not item or status.current_video_id != item.video_id:
            return
        if getattr(self, "_recovering_id", None) == play_id:
            return
        self._recovering_id = play_id
        self.run_async(self._recover_stream(item, play_id))

    async def _recover_stream(self, item: QueueItem, play_id: int) -> None:
        def current():
            return self._current_play_id == play_id and self.queue.current is item
        try:
            if not current():
                return
            attempts = self.main_window._stream_recovery_attempts
            if item.video_id not in attempts and not item.is_local and self.network_monitor.is_connected:
                attempts.add(item.video_id)
                url = await self.extractor.get_alternative_stream(item.video_id)
                if not current():
                    return
                if url and await self._start_media(url, item):
                    return
            if current():
                await self.handle_playback_failure(item, "No se pudo reproducir la pista.")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(f"Stream recovery failed: {exc}")
            if current():
                await self.handle_playback_failure(item, "No se pudo reproducir la pista.")
        finally:
            if self._recovering_id == play_id:
                self._recovering_id = None

    async def handle_playback_failure(self, item: QueueItem, message: str) -> None:
        if self.queue.current is not item:
            return
        from doremi.ui.widgets.toast import ToastNotification
        from doremi.utils.i18n import _
        ToastNotification.show(self.main_window, _(message), "error")
        failed = getattr(self, "_failed_video_ids", set())
        failed.add(item.video_id)
        self._failed_video_ids = failed
        items = self.queue.items
        # El salto por error no repite la pista fallida, ni genera autoplay.
        for offset in range(1, len(items)):
            index = self.queue.current_index + offset
            if index >= len(items):
                if self.queue.repeat_mode != RepeatMode.ALL:
                    break
                index %= len(items)
            candidate = items[index]
            if candidate.video_id not in failed:
                self.queue.jump_to(index)
                self._update_queue_panel()
                await self._play_current(reset_failures=False)
                return
        await self.player.stop()

    async def _play_current_request(self, resume: bool = False) -> None:
        item = self.queue.current
        if not item:
            return

        # Registrar la solicitud antes del primer await: la consulta local
        # también puede terminar después de que el usuario cambie de pista.
        self._current_play_id += 1
        play_id = self._current_play_id
        self._starting_media = False
        if hasattr(self, "crossfade_manager"):
            self.crossfade_manager.cancel()

        def is_current() -> bool:
            return self._current_play_id == play_id and self.queue.current is item

        # Check if downloaded and play local instead of streaming
        try:
            from doremi.db.repository import DownloadRepository
            dl_repo = DownloadRepository()
            download = await dl_repo.get_download(item.video_id)
            if download and download.file_path:
                import os
                if os.path.exists(download.file_path):
                    item.is_local = True
                    item.local_path = download.file_path
        except Exception as e:
            logger.debug(f"Error checking download status in _play_current: {e}")

        # La caché inteligente es independiente de las descargas visibles del usuario.
        if not item.is_local:
            try:
                from doremi.services.offline_cache import OfflineCacheManager
                cached_path = OfflineCacheManager.get_instance().local_path(item.video_id)
                if cached_path:
                    item.is_local = True
                    item.local_path = cached_path
            except Exception as e:
                logger.debug(f"Error checking offline cache in _play_current: {e}")

        if not is_current():
            return

        self.mini_player.update_track_info(
            item.title, item.artist, item.thumbnail_url
        )
        self.now_playing_screen.update_track_info(
            item.title, item.artist, item.thumbnail_url
        )
        if hasattr(self, "tray") and self.tray:
            self.tray.update_track_info(item.title, item.artist)

        async def _check_liked_state() -> None:
            try:
                from doremi.db.repository import SongRepository
                repo = SongRepository()
                song = await repo.get_song(item.video_id)
                liked = song.is_liked if song else False
                if is_current():
                    self.now_playing_screen.set_liked_state(liked)
            except Exception as e:
                logger.error(f"Error checking liked state in _play_current: {e}")
        self.run_async(_check_liked_state())

        self.main_window._stream_recovery_attempts.discard(item.video_id)
        self.main_window._reset_lastfm_scrobble_state(item)

        # Immediate visual feedback for lyrics and related suggestions
        self.now_playing_screen.set_lyrics_loading()
        self.now_playing_screen.set_related([], None)
        self.run_async(self._load_lyrics(item, play_id))
        self.run_async(self._load_related(item, play_id))
        if not item.is_local and not resume:
            if hasattr(self, 'network_monitor') and not self.network_monitor.is_connected:
                logger.warning(f"Offline: cannot play non-local song {item.title}")
                from doremi.ui.widgets.toast import ToastNotification
                ToastNotification.show(self.main_window, f"Sin conexión: '{item.title}' no está descargada.", "error")
                await self.player.stop()
                return

        if item.is_local:
            logger.info(f"Playing local track: {item.title}")

            # Validate local file before attempting playback
            local_path_valid = False
            try:
                import os
                if item.local_path and os.path.isfile(item.local_path) and os.path.getsize(item.local_path) > 0:
                    # Check read permission
                    if os.access(item.local_path, os.R_OK):
                        local_path_valid = True
                    else:
                        logger.warning(f"Local file not readable: {item.local_path}")
                else:
                    logger.warning(f"Local file missing or empty: {item.local_path}")
            except Exception as e:
                logger.warning(f"Error validating local file {item.local_path}: {e}")

            if not local_path_valid:
                # Mark as non-local and fall through to streaming
                logger.info(f"Local file invalid, falling back to streaming for {item.title}")
                item.is_local = False
                item.local_path = None
            else:
                if self.settings.player.crossfade_enabled and self.player.status.state == PlayerState.PLAYING:
                    await self.crossfade_manager.fade_out(self.player, is_current=is_current)

                if not is_current():
                    return
                success = await self._start_media(item.local_path, item)
                if not is_current():
                    return
                if success:
                    self.run_async(self._save_play_history(item))
                    if self.settings.player.crossfade_enabled:
                        self.run_async(self.crossfade_manager.fade_in(self.player, self.settings.player.volume, is_current=is_current))
                    if self.scrobbler:
                        await self.scrobbler.update_now_playing(
                            item.artist, item.title, item.album
                        )
                    if self.discord:
                        await self.discord.update(
                            item.title, item.artist, item.album, True, item.thumbnail_url
                        )
                    if self.mpris:
                        self.mpris.update_metadata(
                            item.title, item.artist, item.album,
                            item.duration_ms * 1000, item.thumbnail_url, item.video_id
                        )
                    return
                else:
                    # Local playback failed, try streaming fallback if online
                    logger.warning(f"Local playback failed for {item.title}, attempting streaming fallback")
                    item.is_local = False
                    item.local_path = None
                    # Don't return here, fall through to streaming logic below

        # Un archivo local sin ID remoto válido no admite fallback online.
        if not item.video_id or item.video_id == "local" or not self.network_monitor.is_connected:
            if is_current():
                await self.main_window._handle_playback_failure(item, "No se pudo reproducir la pista.")
            return

        # Check if preloaded stream_url is already valid
        import time
        has_preloaded = False
        if item.stream_url and hasattr(item, 'stream_expires_at') and time.time() < item.stream_expires_at:
            has_preloaded = True

        if has_preloaded:
            logger.info(f"Playing preloaded: {item.title}")
            if item.stream_url:
                if self.settings.player.crossfade_enabled and self.player.status.state == PlayerState.PLAYING:
                    await self.crossfade_manager.fade_out(self.player, is_current=is_current)

                if not is_current():
                    return
                success = await self._start_media(item.stream_url, item)
                if not is_current():
                    return
                if success:
                    self.run_async(self._save_play_history(item))
                    if self.settings.player.crossfade_enabled:
                        self.run_async(self.crossfade_manager.fade_in(self.player, self.settings.player.volume, is_current=is_current))
                    # Ensure queue panel shows correct duration (preloaded during _preload_next)
                    self._update_queue_panel()
                else:
                    logger.error(f"Player failed for preloaded {item.title}, trying alternative format...")
                    alt_url = await self.extractor.get_alternative_stream(item.video_id)
                    if not is_current():
                        return
                    if alt_url:
                        logger.info(f"Retrying with alternative format")
                        success = await self._start_media(alt_url, item)
                        if not is_current():
                            return
                        if success and self.settings.player.crossfade_enabled:
                            self.run_async(self.crossfade_manager.fade_in(self.player, self.settings.player.volume, is_current=is_current))
                    if not success:
                        await self.main_window._handle_playback_failure(item, "No se pudo reproducir la pista. Saltando a la siguiente.")
                        return
            else:
                logger.error(f"No stream URL for preloaded {item.title}")
                await self.main_window._handle_playback_failure(item, "No se pudo obtener una URL de reproduccion.")
                return

            if getattr(getattr(self.settings, 'network', None), 'preload_next', True):
                self.run_async(self._preload_next())

            if self.scrobbler:
                await self.scrobbler.update_now_playing(
                    item.artist, item.title, item.album
                )
            if self.discord:
                await self.discord.update(
                    item.title, item.artist, item.album, True, item.thumbnail_url
                )
            if self.mpris:
                self.mpris.update_metadata(
                    item.title, item.artist, item.album,
                    item.duration_ms * 1000, item.thumbnail_url, item.video_id
                )
            return

        try:
            logger.info(f"Getting fresh stream for: {item.title}")

            import asyncio
            extraction_task = asyncio.create_task(self.extractor.get_stream_info(item.video_id))

            try:
                if self.player.status.state == PlayerState.PLAYING:
                    if self.settings.player.crossfade_enabled:
                        await self.crossfade_manager.fade_out(self.player, is_current=is_current)
                    else:
                        await self.player.stop()
                stream_info = await extraction_task
            finally:
                if not extraction_task.done():
                    extraction_task.cancel()
                    await asyncio.gather(extraction_task, return_exceptions=True)

            # Check if user clicked another song while we were extracting
            if not is_current():
                logger.info("Song changed during extraction. Aborting play.")
                return

            item.stream_url = stream_info.get("url", "")

            # Update duration from stream info (yt-dlp provides accurate duration)
            if stream_info.get("duration"):
                item.duration_ms = int(stream_info["duration"]) * 1000
                # Refresh queue panel to show correct duration
                self._update_queue_panel()

            if not item.thumbnail_url and stream_info.get("thumbnail"):
                item.thumbnail_url = stream_info.get("thumbnail")
                self.mini_player.update_track_info(item.title, item.artist, item.thumbnail_url)
                self.now_playing_screen.update_track_info(item.title, item.artist, item.thumbnail_url)

            import time
            item.stream_expires_at = time.time() + 21600

            if item.stream_url:
                logger.info(f"Playing: {item.title} - URL length: {len(item.stream_url)}, format: {stream_info.get('format', 'unknown')}")

                success = await self._start_media(item.stream_url, item)
                if not is_current():
                    return
                if success:
                    self.run_async(self._save_play_history(item))
                    if self.settings.player.crossfade_enabled:
                        self.run_async(self.crossfade_manager.fade_in(self.player, self.settings.player.volume, is_current=is_current))
                else:
                    logger.error(f"Player failed for {item.title}, trying alternative format...")
                    alt_url = await self.extractor.get_alternative_stream(item.video_id)
                    if not is_current():
                        return
                    if alt_url:
                        logger.info(f"Retrying with alternative format")
                        success = await self._start_media(alt_url, item)
                        if not is_current():
                            return
                        if success and self.settings.player.crossfade_enabled:
                            self.run_async(self.crossfade_manager.fade_in(self.player, self.settings.player.volume, is_current=is_current))
                    if not success:
                        await self.main_window._handle_playback_failure(item, "No se pudo reproducir la pista. Saltando a la siguiente.")
                        return
            else:
                logger.error(f"No stream URL for {item.title}")
                await self.main_window._handle_playback_failure(item, "No se pudo obtener una URL de reproduccion.")
                return

            if getattr(getattr(self.settings, 'network', None), 'preload_next', True):
                self.run_async(self._preload_next())

            if self.scrobbler:
                await self.scrobbler.update_now_playing(
                    item.artist, item.title, item.album
                )
            if self.discord:
                await self.discord.update(
                    item.title, item.artist, item.album, True, item.thumbnail_url
                )
            if self.mpris:
                self.mpris.update_metadata(
                    item.title, item.artist, item.album,
                    item.duration_ms * 1000, item.thumbnail_url, item.video_id
                )

        except Exception as e:
            logger.error(f"Failed to play {item.video_id}: {e}")
            if is_current():
                await self.main_window._handle_playback_failure(item, "Error de reproduccion. Saltando a la siguiente.")

    async def _load_lyrics(self, item: QueueItem, play_id: int) -> None:
        self.now_playing_screen.set_lyrics_loading()
        try:
            lyrics = None
            if item.is_local and item.local_path:
                import os
                lrc_path = os.path.splitext(item.local_path)[0] + ".lrc"
                if os.path.exists(lrc_path):
                    try:
                        with open(lrc_path, "r", encoding="utf-8") as f:
                            lyrics = f.read()
                        logger.info(f"Loaded offline lyrics from: {lrc_path}")
                    except Exception as e:
                        logger.error(f"Error reading offline lyrics file: {e}")

            if not lyrics:
                # Check global lyrics cache
                from doremi.utils.lyrics_cache import LyricsCache
                lyrics = LyricsCache.get(item.title, item.artist)

            if not lyrics:
                if hasattr(self, 'network_monitor') and not self.network_monitor.is_connected:
                    lyrics = "[Letras no disponibles sin conexión]"
                else:
                    synced = await self.lyrics_client.get_lyrics(
                        item.title, item.artist, item.album
                    )
                    lyrics = synced
                    if lyrics:
                        from doremi.utils.lyrics_cache import LyricsCache
                        LyricsCache.save(item.title, item.artist, str(lyrics))

            if self._current_play_id == play_id:
                self.now_playing_screen.set_lyrics(lyrics)
            else:
                logger.info(f"Discarded stale lyrics for {item.title} (current song changed)")
        except Exception as e:
            logger.error(f"Error loading lyrics: {e}")
            if self._current_play_id == play_id:
                self.now_playing_screen.set_lyrics(None)

    async def _load_related(self, item: QueueItem, play_id: int) -> None:
        """Load related/similar tracks for the SIMILARES tab."""
        try:
            if hasattr(self, 'network_monitor') and not self.network_monitor.is_connected:
                if self._current_play_id == play_id:
                    self.now_playing_screen.set_related([], None)
                return
            video_id = item.video_id

            # If it's a local/imported track or we don't have a valid ID, search for it
            if not video_id or video_id == "local" or len(video_id) < 5:
                if self.yt and item.title and item.artist:
                    logger.info(f"Local track: searching YTM for similar tracks using query: {item.title} - {item.artist}")
                    search_results = await self.yt.search(f"{item.title} {item.artist}", filter="songs", limit=1)
                    if search_results:
                        video_id = search_results[0].get("videoId")

            related = []
            if self.yt and video_id and video_id != "local" and len(video_id) >= 5:
                try:
                    watch_data = await self.yt.get_watch_playlist(video_id=video_id, limit=15)
                    tracks = watch_data.get('tracks', [])
                    # Skip the current song
                    related = [t for t in tracks if t.get('videoId') != video_id]
                except Exception as e:
                    logger.warning(f"Failed to load related tracks with direct video_id: {e}")
                    # Try search fallback as last resort
                    if item.title and item.artist:
                        search_results = await self.yt.search(f"{item.title} {item.artist}", filter="songs", limit=1)
                        if search_results:
                            fallback_id = search_results[0].get("videoId")
                            if fallback_id and fallback_id != video_id:
                                watch_data = await self.yt.get_watch_playlist(video_id=fallback_id, limit=15)
                                tracks = watch_data.get('tracks', [])
                                related = [t for t in tracks if t.get('videoId') != fallback_id]

            if self._current_play_id == play_id:
                self.now_playing_screen.set_related(related, self.main_window._play_song_sync)
        except Exception as e:
            logger.error(f"Error loading related: {e}")
            if self._current_play_id == play_id:
                self.now_playing_screen.set_related([], None)

    async def _save_play_history(self, item: QueueItem) -> None:
        try:
            from doremi.db.repository import HistoryRepository, SongRepository
            history_repo = HistoryRepository()
            song_repo = SongRepository()

            await history_repo.add_entry(
                video_id=item.video_id,
                title=item.title,
                artist=item.artist,
                duration_ms=item.duration_ms
            )

            await song_repo.upsert_song(
                video_id=item.video_id,
                title=item.title,
                artist=item.artist,
                album=item.album,
                duration_ms=item.duration_ms,
                thumbnail_url=item.thumbnail_url,
            )

            await song_repo.record_play(item.video_id)
            logger.debug(f"Saved play history for: {item.title}")
        except Exception as e:
            logger.debug(f"Failed to save play history: {e}")

    async def _preload_next(self) -> None:
        next_item = self.queue.next_item
        if not next_item:
            return

        # 1. Preload artwork
        if next_item.thumbnail_url:
            try:
                from doremi.utils.image_cache import ImageCache
                cache = ImageCache()
                await cache.download(next_item.thumbnail_url)
            except Exception as e:
                logger.debug(f"Failed to preload next artwork: {e}")

        # 2. Preload stream URL
        if not next_item.stream_url:
            try:
                import time
                info = await self.extractor.get_stream_info(next_item.video_id)
                next_item.stream_url = info.get("url", "")
                if next_item.stream_url:
                    next_item.stream_expires_at = time.time() + 21600
                    if info.get("duration"):
                        next_item.duration_ms = int(info["duration"]) * 1000
            except Exception as e:
                logger.debug(f"Failed to preload next stream: {e}")

    async def _advance_queue(self, *, manual: bool = False) -> None:
        item = self.queue.advance(ignore_repeat_one=manual)
        if item:
            self._update_queue_panel()
            await self._play_current()
        else:
            current = self.queue.current
            if current and not current.is_local and self.network_monitor.is_connected:
                queue = self.queue
                play_id = self._current_play_id
                try:
                    watch = await self.yt.get_watch_playlist(current.video_id)
                    if self.queue is not queue or self.queue.current is not current or self._current_play_id != play_id:
                        return
                    new_items = [
                        QueueItem(
                            video_id=t["videoId"],
                            title=t.get("title", ""),
                            artist=t.get("artists", [{}])[0].get("name", ""),
                            album="",
                            duration_ms=0,
                            thumbnail_url=(t.get("thumbnail") or [{}])[0].get("url",""),
                        )
                        for t in watch.get("tracks", [])[1:]
                    ]
                    if new_items:
                        for ni in new_items:
                            self.queue.add_to_end(ni)
                        self.queue.advance()
                        self._update_queue_panel()
                        await self._play_current()
                except Exception as e:
                    logger.warning(f"Autoplay failed: {e}")

    async def _play_local(self, path: str, metadata: dict) -> None:
        title = metadata.get("title", "Unknown")
        artist = metadata.get("artist", "Unknown")
        thumbnail_url = metadata.get("thumbnail_url", "")
        video_id = metadata.get("video_id", "local")

        # Try to get duration from database
        dur_ms = 0
        try:
            from doremi.db.repository import DownloadRepository
            dl_repo = DownloadRepository()
            download = await dl_repo.get_download(video_id)
            if download and download.duration_ms:
                dur_ms = download.duration_ms
        except Exception as e:
            logger.debug(f"Could not get duration from DB: {e}")

        # Set queue to a single local item so queue controls and state work properly
        item = QueueItem(
            video_id=video_id,
            title=title,
            artist=artist,
            album="Local",
            duration_ms=dur_ms,
            thumbnail_url=thumbnail_url,
            is_local=True,
            local_path=path
        )
        self.queue.set_queue([item], 0)
        self._update_queue_panel()

        self.run_async(self._play_current())

    def _play_local_playlist(self, tracks_metadata: list[dict], start_index: int = 0) -> None:
        queue_items = []
        for m in tracks_metadata:
            item = QueueItem(
                video_id=m.get("video_id", "local"),
                title=m.get("title", "Unknown"),
                artist=m.get("artist", "Unknown"),
                album=m.get("album", "Local"),
                duration_ms=m.get("duration_ms", 0),
                thumbnail_url=m.get("thumbnail_url", ""),
                is_local=True,
                local_path=m.get("file_path", "")
            )
            queue_items.append(item)

        if queue_items:
            self.queue.set_queue(queue_items, start_index)
            self._update_queue_panel()
            self.run_async(self._play_current())

    def _play_local_wrapper(self, path: str, metadata: dict) -> None:
        """Wrapper to run _play_local as async task from sync callback."""
        self.run_async(self._play_local(path, metadata))

    def _on_play_pause(self) -> None:
        self.run_async(self._toggle_play_pause())

    async def _toggle_play_pause(self) -> None:
        from doremi.audio.player import PlayerState
        is_vlc_playing = False
        try:
            is_vlc_playing = self.player._player.is_playing()
        except Exception as e:
            logger.debug(f"Could not query VLC playing state: {e}")

        pending = getattr(self, "_play_task", None)
        if (pending and not pending.done()) or self.player.status.state in (PlayerState.PLAYING, PlayerState.LOADING) or is_vlc_playing:
            self._current_play_id += 1
            if pending and not pending.done():
                self._restart_after_pause = True
                pending.cancel()
            self.crossfade_manager.cancel()
            await self.player.pause()
        else:
            if getattr(self, "_restart_after_pause", False):
                self._restart_after_pause = False
                await self._play_current()
            else:
                await self.player.resume()

    def _on_next(self) -> None:
        self.run_async(self._advance_queue(manual=True))

    def _on_prev(self) -> None:
        self.run_async(self._go_prev())

    async def _go_prev(self) -> None:
        if self.player.status.position_ms > 3000:
            await self.player.seek(0)
        else:
            item = self.queue.go_back()
            if item:
                await self._play_current()

    def _on_seek(self, position_ms: int) -> None:
        if self.mpris:
            self.mpris.emit_seeked(position_ms)
        self.run_async(self.player.seek(position_ms))

    def _update_queue_panel(self) -> None:
        """Update the queue tab in the NowPlayingScreen."""
        self.run_async(self._update_queue_panel_async())

    async def _update_queue_panel_async(self) -> None:
        if hasattr(self, 'now_playing_screen') and hasattr(self.now_playing_screen, 'queue_tab'):
            from doremi.db.repository import SongRepository
            repo = SongRepository()
            liked_ids = await repo.get_liked_video_ids()
            self.now_playing_screen.queue_tab.set_queue(self.queue.items, liked_ids)

    def _play_queue_item(self, index: int) -> None:
        item = self.queue.jump_to(index)
        if item:
            self._update_queue_panel()
            self.run_async(self._play_current())

    def _on_queue_move_requested(self, from_index: int, to_index: int) -> None:
        self.queue.move_item(from_index, to_index)
        self._update_queue_panel()

    def _show_full_player(self) -> None:
        now_playing_index = self.main_window.ROUTES.get("now_playing", 8)
        if self.main_window.stack.currentIndex() == now_playing_index:
            # Already on NowPlaying — go back
            self._go_back()
        else:
            self.main_window._navigate_to("now_playing")

    def _go_back(self) -> None:
        """Navigate back to the previous screen in the history stack."""
        if hasattr(self.main_window, '_current_nav_task') and self.main_window._current_nav_task and not self.main_window._current_nav_task.done():
            self.main_window._current_nav_task.cancel()

        if self.main_window._nav_history:
            prev_index = self.main_window._nav_history.pop()
            if hasattr(self.main_window.stack, "setCurrentIndexAnimated"):
                self.main_window.stack.setCurrentIndexAnimated(prev_index)
            else:
                self.main_window.stack.setCurrentIndex(prev_index)
            # _go_back evita NavigationController.set_stack_index; restaura el
            # mini-player explícitamente sólo si ya había una pista activa.
            mini_player = getattr(self.main_window, "mini_player", None)
            if mini_player is not None and getattr(mini_player, "_is_visible", False):
                mini_player.show()
                from doremi.ui.theme_bridge import theme_bridge
                theme_bridge().set_mini_player_visible(True)
                self.main_window._position_mini_player()
                mini_player.raise_()
            self._update_expand_icon()
        else:
            # Fallback to home
            self.main_window._navigate_to("home")

    def _update_expand_icon(self) -> None:
        """Toggle the mini player expand icon between up/down chevron."""
        from doremi.ui.design.icons import Icon
        if hasattr(self, 'mini_player') and hasattr(self.mini_player, 'btn_expand'):
            now_playing_index = self.main_window.ROUTES.get("now_playing", 8)
            if self.main_window.stack.currentIndex() == now_playing_index:
                self.mini_player.btn_expand.setText(Icon.get("expand_more"))
            else:
                self.mini_player.btn_expand.setText(Icon.get("expand_less"))
