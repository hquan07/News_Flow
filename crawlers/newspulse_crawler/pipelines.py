import hashlib
import logging
import re
import boto3

from itemadapter import ItemAdapter
from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError
from scrapy.exceptions import DropItem

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
        if raw_html and url:
            url_hash = hashlib.md5(url.encode()).hexdigest()
            object_name = f"{spider.name}/{url_hash}.html"
            try:
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=object_name,
                    Body=raw_html.encode("utf-8"),
                    ContentType="text/html",
                )
            except Exception as e:
                logger.error("Failed to upload to MinIO: %s", e)
        return item


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
        self.client = MongoClient(self.mongo_uri)
        db = self.client[self.mongo_db]
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
        try:
            self.collection.insert_one(doc)
        except DuplicateKeyError:
            pass
        return item


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
        self.producer.send_article(article)
        return item