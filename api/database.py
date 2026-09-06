from motor.motor_asyncio import AsyncIOMotorClient
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from api.config import get_settings

settings = get_settings()

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
    await close_mongo()