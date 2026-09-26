from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import clickhouse_connect


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "NewsPulse Insights Dashboard"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    CLICKHOUSE_HOST: str = "clickhouse"
    CLICKHOUSE_PORT: int = 8123
    CLICKHOUSE_DB: str = "newspulse"
    CLICKHOUSE_USER: str = "admin"
    CLICKHOUSE_PASSWORD: str = "admin123"

    MONGO_HOST: str = "localhost"
    MONGO_PORT: int = 27018
    MONGO_DB: str = "newspulse"

    JWT_SECRET_KEY: str = Field(
        min_length=16,
        validation_alias=AliasChoices(
            "JWT_SECRET_KEY",
            "AIRFLOW__WEBSERVER__SECRET_KEY",
        ),
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    CORS_ORIGINS: str = "http://localhost,http://localhost:3000"

    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    SPIKE_THRESHOLD_MULTIPLIER: float = 2.0
    SPIKE_WINDOW_HOURS: int = 6

    @property
    def clickhouse_url(self) -> str:
        return f"http://{self.CLICKHOUSE_HOST}:{self.CLICKHOUSE_PORT}"

    @property
    def mongo_url(self) -> str:
        return f"mongodb://{self.MONGO_HOST}:{self.MONGO_PORT}"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()


def get_ch_client():
    """Return a new ClickHouse client instance per request to avoid concurrency errors."""
    s = get_settings()
    return clickhouse_connect.get_client(
        host=s.CLICKHOUSE_HOST,
        port=s.CLICKHOUSE_PORT,
        username=s.CLICKHOUSE_USER,
        password=s.CLICKHOUSE_PASSWORD,
        database=s.CLICKHOUSE_DB,
    )
