from datetime import datetime, timezone
from types import SimpleNamespace

from crawlers.newspulse_crawler import pipelines
from integrations.cloudvault import CloudVaultError
from integrations.cloudvault_raw_html import RawHtmlArchivePolicy


class FakeCollection:
    def __init__(self):
        self.document = None

    def count_documents(self, _query):
        return 0

    def update_one(self, query, update, upsert=False):
        if upsert:
            self.document = dict(update["$setOnInsert"])
            self.document["_id"] = "archive-1"
            return SimpleNamespace(upserted_id="archive-1")
        assert query == {"_id": "archive-1"}
        self.document.update(update["$set"])
        return SimpleNamespace(upserted_id=None)


def archive_pipeline():
    instance = pipelines.CloudVaultArchivePipeline(
        RawHtmlArchivePolicy(
            enabled=True,
            sources=frozenset({"vnexpress"}),
            categories=frozenset(),
            max_bytes=1024,
            daily_limit=10,
            retention_days=14,
        ),
        "mongodb://mongo:27017",
        "newspulse",
    )
    instance.collection = FakeCollection()
    instance.client = object()
    return instance


def article():
    return {
        "url": "https://vnexpress.net/ai",
        "source": "vnexpress",
        "category": "technology",
        "raw_html": "<html>AI</html>",
        "crawl_time": datetime(2026, 10, 14, tzinfo=timezone.utc),
    }


def test_archive_pipeline_records_success_without_changing_crawler_item(monkeypatch):
    instance = archive_pipeline()
    monkeypatch.setattr(
        pipelines,
        "upload_raw_html_bytes",
        lambda *_args, **_kwargs: {"status": "uploaded", "file_id": "file-1"},
    )

    instance._archive(article())

    assert instance.collection.document["status"] == "uploaded"
    assert instance.collection.document["file_id"] == "file-1"


def test_archive_pipeline_queues_transient_failure(monkeypatch):
    instance = archive_pipeline()

    def fail(*_args, **_kwargs):
        raise CloudVaultError("down", code="NETWORK_ERROR", retriable=True)

    monkeypatch.setattr(pipelines, "upload_raw_html_bytes", fail)
    instance._archive(article())

    assert instance.collection.document["status"] == "retry_pending"
    assert instance.collection.document["last_error"]["code"] == "NETWORK_ERROR"
    assert instance.collection.document["attempt_count"] == 1


def test_archive_pipeline_marks_non_retriable_failure(monkeypatch):
    instance = archive_pipeline()

    def fail(*_args, **_kwargs):
        raise CloudVaultError(
            "denied", status_code=403, code="PROJECT_ACCESS_DENIED", retriable=False
        )

    monkeypatch.setattr(pipelines, "upload_raw_html_bytes", fail)
    instance._archive(article())

    assert instance.collection.document["status"] == "failed"
    assert instance.collection.document["last_error"]["retriable"] is False
