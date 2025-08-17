"""
Database configuration with SQLAlchemy and Alembic.
Provides async database support with connection pooling.
"""

from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Generator

from ..core.config import get_settings

settings = get_settings()

# Database URL
DATABASE_URL = settings.get_database_url(async_mode=True)
SYNC_DATABASE_URL = settings.get_database_url(async_mode=False)

# Async engine
async_engine = create_async_engine(
    DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=3600
) if DATABASE_URL else None

# Sync engine for migrations
sync_engine = create_engine(
    SYNC_DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True
) if SYNC_DATABASE_URL else None

# Session factories
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
) if async_engine else None

SessionLocal = sessionmaker(
    sync_engine,
    autocommit=False,
    autoflush=False
) if sync_engine else None

# Base class for models
Base = declarative_base()
metadata = MetaData()

# Dependency for FastAPI
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session."""
    if not AsyncSessionLocal:
        raise RuntimeError("Database not configured")
    
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

def get_sync_db() -> Generator[Session, None, None]:
    """Get sync database session for migrations."""
    if not SessionLocal:
        raise RuntimeError("Database not configured")
    
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

async def init_db():
    """Initialize database tables."""
    if async_engine:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

async def close_db():
    """Close database connections."""
    if async_engine:
        await async_engine.dispose()