from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260708_0001"
down_revision = None
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return set(inspector.get_table_names())


def _columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if table_name in _tables() and index_name not in _indexes(table_name):
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    tables = _tables()

    if "songs" not in tables:
        op.create_table(
            "songs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("video_id", sa.String(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("artist", sa.String(), nullable=False),
            sa.Column("album", sa.String(), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("thumbnail_url", sa.String(), nullable=True),
            sa.Column("is_liked", sa.Boolean(), nullable=True),
            sa.Column("last_played", sa.DateTime(), nullable=True),
            sa.Column("play_count", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("video_id"),
        )

    if "play_history" not in tables:
        op.create_table(
            "play_history",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("video_id", sa.String(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("artist", sa.String(), nullable=False),
            sa.Column("played_at", sa.DateTime(), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    if "downloads" not in tables:
        op.create_table(
            "downloads",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("video_id", sa.String(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("artist", sa.String(), nullable=False),
            sa.Column("album", sa.String(), nullable=True),
            sa.Column("file_path", sa.String(), nullable=False),
            sa.Column("thumbnail_url", sa.String(), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("downloaded_at", sa.DateTime(), nullable=True),
            sa.Column("parent_playlist_id", sa.String(), nullable=True),
            sa.Column("parent_playlist_title", sa.String(), nullable=True),
            sa.Column("parent_playlist_thumbnail_url", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("video_id"),
        )
    elif "parent_playlist_thumbnail_url" not in _columns("downloads"):
        op.add_column(
            "downloads",
            sa.Column("parent_playlist_thumbnail_url", sa.String(), nullable=True),
        )

    if "cached_artwork" not in tables:
        op.create_table(
            "cached_artwork",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("url", sa.String(), nullable=False),
            sa.Column("local_path", sa.String(), nullable=False),
            sa.Column("cached_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("url"),
        )

    if "notifications" not in tables:
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("video_id", sa.String(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("artist", sa.String(), nullable=False),
            sa.Column("artist_id", sa.String(), nullable=True),
            sa.Column("thumbnail_url", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("is_read", sa.Boolean(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("video_id"),
        )
    elif "artist_id" not in _columns("notifications"):
        op.add_column("notifications", sa.Column("artist_id", sa.String(), nullable=True))

    _create_index_if_missing("ix_songs_is_liked", "songs", ["is_liked"])
    _create_index_if_missing("ix_songs_last_played", "songs", ["last_played"])
    _create_index_if_missing("ix_play_history_video_id", "play_history", ["video_id"])
    _create_index_if_missing("ix_play_history_played_at", "play_history", ["played_at"])
    _create_index_if_missing("ix_downloads_downloaded_at", "downloads", ["downloaded_at"])
    _create_index_if_missing("ix_notifications_is_read", "notifications", ["is_read"])


def downgrade() -> None:
    op.drop_index("ix_notifications_is_read", table_name="notifications")
    op.drop_index("ix_downloads_downloaded_at", table_name="downloads")
    op.drop_index("ix_play_history_played_at", table_name="play_history")
    op.drop_index("ix_play_history_video_id", table_name="play_history")
    op.drop_index("ix_songs_last_played", table_name="songs")
    op.drop_index("ix_songs_is_liked", table_name="songs")
    op.drop_table("notifications")
    op.drop_table("cached_artwork")
    op.drop_table("downloads")
    op.drop_table("play_history")
    op.drop_table("songs")
