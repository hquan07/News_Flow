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
from api.services.chat_tools import _intent  # noqa: E402


TOOL_FOR_INTENT = {
    "articles": "search_articles",
    "article_count": "count_articles",
    "trending": "get_trending_keywords",
    "sentiment": "get_sentiment_distribution",
    "sources": "compare_sources",
    "entities": "get_entities",
    "alerts": "get_volume_alerts",
    "rag": "search_article_content",
}


def expected_status(case: dict) -> int:
    if "expected_status" in case:
        return case["expected_status"]
    intent = _intent(case["message"])
    needed = "alerts.read" if intent == "alerts" else "dashboard.read"
    return 200 if intent is None or needed in permissions_for_role(case["role"]) else 403


def evaluate_offline(cases: list[dict]) -> list[str]:
    failures = []
    for index, case in enumerate(cases, 1):
        if expected_status(case) == 403:
            if case.get("role") != "user" or _intent(case["message"]) != "alerts":
                failures.append(f"case {index}: unexpected permission expectation")
            continue
        actual_tool = TOOL_FOR_INTENT.get(_intent(case["message"]))
        if actual_tool != case.get("expected_tool"):
            failures.append(f"case {index}: expected {case.get('expected_tool')}, got {actual_tool}")
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
                    json={"message": case["message"], **({"time_range": case["time_range"]} if case.get("time_range") else {})},
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
                if case.get("time_range") and result.get("time_range") != case["time_range"]:
                    failures.append(f"case {index}: wrong time range")
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
    print(f"{len(cases) - len(failures)}/{len(cases)} checks passed" if not args.live_url else f"{len(failures)} failures across {len(cases)} cases")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
