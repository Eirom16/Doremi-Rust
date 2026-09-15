import asyncio
import json
import os
from pathlib import Path
from PySide6.QtCore import QObject, Signal
from loguru import logger
import yt_dlp

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

    def start(self, max_concurrent: int = 3):
        if self._running:
            return
        if not self._restored_state:
            self._restore_incomplete_tasks()
            self._restored_state = True
        self._running = True
        for _ in range(max_concurrent):
            worker = asyncio.ensure_future(self._worker())
            self._workers.append(worker)

    def stop(self):
        self._running = False
        self._save_incomplete_tasks()
        for worker in self._workers:
            worker.cancel()
        # Note: workers are awaited in async_stop() to avoid blocking
        self._workers.clear()

    async def async_stop(self, timeout: float = 5.0) -> None:
        """Gracefully stop all download workers and wait for them to finish."""
        self._running = False
        self._save_incomplete_tasks()
        
        # Cancel all pending tasks in queue
        while not self._queue.empty():
            try:
                task = self._queue.get_nowait()
                if not task._cancel_flag:
                    task.cancel()
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break
        
        # Wait for workers to finish with timeout
        if self._workers:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._workers, return_exceptions=True),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning("Download workers did not finish within timeout")
            except Exception as e:
                logger.error(f"Error waiting for download workers: {e}")
        
        self._workers.clear()

    @property
    def active_count(self) -> int:
        return sum(
            1 for task in self._tasks.values()
            if task.status in {"queued", "downloading"}
        )

    def add_download(self, video_id: str, title: str, artist: str, thumbnail_url: str, parent_playlist_id: str = None, parent_playlist_title: str = None, parent_playlist_thumbnail_url: str = None) -> bool:
        if video_id in self._tasks:
            return False # already queued/downloading
        
        task = DownloadTask(video_id, title, artist, thumbnail_url, parent_playlist_id, parent_playlist_title, parent_playlist_thumbnail_url)
        self._tasks[video_id] = task
        self.download_queued.emit(task)
        self._queue.put_nowait(task)
        self._save_incomplete_tasks()
        return True

    def cancel_download(self, video_id: str):
        if video_id in self._tasks:
            self._tasks[video_id].cancel()
            self._save_incomplete_tasks()

    def pause_download(self, video_id: str):
        if video_id in self._tasks:
            self._tasks[video_id].pause()
            self._save_incomplete_tasks()

    def resume_download(self, video_id: str):
        if video_id in self._tasks:
            task = self._tasks[video_id]
            if task.status in ["paused", "error"]:
                task.status = "queued"
                task._pause_flag = False
                task._cancel_flag = False
                self.download_queued.emit(task)
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
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)
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
                    self._queue.put_nowait(task)
            self._save_incomplete_tasks()
        except Exception as e:
            logger.debug(f"Failed to restore download tasks: {e}")

    async def _worker(self):
        while self._running:
            try:
                task = await self._queue.get()
                if task._cancel_flag:
                    self._queue.task_done()
                    continue
                
                await self._process_download(task)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Download worker error: {e}")

    async def _process_download(self, task: DownloadTask):
        task.status = "downloading"
        self._save_incomplete_tasks()
        self.download_started.emit(task.video_id)
        
        loop = asyncio.get_event_loop()
        
        def progress_hook(d):
            if task._cancel_flag:
                raise Exception("CANCELLED")
            if task._pause_flag:
                task.status = "paused"
                raise Exception("PAUSED")
                
            if d['status'] == 'downloading':
                try:
                    percent_str = d.get('_percent_str', '0%').replace('%', '').replace('\x1b[0;94m', '').replace('\x1b[0m', '').strip()
                    percent = float(percent_str) if percent_str else 0.0
                    speed = d.get('_speed_str', '')
                    
                    task.progress = percent
                    task.speed = speed
                    # emit in main thread
                    loop.call_soon_threadsafe(self.download_progress.emit, task.video_id, percent, speed)
                except ValueError:
                    pass

        url = f"https://www.youtube.com/watch?v={task.video_id}"
        out_dir = AppDirs.downloads
        
        # Determine path structure
        if task.parent_playlist_title:
            out_dir = out_dir / task.parent_playlist_title
            
        out_dir.mkdir(parents=True, exist_ok=True)
        
        out_tmpl = str(out_dir / f"{task.artist} - {task.title}.%(ext)s")
        
        import shutil
        has_ffmpeg = shutil.which('ffmpeg') is not None
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': out_tmpl,
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True,
            'continuedl': True,
            'nopart': False,
        }
        
        if has_ffmpeg:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
            ext = 'mp3'
        else:
            # No ffmpeg — download audio directly without conversion
            ydl_opts['format'] = 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio'
            ext = None  # Will be determined by yt-dlp
        
        try:
            def _download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    # Get actual filepath — use the real extension
                    base = ydl.prepare_filename(info).rsplit('.', 1)[0]
                    if has_ffmpeg:
                        return base + '.mp3'
                    # Without ffmpeg, find whatever file was downloaded
                    import glob
                    matches = glob.glob(base + '.*')
                    return matches[0] if matches else base
            
            filepath = await loop.run_in_executor(None, _download)
            
            if task._cancel_flag:
                if os.path.exists(filepath):
                    os.remove(filepath)
                self._save_incomplete_tasks()
                return
                
            task.status = "completed"
            self._save_incomplete_tasks()
            
            # Fetch and save offline lyrics (.lrc format next to audio file)
            try:
                from doremi.api.lyrics import LyricsClient
                lyrics_client = LyricsClient()
                lyrics_text = await lyrics_client.get_plain_lyrics(task.title, task.artist)
                if lyrics_text:
                    lrc_filepath = os.path.splitext(filepath)[0] + ".lrc"
                    with open(lrc_filepath, "w", encoding="utf-8") as f:
                        f.write(lyrics_text)
                    logger.info(f"Downloaded offline lyrics saved to: {lrc_filepath}")
            except Exception as le:
                logger.error(f"Failed to download offline lyrics: {le}")
            
            # Save to DB
            await self._repo.add_download(
                video_id=task.video_id,
                title=task.title,
                artist=task.artist,
                album="",
                file_path=filepath,
                thumbnail_url=task.thumbnail_url,
                duration_ms=0,
                parent_playlist_id=task.parent_playlist_id,
                parent_playlist_title=task.parent_playlist_title,
                parent_playlist_thumbnail_url=task.parent_playlist_thumbnail_url
            )
            
            self.download_completed.emit(task.video_id, filepath)
            
        except Exception as e:
            if str(e) == "PAUSED":
                task.status = "paused"
                self._save_incomplete_tasks()
                logger.info(f"Download paused: {task.title}")
                # Do NOT delete from self._tasks so it can be resumed
                return
            elif str(e) == "CANCELLED":
                logger.info(f"Download cancelled: {task.title}")
            else:
                logger.error(f"Download failed for {task.video_id}: {e}")
                task.status = "error"
                self._save_incomplete_tasks()
                # Do NOT delete from self._tasks so it can be retried
                self.download_error.emit(task.video_id, str(e))
                return
        finally:
            # We want to keep paused and error tasks in _tasks so they can be resumed/retried.
            if task.video_id in self._tasks and task.status in ["completed", "queued"]:
                del self._tasks[task.video_id]
            elif task.video_id in self._tasks and task._cancel_flag:
                del self._tasks[task.video_id]
            self._save_incomplete_tasks()
