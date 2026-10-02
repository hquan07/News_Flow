"""Score real article retrieval against reviewer-labeled article IDs.

This read-only runner does not enable RAG or change serving configuration.
"""

import argparse
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import monotonic


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.services import chat_embed_cache, rag_client, rag_retrieval  # noqa: E402


def relevance_scores(predicted: list[str], relevant: list[str], k: int = 5) -> dict:
    expected = set(relevant)
    top = predicted[:k]
    hits = sum(article_id in expected for article_id in top)
    dcg = sum(1 / math.log2(index + 2) for index, article_id in enumerate(top) if article_id in expected)
    ideal = sum(1 / math.log2(index + 2) for index in range(min(len(expected), k)))
    return {"recall": hits / len(expected), "ndcg": dcg / ideal if ideal else 0.0}


def validate_cases(cases: object) -> list[dict]:
    if not isinstance(cases, list) or not cases:
        raise ValueError("Provide a nonempty list of reviewer-labeled retrieval cases")
    ids = set()
    for case in cases:
        if not isinstance(case, dict) or not all(isinstance(case.get(key), str) and case[key].strip() for key in ("id", "query")):
            raise ValueError("Every case needs a nonempty id and query")
        if case["id"] in ids:
            raise ValueError("Case IDs must be unique")
        ids.add(case["id"])
        if case.get("time_range", "7d") not in ("today", "7d", "30d"):
            raise ValueError("time_range must be today, 7d, or 30d")
        relevant = case.get("relevant_article_ids")
        if not isinstance(relevant, list) or not relevant or not all(isinstance(item, str) and item for item in relevant):
            raise ValueError("Every case needs reviewer-labeled relevant_article_ids")
    return cases


def evaluate(cases: list[dict], *, with_vector: bool = False) -> dict:
    modes = ("keyword", "vector", "hybrid") if with_vector else ("keyword",)
    measurements: dict[str, list[dict]] = {mode: [] for mode in modes}
    for case in cases:
        since = datetime.now(timezone.utc) - timedelta(days=rag_retrieval._DAYS[case.get("time_range", "7d")])
        source, category = case.get("source"), case.get("category")
        started = monotonic()
        keyword_ids = rag_retrieval._keyword_candidates(case["query"], since, source, category)
        keyword_ms = (monotonic() - started) * 1000
        vector_hits = []
        vector_ms = 0.0
        if with_vector:
            started = monotonic()
            vector = chat_embed_cache.query_vector(case["query"][:2000])
            vector_hits = rag_client.query_chunks(vector, source=source, category=category, since=since)
            vector_ms = (monotonic() - started) * 1000
        for mode in modes:
            started = monotonic()
            ranked, _ = rag_retrieval.rank_candidate_ids(keyword_ids, vector_hits, mode=mode)
            valid = rag_retrieval._current_articles(ranked, since, source, category)
            top = [article_id for article_id in ranked if article_id in valid][:5]
            selected = [article_id for article_id in top if (valid[article_id].get("content") or "").strip()]
            checked_ms = (monotonic() - started) * 1000
            scores = relevance_scores(selected, case["relevant_article_ids"])
            measurements[mode].append({
                "id": case["id"], "recall_at_5": round(scores["recall"], 4),
                "ndcg_at_5": round(scores["ndcg"], 4),
                "latency_ms": round(checked_ms + (keyword_ms if mode != "vector" else 0) + (vector_ms if mode != "keyword" else 0), 2),
            })
    return {
        "cases": len(cases), "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "modes": {
            mode: {
                "mean_recall_at_5": round(sum(row["recall_at_5"] for row in rows) / len(rows), 4),
                "mean_ndcg_at_5": round(sum(row["ndcg_at_5"] for row in rows) / len(rows), 4),
                "p95_latency_ms": sorted(row["latency_ms"] for row in rows)[math.ceil(0.95 * len(rows)) - 1],
                "case_results": rows,
            }
            for mode, rows in measurements.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--with-vector", action="store_true", help="Requires running embedding and Qdrant services")
    args = parser.parse_args()
    cases = validate_cases(json.loads(args.cases.read_text(encoding="utf-8")))
    print(json.dumps(evaluate(cases, with_vector=args.with_vector), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
