import hashlib
import logging
import re

from itemadapter import ItemAdapter
from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError
from scrapy.exceptions import DropItem

logger = logging.getLogger(__name__)

# 1. Dedup
class DedupPipeline:
    def __init__(self):
        self._seen: set[str] = set()

    def process_item(self, item, spider):
        url_hash = hashlib.md5(item["url"].encode()).hexdigest()
        if url_hash in self._seen:
            raise DropItem(f"Duplicate URL: {item['url']}")
        self._seen.add(url_hash)
        return item

# 2. Clean text
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

# 3. MongoDB
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
        # Unique index on URL for cross-session dedup
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
            logger.debug("Saved to MongoDB: %s", doc.get("url"))
        except DuplicateKeyError:
            logger.debug("Already in MongoDB: %s", doc.get("url"))
        return item

# 4. Kafka
class KafkaPipeline:

    def __init__(self, bootstrap_servers: str):
        self.bootstrap_servers = bootstrap_servers
        self.producer = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            bootstrap_servers=crawler.settings.get("KAFKA_BOOTSTRAP_SERVERS"),
        )

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