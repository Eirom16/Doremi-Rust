"""Imported files and ordered playlists that can mix local and remote tracks."""
from alembic import op
import sqlalchemy as sa

revision = "20260929_0004"
down_revision = "20260929_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("songs", sa.Column("local_path", sa.String(), nullable=True))
    op.create_table("local_playlist_tracks",
                    sa.Column("playlist_id", sa.String(), primary_key=True),
                    sa.Column("position", sa.Integer(), primary_key=True),
                    sa.Column("video_id", sa.String(), nullable=False))
    op.create_index("ix_local_playlist_tracks_video_id", "local_playlist_tracks", ["video_id"])


def downgrade():
    op.drop_table("local_playlist_tracks")
    op.drop_column("songs", "local_path")
