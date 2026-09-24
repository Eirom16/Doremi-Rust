import asyncio
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor
import yt_dlp
from loguru import logger
from doremi.config.settings import AppSettings
from doremi.config.paths import AppDirs

class YouTubeMusicClient:
    """Hybrid YouTube client - uses ytmusicapi for browsing, yt-dlp as fallback."""

    def __init__(self, settings: AppSettings):
        self.settings = settings
        self._executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="ytm")
        self._stream_cache = {}
        self._search_cache = {}
        self._search_time = {}
        self._playlist_cache = {}
        self._playlist_time = {}
        self._album_cache = {}
        self._album_time = {}
        self._podcast_cache = {}
        self._podcast_time = {}
        self._artist_cache = {}
        self._artist_time = {}
        self._ytmusicapi = None          # authenticated instance (for library)
        self._ytmusicapi_public = None   # unauthenticated instance (for search/home/charts)
        self._is_authenticated = False
        self._init_public_client()
        self._load_auth_session()

    def _init_public_client(self):
        """Initialize an unauthenticated ytmusicapi for public operations."""
        try:
            from ytmusicapi import YTMusic
            self._ytmusicapi_public = YTMusic()
            logger.debug("ytmusicapi public client initialized")
        except Exception as e:
            logger.warning(f"Failed to init public ytmusicapi: {e}")

    def _load_auth_session(self):
        """Load auth session securely using SecureStorage."""
        from doremi.utils.secure_storage import SecureStorage
        
        path, temp_file = SecureStorage.make_secure_temp_auth_file()
        if path:
            try:
                self._setup_ytmusicapi(path)
                logger.info("ytmusicapi initialized securely from keyring/secure credentials")
            except Exception as e:
                logger.error(f"Failed to load browser cookies: {e}")
                self._is_authenticated = False
            finally:
                if temp_file and temp_file.exists():
                    try:
                        temp_file.unlink()
                    except Exception as ex:
                        logger.warning(f"Could not delete secure temp auth file: {ex}")
        else:
            self._is_authenticated = False

    def _setup_ytmusicapi(self, auth_path: str):
        """Setup ytmusicapi with the given auth file."""
        try:
            from ytmusicapi import YTMusic
            
            # Browser auth (cookie)
            self._ytmusicapi = YTMusic(auth=auth_path)
                
            self._is_authenticated = True
        except Exception as e:
            logger.error(f"Failed to setup ytmusicapi: {e}")
            self._is_authenticated = False

    @property
    def _public(self):
        """Returns the unauthenticated ytmusicapi instance for public queries.
        Always use the public client for search/home/charts since
        Desktop OAuth credentials cause HTTP 400 with ytmusicapi's internal API."""
        return self._ytmusicapi_public

    @property
    def is_authenticated(self) -> bool:
        return self._is_authenticated

    def load_existing_auth(self) -> bool:
        return self._is_authenticated

    def reload_auth(self):
        """Reload the ytmusicapi instance with new credentials."""
        self._load_auth_session()

    def get_cached_stream_url(self, video_id: str) -> str:
        return self._stream_cache.get(video_id, "")

    def _retryable_status_code(self, exc: Exception) -> int | None:
        status = getattr(exc, "status_code", None)
        if status is None:
            response = getattr(exc, "response", None)
            status = getattr(response, "status_code", None)
        if status is None:
            return None
        try:
            return int(status)
        except (TypeError, ValueError):
            return None

    def _is_retryable_error(self, exc: Exception) -> bool:
        status = self._retryable_status_code(exc)
        if status == 429 or status in {500, 502, 503, 504}:
            return True

        message = str(exc).lower()
        retryable_markers = (
            "429",
            "too many requests",
            "rate limit",
            "ratelimit",
            "temporarily unavailable",
            "internal server error",
            "bad gateway",
            "service unavailable",
            "gateway timeout",
            "http error 500",
            "http error 502",
            "http error 503",
            "http error 504",
        )
        return any(marker in message for marker in retryable_markers)

    async def _run(self, func, *, retries: int = 3, base_delay: float = 0.75):
        last_exc = None
        for attempt in range(retries):
            try:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.get_event_loop()
                return await loop.run_in_executor(self._executor, func)
            except Exception as exc:
                last_exc = exc
                if attempt >= retries - 1 or not self._is_retryable_error(exc):
                    raise

                delay = base_delay * (2 ** attempt) + random.uniform(0.0, 0.35)
                logger.warning(
                    "YouTube Music transient failure; retrying in "
                    f"{delay:.2f}s ({attempt + 1}/{retries}): {exc}"
                )
                await asyncio.sleep(delay)

        raise last_exc



    async def search(self, query: str, filter: str = None, limit: int = 20) -> list:
        """Search using ytmusicapi (public, no auth needed), fallback to yt-dlp."""
        query_lower = query.lower().strip()
        cache_key = f"{query_lower}:{filter}:{limit}"

        if cache_key in self._search_cache:
            age = time.time() - self._search_time.get(cache_key, 0)
            if age < 300:
                logger.debug(f"Using cached search for '{query_lower}'")
                return self._search_cache[cache_key]

        # Try ytmusicapi first (richer results with types)
        client = self._ytmusicapi if (self._is_authenticated and self._ytmusicapi) else self._public
        if client:
            def _ytm_search():
                return client.search(query_lower, filter=filter, limit=limit)

            try:
                results = await self._run(_ytm_search)
                if results:
                    self._search_cache[cache_key] = results
                    self._search_time[cache_key] = time.time()
                    for track in results[:3]:
                        vid = track.get('videoId')
                        if vid:
                            asyncio.create_task(self._prefetch_stream(vid))
                    return results
            except Exception as e:
                logger.warning(f"ytmusicapi search failed: {e}")

        # yt-dlp sólo puede reconstruir resultados de canciones/vídeos; usarlo
        # para colecciones produciría tarjetas sin browseId y tipos incorrectos.
        if filter not in (None, "songs", "videos"):
            return []

        # Fallback to yt-dlp
        def _ytdlp_search():
            opts = {
                'quiet': True,
                'no_warnings': True,
                'default_search': f'ytsearch{limit}',
                'skip_download': True,
                'ignoreerrors': True,
            }
            ydl = yt_dlp.YoutubeDL(opts)
            results = ydl.extract_info(query_lower, download=False)
            if not results or not results.get('entries'):
                return []
            tracks = []
            for entry in results['entries']:
                if not entry:
                    continue
                video_id = entry.get('id', '')
                if video_id and entry.get('title'):
                    thumbnails = entry.get('thumbnails', [])
                    thumb_url = thumbnails[-1].get('url', '') if thumbnails else ''
                    tracks.append({
                        'videoId': video_id,
                        'title': entry.get('title', 'Unknown'),
                        'artists': [{'name': entry.get('uploader', 'Unknown')}],
                        'thumbnails': [{'url': thumb_url}] if thumb_url else [],
                        'duration': entry.get('duration', 0),
                        'resultType': 'song',
                    })
            return tracks

        try:
            tracks = await self._run(_ytdlp_search)
            if tracks:
                self._search_cache[cache_key] = tracks
                self._search_time[cache_key] = time.time()
            return tracks
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

    async def _prefetch_stream(self, video_id: str):
        if video_id in self._stream_cache:
            return
        try:
            from doremi.api.stream_extractor import StreamExtractor
            extractor = StreamExtractor(self.settings)
            result = await extractor.get_stream_info(video_id)
            url = result.get("url", "")
            if url:
                self._stream_cache[video_id] = url
                logger.debug(f"Prefetched stream for {video_id}")
        except Exception as e:
            logger.debug(f"Stream prefetch skipped for {video_id}: {e}")

    async def get_stream_url(self, video_id: str) -> str:
        if video_id in self._stream_cache:
            return self._stream_cache[video_id]
        try:
            from doremi.api.stream_extractor import StreamExtractor
            extractor = StreamExtractor(self.settings)
            result = await extractor.get_stream_info(video_id)
            url = result.get("url", "")
            if url:
                self._stream_cache[video_id] = url
            return url
        except Exception as e:
            logger.warning(f"Could not extract stream URL for {video_id}: {e}")
            return ""

    async def get_library_songs(self, limit: int = 25) -> dict:
        """Get user's liked songs - requires auth."""
        if not self._is_authenticated or not self._ytmusicapi:
            return {'tracks': []}

        def _get_liked():
            # ytmusicapi already returns {'tracks': [...], ...}
            return self._ytmusicapi.get_liked_songs(limit=limit)

        try:
            return await self._run(_get_liked)
        except Exception as e:
            logger.error(f"Library songs error: {e}")
            return {'tracks': []}

    async def get_library_playlists(self) -> list:
        """Get user's playlists - requires auth."""
        if not self._is_authenticated or not self._ytmusicapi:
            return []

        def _get_playlists():
            return self._ytmusicapi.get_library_playlists()

        try:
            return await self._run(_get_playlists)
        except Exception as e:
            logger.error(f"get_playlists error: {e}")
            return []

    async def get_library_albums(self) -> list:
        """Get user's albums - requires auth."""
        if not self._is_authenticated or not self._ytmusicapi:
            return []

        def _get_albums():
            return self._ytmusicapi.get_library_albums()

        try:
            return await self._run(_get_albums)
        except Exception as e:
            logger.error(f"get_albums error: {e}")
            return []

    async def get_library_artists(self, limit: int = 20) -> list:
        """Get user's subscribed artists - requires auth."""
        if not self._is_authenticated or not self._ytmusicapi:
            return []

        def _get_artists():
            # Use get_library_artists instead of subscriptions, because subscriptions can hang
            # for users with thousands of Youtube channels, and get_library_artists is faster.
            try:
                return self._ytmusicapi.get_library_artists(limit=limit)
            except Exception as e:
                if self._is_retryable_error(e):
                    raise
                return self._ytmusicapi.get_library_subscriptions(limit=limit)

        try:
            return await self._run(_get_artists)
        except Exception as e:
            logger.error(f"get_library_artists error: {e}")
            return []

    async def get_liked_songs(self, limit: int = 25) -> dict:
        """Get liked songs - wrapper for library."""
        return await self.get_library_songs(limit)

    async def get_home(self, limit: int = 10) -> dict:
        """Get home recommendations - uses auth client if available."""
        client = self._ytmusicapi if self._is_authenticated else self._public
        if not client:
            return {'contents': []}

        def _get_home():
            return client.get_home(limit=limit)

        try:
            return await self._run(_get_home)
        except Exception as e:
            logger.error(f"get_home error: {e}")
            return {'contents': []}

    async def get_explore(self) -> dict:
        """Get explore data - uses auth client if available."""
        client = self._ytmusicapi if self._is_authenticated else self._public
        if not client:
            return {'moodCategories': []}

        def _get_explore():
            return client.get_explore()

        try:
            return await self._run(_get_explore)
        except Exception as e:
            logger.error(f"get_explore error: {e}")
            return {'moodCategories': []}

    async def get_charts(self, country: str = "ZZ") -> dict:
        """Get charts - uses auth client if available."""
        client = self._ytmusicapi if self._is_authenticated else self._public
        if not client:
            return {'items': []}

        def _get_charts():
            return client.get_charts(country=country)

        try:
            return await self._run(_get_charts)
        except Exception as e:
            logger.error(f"get_charts error: {e}")
            return {'items': []}

    async def get_playlist(self, playlist_id: str) -> dict:
        """Get playlist details - uses authenticated client if available, falls back to public."""
        if not playlist_id:
            return {}

        # Strip the "VL" prefix from the browse ID if present, as ytmusicapi
        # expects raw playlist IDs (e.g. starting with "PL" or "RD").
        if playlist_id.startswith("VL"):
            playlist_id = playlist_id[2:]

        if playlist_id in self._playlist_cache:
            age = time.time() - self._playlist_time.get(playlist_id, 0)
            if age < 300:
                logger.debug(f"Using cached playlist for '{playlist_id}'")
                return self._playlist_cache[playlist_id]

        client = self._ytmusicapi if (self._is_authenticated and self._ytmusicapi) else self._public
        if not client:
            return {}

        def _get_playlist():
            try:
                return client.get_playlist(playlist_id)
            except Exception as e:
                if self._is_retryable_error(e):
                    raise
                logger.error(f"get_playlist error: {e}")
                # Fall back to public client if the authenticated one failed
                if client != self._public and self._public:
                    try:
                        logger.info("Falling back to public client for get_playlist...")
                        return self._public.get_playlist(playlist_id)
                    except Exception as e2:
                        logger.error(f"get_playlist public fallback error: {e2}")
                return {}

        try:
            res = await self._run(_get_playlist)
            if res and (res.get("tracks") or "title" in res):
                self._playlist_cache[playlist_id] = res
                self._playlist_time[playlist_id] = time.time()
            return res
        except Exception as e:
            logger.error(f"get_playlist error: {e}")
            return {}

    async def get_album(self, browse_id: str) -> dict:
        """Get album details - uses public client."""
        if not browse_id:
            return {}

        if browse_id in self._album_cache:
            age = time.time() - self._album_time.get(browse_id, 0)
            if age < 300:
                logger.debug(f"Using cached album for '{browse_id}'")
                return self._album_cache[browse_id]

        client = self._public
        if not client:
            return {}

        def _get_album():
            return client.get_album(browse_id)

        try:
            res = await self._run(_get_album)
            if res and (res.get("tracks") or "title" in res):
                self._album_cache[browse_id] = res
                self._album_time[browse_id] = time.time()
            return res
        except Exception as e:
            logger.error(f"get_album error: {e}")
            return {}

    async def get_podcast(self, playlist_id: str) -> dict:
        """Obtiene los metadatos y episodios de un podcast público."""
        if not playlist_id:
            return {}

        if playlist_id in self._podcast_cache:
            age = time.time() - self._podcast_time.get(playlist_id, 0)
            if age < 300:
                logger.debug(f"Using cached podcast for '{playlist_id}'")
                return self._podcast_cache[playlist_id]

        client = self._public
        if not client:
            return {}

        try:
            result = await self._run(lambda: client.get_podcast(playlist_id))
            if result and (result.get("episodes") or "title" in result):
                self._podcast_cache[playlist_id] = result
                self._podcast_time[playlist_id] = time.time()
            return result
        except Exception as e:
            logger.error(f"get_podcast error: {e}")
            return {}

    async def get_artist(self, channel_id: str) -> dict:
        """Get artist details - uses public client."""
        if not channel_id:
            return {}

        if channel_id in self._artist_cache:
            age = time.time() - self._artist_time.get(channel_id, 0)
            if age < 300:
                logger.debug(f"Using cached artist for '{channel_id}'")
                return self._artist_cache[channel_id]

        client = self._public
        if not client:
            return {}

        def _get_artist():
            return client.get_artist(channel_id)

        try:
            res = await self._run(_get_artist)
            if res and (res.get("songs") or "name" in res):
                self._artist_cache[channel_id] = res
                self._artist_time[channel_id] = time.time()
            return res
        except Exception as e:
            logger.error(f"get_artist error: {e}")
            return {}

    async def get_watch_playlist(self, video_id: str = None, limit: int = 25) -> dict:
        """Get watch playlist - uses public or authenticated client."""
        client = self._ytmusicapi or self._ytmusicapi_public
        if not client:
            return {'tracks': []}

        # The watch playlist endpoint currently fails for every request (ytmusicapi
        # KeyError 'endpoint'). Cache the failure so we don't spam ERROR logs or
        # repeat the failed network round-trip on every track change.
        if getattr(self, "_watch_disabled_until", 0) > time.time():
            return {'tracks': []}

        def _get_watch():
            return client.get_watch_playlist(videoId=video_id, limit=limit)

        try:
            return await self._run(_get_watch)
        except Exception as e:
            logger.debug(f"get_watch_playlist error (suppressing retries for 60s): {e}")
            self._watch_disabled_until = time.time() + 60
            return {'tracks': []}

    async def get_history(self) -> list:
        """Get user's listening history - requires auth."""
        if not self._is_authenticated or not self._ytmusicapi:
            return []

        def _get_history():
            return self._ytmusicapi.get_history()

        try:
            return await self._run(_get_history)
        except Exception as e:
            logger.error(f"get_history error: {e}")
            return []

    async def remove_history_items(self, feedback_tokens: list) -> bool:
        """Remove items from user's listening history."""
        if not self._is_authenticated or not self._ytmusicapi:
            return False

        def _remove():
            # remove_history_items returns a dict or list usually
            self._ytmusicapi.remove_history_items(feedback_tokens)
            return True

        try:
            return await self._run(_remove)
        except Exception as e:
            logger.error(f"remove_history_items error: {e}")
            return False
    async def create_playlist(self, title: str, description: str = "") -> str:
        """Create a playlist - requires auth."""
        if not self._is_authenticated or not self._ytmusicapi:
            return ""

        self.invalidate_playlist_cache()

        def _create():
            # Returns the playlistId as a string
            return self._ytmusicapi.create_playlist(title, description)

        try:
            return await self._run(_create)
        except Exception as e:
            logger.error(f"create_playlist error: {e}")
            return ""

    async def add_playlist_items(self, playlist_id: str, video_ids: list) -> dict:
        """Add songs to a playlist - requires auth."""
        if not self._is_authenticated or not self._ytmusicapi:
            return {}

        self.invalidate_playlist_cache(playlist_id)

        def _add():
            return self._ytmusicapi.add_playlist_items(playlist_id, video_ids)

        try:
            return await self._run(_add)
        except Exception as e:
            logger.error(f"add_playlist_items error: {e}")
            return {}

    async def remove_playlist_items(self, playlist_id: str, videos: list) -> dict:
        """Remove songs from a playlist - requires auth.
        'videos' must be a list of dicts with 'videoId' and 'setVideoId'
        """
        if not self._is_authenticated or not self._ytmusicapi:
            return {}

        self.invalidate_playlist_cache(playlist_id)

        def _remove_items():
            return self._ytmusicapi.remove_playlist_items(playlist_id, videos)

        try:
            return await self._run(_remove_items)
        except Exception as e:
            logger.error(f"remove_playlist_items error: {e}")
            return {}

    async def delete_playlist(self, playlist_id: str) -> bool:
        """Delete a playlist - requires auth."""
        if not self._is_authenticated or not self._ytmusicapi:
            return False

        self.invalidate_playlist_cache()

        def _delete():
            self._ytmusicapi.delete_playlist(playlist_id)
            return True

        try:
            return await self._run(_delete)
        except Exception as e:
            logger.error(f"delete_playlist error: {e}")
            return False

    async def rename_playlist(self, playlist_id: str, new_title: str, new_description: str = None) -> bool:
        """Rename a playlist - requires auth."""
        if not self._is_authenticated or not self._ytmusicapi:
            return False

        self.invalidate_playlist_cache(playlist_id)

        def _rename():
            kwargs = {"title": new_title}
            if new_description is not None:
                kwargs["description"] = new_description
            return self._ytmusicapi.edit_playlist(playlist_id, **kwargs)

        try:
            res = await self._run(_rename)
            return bool(res)
        except Exception as e:
            logger.error(f"rename_playlist error: {e}")
            return False

    async def rate_song(self, video_id: str, rating: str = "LIKE") -> bool:
        """Rate a song (LIKE, DISLIKE, INDIFFERENT) - requires auth."""
        if not self._is_authenticated or not self._ytmusicapi:
            return False

        def _rate():
            self._ytmusicapi.rate_song(video_id, rating)
            return True

        try:
            return await self._run(_rate)
        except Exception as e:
            logger.error(f"rate_song error: {e}")
            return False

    def logout(self) -> None:
        """Clear auth session and reset auth state securely."""
        from doremi.utils.secure_storage import SecureStorage
        SecureStorage.delete_youtube_headers()
        self._ytmusicapi = None
        self._is_authenticated = False
        self.invalidate_playlist_cache()
        self.invalidate_album_cache()
        self.invalidate_artist_cache()
        logger.info("Logged out of YouTube")

    def invalidate_playlist_cache(self, playlist_id: str = None):
        """Invalidate the cache for a specific playlist or all playlists."""
        if playlist_id:
            if playlist_id.startswith("VL"):
                playlist_id = playlist_id[2:]
            self._playlist_cache.pop(playlist_id, None)
            self._playlist_time.pop(playlist_id, None)
            logger.debug(f"Invalidated cache for playlist '{playlist_id}'")
        else:
            self._playlist_cache.clear()
            self._playlist_time.clear()
            logger.debug("Cleared all playlist cache")

    def invalidate_album_cache(self, browse_id: str = None):
        """Invalidate the cache for a specific album or all albums."""
        if browse_id:
            self._album_cache.pop(browse_id, None)
            self._album_time.pop(browse_id, None)
            logger.debug(f"Invalidated cache for album '{browse_id}'")
        else:
            self._album_cache.clear()
            self._album_time.clear()
            logger.debug("Cleared all album cache")

    def invalidate_artist_cache(self, channel_id: str = None):
        """Invalidate the cache for a specific artist or all artists."""
        if channel_id:
            self._artist_cache.pop(channel_id, None)
            self._artist_time.pop(channel_id, None)
            logger.debug(f"Invalidated cache for artist '{channel_id}'")
        else:
            self._artist_cache.clear()
            self._artist_time.clear()
            logger.debug("Cleared all artist cache")

    async def search_suggestions(self, query: str) -> dict:
        """Get rich search suggestions - uses search API for top results."""
        if not self._public or not query:
            return {}

        def _get_rich_suggestions():
            # Search without filter to get a mix of top results
            results = self._public.search(query, limit=5)
            # Group by category
            grouped = {
                'songs': [r for r in results if r['resultType'] in ('song', 'video')][:3],
                'albums': [r for r in results if r['resultType'] == 'album'][:2],
                'artists': [r for r in results if r['resultType'] == 'artist'][:2],
                'text': []
            }
            # Text suggestions are optional; keep rich result suggestions if this call fails.
            try:
                grouped['text'] = self._public.get_search_suggestions(query)[:5]
            except Exception as e:
                if self._is_retryable_error(e):
                    raise
                logger.debug(f"Search text suggestions unavailable: {e}")
            return grouped

        try:
            return await self._run(_get_rich_suggestions)
        except Exception as e:
            logger.error(f"Rich suggestions error: {e}")
            return {}
