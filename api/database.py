from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from motor.motor_asyncio import AsyncIOMotorClient
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from api.config import get_settings

settings = get_settings()

# PostgreSQL (warehouse)
engine = create_async_engine(
    settings.postgres_async_url,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_pg_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


# MongoDB (raw storage)
_mongo_client: AsyncIOMotorClient | None = None

def get_mongo_client() -> AsyncIOMotorClient:
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = AsyncIOMotorClient(settings.mongo_url)
    return _mongo_client


def get_mongo_db():
    return get_mongo_client()[settings.MONGO_DB]

async def close_mongo():
    global _mongo_client
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None


# Lifecycle
@asynccontextmanager
async def lifespan_db():
    yield
    await engine.dispose()
    await close_mongo()