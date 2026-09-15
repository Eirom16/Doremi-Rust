from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from doremi.config.paths import AppDirs
from loguru import logger
from pathlib import Path
import asyncio

Base = declarative_base()

DATABASE_URL = f"sqlite+aiosqlite:///{AppDirs.database}"

_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(DATABASE_URL, echo=False)
    return _engine


async def get_session_factory():
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(engine, class_=AsyncSession)
    return _session_factory


async def init_db():
    from doremi.db import models

    engine = get_engine()

    if _is_in_memory_database(DATABASE_URL):
        async with engine.begin() as conn:
            await conn.run_sync(models.Base.metadata.create_all)
    else:
        await _run_alembic_migrations()

    logger.info("Database initialized")


def _is_in_memory_database(database_url: str) -> bool:
    return ":memory:" in database_url


def _sync_database_url(database_url: str) -> str:
    return database_url.replace("sqlite+aiosqlite://", "sqlite://", 1)


def _alembic_config():
    from alembic.config import Config

    migrations_dir = Path(__file__).resolve().parent / "migrations"
    project_root = Path(__file__).resolve().parents[3]
    config_file = project_root / "alembic.ini"
    config = Config(str(config_file) if config_file.exists() else None)
    config.set_main_option("script_location", str(migrations_dir))
    config.set_main_option("sqlalchemy.url", _sync_database_url(DATABASE_URL))
    return config


async def _run_alembic_migrations() -> None:
    try:
        from alembic import command
    except ImportError:
        logger.warning("Alembic is not installed; falling back to metadata.create_all")
        from doremi.db import models

        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(models.Base.metadata.create_all)
        return

    config = _alembic_config()
    await asyncio.to_thread(command.upgrade, config, "head")

from contextlib import asynccontextmanager


@asynccontextmanager
async def get_session():
    import asyncio
    factory = await get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        try:
            await asyncio.shield(session.close())
        except Exception as e:
            logger.warning(f"Error closing database session: {e}")
