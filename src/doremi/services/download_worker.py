"""Trabajo bloqueante de yt-dlp, aislado del proceso Qt."""
import os
import time
from pathlib import Path


def download_audio(connection, url: str, options: dict, convert_mp3: bool) -> None:
    # El grupo permite terminar también FFmpeg durante el posprocesado.
    if os.name == "posix":
        os.setsid()
    try:
        import yt_dlp

        last_progress = 0.0

        def progress(data):
            nonlocal last_progress
            now = time.monotonic()
            if now - last_progress < 0.1:
                return
            last_progress = now
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            percent = min(100.0, data.get("downloaded_bytes", 0) * 100 / total) if total else 0.0
            connection.send(("progress", percent, data.get("_speed_str") or ""))

        options = dict(options, progress_hooks=[progress])
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = Path(ydl.prepare_filename(info))
            if convert_mp3:
                filename = filename.with_suffix(".mp3")
            if not filename.is_file():
                raise FileNotFoundError(str(filename))
            connection.send(("completed", str(filename)))
    except Exception as exc:
        connection.send(("error", str(exc)))
    finally:
        connection.close()
