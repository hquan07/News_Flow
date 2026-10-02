# Chatbot evaluation

`chatbot_cases.json` contains 45 hand-written Vietnamese regression cases for
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

## Article-content retrieval

Create a private JSON file containing reviewer-labeled article IDs, for example:

```json
[{"id":"interest-rates-01","query":"Tóm tắt nội dung về lãi suất","time_range":"7d","source":"vnexpress","category":null,"relevant_article_ids":["REVIEWED_URL_HASH"]}]
```

Use real `raw_articles.url_hash` values from a stable test snapshot; the placeholder
above is not a benchmark. Run `python3 scripts/evaluate_chat_retrieval.py --cases
path/to/reviewed.json` for the keyword baseline. With the optional RAG services
running, add `--with-vector` to compare keyword, vector, and the production
article-level fusion on the same labels. The runner rechecks every candidate in
ClickHouse and reports recall@5, nDCG@5, and estimated p95 latency without
printing question text. It does not change `RAG_ENABLED` or choose a winner.
Keep a held-out set, compare source/date-filtered and empty-result cases, and
review citation support separately before changing production retrieval.

## User feedback

Each assistant message accepts one of `helpful`, `wrong_source`, or
`wrong_number` through its owner-scoped feedback endpoint. The user may change
their choice. Feedback is stored on the existing message and removed with its
conversation; no extra copy of the prompt or answer is created. An operator or
admin can read aggregate counts by reason and tool at
`GET /api/v1/chat/feedback/summary?days=7`. These reports help select cases for
human review; they are not ground-truth relevance labels.
