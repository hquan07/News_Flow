# Chatbot evaluation

`chatbot_cases.json` contains 41 hand-written Vietnamese regression cases for
intent, time/source/category scope, clarification, and role permissions. Each
case has an independent `expected_tool` label. Optional `expected_time_range`,
`expected_source`, `expected_category`, `expected_compare_sources`,
`needs_clarification`, and `expected_status` labels make scope mistakes visible.

Run `python3 scripts/evaluate_chatbot.py` for an offline routing check. Running
with `--live-url` also posts the cases to the actual API. Use staging and test
accounts: live evaluation creates conversations and can query the configured
ClickHouse/Qdrant services. It checks API contracts and citation URL shape, not
the factual correctness of answers or whether a citation supports a claim.

To build a meaningful accuracy benchmark, collect 100–300 consenting or
appropriately anonymized real Vietnamese questions. Remove personal data,
tokens, and confidential article text. Have a reviewer label the permitted
role, intended tool, exact source/date/category/topic, whether clarification is
required, expected answer or calculation against a fixed database snapshot, and
supporting citation IDs. Include adversarial scope changes, empty-result cases,
permission denials, RAG relevance, and data/service outages. Review disagreements
before accepting labels, keep a held-out set, and report per-category error rates
and factual/citation accuracy separately from this routing pass rate.
