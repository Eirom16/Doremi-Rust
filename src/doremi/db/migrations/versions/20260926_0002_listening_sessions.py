"""Persist real listening-session metrics in play history."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260926_0002"
down_revision = "20260708_0001"
branch_labels = None
depends_on = None


def _columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns("play_history")}


def upgrade() -> None:
    columns = _columns()
    additions = [
        ("listen_time_ms", sa.Integer(), 0),
        ("completion_ratio", sa.Float(), 0.0),
        ("skip_count", sa.Integer(), 0),
        ("completed", sa.Boolean(), False),
        ("was_played", sa.Boolean(), True),
        ("context_type", sa.String(), "queue"),
        ("context_id", sa.String(), ""),
    ]
    for name, column_type, default in additions:
        if name not in columns:
            op.add_column(
                "play_history",
                sa.Column(name, column_type, nullable=True, server_default=sa.text(repr(default))),
            )
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("play_history")}
    if "ix_play_history_was_played" not in indexes:
        op.create_index("ix_play_history_was_played", "play_history", ["was_played"])


def downgrade() -> None:
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("play_history")}
    if "ix_play_history_was_played" in indexes:
        op.drop_index("ix_play_history_was_played", table_name="play_history")
    for name in (
        "context_id", "context_type", "was_played", "completed", "skip_count",
        "completion_ratio", "listen_time_ms",
    ):
        if name in _columns():
            op.drop_column("play_history", name)
