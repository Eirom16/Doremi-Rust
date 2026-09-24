import asyncio
import json
import os
import hashlib
import multiprocessing
import re
import signal
import shutil
from pathlib import Path
from PySide6.QtCore import QObject, Signal
from loguru import logger
from doremi.services.download_worker import download_audio

from doremi.config.paths import AppDirs
from doremi.db.repository import DownloadRepository

class DownloadTask:
    def __init__(self, video_id: str, title: str, artist: str, thumbnail_url: str, parent_playlist_id: str = None, parent_playlist_title: str = None, parent_playlist_thumbnail_url: str = None):
        self.video_id = video_id
        self.title = title
        self.artist = artist
        self.thumbnail_url = thumbnail_url
        self.parent_playlist_id = parent_playlist_id
        self.parent_playlist_title = parent_playlist_title
        self.parent_playlist_thumbnail_url = parent_playlist_thumbnail_url
        self.status = "queued" # queued, downloading, completed, error, paused
        self.progress = 0.0
        self.speed = ""
        self._cancel_flag = False
        self._pause_flag = False
        self._queued = False

    def cancel(self):
        self._cancel_flag = True

    def pause(self):
        self._pause_flag = True

    def to_dict(self) -> dict:
        status = "queued" if self.status == "downloading" else self.status
        return {
            "video_id": self.video_id,
            "title": self.title,
            "artist": self.artist,
            "thumbnail_url": self.thumbnail_url,
            "parent_playlist_id": self.parent_playlist_id,
            "parent_playlist_title": self.parent_playlist_title,
            "parent_playlist_thumbnail_url": self.parent_playlist_thumbnail_url,
            "status": status,
            "progress": self.progress,
            "speed": self.speed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DownloadTask":
        task = cls(
            video_id=str(data.get("video_id", "")),
            title=str(data.get("title", "Unknown")),
            artist=str(data.get("artist", "Unknown")),
            thumbnail_url=str(data.get("thumbnail_url", "")),
            parent_playlist_id=data.get("parent_playlist_id"),
            parent_playlist_title=data.get("parent_playlist_title"),
            parent_playlist_thumbnail_url=data.get("parent_playlist_thumbnail_url"),
        )
        task.status = str(data.get("status", "queued"))
        task.progress = float(data.get("progress", 0.0) or 0.0)
        task.speed = str(data.get("speed", ""))
        return task

class DownloadManager(QObject):
    download_queued = Signal(object) # DownloadTask
    download_started = Signal(str) # video_id
    download_progress = Signal(str, float, str) # video_id, progress (0-100), speed
    download_completed = Signal(str, str) # video_id, filepath
    download_error = Signal(str, str) # video_id, error_msg
    tasks_changed = Signal()

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = DownloadManager()
        return cls._instance

    def __init__(self):
        super().__init__()
        self._queue = asyncio.Queue()
        self._tasks = {} # video_id -> DownloadTask
        self._workers = []
        self._running = False
        self._repo = DownloadRepository()
        self._state_file = AppDirs.data / "download_tasks.json"
        self._restored_state = False
        self._closing = False
        self._processes = {}
        self._process_stop_timeout = 0.5

    def start(self, max_concurrent: int = 3):
        if self._running:
            return
        if not self._restored_state:
            self._restore_incomplete_tasks()
            self._restored_state = True
        self._closing = False
        self._running = True
        for _ in range(max_concurrent):
            worker = asyncio.ensure_future(self._worker())
            self._workers.append(worker)

    def stop(self):
        self._closing = True
        self._running = False
        self._save_incomplete_tasks()
        for worker in self._workers:
            worker.cancel()

    async def async_stop(self, timeout: float = 5.0) -> None:
        """Cancelar workers y esperar la terminación de sus procesos hijos."""
        self._process_stop_timeout = min(0.5, max(0.0, timeout))
        self.stop()
        workers = list(self._workers)
        if workers:
            # Cada worker termina y recoge su proceso en finally.
            await asyncio.gather(*workers, return_exceptions=True)
        self._workers.clear()
        while not self._queue.empty():
            task = self._queue.get_nowait()
            task._queued = False
            self._queue.task_done()
        self._save_incomplete_tasks()
        self._restored_state = False
        self._tasks.clear()

    @property
    def active_count(self) -> int:
        return sum(
            1 for task in self._tasks.values()
            if task.status in {"queued", "downloading"} and not task._cancel_flag
        )

    def add_download(self, video_id: str, title: str, artist: str, thumbnail_url: str, parent_playlist_id: str = None, parent_playlist_title: str = None, parent_playlist_thumbnail_url: str = None) -> bool:
        if self._closing or video_id in self._tasks:
            return False # already queued/downloading
        
        task = DownloadTask(video_id, title, artist, thumbnail_url, parent_playlist_id, parent_playlist_title, parent_playlist_thumbnail_url)
        self._tasks[video_id] = task
        self.download_queued.emit(task)
        task._queued = True
        self._queue.put_nowait(task)
        self._save_incomplete_tasks()
        return True

    def cancel_download(self, video_id: str):
        if video_id in self._tasks:
            task = self._tasks[video_id]
            task.cancel()
            if task.status != "downloading":
                self._tasks.pop(video_id, None)
            self._save_incomplete_tasks()
            self.tasks_changed.emit()

    def pause_download(self, video_id: str):
        if video_id in self._tasks:
            task = self._tasks[video_id]
            task.pause()
            if task.status == "queued":
                task.status = "paused"
            self._save_incomplete_tasks()
            self.tasks_changed.emit()

    def resume_download(self, video_id: str):
        if video_id in self._tasks:
            task = self._tasks[video_id]
            if task.status in ["paused", "error"]:
                task.status = "queued"
                task._pause_flag = False
                task._cancel_flag = False
                self.download_queued.emit(task)
                if not task._queued:
                    task._queued = True
                    self._queue.put_nowait(task)
                self._save_incomplete_tasks()

    def retry_download(self, video_id: str):
        self.resume_download(video_id)

    def _save_incomplete_tasks(self) -> None:
        try:
            tasks = [
                task.to_dict()
                for task in self._tasks.values()
                if task.status in {"queued", "downloading", "paused", "error"}
                and not task._cancel_flag
            ]
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = self._state_file.with_suffix(".tmp")
            temporary.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(self._state_file)
        except Exception as e:
            logger.debug(f"Failed to persist download tasks: {e}")

    def _restore_incomplete_tasks(self) -> None:
        try:
            if not self._state_file.exists():
                return
            with open(self._state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                return
            for item in data:
                task = DownloadTask.from_dict(item)
                if not task.video_id or task.video_id in self._tasks:
                    continue
                self._tasks[task.video_id] = task
                if task.status in {"queued", "downloading"}:
                    task.status = "queued"
                    self.download_queued.emit(task)
                    task._queued = True
                    self._queue.put_nowait(task)
            self._save_incomplete_tasks()
        except Exception as e:
            logger.debug(f"Failed to restore download tasks: {e}")

    async def _worker(self):
        while self._running:
            task = None
            try:
                task = await self._queue.get()
                task._queued = False
                if task._cancel_flag or task._pause_flag:
                    continue
                await self._process_download(task)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Download worker error: {exc}")
            finally:
                if task is not None:
                    self._queue.task_done()
                    if task._cancel_flag and self._tasks.get(task.video_id) is task:
                        del self._tasks[task.video_id]
                    self._save_incomplete_tasks()
                    if not self._closing:
                        self.tasks_changed.emit()

    @staticmethod
    def _safe_component(value: str, fallback: str) -> str:
        value = re.sub(r'[\x00-\x1f\x7f/\\<>:"|?*%]', '_', value).strip(' .')
        # Limitar bytes, no sólo caracteres, para nombres Unicode.
        return value.encode('utf-8')[:100].decode('utf-8', errors='ignore') or fallback

    def _output_template(self, task: DownloadTask) -> str:
        root = AppDirs.downloads.resolve()
        directory = root
        if task.parent_playlist_title:
            name = self._safe_component(task.parent_playlist_title, 'playlist')
            identity = task.parent_playlist_id or task.parent_playlist_title
            suffix = hashlib.sha256(identity.encode()).hexdigest()[:12]
            directory = root / f"{name} [{suffix}]"
        if not directory.resolve().is_relative_to(root):
            raise ValueError("Download directory escapes configured root")
        directory.mkdir(parents=True, exist_ok=True)
        artist = self._safe_component(task.artist, 'artist')
        title = self._safe_component(task.title, 'track')
        identity = hashlib.sha256(task.video_id.encode()).hexdigest()[:16]
        stem = f"{artist} - {title} [{identity}]"
        for existing in directory.iterdir():
            if existing.name.startswith(stem + '.') and existing.is_symlink():
                raise ValueError("Refusing symlink in download destination")
        return str(directory / (stem + '.%(ext)s'))

    async def _finish_process(self, process) -> None:
        # El proceso conserva su PID hasta join; su grupo no se puede reutilizar.
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        if process.is_alive():
            process.terminate()
        deadline = asyncio.get_running_loop().time() + self._process_stop_timeout
        while process.is_alive() and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.01)
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process.is_alive():
            process.kill()
        while process.is_alive():
            await asyncio.sleep(0.01)
        process.join()
        process.close()

    async def _run_download(self, task: DownloadTask, options: dict, convert: bool) -> str:
        ctx = multiprocessing.get_context("spawn")
        receiver, sender = ctx.Pipe(duplex=False)
        process = ctx.Process(target=download_audio, args=(
            sender, f"https://www.youtube.com/watch?v={task.video_id}", options, convert,
        ))
        try:
            process.start()
        except BaseException:
            receiver.close()
            sender.close()
            process.close()
            raise
        sender.close()
        self._processes[task.video_id] = process
        try:
            while True:
                if self._closing or task._cancel_flag or task._pause_flag:
                    raise asyncio.CancelledError
                if receiver.poll():
                    try:
                        message = receiver.recv()
                    except EOFError:
                        raise RuntimeError("Download process ended without a result") from None
                    if message[0] == "completed":
                        return message[1]
                    if message[0] == "error":
                        raise RuntimeError(message[1])
                    task.progress, task.speed = message[1:]
                    self.download_progress.emit(task.video_id, task.progress, task.speed)
                elif not process.is_alive():
                    raise RuntimeError("Download process ended without a result")
                await asyncio.sleep(0.02)
        finally:
            await self._finish_process(process)
            receiver.close()
            self._processes.pop(task.video_id, None)

    async def _process_download(self, task: DownloadTask):
        task.status = "downloading"
        self._save_incomplete_tasks()
        self.download_started.emit(task.video_id)
        try:
            convert = shutil.which('ffmpeg') is not None
            options = {
                'format': 'bestaudio/best' if convert else 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio',
                'outtmpl': self._output_template(task),
                'quiet': True, 'no_warnings': True, 'continuedl': True, 'nopart': False,
                'socket_timeout': 10, 'retries': 2, 'fragment_retries': 2,
                'noplaylist': True,
            }
            if convert:
                options['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192',
                }]
            filepath = await self._run_download(task, options, convert)
            path = Path(filepath).resolve()
            if not path.is_relative_to(AppDirs.downloads.resolve()) or not path.is_file():
                raise ValueError("Invalid downloaded file")
            if self._closing or task._cancel_flag or task._pause_flag:
                raise asyncio.CancelledError
            # Registrar el audio antes de buscar letras; completed significa persistido.
            await self._repo.add_download(
                video_id=task.video_id, title=task.title, artist=task.artist, album="",
                file_path=str(path), thumbnail_url=task.thumbnail_url, duration_ms=0,
                parent_playlist_id=task.parent_playlist_id,
                parent_playlist_title=task.parent_playlist_title,
                parent_playlist_thumbnail_url=task.parent_playlist_thumbnail_url,
            )
            task.status = "completed"
            self._save_incomplete_tasks()
            self.download_completed.emit(task.video_id, str(path))
            try:
                from doremi.api.lyrics import LyricsClient
                lyrics = await asyncio.wait_for(
                    LyricsClient().get_plain_lyrics(task.title, task.artist), timeout=10,
                )
                if lyrics:
                    path.with_suffix('.lrc').write_text(lyrics, encoding='utf-8')
            except Exception as exc:
                logger.debug(f"Optional download lyrics unavailable: {exc}")
        except asyncio.CancelledError:
            if task.status != "completed":
                task.status = "paused" if task._pause_flag else "queued"
            if self._closing or not (task._cancel_flag or task._pause_flag):
                raise
        except Exception as exc:
            task.status = "error"
            self.download_error.emit(task.video_id, str(exc))
            logger.error(f"Download failed for {task.video_id}: {exc}")
        finally:
            if (task.status == "completed" or task._cancel_flag) and self._tasks.get(task.video_id) is task:
                del self._tasks[task.video_id]
            self._save_incomplete_tasks()
            if not self._closing:
                self.tasks_changed.emit()
