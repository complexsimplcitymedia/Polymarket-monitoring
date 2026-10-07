"""
Database configuration and session management.

Provides async SQLite connection using SQLAlchemy 2.0 with aiosqlite.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
try:
    from src.backend.config import settings
except ModuleNotFoundError:
    import sys
    from pathlib import Path
    _repo_root = str(Path(__file__).resolve().parents[2])
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    from src.backend.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session.

    Yields:
        AsyncSession: An async database session.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def _add_missing_columns(sync_conn) -> None:
    """Add columns that were introduced after a table was first created."""
    from sqlalchemy import inspect, text

    wanted = {
        "markets": {"outcomes_json": "TEXT"},
        "game_snapshots": {"poly_score": "VARCHAR(20)", "poly_period": "VARCHAR(10)", "poly_elapsed": "VARCHAR(10)",
                           "poly_updated_at": "TIMESTAMP", "ts_score": "VARCHAR(20)", "ts_clock": "VARCHAR(20)",
                           "ts_updated_at": "TIMESTAMP", "poly_ms": "INTEGER", "espn_ms": "INTEGER", "ts_ms": "INTEGER",
                           "ncaa_score": "VARCHAR(20)", "ncaa_clock": "VARCHAR(30)"},
        "alerts": {"status": "VARCHAR(12) DEFAULT 'active' NOT NULL", "retracted_at": "TIMESTAMP", "retract_note": "TEXT"},
    }
    inspector = inspect(sync_conn)
    for table, columns in wanted.items():
        if table not in inspector.get_table_names():
            continue
        existing = {c["name"] for c in inspector.get_columns(table)}
        for name, ddl in columns.items():
            if name not in existing:
                sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


async def init_db() -> None:
    """Initialize the database by creating all tables."""
    async with engine.begin() as conn:
        if "postgresql" in settings.DATABASE_URL:
            from sqlalchemy import text
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)


async def close_db() -> None:
    """Close the database connection."""
    await engine.dispose()
