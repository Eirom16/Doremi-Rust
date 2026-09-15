import asyncio
from loguru import logger
from doremi.db.repository import get_session, Song
from sqlalchemy import select
from doremi.utils.lyrics_cache import LyricsCache
from doremi.api.lyrics import LyricsClient

class LyricsPrefetcher:
    """Background service that pre-fetches lyrics for the user's most played songs."""

    def __init__(self):
        self._lyrics_client = LyricsClient()

    async def run(self):
        """Starts the background pre-fetch process."""
        try:
            logger.info("Starting background lyrics prefetcher for most played songs...")
            
            # Wait a little bit after startup to not block initial loading
            await asyncio.sleep(10)

            # Get the top 50 most played songs
            async with get_session() as session:
                result = await session.execute(
                    select(Song).where(Song.play_count > 0).order_by(Song.play_count.desc()).limit(50)
                )
                top_songs = result.scalars().all()

            if not top_songs:
                logger.info("No played songs found for lyrics prefetching.")
                return

            fetched_count = 0
            for song in top_songs:
                if not song.title or not song.artist:
                    continue

                # Check if it's already in cache
                cached_lyrics = LyricsCache.get(song.title, song.artist)
                if cached_lyrics:
                    continue  # Already cached

                logger.debug(f"Prefetching lyrics for: {song.title} - {song.artist}")
                lyrics = await self._lyrics_client.get_lyrics(song.title, song.artist, song.album)
                
                if lyrics:
                    LyricsCache.save(song.title, song.artist, str(lyrics))
                    fetched_count += 1
                
                # Sleep between requests to avoid rate limits
                await asyncio.sleep(2)

            logger.info(f"Lyrics prefetcher completed. Fetched {fetched_count} new lyrics.")

        except Exception as e:
            logger.error(f"Error in lyrics prefetcher: {e}")
