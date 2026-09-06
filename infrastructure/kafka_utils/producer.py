import json
import hashlib
import logging
from datetime import datetime, timezone

from kafka import KafkaProducer
from kafka.errors import KafkaError

from kafka_utils import get_topic

logger = logging.getLogger(__name__)

class ArticleProducer:
    def __init__(self, bootstrap_servers: str = "kafka:9092"):
        self._producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False, default=str).encode('utf-8'),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",
            retries=3,
            max_in_flight_requests_per_connection=1,
            linger_ms=50,
            batch_size=32768,
        )

    def send_article(self, article: dict) -> bool:
        try:
            topic = get_topic(article.get("category", ""))
            key = self._make_key(article["url"])

            if "crawl_time" not in article:
                article["crawl_time"] = datetime.now(timezone.utc).isoformat()

            future = self._producer.send(topic, key=key, value=article)
            record_metadata = future.get(timeout=10)

            logger.info(
                "Published to %s [partition=%d, offset=%d]: %s",
                record_metadata.topic,
                record_metadata.partition,
                record_metadata.offset,
                article.get("title", "")[:60],
            )
            return True
        except KafkaError as e:
            logger.error("Failed to publish article %s: %s", article.get("url"), e)
            return False

    def flush(self):
        self._producer.flush()

    def close(self):
        self._producer.flush()
        self._producer.close()

    @staticmethod
    def _make_key(url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()