# Database migrations

Doremi uses Alembic for persistent SQLite schema changes.

Runtime startup calls `alembic upgrade head` for file-backed databases. In-memory
test databases use `Base.metadata.create_all()` directly.
