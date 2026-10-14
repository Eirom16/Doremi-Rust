"""Imported files and ordered playlists that can mix local and remote tracks.

REC-02 adaptation: same revision identifiers and schema as the rescue
commit 11f15a8, but idempotent like 0001/0002 (guards for re-run on
existing databases). No packaging or native changes.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260929_0004"
down_revision = "20260929_0003"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    if "local_path" not in _columns("songs"):
        op.add_column("songs", sa.Column("local_path", sa.String(), nullable=True))
    if "local_playlist_tracks" not in _tables():
        op.create_table(
            "local_playlist_tracks",
            sa.Column("playlist_id", sa.String(), primary_key=True),
            sa.Column("position", sa.Integer(), primary_key=True),
            sa.Column("video_id", sa.String(), nullable=False),
        )
    if "ix_local_playlist_tracks_video_id" not in _indexes("local_playlist_tracks"):
        op.create_index("ix_local_playlist_tracks_video_id", "local_playlist_tracks", ["video_id"])


def downgrade() -> None:
    # Destructive only for REC-02 artifacts; pre-0004 user data is preserved.
    if "ix_local_playlist_tracks_video_id" in _indexes("local_playlist_tracks"):
        op.drop_index("ix_local_playlist_tracks_video_id", table_name="local_playlist_tracks")
    if "local_playlist_tracks" in _tables():
        op.drop_table("local_playlist_tracks")
    if "local_path" in _columns("songs"):
        op.drop_column("songs", "local_path")
