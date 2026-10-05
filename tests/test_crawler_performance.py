from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from types import SimpleNamespace
import sys

from scrapy import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "crawlers"))

from newspulse_crawler.middlewares import ExistingUrlFilterMiddleware
from newspulse_crawler.spiders.vnexpress import VnExpressSpider
from newspulse_crawler import setting


class _Settings:
    def __init__(self, max_age_hours: float):
        self.max_age_hours = max_age_hours

    def getfloat(self, _name: str, _default: float) -> float:
        return self.max_age_hours


class _Stats:
    def __init__(self):
        self.values = {}

    def inc_value(self, key: str):
        self.values[key] = self.values.get(key, 0) + 1


def _spider(max_age_hours: float = 6.0):
    spider = VnExpressSpider()
    spider.crawler = SimpleNamespace(
        settings=_Settings(max_age_hours),
        stats=_Stats(),
    )
    return spider


def test_rss_filter_rejects_stale_entries():
    spider = _spider()
    stale = format_datetime(datetime.now(timezone.utc) - timedelta(hours=7))

    assert spider._is_fresh_rss_item(stale) is False
    assert spider.crawler.stats.values["rss_items/stale_skipped"] == 1


def test_rss_filter_keeps_recent_and_unparseable_entries():
    spider = _spider()
    recent = format_datetime(datetime.now(timezone.utc) - timedelta(minutes=30))

    assert spider._is_fresh_rss_item(recent) is True
    assert spider._is_fresh_rss_item("unknown date") is True


def test_existing_url_filter_drops_only_persisted_requests():
    middleware = ExistingUrlFilterMiddleware("mongodb://unused", "newspulse")
    middleware.seen_urls = {"https://example.com/existing.html"}
    spider = _spider()
    existing = Request("https://example.com/existing.html")
    new = Request("https://example.com/new.html")

    output = list(
        middleware.process_spider_output(None, [existing, new, {"item": True}], spider)
    )

    assert output == [new, {"item": True}]
    assert spider.crawler.stats.values["requests/existing_url_skipped"] == 1


def test_mongo_marks_completion_only_after_kafka_publish():
    pipelines = setting.ITEM_PIPELINES

    assert pipelines["newspulse_crawler.pipelines.KafkaPipeline"] < pipelines[
        "newspulse_crawler.pipelines.MongoPipeline"
    ]
