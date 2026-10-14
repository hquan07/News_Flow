import hashlib
import logging
import re
import time
from datetime import datetime, timedelta, timezone

import boto3

from itemadapter import ItemAdapter
from pymongo import MongoClient, ASCENDING
from pymongo.errors import AutoReconnect, NetworkTimeout
from scrapy.exceptions import DropItem
from twisted.internet.threads import deferToThread

from integrations.cloudvault import CloudVaultClient, CloudVaultError
from integrations.cloudvault_raw_html import (
    RawHtmlArchivePolicy,
    build_archive_record,
    raw_html_object_name,
    upload_raw_html_bytes,
)

logger = logging.getLogger(__name__)


class DedupPipeline:
    def __init__(self):
        self._seen: set[str] = set()

    def process_item(self, item, spider):
        url_hash = hashlib.md5(item["url"].encode()).hexdigest()
        if url_hash in self._seen:
            raise DropItem(f"Duplicate URL: {item['url']}")
        self._seen.add(url_hash)
        return item


class CleanTextPipeline:
    _TAG_RE = re.compile(r"<[^>]+>")
    _MULTI_SPACE = re.compile(r"\s+")

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        content = adapter.get("content", "")
        if content:
            content = self._TAG_RE.sub(" ", content)
            content = self._MULTI_SPACE.sub(" ", content).strip()
            adapter["content"] = content

        title = adapter.get("title", "")
        if title:
            adapter["title"] = self._MULTI_SPACE.sub(" ", title).strip()

        if not adapter.get("title"):
            raise DropItem("Article has no title")
        return item


class FreshnessPipeline:
    """Drop stale news after parsing the article's authoritative publish time."""

    SOCIAL_SPIDERS = {"voz_forum", "youtube_comments", "reddit_vn"}

    def process_item(self, item, spider):
        if spider.name in self.SOCIAL_SPIDERS:
            return item

        adapter = ItemAdapter(item)
        is_fresh = getattr(spider, "_is_fresh_published_at", None)
        if is_fresh and not is_fresh(
            adapter.get("publish_time"), "items/stale_dropped"
        ):
            raise DropItem(f"Stale article: {adapter.get('url', 'unknown')}")
        return item


class MinIOPipeline:
    def __init__(self, endpoint, access_key, secret_key, bucket_name):
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name
        self.s3_client = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            endpoint=crawler.settings.get("MINIO_ENDPOINT", "http://minio:9000"),
            access_key=crawler.settings.get("MINIO_ACCESS_KEY", "admin"),
            secret_key=crawler.settings.get("MINIO_SECRET_KEY", "admin123"),
            bucket_name=crawler.settings.get("MINIO_BUCKET", "raw-html"),
        )

    def open_spider(self, spider):
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )
        try:
            self.s3_client.create_bucket(Bucket=self.bucket_name)
        except Exception:
            pass

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        raw_html = adapter.get("raw_html")
        url = adapter.get("url")
        if not raw_html or not url:
            return item

        deferred = deferToThread(self._upload, raw_html, url, spider.name)
        deferred.addCallback(lambda _result: item)
        return deferred

    def _upload(self, raw_html: str, url: str, spider_name: str) -> None:
        object_name = raw_html_object_name(url, spider_name)
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=object_name,
                Body=raw_html.encode("utf-8"),
                ContentType="text/html",
            )
        except Exception as exc:
            logger.error("Failed to upload to MinIO: %s", exc)


class CloudVaultArchivePipeline:
    """Archive selected HTML while keeping normal crawler persistence independent."""

    def __init__(self, policy, mongo_uri: str, mongo_db: str):
        self.policy = policy
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.client = None
        self.mongo = None
        self.collection = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            policy=RawHtmlArchivePolicy.from_env(),
            mongo_uri=crawler.settings.get("MONGO_URI"),
            mongo_db=crawler.settings.get("MONGO_DB"),
        )

    def open_spider(self, spider):
        if not self.policy.enabled:
            return
        if not self.policy.sources:
            logger.warning("CloudVault raw HTML archive enabled without an allowlisted source")
            return
        self.client = CloudVaultClient.from_env()
        self.mongo = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=3000)
        self.collection = self.mongo[self.mongo_db]["cloudvault_raw_html_archives"]
        self.collection.create_index(
            [("url_sha256", ASCENDING), ("content_sha256", ASCENDING)], unique=True
        )
        self.collection.create_index([("status", ASCENDING), ("next_retry_at", ASCENDING)])
        self.collection.create_index("expires_at", expireAfterSeconds=0)

    def close_spider(self, spider):
        if self.mongo is not None:
            self.mongo.close()

    def process_item(self, item, spider):
        if self.collection is None or self.client is None:
            return item
        adapter = ItemAdapter(item)
        raw_html = adapter.get("raw_html") or ""
        source = str(adapter.get("source") or spider.name)
        size_bytes = len(raw_html.encode("utf-8")) if isinstance(raw_html, str) else len(raw_html)
        if not self.policy.allows(
            source=source,
            category=adapter.get("category"),
            size_bytes=size_bytes,
        ):
            return item
        document = adapter.asdict()
        document["source"] = source
        document["_spider_name"] = spider.name
        deferred = deferToThread(self._archive, document)
        deferred.addCallback(lambda _result: item)
        return deferred

    def _archive(self, item: dict) -> None:
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        selected_today = self.collection.count_documents({
            "selected_at": {"$gte": start_of_day},
            "status": {"$in": ["uploading", "retry_pending", "uploaded"]},
        })
        if selected_today >= self.policy.daily_limit:
            logger.info("CloudVault daily raw HTML archive limit reached")
            return

        record, content = build_archive_record(item, policy=self.policy, now=now)
        result = self.collection.update_one(
            {
                "url_sha256": record["url_sha256"],
                "content_sha256": record["content_sha256"],
            },
            {"$setOnInsert": {**record, "status": "uploading", "attempt_count": 0}},
            upsert=True,
        )
        if result.upserted_id is None:
            return

        key = {"_id": result.upserted_id}
        try:
            uploaded = upload_raw_html_bytes(content, record, client=self.client)
        except CloudVaultError as error:
            self.collection.update_one(key, {"$set": {
                "status": "retry_pending" if error.retriable else "failed",
                "last_error": {
                    "code": error.code,
                    "http_status": error.status_code,
                    "retriable": error.retriable,
                },
                "attempt_count": 1,
                "next_retry_at": now + timedelta(minutes=5),
                "updated_at": now,
            }})
            logger.warning("CloudVault raw HTML archive failed: %s", error.code)
            return
        except Exception:
            self.collection.update_one(key, {"$set": {
                "status": "retry_pending",
                "last_error": {"code": "ARCHIVE_UPLOAD_FAILED", "retriable": True},
                "attempt_count": 1,
                "next_retry_at": now + timedelta(minutes=5),
                "updated_at": now,
            }})
            logger.exception("Unexpected CloudVault raw HTML archive failure")
            return

        self.collection.update_one(key, {"$set": {
            **uploaded,
            "last_error": None,
            "updated_at": now,
        }})


class MongoPipeline:
    def __init__(self, mongo_uri: str, mongo_db: str):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.client = None
        self.collection = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            mongo_uri=crawler.settings.get("MONGO_URI"),
            mongo_db=crawler.settings.get("MONGO_DB"),
        )

    def open_spider(self, spider):
        from pymongo import ASCENDING
        self.client = MongoClient(self.mongo_uri)
        db = self.client[self.mongo_db]
        
        if spider.name in ["voz_forum", "youtube_comments", "reddit_vn"]:
            self.collection = db["raw_social_posts"]
            self.collection.create_index([("url", ASCENDING)], unique=True)
            self.collection.create_index([("crawl_time", ASCENDING)])
            self.collection.create_index([("source", ASCENDING)])
        else:
            self.collection = db["articles_raw"]
            self.collection.create_index([("url", ASCENDING)], unique=True)
            self.collection.create_index([("crawl_time", ASCENDING)])
            self.collection.create_index([("source", ASCENDING), ("category", ASCENDING)])

    def close_spider(self, spider):
        if self.client:
            self.client.close()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        doc = adapter.asdict()
        deferred = deferToThread(self._persist, doc)
        deferred.addCallback(lambda _result: item)
        return deferred

    def _persist(self, doc: dict) -> None:
        for attempt in range(1, 4):
            try:
                result = self.collection.update_one(
                    {"url": doc["url"]},
                    {"$setOnInsert": doc},
                    upsert=True,
                )
                if result.upserted_id is None:
                    logger.debug("Article already persisted: %s", doc["url"])
                break
            except (AutoReconnect, NetworkTimeout):
                if attempt == 3:
                    raise
                time.sleep(0.25 * (2 ** (attempt - 1)))


class KafkaPipeline:
    def __init__(self, bootstrap_servers: str):
        self.bootstrap_servers = bootstrap_servers
        self.producer = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(bootstrap_servers=crawler.settings.get("KAFKA_BOOTSTRAP_SERVERS"))

    def open_spider(self, spider):
        from kafka_utils.producer import ArticleProducer
        self.producer = ArticleProducer(self.bootstrap_servers)

    def close_spider(self, spider):
        if self.producer:
            self.producer.close()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        article = adapter.asdict()
        article.pop("raw_html", None)
        deferred = deferToThread(self._publish, article)
        deferred.addCallback(lambda _result: item)
        return deferred

    def _publish(self, article: dict) -> None:
        if not self.producer.send_article(article):
            raise DropItem(f"Kafka publish failed: {article.get('url', 'unknown')}")
