import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

# Fallback to local async sqlite if DATABASE_URL is not provided
# Note: For async sqlite, we must use sqlite+aiosqlite
_default_url = "sqlite+aiosqlite:///veetrack_local.db"
DATABASE_URL = os.getenv("DATABASE_URL", _default_url)

# If it's Postgres, use asyncpg and connection pooling
if DATABASE_URL.startswith("postgresql"):
    # Ensure it's using the asyncpg driver
    if "postgresql+asyncpg" not in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        echo=False,
    )
else:
    # SQLite cannot handle connection pooling the same way
    engine = create_async_engine(
        DATABASE_URL,
        poolclass=NullPool,
        echo=False,
    )

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI endpoints."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
