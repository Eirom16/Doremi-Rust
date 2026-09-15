import asyncio
from concurrent.futures import ThreadPoolExecutor
import yt_dlp
from loguru import logger


class StreamExtractor:
    """Fast stream extractor with format selection."""

    def __init__(self, settings=None):
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="stream")

    @staticmethod
    def _load_cookie_opts() -> dict:
        """Load auth cookies into yt-dlp options if available."""
        from doremi.config.paths import AppDirs
        cookie_file = AppDirs.config / "headers_auth.json"
        opts = {}
        if cookie_file.exists():
            try:
                import json
                with open(cookie_file) as f:
                    data = json.load(f)
                    cookie_str = data.get('cookie', '')
                    if cookie_str:
                        opts['headers'] = {
                            'Cookie': cookie_str,
                            'User-Agent': data.get('user-agent', '')
                        }
            except Exception as e:
                logger.warning(f"Failed to load cookies for yt-dlp: {e}")
        return opts

    async def get_stream_info(self, video_id: str) -> dict:
        """Get stream info - prefer stable formats."""

        def _extract():
            opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'nocheckcertificate': True,
                **StreamExtractor._load_cookie_opts(),
            }
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(
                        f"https://www.youtube.com/watch?v={video_id}",
                        download=False
                    )
                    if not info:
                        return {"url": "", "format": "unknown", "quality": 0, "duration": 0}
                    
                    formats = info.get('formats', [])
                    best_url = ""
                    best_ext = "m4a"
                    best_abr = 0
                    best_duration = info.get('duration', 0)
                    best_format_note = ""
                    
                    for fmt in formats:
                        url = fmt.get('url', '')
                        if not url or not url.startswith('http'):
                            continue
                        if fmt.get('vcodec', 'none') != 'none':
                            continue
                        
                        ext = fmt.get('ext', 'm4a')
                        abr = fmt.get('abr', 0) or 0
                        
                        if ext in ['m4a', 'mp4'] and abr >= best_abr:
                            best_url = url
                            best_ext = ext
                            best_abr = abr
                            best_format_note = fmt.get('format_note', '')
                        elif not best_url and ext == 'webm':
                            best_url = url
                            best_ext = ext
                            best_abr = abr
                    
                    return {
                        "url": best_url,
                        "format": best_ext,
                        "quality": int(best_abr),
                        "duration": best_duration,
                        "format_note": best_format_note,
                        "thumbnail": info.get('thumbnail', '')
                    }
            except Exception as e:
                logger.error(f"Stream extraction error: {e}")
                return {"url": "", "format": "unknown", "quality": 0, "duration": 0}

        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(self._executor, _extract)
            if result.get('url'):
                logger.debug(f"Stream extracted: {result.get('format')} @ {result.get('quality')}kbps")
            return result
        except Exception as e:
            logger.error(f"Stream extraction error: {e}")
            return {"url": "", "format": "unknown", "quality": 0, "duration": 0}

    async def get_alternative_stream(self, video_id: str) -> str:
        """Get alternative stream format - try different format."""

        def _extract_alt():
            opts = {
                'format': 'worstaudio/worst',
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                **StreamExtractor._load_cookie_opts(),
            }
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(
                        f"https://www.youtube.com/watch?v={video_id}",
                        download=False
                    )
                    if not info:
                        return ""
                    
                    for fmt in info.get('formats', []):
                        url = fmt.get('url', '')
                        if url and url.startswith('http'):
                            return url
                    return ""
            except Exception as e:
                logger.error(f"Alt stream error: {e}")
                return ""

        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(self._executor, _extract_alt)
        except Exception as e:
            logger.error(f"Alt stream executor error: {e}")
            return ""

    async def get_download_url_and_info(self, video_id: str) -> dict:
        return await self.get_stream_info(video_id)
