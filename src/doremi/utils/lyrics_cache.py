import os
import hashlib
from doremi.config.paths import AppDirs
from loguru import logger


class LyricsCache:
    """Manages the local cache for downloaded lyrics."""

    @classmethod
    def _get_filename(cls, title: str, artist: str) -> str:
        # Create a consistent hash based on title and artist
        key = f"{title}_{artist}".lower().encode("utf-8")
        return hashlib.md5(key).hexdigest() + ".lrc"

    @classmethod
    def get(cls, title: str, artist: str) -> str | None:
        """Retrieves lyrics from cache if available."""
        if not title or not artist:
            return None
            
        filename = cls._get_filename(title, artist)
        filepath = AppDirs.lyrics_cache / filename
        
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                logger.debug(f"Loaded lyrics from cache for: {title} - {artist}")
                return content
            except Exception as e:
                logger.error(f"Error reading lyrics cache for {title}: {e}")
        return None

    @classmethod
    def save(cls, title: str, artist: str, lyrics: str) -> None:
        """Saves lyrics to the local cache."""
        if not title or not artist or not lyrics:
            return
            
        filename = cls._get_filename(title, artist)
        filepath = AppDirs.lyrics_cache / filename
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(lyrics)
            logger.debug(f"Saved lyrics to cache for: {title} - {artist}")
        except Exception as e:
            logger.error(f"Error writing lyrics cache for {title}: {e}")

    @classmethod
    def clear(cls) -> None:
        """Clears all cached lyrics."""
        try:
            for filepath in AppDirs.lyrics_cache.glob("*.lrc"):
                filepath.unlink()
            logger.info("Cleared lyrics cache")
        except Exception as e:
            logger.error(f"Error clearing lyrics cache: {e}")
