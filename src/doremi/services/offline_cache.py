"""Caché rotativa de audio y metadatos para el modo sin conexión."""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

from loguru import logger

from doremi.config.paths import AppDirs


_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,32}$")


class OfflineCacheManager:
    """Mantiene un feed reproducible sin mezclarlo con descargas del usuario."""

    _instance: OfflineCacheManager | None = None

    def __init__(self) -> None:
        self.root = AppDirs.cache / "offline"
        self.audio_dir = self.root / "audio"
        self.artwork_dir = self.root / "artwork"
        self.feed_path = self.root / "home.json"
        self.manifest_path = self.root / "manifest.json"
        self._sync_task: asyncio.Task | None = None

    @classmethod
    def get_instance(cls) -> OfflineCacheManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _setup(self) -> None:
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.artwork_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _read_json(path: Path, fallback: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return fallback

    @staticmethod
    def _write_json(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(temporary, path)

    def remember_feed(self, feed: dict) -> None:
        """Guarda metadatos normalizados; el audio se actualiza en segundo plano."""
        self._setup()
        stored = {key: value for key, value in feed.items() if not key.startswith("_")}
        stored["saved_at"] = int(time.time())
        try:
            self._write_json(self.feed_path, stored)
        except OSError as exc:
            logger.warning(f"No se pudo guardar el feed sin conexión: {exc}")

    def _manifest(self) -> dict[str, dict]:
        raw = self._read_json(self.manifest_path, {})
        return raw if isinstance(raw, dict) else {}

    def local_path(self, video_id: str) -> str | None:
        record = self._manifest().get(video_id, {})
        path = Path(record.get("audio_path", ""))
        if path.is_file() and path.stat().st_size > 0:
            return str(path)
        return None

    def load_home(self) -> dict:
        """Construye un Home que sólo contiene canciones realmente reproducibles."""
        feed = self._read_json(self.feed_path, {})
        manifest = self._manifest()
        available: dict[str, dict] = {}
        for video_id, record in manifest.items():
            audio_path = Path(record.get("audio_path", ""))
            if audio_path.is_file() and audio_path.stat().st_size > 0:
                available[video_id] = record

        def adapt(item: dict) -> dict | None:
            video_id = item.get("videoId", "")
            record = available.get(video_id)
            if not record:
                return None
            result = dict(item)
            artwork = Path(record.get("artwork_path", ""))
            if artwork.is_file():
                result["thumbnail_url"] = artwork.as_uri()
            result["is_downloaded"] = True
            return result

        tiles = [item for raw in feed.get("tiles", []) if (item := adapt(raw))]
        songs = [item for raw in feed.get("songs", []) if (item := adapt(raw))]
        known = {item.get("videoId") for item in tiles + songs}
        for video_id, record in available.items():
            if video_id in known:
                continue
            artwork = Path(record.get("artwork_path", ""))
            songs.append({
                "videoId": video_id,
                "title": record.get("title", ""),
                "artist": record.get("artist", ""),
                "duration": "",
                "duration_ms": int(record.get("duration_ms", 0) or 0),
                "thumbnail_url": artwork.as_uri() if artwork.is_file() else "",
                "is_liked": False,
                "is_downloaded": True,
            })

        # En offline no se muestran playlists, álbumes ni categorías que no abren.
        primary = (tiles + songs)[:1]
        spotlight = []
        if primary:
            item = primary[0]
            spotlight = [{
                "title": item.get("title", ""),
                "subtitle": item.get("artist", ""),
                "thumbnail_url": item.get("thumbnail_url", ""),
                "navigate": f"play:{item.get('videoId', '')}",
            }]
        return {
            "greeting": "Modo sin conexión",
            "spotlight": spotlight,
            "tiles": tiles[:6],
            "horizontal": [],
            "sections": [],
            "songs": songs,
            "_source": "cache" if available else "empty",
        }

    def schedule_sync(self, feed: dict, settings) -> None:
        offline = getattr(settings, "offline", None)
        if offline is not None and not offline.enabled:
            return
        if self._sync_task and not self._sync_task.done():
            return
        limit = max(1, int(getattr(offline, "song_limit", 25)))
        self._sync_task = asyncio.create_task(self.sync_from_feed(feed, limit))

    @staticmethod
    def _candidates(feed: dict) -> list[dict]:
        candidates: list[dict] = []
        seen: set[str] = set()
        for item in [*feed.get("tiles", []), *feed.get("songs", [])]:
            video_id = item.get("videoId", "")
            if video_id and video_id not in seen and _VIDEO_ID_RE.fullmatch(video_id):
                seen.add(video_id)
                candidates.append(item)
        return candidates

    async def sync_from_feed(self, feed: dict, limit: int) -> None:
        """Rellena y rota la caché sin bloquear el hilo de Qt."""
        self._setup()
        manifest = self._manifest()
        candidates = self._candidates(feed)
        try:
            for item in candidates[:limit]:
                video_id = item["videoId"]
                existing = manifest.get(video_id, {})
                existing_path = Path(existing.get("audio_path", ""))
                if existing_path.is_file() and existing_path.stat().st_size > 0:
                    existing["last_seen"] = int(time.time())
                    continue

                audio_path = await self._download_track(video_id)
                if not audio_path:
                    continue
                artwork_path = await self._cache_artwork(
                    video_id, item.get("thumbnail_url", "")
                )
                manifest[video_id] = {
                    "audio_path": str(audio_path),
                    "artwork_path": str(artwork_path) if artwork_path else "",
                    "title": item.get("title", ""),
                    "artist": item.get("artist", ""),
                    "duration_ms": int(item.get("duration_ms", 0) or 0),
                    "cached_at": int(time.time()),
                    "last_seen": int(time.time()),
                }
                self._prune(manifest, limit, keep=video_id)
                self._write_json(self.manifest_path, manifest)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(f"Actualización de caché sin conexión interrumpida: {exc}")
        finally:
            self._prune(manifest, limit)
            try:
                self._write_json(self.manifest_path, manifest)
            except OSError as exc:
                logger.warning(f"No se pudo guardar la caché sin conexión: {exc}")

    def _prune(self, manifest: dict[str, dict], limit: int, keep: str = "") -> None:
        while len(manifest) > limit:
            removable = [(key, value) for key, value in manifest.items() if key != keep]
            if not removable:
                return
            video_id, record = min(
                removable,
                key=lambda pair: pair[1].get("last_seen", pair[1].get("cached_at", 0)),
            )
            for field in ("audio_path", "artwork_path"):
                path = Path(record.get(field, ""))
                try:
                    if path.is_file() and path.is_relative_to(self.root):
                        path.unlink()
                except OSError:
                    pass
            manifest.pop(video_id, None)

    async def _download_track(self, video_id: str) -> Path | None:
        # Sin cookies YouTube rechaza gran parte de los formatos. Las
        # credenciales viven en el llavero; se pasan como header Cookie
        # (un archivo --cookies Netscape pierde las cookies de otros dominios
        # de Google y YouTube devuelve "The page needs to be reloaded").
        # El proceso es efímero y sólo legible por el propio usuario.
        from doremi.utils.secure_storage import SecureStorage
        headers = SecureStorage.load_youtube_headers() or {}
        auth_args: list[str] = []
        cookie = headers.get("cookie", "")
        if cookie:
            auth_args += ["--add-headers", f"Cookie:{cookie}"]
        user_agent = headers.get("user-agent", "")
        if user_agent:
            auth_args += ["--user-agent", user_agent]

        template = str(self.audio_dir / f"{video_id}.%(ext)s")
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "yt_dlp",
            "--quiet", "--no-warnings", "--no-playlist",
            "--socket-timeout", "10", "--retries", "2",
            *auth_args,
            # Algunos vídeos sólo publican un formato combinado; `best` es el
            # último recurso para que la caché siga siendo reproducible.
            "-f", "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
            "-o", template,
            f"https://www.youtube.com/watch?v={video_id}",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await process.communicate()
        except asyncio.CancelledError:
            process.kill()
            await process.wait()
            raise
        if process.returncode != 0:
            message = stderr.decode(errors="replace").strip()[-300:]
            logger.debug(f"No se pudo cachear {video_id}: {message}")
            return None
        matches = [path for path in self.audio_dir.glob(f"{video_id}.*") if path.is_file()]
        return max(matches, key=lambda path: path.stat().st_mtime) if matches else None

    async def _cache_artwork(self, video_id: str, url: str) -> Path | None:
        if not url.startswith(("http://", "https://")):
            return None
        destination = self.artwork_dir / f"{video_id}.jpg"

        def fetch() -> None:
            request = urllib.request.Request(url, headers={"User-Agent": "Doremi/1"})
            with urllib.request.urlopen(request, timeout=10) as response:
                destination.write_bytes(response.read(4 * 1024 * 1024))

        try:
            await asyncio.to_thread(fetch)
            return destination
        except Exception as exc:
            logger.debug(f"No se pudo cachear la portada de {video_id}: {exc}")
            return None
