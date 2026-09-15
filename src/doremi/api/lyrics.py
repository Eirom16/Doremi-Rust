import asyncio
import syncedlyrics
from loguru import logger


class LyricsClient:

    def __init__(self):
        pass

    def _clean_metadata(self, title: str, artist: str) -> tuple[str, str]:
        import re
        t = title
        # Remove common video title suffixes
        t = re.sub(r'\s*[\(\[][Oo]fficial\s+[Vv]ideo[\)\]]', '', t)
        t = re.sub(r'\s*[\(\[][Oo]fficial\s+[Aa]udio[\)\]]', '', t)
        t = re.sub(r'\s*[\(\[][Oo]fficial\s+[Mm]usic\s+[Vv]ideo[\)\]]', '', t)
        t = re.sub(r'\s*[\(\[][Oo]fficial\s+[Ll]yric\s+[Vv]ideo[\)\]]', '', t)
        t = re.sub(r'\s*[\(\[][Ll]yric\s+[Vv]ideo[\)\]]', '', t)
        t = re.sub(r'\s*[\(\[][Vv]ideo\s+[Cc]lip[\)\]]', '', t)
        t = re.sub(r'\s*[\(\[][Hh][Dd][\)\]]', '', t)
        t = re.sub(r'\s*[\(\[][4]k[\)\]]', '', t)
        
        # Remove "feat." or "ft." in title for simpler search
        t = re.sub(r'\s*[\(\[][Ff]eat\.\s+.*?[\)\]]', '', t)
        t = re.sub(r'\s*[\(\[][Ff]t\.\s+.*?[\)\]]', '', t)
        
        # Clean artist
        a = artist
        a = re.sub(r'\s*-\s*[Tt]opic', '', a)
        
        return t.strip(), a.strip()

    def _sync_search(self, title: str, artist: str, album: str = "") -> str | None:
        try:
            clean_title, clean_artist = self._clean_metadata(title, artist)
            logger.info(f"Searching lyrics for cleaned: '{clean_title}' by '{clean_artist}'")
            result = syncedlyrics.search(
                f"{clean_title} {clean_artist}",
                plain_only=False,
                providers=["lrclib", "netease"]
            )
            return result
        except Exception as e:
            logger.debug(f"Lyrics search failed: {e}")
            return None

    async def get_lyrics(
        self, title: str, artist: str, album: str = ""
    ) -> str | None:
        try:
            # Use asyncio.to_thread instead of loop.run_in_executor to avoid qasync cancellation SIGSEGV bugs
            return await asyncio.wait_for(
                asyncio.to_thread(self._sync_search, title, artist, album),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            logger.warning(f"Lyrics search timed out for {title} - {artist}")
            return None

    async def get_plain_lyrics(self, title: str, artist: str) -> str | None:
        try:
            # Use asyncio.to_thread instead of loop.run_in_executor to avoid qasync cancellation SIGSEGV bugs
            return await asyncio.wait_for(
                asyncio.to_thread(self._sync_search, title, artist),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            logger.warning(f"Plain lyrics search timed out for {title} - {artist}")
            return None
