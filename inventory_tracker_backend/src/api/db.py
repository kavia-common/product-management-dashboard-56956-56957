import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def _coerce_postgres_url_to_async(url: str) -> str:
    """
    Convert a PostgreSQL URL to an asyncpg-compatible SQLAlchemy URL.

    Accepts:
      - postgresql://user:pass@host:port/db
      - postgres://user:pass@host:port/db

    Returns:
      - postgresql+asyncpg://user:pass@host:port/db
    """
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def get_database_url() -> str:
    """
    Resolve the database connection URL from environment variables.

    The DB container provides a canonical connection string in:
      product-management-dashboard-56956-56958/inventory_tracker_db/db_connection.txt

    For this backend, provide it via one of:
      - DATABASE_URL (preferred)
      - POSTGRES_URL (fallback)

    NOTE: Do not hardcode connection strings in source code.
    """
    url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if not url:
        raise RuntimeError(
            "Database URL not configured. Set DATABASE_URL (preferred) or POSTGRES_URL "
            "to the value from inventory_tracker_db/db_connection.txt."
        )
    return _coerce_postgres_url_to_async(url)


_engine = create_async_engine(get_database_url(), pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an AsyncSession.
    """
    async with AsyncSessionLocal() as session:
        yield session
