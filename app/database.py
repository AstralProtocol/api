"""Database utilities for the Astral API."""

import os
from typing import AsyncGenerator, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Get database URL from environment variable or use a default for development
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost/astral"
)

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query logging
    pool_pre_ping=True,  # Check connection before using from pool
    pool_size=10,  # Maximum number of connections in the pool
    max_overflow=20,  # Maximum number of connections beyond pool_size
)

# Create async session factory
async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session.

    This function creates a new SQLAlchemy AsyncSession that can be used
    as a dependency in FastAPI endpoints.

    Yields:
        AsyncSession: SQLAlchemy async session
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Type for session factory
SessionFactory = Callable[[], AsyncGenerator[AsyncSession, None]]
