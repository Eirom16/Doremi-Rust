from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Index
from doremi.db.database import Base
from datetime import datetime, timezone

# The local library schema is intentionally denormalized. Tables such as
# play_history, downloads and notifications keep their own title/artist fields
# instead of cascading from songs, so user history and offline files survive
# when a Song row is removed or re-created from remote metadata.


class Song(Base):
    __tablename__ = "songs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    artist = Column(String, nullable=False)
    album = Column(String, default="")
    duration_ms = Column(Integer, default=0)
    thumbnail_url = Column(String, default="")
    is_liked = Column(Boolean, default=False, index=True)
    last_played = Column(DateTime, nullable=True, index=True)
    play_count = Column(Integer, default=0)
    local_path = Column(String, nullable=True)

    def __repr__(self):
        return f"<Song {self.title} by {self.artist}>"




class PlayHistory(Base):
    __tablename__ = "play_history"
    __table_args__ = (Index("ix_history_context_time", "context_type", "context_id", "played_at"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    artist = Column(String, nullable=False)
    played_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    duration_ms = Column(Integer, default=0)
    listen_time_ms = Column(Integer, default=0)
    completion_ratio = Column(Float, default=0.0)
    skip_count = Column(Integer, default=0)
    completed = Column(Boolean, default=False)
    was_played = Column(Boolean, default=True, index=True)
    context_type = Column(String, default="queue")
    context_id = Column(String, default="")
    position_ms = Column(Integer, default=0)


class Collection(Base):
    """Small metadata cache shared by origins and ordered sidebar pins."""
    __tablename__ = "collections"
    context_type = Column(String, primary_key=True)
    context_id = Column(String, primary_key=True)
    title = Column(String, nullable=False, default="")
    thumbnail_url = Column(String, nullable=False, default="")
    pinned_at = Column(DateTime, nullable=True)
    position = Column(Integer, nullable=True)


class LocalPlaylistTrack(Base):
    __tablename__ = "local_playlist_tracks"
    playlist_id = Column(String, primary_key=True)
    position = Column(Integer, primary_key=True)
    video_id = Column(String, nullable=False, index=True)


class Download(Base):
    __tablename__ = "downloads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    artist = Column(String, nullable=False)
    album = Column(String, default="")
    file_path = Column(String, nullable=False)
    thumbnail_url = Column(String, default="")
    duration_ms = Column(Integer, default=0)
    downloaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    parent_playlist_id = Column(String, nullable=True)
    parent_playlist_title = Column(String, nullable=True)
    parent_playlist_thumbnail_url = Column(String, nullable=True)


class CachedArtwork(Base):
    __tablename__ = "cached_artwork"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String, unique=True, nullable=False)
    local_path = Column(String, nullable=False)
    cached_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    artist = Column(String, nullable=False)
    artist_id = Column(String, nullable=True)
    thumbnail_url = Column(String, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    is_read = Column(Boolean, default=False, index=True)
    
    def __repr__(self):
        return f"<Notification {self.title} by {self.artist}>"
