import random
import logging

from pymongo import MongoClient
from scrapy import Request, signals

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


class RotateUserAgentMiddleware:

    def process_request(self, request, spider):
        request.headers["User-Agent"] = random.choice(USER_AGENTS)


class ExistingUrlFilterMiddleware:
    """Avoid downloading article URLs that were persisted by an earlier run."""

    SOCIAL_SPIDERS = {"voz_forum", "youtube_comments", "reddit_vn"}

    def __init__(self, mongo_uri: str, mongo_db: str, enabled: bool = True):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.enabled = enabled
        self.client = None
        self.seen_urls: set[str] = set()

    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls(
            mongo_uri=crawler.settings.get("MONGO_URI"),
            mongo_db=crawler.settings.get("MONGO_DB"),
            enabled=crawler.settings.getbool("PERSISTENT_DEDUP_ENABLED", True),
        )
        crawler.signals.connect(middleware.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware

    def spider_opened(self, spider):
        if not self.enabled:
            return
        collection_name = (
            "raw_social_posts" if spider.name in self.SOCIAL_SPIDERS else "articles_raw"
        )
        try:
            self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=3000)
            collection = self.client[self.mongo_db][collection_name]
            self.seen_urls = {
                row["url"]
                for row in collection.find(
                    {"source": spider.name, "url": {"$exists": True}},
                    {"_id": 0, "url": 1},
                )
                if row.get("url")
            }
            logger.info(
                "Loaded %d existing URLs for %s", len(self.seen_urls), spider.name
            )
        except Exception as exc:
            logger.warning("Persistent URL dedup unavailable: %s", exc)
            self.seen_urls.clear()

    def spider_closed(self, spider):
        if self.client:
            self.client.close()

    def process_spider_output(self, response, result, spider):
        for output in result:
            if isinstance(output, Request) and output.url in self.seen_urls:
                spider.crawler.stats.inc_value("requests/existing_url_skipped")
                continue
            yield output


class MockProxyMiddleware:
    """Mock proxy rotation for testing"""
    
    PROXIES = [
        "http://mock-proxy-1.local:8080",
        "http://mock-proxy-2.local:8080",
        "http://mock-proxy-3.local:8080",
    ]

    def process_request(self, request, spider):
        proxy = random.choice(self.PROXIES)
        request.meta['proxy'] = proxy
        logger.debug(f"Using mock proxy: {proxy}")
