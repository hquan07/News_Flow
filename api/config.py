from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # App
    APP_NAME: str = "NewsPulse Insights Dashboard"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # PostgreSQL (warehouse)
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "newspulse"
    POSTGRES_USER: str = "newspulse"
    POSTGRES_PASSWORD: str = "newspulse"

    # MongoDB (raw storage - for CRUD reads)
    MONGO_HOST: str = "localhost"
    MONGO_PORT: int = 27018
    MONGO_DB: str = "newspulse"

    # Pagination defaults
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # Spike detection
    SPIKE_THRESHOLD_MULTIPLIER: float = 2.0
    SPIKE_WINDOW_HOURS: int = 6

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def postgres_async_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def mongo_url(self) -> str:
        return f"mongodb://{self.MONGO_HOST}:{self.MONGO_PORT}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
import psycopg2

def get_pg_connection():
    s = get_settings()
    return psycopg2.connect(
        host=s.POSTGRES_HOST,
        port=s.POSTGRES_PORT,
        dbname=s.POSTGRES_DB,
        user=s.POSTGRES_USER,
        password=s.POSTGRES_PASSWORD,
    )


import psycopg2

def get_pg_connection():
    s = get_settings()
    return psycopg2.connect(
        host=s.POSTGRES_HOST,
        port=s.POSTGRES_PORT,
        dbname=s.POSTGRES_DB,
        user=s.POSTGRES_USER,
        password=s.POSTGRES_PASSWORD,
    )
