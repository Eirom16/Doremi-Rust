import asyncio
from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from loguru import logger
from doremi.utils.i18n import _, _f
from doremi.ui.screens.downloads_data import delete_audio_file


class DownloadController:
    """Specialized controller for download/delete operations.

    Owns the download/delete logic previously living in MainWindow's god object:
    single-song downloads, playlist/album bulk downloads, download/playlist
    deletion and local-playlist playback.

    ``main_window`` is the back-reference to MainWindow. Shared state and UI
    objects (yt client, screens, stack, statusBar, notifications, navigation,
    playback_controller) are accessed through ``self.main_window`` rather than
    cached, because MainWindow finishes building them after this controller is
    constructed.

    ``download_manager`` is injected directly (already a singleton started in
    MainWindow.__init__) so the controller can enqueue downloads and read the
    repository directly.

    ``run_async`` is a callable (MainWindow._run_async) used to launch coroutines
    as asyncio tasks.
    """

    def __init__(self, main_window, download_manager, run_async):
        self.main_window = main_window
        self.download_manager = download_manager
        self.run_async = run_async

    def on_download_requested(self, video_id, title, artist, thumb_url):
        logger.info(f"Download requested: {title} by {artist}")
        self.run_async(self.on_download_requested_async(video_id, title, artist, thumb_url))

    async def on_download_requested_async(self, video_id, title, artist, thumb_url):
        existing = await self.download_manager._repo.get_download(video_id)
        if existing:
            self.main_window.statusBar().showMessage(f"Ya descargada: {title}", 3000)
            self.main_window.show_notification(f"Ya descargada: {title}", "success")
            return

        if self.download_manager.add_download(video_id, title, artist, thumb_url):
            self.main_window.statusBar().showMessage(f"Descargando: {title}", 3000)

            def navigate_to_downloads():
                self.main_window._navigate_to("downloads")

            self.main_window.show_notification(
                f"Descargando: {title}", "info",
                action_text="VER", action_callback=navigate_to_downloads,
            )
        else:
            self.main_window.statusBar().showMessage(f"Ya en cola: {title}", 3000)

    def on_download_finished(self, video_id, file_path):
        self.main_window.statusBar().showMessage(f"Descarga completa!", 5000)

    def on_download_playlist_requested(self, playlist_id, title, thumbnail_url):
        self.run_async(self.download_playlist_async(playlist_id, title, thumbnail_url))

    async def download_playlist_async(self, playlist_id, title, thumbnail_url):
        self.main_window.statusBar().showMessage(f"Iniciando descarga de playlist: {title}", 3000)

        def navigate_to_downloads():
            self.main_window._navigate_to("downloads")

        self.main_window.show_notification(
            f"Descargando playlist: {title}", "info",
            action_text="VER", action_callback=navigate_to_downloads,
        )

        try:
            data = await self.main_window.yt.get_playlist(playlist_id)
            playlist_thumbnails = data.get('thumbnails', [])
            if playlist_thumbnails:
                high_res_thumb = playlist_thumbnails[-1].get('url', '')
                if high_res_thumb:
                    thumbnail_url = high_res_thumb
            tracks = data.get('tracks', [])

            queued = 0
            already_downloaded = 0
            for track in tracks:
                vid = track.get('videoId')
                if not vid:
                    continue

                # Check if already downloaded
                existing = await self.download_manager._repo.get_download(vid)
                if existing:
                    already_downloaded += 1
                    continue

                t_title = track.get('title', 'Unknown')
                artists = track.get('artists', [])
                artist_names = ", ".join([a.get('name', '') for a in artists]) if isinstance(artists, list) else str(artists)
                track_thumbnails = track.get('thumbnails', [])
                track_thumb = track_thumbnails[-1].get('url', '') if track_thumbnails else ''

                if self.download_manager.add_download(vid, t_title, artist_names, track_thumb, playlist_id, title, thumbnail_url):
                    queued += 1

            if already_downloaded > 0:
                self.main_window.statusBar().showMessage(f"{queued} añadidas a cola • {already_downloaded} ya descargadas", 5000)
                self.main_window.show_notification(f"{queued} añadidas, {already_downloaded} omitidas (ya descargadas).", "success")
            else:
                self.main_window.statusBar().showMessage(f"{queued} canciones añadidas a cola", 4000)
                self.main_window.show_notification(f"{queued} canciones añadidas a la cola", "success")
        except Exception as e:
            logger.error(f"Error downloading playlist: {e}")
            self.main_window.statusBar().showMessage("Error al iniciar descarga de playlist", 4000)

    def on_download_album_requested(self, browse_id, title, thumbnail_url):
        self.run_async(self.download_album_async(browse_id, title, thumbnail_url))

    async def download_album_async(self, browse_id, title, thumbnail_url):
        from doremi.ui.screens.album_data import fetch_album_or_podcast, is_podcast_id

        collection_name = "podcast" if is_podcast_id(browse_id) else "álbum"
        item_name = "episodios" if is_podcast_id(browse_id) else "canciones"
        self.main_window.statusBar().showMessage(
            f"Iniciando descarga de {collection_name}: {title}", 3000
        )

        def navigate_to_downloads():
            self.main_window._navigate_to("downloads")

        self.main_window.show_notification(
            f"Iniciando descarga de {collection_name}: {title}", "info",
            action_text="VER", action_callback=navigate_to_downloads,
        )

        try:
            data = await fetch_album_or_podcast(self.main_window.yt, browse_id)
            album_thumbnails = data.get('thumbnails', [])
            if album_thumbnails:
                high_res_thumb = album_thumbnails[-1].get('url', '')
                if high_res_thumb:
                    thumbnail_url = high_res_thumb

            tracks = data.get('tracks', [])
            artists = data.get('artists', [])
            album_artist = ", ".join([a.get('name', '') for a in artists]) if isinstance(artists, list) else str(artists)
            parent_id = f"album_{browse_id}"

            queued = 0
            already_downloaded = 0
            for track in tracks:
                vid = track.get('videoId')
                if not vid:
                    continue

                existing = await self.download_manager._repo.get_download(vid)
                if existing:
                    already_downloaded += 1
                    continue

                t_title = track.get('title', 'Unknown')
                track_artists = track.get('artists', [])
                if track_artists:
                    artist_names = ", ".join([a.get('name', '') for a in track_artists]) if isinstance(track_artists, list) else str(track_artists)
                else:
                    artist_names = album_artist
                track_thumbnails = track.get('thumbnails', [])
                track_thumb = track_thumbnails[-1].get('url', '') if track_thumbnails else thumbnail_url

                if self.download_manager.add_download(vid, t_title, artist_names, track_thumb, parent_id, title, thumbnail_url):
                    queued += 1

            if already_downloaded > 0:
                self.main_window.statusBar().showMessage(f"{queued} añadidas a cola • {already_downloaded} ya descargadas", 5000)
                self.main_window.show_notification(f"{queued} añadidas, {already_downloaded} omitidas (ya descargadas).", "success")
            else:
                message = f"{queued} {item_name} del {collection_name} añadidos a la cola"
                self.main_window.statusBar().showMessage(message, 4000)
                self.main_window.show_notification(message, "success")
        except Exception as e:
            logger.error(f"Error downloading album/podcast: {e}")
            self.main_window.statusBar().showMessage(
                f"Error al iniciar descarga de {collection_name}", 4000
            )

    def on_download_error(self, video_id, error):
        self.main_window.statusBar().showMessage(f"Error en descarga: {error}", 5000)

    def on_delete_download_requested(self, video_id: str):
        self.run_async(self.delete_download_async(video_id))

    def confirm_destructive_action(self, title: str, message: str) -> bool:
        result = QMessageBox.question(
            self.main_window,
            title,
            message,
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        return result == QMessageBox.StandardButton.Yes

    async def delete_download_async(self, video_id: str):
        from doremi.db.repository import DownloadRepository
        repo = DownloadRepository()
        d = await repo.get_download(video_id)
        if d:
            title = d.title
            if not self.confirm_destructive_action(
                "Eliminar descarga",
                f"¿Eliminar la descarga local de \"{title}\"?",
            ):
                return
            try:
                lyrics_deleted = delete_audio_file(d.file_path)
                await repo.remove_download(video_id)
            except Exception as exc:
                logger.error(f"No se pudo eliminar {video_id}: {exc}")
                self.main_window.show_notification(_("No se pudo eliminar la descarga. Puedes reintentarlo."), "error")
                return
            if not lyrics_deleted:
                self.main_window.show_notification(_("Se eliminó el audio, pero no se pudo borrar la letra."), "warning")
            self.main_window.statusBar().showMessage(f"Descarga eliminada: {title}", 3000)
            self.main_window.show_notification(f"Descarga eliminada: {title}", "info")

            # Reload current screen
            current_screen = self.main_window.stack.currentWidget()
            if current_screen == self.main_window.downloads_screen:
                await self.main_window.downloads_screen.load()
            elif current_screen == self.main_window.playlist_screen:
                await self.main_window.playlist_screen.load(self.main_window.playlist_screen._playlist_id)
            elif current_screen == self.main_window.library_screen:
                await self.main_window.library_screen.load()

    def on_delete_playlist_requested(self, playlist_id: str):
        self.run_async(self.delete_playlist_async(playlist_id))

    async def delete_playlist_async(self, playlist_id: str):
        from doremi.db.repository import DownloadRepository
        repo = DownloadRepository()
        downloads = await repo.get_downloads()

        playlist_downloads = [
            d for d in downloads if d.parent_playlist_id == playlist_id
        ]
        playlist_title = next(
            (d.parent_playlist_title for d in playlist_downloads if d.parent_playlist_title),
            playlist_id,
        )
        if not playlist_downloads:
            return
        if not self.confirm_destructive_action(
            "Eliminar playlist local",
            f"¿Eliminar \"{playlist_title}\" y sus {len(playlist_downloads)} canciones descargadas?",
        ):
            return

        count, failures = 0, 0
        for d in playlist_downloads:
            try:
                lyrics_deleted = delete_audio_file(d.file_path)
                await repo.remove_download(d.video_id)
                count += 1
                if not lyrics_deleted:
                    failures += 1
            except Exception as exc:
                failures += 1
                logger.error(f"No se pudo eliminar {d.video_id}: {exc}")
        message = _f("Audios eliminados: {count}. Fallos de borrado: {failed}.", count=count, failed=failures)
        self.main_window.statusBar().showMessage(message, 4000)
        self.main_window.show_notification(message, "warning" if failures else "info")
        await self.main_window._navigate("downloads")

    def play_local_playlist(self, tracks_metadata: list[dict], start_index: int = 0) -> None:
        self.main_window.playback_controller._play_local_playlist(tracks_metadata, start_index)
