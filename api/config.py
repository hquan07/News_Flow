from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import clickhouse_connect
from clickhouse_connect import common as clickhouse_common


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

    CLICKHOUSE_HOST: str = "localhost"
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
    CLICKHOUSE_QUERY_RETRIES: int = 3
    CLICKHOUSE_QUERY_TIMEOUT_SECONDS: int = 10
    RETRY_BASE_DELAY_SECONDS: float = 0.2
    RETRY_MAX_DELAY_SECONDS: float = 2.0
    RETRY_JITTER_SECONDS: float = 0.1
    CLICKHOUSE_MAX_CONCURRENCY: int = 8
    CLICKHOUSE_ACQUIRE_TIMEOUT_SECONDS: float = 1.0
    CLICKHOUSE_CIRCUIT_FAILURE_THRESHOLD: int = 5
    CLICKHOUSE_CIRCUIT_RECOVERY_SECONDS: float = 15.0
    HEALTHCHECK_TIMEOUT_SECONDS: float = 3.0
    SSE_ALERT_CACHE_SECONDS: float = 5.0
    SSE_HEARTBEAT_SECONDS: float = 5.0
    SSE_RETRY_MILLISECONDS: int = 5000
    SSE_MAX_CONNECTIONS_PER_WORKER: int = 80
    API_RATE_LIMIT_PER_MINUTE: int = 120
    API_MAX_BODY_BYTES: int = 1_048_576

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_ALLOWED_CHAT_IDS: str = ""
    TELEGRAM_ALLOWED_USER_IDS: str = ""
    TELEGRAM_POLL_TIMEOUT_SECONDS: int = 25
    TELEGRAM_RATE_LIMIT_PER_MINUTE: int = 20
    TELEGRAM_AUDIT_RETENTION_DAYS: int = 90

    RAG_ENABLED: bool = False
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "newspulse_article_chunks_v1"
    EMBEDDING_URL: str = "http://localhost:8088"
    RAG_TIMEOUT_SECONDS: float = 8.0
    CHAT_RATE_LIMIT_PER_MINUTE: int = 20
    CHAT_EMBED_CACHE_TTL_SECONDS: int = 120
    CHAT_EMBED_CACHE_MAX_ITEMS: int = 256

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

    @property
    def telegram_allowed_chat_ids(self) -> set[int]:
        values = self.TELEGRAM_ALLOWED_CHAT_IDS
        if self.TELEGRAM_CHAT_ID:
            values = f"{values},{self.TELEGRAM_CHAT_ID}"
        return _parse_integer_set(values)

    @property
    def telegram_allowed_user_ids(self) -> set[int]:
        return _parse_integer_set(self.TELEGRAM_ALLOWED_USER_IDS)


def _parse_integer_set(value: str) -> set[int]:
    result = set()
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            result.add(int(item))
        except ValueError as exc:
            raise ValueError(f"Expected a comma-separated integer list, got {item!r}") from exc
    return result


@lru_cache()
def get_settings() -> Settings:
    return Settings()


@lru_cache()
def get_ch_client():
    """Return a singleton ClickHouse client instance to prevent FD leak."""
    s = get_settings()
    # ClickHouse sessions reject concurrent queries. The shared HTTP client is
    # safe to reuse when requests do not share a server-side session.
    clickhouse_common.set_setting("autogenerate_session_id", False)
    return clickhouse_connect.get_client(
        host=s.CLICKHOUSE_HOST,
        port=s.CLICKHOUSE_PORT,
        username=s.CLICKHOUSE_USER,
        password=s.CLICKHOUSE_PASSWORD,
        database=s.CLICKHOUSE_DB,
        connect_timeout=s.HEALTHCHECK_TIMEOUT_SECONDS,
        send_receive_timeout=s.CLICKHOUSE_QUERY_TIMEOUT_SECONDS,
        query_retries=0,
        client_name="newspulse-api",
    )


def close_ch_client() -> None:
    """Close and evict the process-wide ClickHouse client at shutdown only."""
    if get_ch_client.cache_info().currsize == 0:
        return
    client = get_ch_client()
    try:
        client.close()
    finally:
        get_ch_client.cache_clear()
