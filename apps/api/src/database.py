import uuid
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, func
from datetime import datetime

from src.config import settings

import uuid
import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, func
from datetime import datetime

from src.config import settings

logger = logging.getLogger(__name__)

# Engine configuration
# Handles sqlite (for tests/local dev fallback) and postgresql+asyncpg
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENVIRONMENT == "development",
    future=True,
    connect_args=connect_args
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


async def init_db() -> None:
    global engine, AsyncSessionLocal
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully at %s", settings.DATABASE_URL)
    except Exception as e:
        if settings.ENVIRONMENT == "development" and not settings.DATABASE_URL.startswith("sqlite"):
            logger.warning(
                "Could not connect to PostgreSQL at %s: %s. Falling back to SQLite for local development.",
                settings.DATABASE_URL, e
            )
            fallback_url = "sqlite+aiosqlite:///./codepilot_dev.db"
            engine = create_async_engine(
                fallback_url,
                echo=False,
                future=True,
                connect_args={"check_same_thread": False}
            )
            AsyncSessionLocal = async_sessionmaker(
                bind=engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False
            )
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Initialized local fallback database at %s", fallback_url)
        else:
            raise e


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
