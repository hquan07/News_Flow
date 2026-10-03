from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.services import briefing_service, scheduled_reports
from tests.test_chat_foundation import _Collection


def test_citation_summary_preserves_excerpts_and_citation_numbers():
    answer = "Các đoạn liên quan:\n[1] Article one: verified excerpt\n[2] Article two: another excerpt\nĐây là trích đoạn"
    result = briefing_service.citation_summary(answer, [
        {"article_id": "a"}, {"article_id": "b"},
    ])
    assert "verified excerpt [1]" in result
    assert "another excerpt [2]" in result
    assert "giữ nguyên nội dung nguồn" in result


def test_event_briefing_contains_timeline_and_citations(monkeypatch):
    published = datetime(2026, 10, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(briefing_service, "event_detail", lambda *_args, **_kwargs: {
        "title": "Event", "article_count": 2, "duplicate_count": 1,
        "sources": ["one", "two"], "articles": [
            {"article_id": "a", "title": "First", "url": "https://example.com/a", "source": "one", "published_at": published},
            {"article_id": "b", "title": "Second", "url": "https://example.com/b", "source": "two", "published_at": published},
        ],
    })
    responses = iter([
        [{"label": "neutral", "count": 2}],
        [{"keyword": "AI", "article_count": 2}],
    ])
    monkeypatch.setattr(briefing_service, "_query", lambda *_args, **_kwargs: next(responses))
    result = briefing_service.event_briefing("event-id")
    assert len(result["timeline"]) == len(result["citations"]) == 2
    assert result["timeline"][0]["citation"] == 1
    assert result["generated_from"] == "warehouse facts and extractive metadata"


@pytest.mark.asyncio
async def test_saved_query_report_has_chart_and_citations(monkeypatch):
    database = SimpleNamespace(intelligence_reports=_Collection())
    monkeypatch.setattr(scheduled_reports, "get_mongo_db", lambda: database)

    async def fake_item(_kind, owner_id, item_id):
        assert owner_id == "alice" and item_id == "query-id"
        return {"id": item_id, "name": "AI report", "query": "AI", "source": None, "category": None, "entity": None, "keyword": None, "sentiment": None}

    monkeypatch.setattr(scheduled_reports, "get_item", fake_item)
    monkeypatch.setattr(scheduled_reports, "_report_data", lambda _query: {
        "article_count": 4, "source_count": 2,
        "chart": {"type": "bar", "title": "Articles by source", "unit": "articles", "points": [{"label": "one", "value": 4}]},
        "citations": [{"article_id": "a", "title": "AI", "url": "https://example.com/a", "source": "one"}],
    })
    report = await scheduled_reports.generate("alice", "query-id")
    assert report["article_count"] == 4
    assert report["chart"]["points"][0]["value"] == 4
    assert report["citations"][0]["article_id"] == "a"
    with pytest.raises(HTTPException) as error:
        await scheduled_reports.delete_report("bob", report["id"])
    assert error.value.status_code == 404
    await scheduled_reports.delete_report("alice", report["id"])
    assert database.intelligence_reports.documents == []
