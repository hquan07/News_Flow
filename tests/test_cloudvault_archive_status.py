from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from bson import ObjectId

from api.routers import crawler_admin
from tests.test_chat_foundation import _Collection


@pytest.mark.asyncio
async def test_archive_status_is_filterable_and_redacts_storage_details(monkeypatch):
    collection = _Collection()
    collection.documents = [
        {
            "_id": ObjectId(),
            "source": "vnexpress",
            "category": "technology",
            "canonical_url": "https://vnexpress.net/ai",
            "status": "retry_pending",
            "attempt_count": 2,
            "last_error": {"code": "NETWORK_ERROR", "retriable": True},
            "local_bucket": "raw-html",
            "local_object_key": "vnexpress/secret.html",
            "selected_at": datetime(2026, 10, 14, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 10, 14, tzinfo=timezone.utc),
            "expires_at": datetime(2026, 10, 28, tzinfo=timezone.utc),
        },
        {
            "_id": ObjectId(),
            "source": "tuoitre",
            "status": "uploaded",
            "attempt_count": 1,
            "updated_at": datetime(2026, 10, 13, tzinfo=timezone.utc),
        },
    ]
    database = SimpleNamespace(cloudvault_raw_html_archives=collection)
    monkeypatch.setattr(crawler_admin, "get_mongo_db", lambda: database)

    response = await crawler_admin.cloudvault_archive_status(
        status="retry_pending", limit=50, user={}
    )

    assert len(response["archives"]) == 1
    archive = response["archives"][0]
    assert archive["last_error"]["code"] == "NETWORK_ERROR"
    assert "local_bucket" not in archive
    assert "local_object_key" not in archive
