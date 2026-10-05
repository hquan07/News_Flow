import json
import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from kafka import KafkaProducer
from kafka.errors import KafkaError
from pydantic import BaseModel, Field, ValidationError

from kafka_utils import get_topic

logger = logging.getLogger(__name__)
KAFKA_DLQ_TOPIC = os.getenv("KAFKA_DLQ_TOPIC", "newspulse.dlq")

class ArticleSchema(BaseModel):
    schema_version: int = 1
    event_type: str = "article"
    event_id: str
    url: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    content: str = ""
    author: Optional[str] = None
    publish_time: Optional[str] = None
    crawled_time: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)

    model_config = {
        "extra": "allow"
    }

class ArticleProducer:
    def __init__(self, bootstrap_servers: str = "kafka:9092"):
        self.bootstrap_servers = bootstrap_servers
        self.published = 0
        self.failed = 0
        self.dead_lettered = 0
        self.delivery_timeout_seconds = int(os.getenv("KAFKA_DELIVERY_TIMEOUT_SECONDS", "120"))
        
        self._producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False, default=str).encode('utf-8'),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",
            retries=10,
            retry_backoff_ms=500,
            request_timeout_ms=30000,
            max_block_ms=30000,
            max_in_flight_requests_per_connection=1,
            linger_ms=20,
            batch_size=32768,
            compression_type="lz4",
        )
        
    def send_article(self, article: dict) -> bool:
        try:
            article = dict(article)
            # Data Quality Guard: Validate trước khi gửi
            if "crawl_time" in article:
                article["crawled_time"] = article.pop("crawl_time")
            if not article.get("crawled_time"):
                article["crawled_time"] = datetime.now(timezone.utc).isoformat()
            article["event_id"] = self._make_key(str(article.get("url", "")))

            # Validate bằng Pydantic (Đảm bảo chuẩn Schema)
            valid_article = ArticleSchema(**article)
            
            topic = get_topic(valid_article.category)
            key = valid_article.event_id

            future = self._producer.send(topic, key=key, value=valid_article.model_dump())
            record_metadata = future.get(timeout=self.delivery_timeout_seconds)
            self.published += 1

            logger.info(
                "Published to %s [partition=%d, offset=%d]: %s",
                record_metadata.topic,
                record_metadata.partition,
                record_metadata.offset,
                valid_article.title[:60],
            )
            return True
        except ValidationError as ve:
            self.failed += 1
            logger.error("Data Quality Error: Article failed schema validation %s: %s", article.get("url"), ve)
            self._send_dead_letter(article, "schema_validation", str(ve))
            return False
        except (KafkaError, TimeoutError) as e:
            self.failed += 1
            logger.error("Failed to publish article %s: %s", article.get("url"), e)
            return False

    def _send_dead_letter(self, article: dict, reason: str, error: str) -> None:
        """Preserve invalid payloads that reached a healthy Kafka broker."""
        try:
            url = str(article.get("url", ""))
            self._producer.send(
                KAFKA_DLQ_TOPIC,
                key=self._make_key(url) if url else None,
                value={
                    "reason": reason,
                    "error": error,
                    "payload": article,
                    "failed_at": datetime.now(timezone.utc).isoformat(),
                },
            ).get(timeout=self.delivery_timeout_seconds)
            self.dead_lettered += 1
        except Exception:
            logger.exception("Failed to publish invalid payload to DLQ")

    def flush(self):
        self._producer.flush()

    def close(self):
        self._producer.flush()
        self._producer.close()
        logger.info(
            "Article producer totals: published=%d failed=%d dead_lettered=%d",
            self.published, self.failed, self.dead_lettered,
        )

    @staticmethod
    def _make_key(url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
