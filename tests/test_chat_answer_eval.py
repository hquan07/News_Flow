"""Live-data answer checks must catch incorrect figures and fabricated citations."""

from datetime import datetime, timezone

import pytest

from api.services import chat_tools
from scripts import evaluate_chat_answers


ARTICLE_CASE = {
    "id": "count-test", "message": "Tổng số bài báo từ VnExpress",
    "oracle": "article_count", "expected_tool": "count_articles",
    "expected_time_range": "all", "expected_source": "vnexpress",
}


def test_live_case_validation_rejects_unscored_or_duplicate_cases():
    assert evaluate_chat_answers.validate_cases([ARTICLE_CASE]) == [ARTICLE_CASE]
    with pytest.raises(ValueError, match="unique"):
        evaluate_chat_answers.validate_cases([ARTICLE_CASE, ARTICLE_CASE])
    with pytest.raises(ValueError, match="topic-count"):
        evaluate_chat_answers.validate_cases([{**ARTICLE_CASE, "message": "Có bao nhiêu bài báo về AI?"}])
    with pytest.raises(ValueError, match="explicit query filters"):
        evaluate_chat_answers.validate_cases([{**ARTICLE_CASE, "category": "technology"}])


def test_live_count_evaluation_detects_wrong_number_without_persisting_chat(monkeypatch):
    monkeypatch.setattr(evaluate_chat_answers, "_query", lambda *_args: [{"actual_count": 7}])
    monkeypatch.setattr(chat_tools, "_query", lambda *_args: [{"article_count": 7}])
    correct = evaluate_chat_answers.evaluate_case(ARTICLE_CASE)
    assert correct["passed"] is True
    assert correct["checks"]["factual_number"] is True

    monkeypatch.setattr(chat_tools, "_query", lambda *_args: [{"article_count": 8}])
    incorrect = evaluate_chat_answers.evaluate_case(ARTICLE_CASE)
    assert incorrect["passed"] is False
    assert incorrect["checks"]["factual_number"] is False


def test_citation_integrity_needs_real_matching_metadata_and_reviewer_label(monkeypatch):
    case = {
        "id": "citation-test", "message": "Tin mới từ VnExpress",
        "oracle": "article_sources", "expected_tool": "search_articles",
        "expected_time_range": "7d", "expected_source": "vnexpress",
        "expect_nonempty": True,
    }
    source = {"article_id": "article-1", "title": "Tiêu đề", "url": "https://example.com/1", "source": "vnexpress"}
    row = {"article_id": "article-1", "title": "Tiêu đề", "url": "https://example.com/1",
           "source": "vnexpress", "publish_time": datetime.now(timezone.utc)}
    monkeypatch.setattr(evaluate_chat_answers, "_query", lambda *_args: [row])
    checks = evaluate_chat_answers._citation_checks(case, [source])
    assert checks == {"citations_exist": True, "citation_integrity": True, "reviewed_relevant_hit": None}
    assert evaluate_chat_answers._citation_checks({**case, "relevant_article_ids": ["article-1"]}, [source])["reviewed_relevant_hit"] is True
    assert evaluate_chat_answers._citation_checks(case, [{**source, "title": "Sai tiêu đề"}])["citation_integrity"] is False
    assert evaluate_chat_answers._citation_checks(case, [])["citations_exist"] is False


def test_new_phrasings_keep_topic_and_source_separate():
    request = chat_tools.ChatRequest(message="Đọc tin về lãi suất từ VnExpress trong 7 ngày qua")
    plan = chat_tools.plan_question(request)
    assert plan.intent == "articles"
    assert plan.request.source == "vnexpress"
    assert chat_tools._search_term(plan.request) == "lãi suất"
    week = chat_tools.ChatRequest(message="Đọc tin về lãi suất từ VnExpress tuần qua")
    assert chat_tools._search_term(week) == "lãi suất"
    assert chat_tools.plan_question(chat_tools.ChatRequest(message="Có bao nhiêu bình luận social?")).clarification
