"""Playback origins, resume position and extensible ordered collection pins.

REC-02 adaptation: same revision identifiers and schema as the rescue
commit 11f15a8, but idempotent like 0001/0002 (guards for re-run on
existing databases). No packaging or native changes.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260929_0003"
down_revision = "20260926_0002"
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
    if "position_ms" not in _columns("play_history"):
        op.add_column("play_history", sa.Column("position_ms", sa.Integer(), server_default="0"))
    if "ix_history_context_time" not in _indexes("play_history"):
        op.create_index("ix_history_context_time", "play_history", ["context_type", "context_id", "played_at"])
    if "collections" not in _tables():
        op.create_table(
            "collections",
            sa.Column("context_type", sa.String(), primary_key=True),
            sa.Column("context_id", sa.String(), primary_key=True),
            sa.Column("title", sa.String(), nullable=False, server_default=""),
            sa.Column("thumbnail_url", sa.String(), nullable=False, server_default=""),
            sa.Column("pinned_at", sa.DateTime(), nullable=True),
            sa.Column("position", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    # Destructive only for REC-02 artifacts; pre-0003 user data is preserved.
    if "collections" in _tables():
        op.drop_table("collections")
    if "ix_history_context_time" in _indexes("play_history"):
        op.drop_index("ix_history_context_time", table_name="play_history")
    if "position_ms" in _columns("play_history"):
        op.drop_column("play_history", "position_ms")
