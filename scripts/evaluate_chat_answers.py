"""Read-only, live-data checks for chatbot numbers, scope, and citation integrity.

No conversation or prompt is persisted. Citation relevance still needs reviewer labels.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.models.chat import ChatRequest  # noqa: E402
from api.security import permissions_for_role  # noqa: E402
from api.services import chat_tools  # noqa: E402
from api.services.analytics import _query  # noqa: E402


WINDOWS = {"today": "24 HOUR", "7d": "7 DAY", "30d": "30 DAY"}
SOCIAL_GROUPS = {"voz": ["voz", "voz_forum"], "youtube": ["youtube", "youtube_comments"]}
COUNT_PATTERNS = {
    "article_count": re.compile(r"^Đã thu thập ([\d.]+) bài báo"),
    "social_count": re.compile(r"^Có ([\d.]+) bài đăng/bình luận social duy nhất"),
    "social_records": re.compile(r"Bảng lưu ([\d.]+) bản ghi thu thập"),
}


def validate_cases(cases: object) -> list[dict]:
    if not isinstance(cases, list) or not cases:
        raise ValueError("Expected a nonempty list of live answer cases")
    seen = set()
    for case in cases:
        if not isinstance(case, dict) or not all(
            isinstance(case.get(key), str) and case[key].strip()
            for key in ("id", "message", "oracle", "expected_tool", "expected_time_range")
        ):
            raise ValueError("Each case needs id, message, oracle, expected_tool and expected_time_range")
        if case["id"] in seen:
            raise ValueError("Case IDs must be unique")
        seen.add(case["id"])
        if any(key in case for key in ("source", "category", "query", "compare_sources")):
            raise ValueError(f"{case['id']}: explicit query filters are not supported by this evaluator")
        if case["oracle"] not in ("article_count", "social_count", "article_sources"):
            raise ValueError(f"{case['id']}: unsupported oracle")
        if case["expected_time_range"] not in (*WINDOWS, "all"):
            raise ValueError(f"{case['id']}: unsupported time range")
        if case["oracle"] == "social_count" and case.get("expected_source") not in SOCIAL_GROUPS:
            raise ValueError(f"{case['id']}: social count requires a supported source")
        if case["oracle"] == "article_sources" and case["expected_time_range"] == "all":
            raise ValueError(f"{case['id']}: article search requires a bounded time range")
        if case["oracle"] == "article_sources" and not isinstance(case.get("expect_nonempty"), bool):
            raise ValueError(f"{case['id']}: article search needs an explicit expect_nonempty label")
        if case["oracle"] == "article_count" and re.search(r"\b(?:về|ve|about|liên quan đến)\b", case["message"], re.IGNORECASE):
            raise ValueError(f"{case['id']}: topic-count oracle is not implemented")
        if case.get("role", "user") not in ("user", "analyst", "operator", "admin"):
            raise ValueError(f"{case['id']}: unsupported role")
        relevant = case.get("relevant_article_ids")
        if relevant is not None and (case["oracle"] != "article_sources" or not isinstance(relevant, list)
                                     or not relevant or not all(isinstance(item, str) and item for item in relevant)):
            raise ValueError(f"{case['id']}: relevant_article_ids needs reviewer-labeled article IDs")
    return cases


def _count_snapshot(case: dict) -> tuple[int, int | None]:
    time_range = case["expected_time_range"]
    conditions = []
    params = {}
    if time_range != "all":
        conditions.append(f"publish_time >= now() - INTERVAL {WINDOWS[time_range]}")
    if case["oracle"] == "article_count":
        if case.get("expected_source"):
            conditions.append("source = {source:String}")
            params["source"] = case["expected_source"]
        where = " AND ".join(conditions) or "1 = 1"
        rows = _query(
            "SELECT uniqExact(url_hash) AS actual_count FROM newspulse.raw_articles FINAL "
            f"WHERE {where}", params,
        )
        return int(rows[0]["actual_count"]), None
    conditions.append("source IN {sources:Array(String)}")
    params["sources"] = SOCIAL_GROUPS[case["expected_source"]]
    rows = _query(
        "SELECT uniqExact(source, post_id) AS actual_count, count() AS record_count "
        "FROM newspulse.social_sentiment_metrics WHERE " + " AND ".join(conditions), params,
    )
    return int(rows[0]["actual_count"]), int(rows[0]["record_count"])


def _number(answer: str, pattern: re.Pattern[str]) -> int | None:
    match = pattern.search(answer)
    return int(match.group(1).replace(".", "")) if match else None


def _citation_checks(case: dict, sources: list[dict]) -> dict[str, bool | None]:
    if not sources:
        return {"citations_exist": not case["expect_nonempty"], "citation_integrity": True,
                "reviewed_relevant_hit": None}
    ids = [str(source.get("article_id", "")) for source in sources]
    rows = _query(
        "SELECT url_hash AS article_id, title, url, source, publish_time "
        "FROM newspulse.raw_articles FINAL WHERE url_hash IN {ids:Array(String)}",
        {"ids": ids},
    )
    current = {str(row["article_id"]): row for row in rows}
    cutoff = datetime.now(timezone.utc) - timedelta(
        days={"today": 1, "7d": 7, "30d": 30}[case["expected_time_range"]]
    ) - timedelta(minutes=1)
    integrity = len(ids) == len(set(ids)) and all(
        (row := current.get(article_id)) is not None
        and row["title"] == source["title"]
        and row["url"] == source["url"]
        and row["source"] == source["source"]
        and (not case.get("expected_source") or row["source"] == case["expected_source"])
        and (row["publish_time"].replace(tzinfo=timezone.utc) if row["publish_time"].tzinfo is None
             else row["publish_time"].astimezone(timezone.utc)) >= cutoff
        for article_id, source in zip(ids, sources)
    )
    relevant = case.get("relevant_article_ids")
    return {
        "citations_exist": case["expect_nonempty"],
        "citation_integrity": integrity,
        # Only reviewer-approved IDs can establish relevance; metadata checks cannot.
        "reviewed_relevant_hit": bool(set(ids) & set(relevant)) if relevant is not None else None,
    }


def evaluate_case(case: dict) -> dict:
    before = _count_snapshot(case) if case["oracle"] != "article_sources" else None
    request = ChatRequest(message=case["message"], time_range=case.get("time_range"))
    actor = {"permissions": permissions_for_role(case.get("role", "user"))}
    result = chat_tools.answer_question(request, actor)
    after = _count_snapshot(case) if before is not None else None
    context = result.context or {}
    checks: dict[str, bool | None] = {
        "tool": result.tool == case["expected_tool"],
        "scope": (
            context.get("time_range") == case["expected_time_range"]
            and context.get("source") == case.get("expected_source")
            and not context.get("clarification")
        ),
    }
    if before is not None and after is not None:
        actual_count = _number(result.answer, COUNT_PATTERNS[case["oracle"]])
        checks["factual_number"] = actual_count is not None and min(before[0], after[0]) <= actual_count <= max(before[0], after[0])
        if case["oracle"] == "social_count":
            record_count = _number(result.answer, COUNT_PATTERNS["social_records"])
            checks["record_number"] = record_count is not None and min(before[1], after[1]) <= record_count <= max(before[1], after[1])
    else:
        checks.update(_citation_checks(case, result.sources))
    return {"id": case["id"], "passed": all(value for value in checks.values() if value is not None), "checks": checks}


def evaluate(cases: list[dict]) -> dict:
    results = []
    for case in cases:
        try:
            results.append(evaluate_case(case))
        except Exception as exc:
            results.append({"id": case["id"], "passed": False, "error": type(exc).__name__})
    return {
        "cases": len(results), "passed": sum(row["passed"] for row in results),
        "unreviewed_citation_cases": sum(
            row.get("checks", {}).get("reviewed_relevant_hit", True) is None for row in results
        ),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "eval/chat_answer_live_cases.json")
    args = parser.parse_args()
    cases = validate_cases(json.loads(args.cases.read_text(encoding="utf-8")))
    report = evaluate(cases)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(report["passed"] != report["cases"])


if __name__ == "__main__":
    raise SystemExit(main())
