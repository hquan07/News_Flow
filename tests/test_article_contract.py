import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import jsonschema
from kafka.errors import KafkaTimeoutError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "infrastructure"))

from kafka_utils.producer import ArticleProducer  # noqa: E402


def test_producer_event_matches_shared_contract_and_preserves_input():
    source = {
        "url": "https://example.org/news/1",
        "title": "Tin mới",
        "content": "Nội dung",
        "source": "example",
        "category": "tech",
        "crawl_time": "2026-01-02T12:00:00+00:00",
    }
    original = dict(source)
    with patch("kafka_utils.producer.KafkaProducer") as factory:
        factory.return_value.send.return_value.get.return_value = MagicMock(
            topic="news.tech", partition=0, offset=1
        )
        producer = ArticleProducer()
        assert producer.send_article(source)

    assert source == original
    topic = factory.return_value.send.call_args.args[0]
    payload = factory.return_value.send.call_args.kwargs["value"]
    contract = json.loads((ROOT / "contracts" / "article.schema.json").read_text())
    jsonschema.validate(payload, contract)
    assert topic == "news.tech"
    assert payload["crawled_time"] == source["crawl_time"]
    assert payload["event_id"] == factory.return_value.send.call_args.kwargs["key"]


def test_producer_counts_failed_delivery():
    with patch("kafka_utils.producer.KafkaProducer") as factory:
        factory.return_value.send.return_value.get.side_effect = KafkaTimeoutError("timeout")
        producer = ArticleProducer()
        assert not producer.send_article({
            "url": "https://example.org/news/2", "title": "Tin",
            "source": "example", "category": "tech",
        })
        assert producer.failed == 1
        assert producer.published == 0
        assert factory.call_args.kwargs["compression_type"] == "lz4"
        assert factory.call_args.kwargs["acks"] == "all"
