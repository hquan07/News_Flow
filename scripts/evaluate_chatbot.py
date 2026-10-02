"""Run reproducible chatbot routing checks, optionally against a live API.

Offline mode checks intent and role contracts without database services. Live mode
uses a caller-supplied JWT and reports tool/status mismatches without printing answers.
"""

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.security import permissions_for_role  # noqa: E402
from api.models.chat import ChatRequest  # noqa: E402
from api.services.chat_tools import plan_question  # noqa: E402


TOOL_FOR_INTENT = {
    "articles": "search_articles",
    "article_count": "count_articles",
    "social_count": "count_social_posts",
    "trending": "get_trending_keywords",
    "sentiment": "get_sentiment_distribution",
    "sources": "compare_sources",
    "entities": "get_entities",
    "alerts": "get_volume_alerts",
    "rag": "search_article_content",
}


def expected_status(case: dict) -> int:
    return case.get("expected_status", 200)


def _request(case: dict) -> ChatRequest:
    return ChatRequest(**{
        field: case[field]
        for field in ("message", "time_range", "source", "category", "query", "compare_sources")
        if field in case
    })


def _tool(plan) -> str | None:
    return "clarify_scope" if plan.clarification else TOOL_FOR_INTENT.get(plan.intent)


def evaluate_offline(cases: list[dict]) -> list[str]:
    failures = []
    for index, case in enumerate(cases, 1):
        label = case.get("id", f"case {index}")
        plan = plan_question(_request(case))
        actual_tool = _tool(plan)
        if actual_tool != case.get("expected_tool"):
            failures.append(f"{label}: expected {case.get('expected_tool')}, got {actual_tool}")
        for key, actual in (
            ("expected_time_range", plan.time_range),
            ("expected_source", plan.request.source),
            ("expected_category", plan.request.category),
            ("expected_compare_sources", plan.compare_sources),
            ("needs_clarification", bool(plan.clarification)),
        ):
            if key in case and actual != case[key]:
                failures.append(f"{label}: {key} expected {case[key]}, got {actual}")
        needed = "alerts.read" if plan.intent == "alerts" else "dashboard.read" if plan.intent else None
        allowed = needed is None or needed in permissions_for_role(case["role"])
        if allowed != (expected_status(case) == 200):
            failures.append(f"{label}: permission expectation does not match role")
    return failures


def evaluate_live(cases: list[dict], base_url: str, tokens: dict[str, str]) -> list[str]:
    import httpx

    failures = []
    with httpx.Client(timeout=15) as client:
        for index, case in enumerate(cases, 1):
            token = tokens.get(case["role"])
            if not token:
                failures.append(f"case {index}: missing token for role {case['role']}")
                continue
            try:
                response = client.post(
                    base_url.rstrip("/") + "/api/v1/chat",
                    headers={"Authorization": f"Bearer {token}"},
                    json=_request(case).model_dump(exclude_none=True),
                )
            except httpx.HTTPError as exc:
                failures.append(f"case {index}: request failed ({type(exc).__name__})")
                continue
            target_status = expected_status(case)
            if response.status_code != target_status:
                failures.append(f"case {index}: expected HTTP {target_status}, got {response.status_code}")
                continue
            if response.status_code == 200:
                result = response.json()
                if result.get("tool") != case.get("expected_tool"):
                    failures.append(f"case {index}: wrong tool")
                context = result.get("context") or {}
                for key, actual in (
                    ("expected_time_range", context.get("time_range") if not context.get("clarification") else None),
                    ("expected_source", context.get("source")),
                    ("expected_category", context.get("category")),
                    ("expected_compare_sources", context.get("compare_sources")),
                    ("needs_clarification", bool(context.get("clarification"))),
                ):
                    if key in case and actual != case[key]:
                        failures.append(f"case {index}: wrong {key}")
                if result.get("tool") == "clarify_scope" and result.get("queried_at") is not None:
                    failures.append(f"case {index}: clarification queried data")
                for source in result.get("sources", []):
                    if not str(source.get("url", "")).startswith(("https://", "http://")):
                        failures.append(f"case {index}: invalid citation URL")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-url", help="Optional running API base URL")
    parser.add_argument("--dataset", type=Path, default=ROOT / "eval/chatbot_cases.json")
    args = parser.parse_args()
    cases = json.loads(args.dataset.read_text(encoding="utf-8"))
    failures = evaluate_offline(cases)
    if args.live_url:
        tokens = {role: os.getenv(f"CHAT_EVAL_TOKEN_{role.upper()}", "") for role in ("user", "analyst", "operator")}
        failures.extend(evaluate_live(cases, args.live_url, tokens))
    for failure in failures:
        print(failure)
    print(f"{len(cases)} cases, {len(failures)} failures")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
