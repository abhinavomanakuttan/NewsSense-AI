from collections.abc import AsyncGenerator

from sqlalchemy import event as sa_event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool, QueuePool

from app.core.config import settings


def _create_engine():
    url = settings.database_url
    is_sqlite = url.startswith("sqlite")

    if is_sqlite:
        engine = create_async_engine(
            url,
            poolclass=NullPool,
            echo=settings.debug,
            connect_args={"check_same_thread": False},
        )
    elif settings.environment == "development":
        engine = create_async_engine(
            url,
            poolclass=NullPool,
            echo=settings.debug,
        )
    else:
        engine = create_async_engine(
            url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=settings.debug,
        )

    if is_sqlite:

        @sa_event.listens_for(Engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return engine


engine = _create_engine()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables():
    from app.db.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables():
    from app.db.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
