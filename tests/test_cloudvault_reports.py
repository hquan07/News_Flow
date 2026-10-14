import json
from datetime import datetime, timezone

import pytest
from bson import ObjectId

from integrations.cloudvault import CloudVaultError
from integrations.cloudvault_reports import (
    owner_reference,
    report_export_payload,
    upload_intelligence_report,
)


class RecordingClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def upload_file(self, path, **kwargs):
        self.calls.append((path.read_text(encoding="utf-8"), kwargs))
        return self.response


def report():
    return {
        "_id": ObjectId("652000000000000000000001"),
        "owner_id": "alice@example.com",
        "saved_query_id": "652000000000000000000002",
        "name": "Morning AI",
        "article_count": 2,
        "created_at": datetime(2026, 10, 14, tzinfo=timezone.utc),
        "cloudvault_archive": {"status": "pending"},
    }


def test_report_payload_redacts_owner_and_archive_state():
    payload = report_export_payload(report(), "alice@example.com")
    assert "owner_id" not in payload
    assert "cloudvault_archive" not in payload
    assert payload["owner_ref"] == owner_reference("alice@example.com")


def test_upload_uses_stable_owner_scoped_idempotency_and_metadata():
    client = RecordingClient({
        "file_id": "file-1",
        "checksum_sha256": "abc",
        "retention_until": "2027-01-12T00:00:00Z",
    })
    result = upload_intelligence_report(
        report(),
        owner_id="alice@example.com",
        logical_date="2026-10-14T00:00:00+00:00",
        source_run_id="scheduled__2026-10-14",
        client=client,
    )

    assert result["file_id"] == "file-1"
    content, kwargs = client.calls[0]
    assert "alice@example.com" not in content
    assert json.loads(content)["name"] == "Morning AI"
    assert kwargs["metadata"]["visibility"] == "owner"
    assert kwargs["metadata"]["owner_ref"] == owner_reference("alice@example.com")
    assert kwargs["idempotency_key"].endswith(
        ":652000000000000000000002:2026-10-14T00:00:00+00:00"
    )


def test_upload_rejects_response_without_file_id():
    with pytest.raises(CloudVaultError) as caught:
        upload_intelligence_report(
            report(),
            owner_id="alice@example.com",
            logical_date="2026-10-14",
            source_run_id="run-1",
            client=RecordingClient({"status": "AVAILABLE"}),
        )
    assert caught.value.code == "INVALID_RESPONSE"
