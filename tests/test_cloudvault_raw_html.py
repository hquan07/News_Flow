from datetime import datetime, timezone

import pytest

from integrations.cloudvault import CloudVaultError
from integrations.cloudvault_raw_html import (
    RawHtmlArchivePolicy,
    build_archive_record,
    canonicalize_url,
    raw_html_object_name,
    upload_raw_html_bytes,
)


class RecordingClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def upload_file(self, path, **kwargs):
        self.calls.append((path.read_bytes(), kwargs))
        return self.response


def policy(**overrides):
    values = {
        "enabled": True,
        "sources": frozenset({"vnexpress"}),
        "categories": frozenset({"technology"}),
        "max_bytes": 1024,
        "daily_limit": 10,
        "retention_days": 14,
    }
    values.update(overrides)
    return RawHtmlArchivePolicy(**values)


def article():
    return {
        "url": "HTTPS://VNEXPRESS.NET:443/ai?id=1#comments",
        "source": "vnexpress",
        "category": "technology",
        "raw_html": "<html>AI</html>",
        "crawl_time": datetime(2026, 10, 14, 8, 0, tzinfo=timezone.utc),
    }


def test_policy_requires_feature_flag_source_category_and_size():
    selected = policy()
    assert selected.allows(source="VNEXPRESS", category="Technology", size_bytes=20)
    assert not selected.allows(source="tuoitre", category="technology", size_bytes=20)
    assert not selected.allows(source="vnexpress", category="business", size_bytes=20)
    assert not selected.allows(source="vnexpress", category="technology", size_bytes=2048)
    assert not policy(enabled=False).allows(
        source="vnexpress", category="technology", size_bytes=20
    )


def test_archive_record_uses_canonical_url_sha256_and_legacy_minio_key():
    record, content = build_archive_record(
        article(),
        policy=policy(),
        now=datetime(2026, 10, 14, tzinfo=timezone.utc),
    )
    assert canonicalize_url(article()["url"]) == "https://vnexpress.net/ai?id=1"
    assert record["canonical_url"] == "https://vnexpress.net/ai?id=1"
    assert record["local_object_key"] == raw_html_object_name(
        article()["url"], "vnexpress"
    )
    assert record["logical_date"] == "2026-10-14"
    assert content == b"<html>AI</html>"
    assert record["idempotency_key"].endswith(record["content_sha256"])


def test_upload_raw_html_sets_required_metadata_and_returns_file_id():
    record, content = build_archive_record(article(), policy=policy())
    client = RecordingClient({"file_id": "file-html", "checksum_sha256": "abc"})
    result = upload_raw_html_bytes(content, record, client=client)

    assert result["file_id"] == "file-html"
    uploaded, kwargs = client.calls[0]
    assert uploaded == content
    assert kwargs["metadata"]["artifact_type"] == "selected_raw_html"
    assert kwargs["metadata"]["retention_class"] == "raw_html"
    assert kwargs["idempotency_key"] == record["idempotency_key"]


def test_upload_raw_html_requires_file_id_response():
    record, content = build_archive_record(article(), policy=policy())
    with pytest.raises(CloudVaultError) as caught:
        upload_raw_html_bytes(content, record, client=RecordingClient({}))
    assert caught.value.code == "INVALID_RESPONSE"
