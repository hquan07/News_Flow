"""Retrieval evaluation must use the same ranking as the serving path."""

import pytest

from api.services import rag_retrieval
from scripts import evaluate_chat_retrieval


def test_rank_candidates_deduplicates_chunks_and_fuses_articles():
    hits = [
        {"payload": {"article_id": "vector-1", "text": "first"}},
        {"payload": {"article_id": "vector-1", "text": "second"}},
        {"payload": {"article_id": "shared", "text": "shared excerpt"}},
    ]
    keyword = ["shared", "keyword-1"]
    hybrid, snippets = rag_retrieval.rank_candidate_ids(keyword, hits)
    assert hybrid[0] == "shared"
    assert len(hybrid) == 3
    assert snippets["vector-1"] == "first"
    assert rag_retrieval.rank_candidate_ids(keyword, hits, mode="keyword")[0] == keyword
    assert rag_retrieval.rank_candidate_ids(keyword, hits, mode="vector")[0] == ["vector-1", "shared"]


def test_labeled_relevance_metrics():
    scores = evaluate_chat_retrieval.relevance_scores(["bad", "good", "other"], ["good"])
    assert scores["recall"] == 1.0
    assert 0 < scores["ndcg"] < 1
    with pytest.raises(ValueError):
        evaluate_chat_retrieval.validate_cases([{"id": "missing-labels", "query": "AI"}])


def test_evaluator_rechecks_current_article_scope(monkeypatch):
    monkeypatch.setattr(rag_retrieval, "_keyword_candidates", lambda *_args: ["stale", "current"])
    monkeypatch.setattr(rag_retrieval, "_current_articles", lambda *_args: {"current": {"article_id": "current", "content": "Article body"}})
    cases = evaluate_chat_retrieval.validate_cases([{
        "id": "case-1", "query": "AI", "relevant_article_ids": ["current"], "time_range": "7d",
    }])
    result = evaluate_chat_retrieval.evaluate(cases)
    assert result["modes"]["keyword"]["mean_recall_at_5"] == 1.0
    assert result["modes"]["keyword"]["case_results"][0]["id"] == "case-1"
