import asyncio
from concurrent.futures import ThreadPoolExecutor
import yt_dlp
from loguru import logger


class StreamExtractor:
    """Fast stream extractor with format selection."""

    def __init__(self, settings=None):
        # The settings object is shared with the runtime settings controller,
        # so changes saved by the UI are observed by subsequent extractions.
        self.settings = settings
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="stream")
        self._closed = False

    def close(self) -> None:
        """Release worker threads when this extractor is no longer needed."""
        if not self._closed:
            self._closed = True
            self._executor.shutdown(wait=False, cancel_futures=True)

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def _network_options(self) -> dict:
        """Return the yt-dlp network policy configured by the user."""
        network = getattr(self.settings, "network", None)
        proxy = str(getattr(network, "proxy_url", "") or "").strip()
        return {"proxy": proxy} if proxy else {}

    def _quality_ceiling(self) -> int | None:
        """Map the persisted quality preference to an audio bitrate ceiling.

        ``best`` and unknown values deliberately retain yt-dlp's best audio
        behaviour.  The lower presets are useful for metered connections and
        avoid silently returning a higher bitrate than the setting promises.
        """
        network = getattr(self.settings, "network", None)
        quality = str(getattr(network, "stream_quality", "best") or "best").lower()
        return {"low": 64, "medium": 128, "high": 192}.get(quality)

    @staticmethod
    def _load_cookie_opts() -> dict:
        """Load auth cookies into yt-dlp options if available.

        Las credenciales viven en el llavero del sistema (con fallback al
        archivo legacy); sin ellas YouTube rechaza gran parte de los formatos.
        """
        try:
            from doremi.utils.secure_storage import SecureStorage
            data = SecureStorage.load_youtube_headers() or {}
        except Exception as e:
            logger.warning(f"Failed to load cookies for yt-dlp: {e}")
            return {}
        cookie_str = data.get('cookie', '')
        if not cookie_str:
            return {}
        return {
            'headers': {
                'Cookie': cookie_str,
                'User-Agent': data.get('user-agent', '')
            }
        }

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
                **self._network_options(),
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
                    fallback_url = ""
                    fallback_ext = "m4a"
                    fallback_abr = float("inf")
                    fallback_note = ""
                    quality_ceiling = self._quality_ceiling()
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
                        if ext in ['m4a', 'mp4'] and abr < fallback_abr:
                            # Some streams do not expose every bitrate.  Keep
                            # the lowest compatible audio as a graceful
                            # fallback instead of turning a quality preference
                            # into an unplayable track.
                            fallback_url, fallback_ext = url, ext
                            fallback_abr = abr
                            fallback_note = fmt.get('format_note', '')
                        if quality_ceiling is not None and abr > quality_ceiling:
                            continue
                        
                        if ext in ['m4a', 'mp4'] and abr >= best_abr:
                            best_url = url
                            best_ext = ext
                            best_abr = abr
                            best_format_note = fmt.get('format_note', '')
                        elif not best_url and ext == 'webm':
                            best_url = url
                            best_ext = ext
                            best_abr = abr

                    if not best_url and fallback_url:
                        best_url, best_ext, best_abr = fallback_url, fallback_ext, fallback_abr
                        best_format_note = fallback_note
                    
                    return {
                        "url": best_url,
                        "format": best_ext,
                        "quality": int(best_abr),
                        "duration": best_duration,
                        "format_note": best_format_note,
                        "thumbnail": info.get('thumbnail', ''),
                        # Créditos publicados por la fuente. Son opcionales:
                        # nunca se rellenan con conjeturas en la interfaz.
                        "artist": info.get("artist", "") or "",
                        "album": info.get("album", "") or "",
                        "uploader": info.get("uploader", "") or info.get("channel", "") or "",
                        "release_date": info.get("release_date", "") or info.get("upload_date", "") or "",
                        "license": info.get("license", "") or "",
                        "webpage_url": info.get("webpage_url", "") or "",
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
                **self._network_options(),
            }
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(
                        f"https://www.youtube.com/watch?v={video_id}",
                        download=False
                    )
                    if not info:
                        return ""
                    
                    # El fallback alimenta el motor de audio (VLC): no debe
                    # devolver streams video-only salvo como último recurso.
                    video_fallback = ""
                    for fmt in info.get('formats', []):
                        url = fmt.get('url', '')
                        if not url or not url.startswith('http'):
                            continue
                        if fmt.get('vcodec', 'none') == 'none':
                            return url
                        if not video_fallback:
                            video_fallback = url
                    return video_fallback
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
