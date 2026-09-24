import asyncio
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from loguru import logger
import httpx
from doremi.db.repository import NotificationRepository
from PySide6.QtCore import QObject, Signal

class NotificationService(QObject):
    unread_changed = Signal(bool)

    def __init__(self, yt_client):
        super().__init__()
        self.yt = yt_client
        self._repo = NotificationRepository()
        self._is_running = False
        self._task = None

    def start(self):
        if not self._is_running:
            self._is_running = True
            self._task = asyncio.create_task(self._poll_loop())
            logger.info("NotificationService started")

    def stop(self):
        self._is_running = False
        if self._task:
            self._task.cancel()

    async def _poll_loop(self):
        # Initial delay to not block startup
        await asyncio.sleep(10)
        
        while self._is_running:
            try:
                if self.yt and self.yt.is_authenticated:
                    logger.debug("NotificationService: Checking for new releases...")
                    await self._check_subscriptions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"NotificationService error: {e}")
                
            # Sleep for 1 hour before checking again
            for _ in range(3600):
                if not self._is_running:
                    break
                await asyncio.sleep(1)

    async def _check_subscriptions(self):
        try:
            if not self.yt or not getattr(self.yt, "is_authenticated", False) or not getattr(self.yt, "_ytmusicapi", None):
                return
            # We must use self.yt._run to call the sync ytmusicapi function
            subs = await self.yt._run(lambda: self.yt._ytmusicapi.get_library_subscriptions(limit=100))
            if not subs:
                return

            async with httpx.AsyncClient(timeout=10.0) as client:
                for sub in subs:
                    if not self._is_running:
                        break
                        
                    channel_id = sub.get("browseId")
                    if not channel_id:
                        continue
                        
                    # YouTube returns channel IDs sometimes with UC, RSS needs UC
                    await self._check_channel_rss(client, channel_id, sub.get("artist", "Unknown Artist"))
                    
                    # Sleep heavily between requests to avoid any rate limiting or performance hits
                    await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Failed to check subscriptions: {e}")

    async def _check_channel_rss(self, client: httpx.AsyncClient, channel_id: str, artist_name: str):
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        try:
            response = await client.get(url)
            if response.status_code != 200:
                return
                
            root = ET.fromstring(response.text)
            ns = {'atom': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015'}
            
            # Get videos from the last 7 days
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            
            for entry in root.findall('atom:entry', ns):
                video_id_elem = entry.find('yt:videoId', ns)
                title_elem = entry.find('atom:title', ns)
                published_elem = entry.find('atom:published', ns)
                
                if video_id_elem is None or title_elem is None or published_elem is None:
                    continue
                    
                video_id = video_id_elem.text
                title = title_elem.text
                pub_str = published_elem.text
                
                try:
                    # Format: 2023-10-10T00:00:00+00:00
                    pub_date = datetime.fromisoformat(pub_str)
                except ValueError:
                    continue
                    
                if pub_date > week_ago:
                    # Found a recent video, extract thumbnail
                    group = entry.find('{http://search.yahoo.com/mrss/}group')
                    thumbnail_url = ""
                    if group is not None:
                        thumb_elem = group.find('{http://search.yahoo.com/mrss/}thumbnail')
                        if thumb_elem is not None:
                            thumbnail_url = thumb_elem.get('url', '')
                            
                    await self._save_notification_if_new(video_id, title, artist_name, thumbnail_url, pub_date, channel_id)
                    
        except Exception as e:
            logger.debug(f"Failed to parse RSS for {channel_id}: {e}")

    async def _save_notification_if_new(self, video_id: str, title: str, artist: str, thumbnail_url: str, pub_date: datetime, artist_id: str):
        created = await self._repo.add_if_new(
            video_id=video_id,
            title=title,
            artist=artist,
            thumbnail_url=thumbnail_url,
            created_at=pub_date,
            artist_id=artist_id,
        )
        if created:
            logger.info(f"New notification: {title} by {artist}")
            self.unread_changed.emit(True)

    async def check_unread(self):
        self.unread_changed.emit(await self._repo.has_unread())
