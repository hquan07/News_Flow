import json
import hashlib
import logging
import requests
from datetime import datetime, timezone
from typing import Optional

from kafka import KafkaProducer
from kafka.errors import KafkaError
from pydantic import BaseModel, HttpUrl, Field, ValidationError

from kafka_utils import get_topic

logger = logging.getLogger(__name__)

class ArticleSchema(BaseModel):
    url: str
    title: str = Field(..., min_length=5)
    content: str = Field(..., min_length=100)
    author: Optional[str] = None
    publish_time: Optional[str] = None
    crawled_time: Optional[str] = None
    source: str
    category: str

class ArticleProducer:
    def __init__(self, bootstrap_servers: str = "kafka:9092", schema_registry_url: str = "http://schema-registry:8081"):
        self.bootstrap_servers = bootstrap_servers
        self.schema_registry_url = schema_registry_url
        
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
        
        # Đăng ký Schema với Schema Registry (nếu registry đang chạy)
        self._register_schema()

    def _register_schema(self):
        try:
            # Lấy JSON Schema chuẩn từ Pydantic
            schema_dict = ArticleSchema.model_json_schema()
            payload = {
                "schemaType": "JSON",
                "schema": json.dumps(schema_dict)
            }
            # Đăng ký schema cho subject "news-value"
            res = requests.post(
                f"{self.schema_registry_url}/subjects/news-value/versions",
                json=payload,
                timeout=5
            )
            if res.status_code == 200:
                logger.info("Successfully registered JSON Schema to Confluent Schema Registry.")
            else:
                logger.warning(f"Failed to register schema: {res.text}")
        except Exception as e:
            logger.warning(f"Could not connect to Schema Registry at {self.schema_registry_url}: {e}")

    def send_article(self, article: dict) -> bool:
        try:
            # Data Quality Guard: Validate trước khi gửi
            if "crawl_time" not in article and "crawled_time" not in article:
                article["crawled_time"] = datetime.now(timezone.utc).isoformat()
            
            # Đổi key crawl_time thành crawled_time cho khớp schema (nếu có)
            if "crawl_time" in article:
                article["crawled_time"] = article.pop("crawl_time")

            # Validate bằng Pydantic (Đảm bảo chuẩn Schema)
            valid_article = ArticleSchema(**article)
            
            topic = get_topic(valid_article.category)
            key = self._make_key(valid_article.url)

            future = self._producer.send(topic, key=key, value=valid_article.model_dump())
            record_metadata = future.get(timeout=10)

            logger.info(
                "Published to %s [partition=%d, offset=%d]: %s",
                record_metadata.topic,
                record_metadata.partition,
                record_metadata.offset,
                valid_article.title[:60],
            )
            return True
        except ValidationError as ve:
            logger.error("Data Quality Error: Article failed schema validation %s: %s", article.get("url"), ve)
            return False
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