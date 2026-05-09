"""
Hotel ABC Platform — Database Connection
Async SQLAlchemy engine + session factory.
"""
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData
from app.config import get_settings

settings = get_settings()

# ── Naming convention per Alembic migrations ─────────────────────────────────
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)


class Base(DeclarativeBase):
    metadata = metadata


# ── Engine ────────────────────────────────────────────────────────────────
engine_kwargs = {
    "echo": settings.debug,
    "future": True,
}
if "sqlite" not in settings.database_url:
    engine_kwargs["pool_size"] = settings.database_pool_size
    engine_kwargs["max_overflow"] = settings.database_max_overflow

engine = create_async_engine(
    settings.database_url,
    **engine_kwargs,
)

# ── Session factory ───────────────────────────────────────────────────────
AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    """Dependency injection per FastAPI route handlers."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables():
    """Crea tutte le tabelle (usato solo per test/dev)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
