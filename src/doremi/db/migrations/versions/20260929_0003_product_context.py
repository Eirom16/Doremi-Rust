"""Playback origins, resume position and extensible ordered collection pins."""
from alembic import op
import sqlalchemy as sa

revision = "20260929_0003"
down_revision = "20260926_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("play_history", sa.Column("position_ms", sa.Integer(), server_default="0"))
    op.create_index("ix_history_context_time", "play_history", ["context_type", "context_id", "played_at"])
    op.create_table(
        "collections",
        sa.Column("context_type", sa.String(), primary_key=True),
        sa.Column("context_id", sa.String(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False, server_default=""),
        sa.Column("thumbnail_url", sa.String(), nullable=False, server_default=""),
        sa.Column("pinned_at", sa.DateTime(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=True),
    )


def downgrade():
    op.drop_table("collections")
    op.drop_index("ix_history_context_time", table_name="play_history")
    op.drop_column("play_history", "position_ms")
