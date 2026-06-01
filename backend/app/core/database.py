"""Async database engine and session factory for VOC360 PostgreSQL."""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import get_settings

_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        s = get_settings()
        _engine = create_async_engine(
            s.voc_database_url,
            pool_size=s.VOC_DB_POOL_SIZE,
            max_overflow=s.VOC_DB_MAX_OVERFLOW,
            pool_pre_ping=True,
            pool_recycle=600,
            echo=False,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _session_factory


async def get_db():
    """FastAPI dependency — yields an async session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def dispose_engine():
    """Call on shutdown to close all connections."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
