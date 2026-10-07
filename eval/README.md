# Chatbot evaluation

`chatbot_cases.json` contains 57 hand-written Vietnamese regression cases for
intent, time/source/category scope, clarification, and role permissions. Each
case has an independent `expected_tool` label. Optional `expected_time_range`,
`expected_source`, `expected_category`, `expected_compare_sources`,
`needs_clarification`, and `expected_status` labels make scope mistakes visible.

Run `python3 scripts/evaluate_chatbot.py` for an offline routing check. Running
with `--live-url` also posts the cases to the actual API. Use staging and test
accounts: live evaluation creates conversations and can query the configured
ClickHouse/Qdrant services. It checks API contracts and citation URL shape, not
the factual correctness of answers or whether a citation supports a claim.

## Live answer checks against real data

Run `.venv/bin/python scripts/evaluate_chat_answers.py` while ClickHouse is
available. The seven cases in `chat_answer_live_cases.json` use news and social
sources present in this project's data. The runner calls the read-only chatbot
tool directly (it does not create conversations), then independently queries
ClickHouse before and after each count answer. It verifies the number in the
Vietnamese answer falls between those two snapshots, its tool and source/time
scope match the label, and returned article citations still match their IDs,
titles, URLs, sources and publication windows in ClickHouse. It reports case IDs
and pass/fail checks, not question text or answers. The count bracket tolerates
new ingestion during an evaluation, but it is not a substitute for a frozen
snapshot when comparing different implementations.

To add real, consented or anonymized questions, make a private copy of
`chat_answer_live_cases.json` and run `--cases path/to/private.json`. The source
must be stated in the question; explicit request filters are not supported by
this evaluator. Count oracles currently support source/time, not topic/category.
For an article-search case, a reviewer may add `relevant_article_ids` containing
verified `raw_articles.url_hash` IDs. `reviewed_relevant_hit` only checks
whether at least one returned ID is among them; a human must still judge whether
the cited article supports each claim. A null value and the
`unreviewed_citation_cases` total make missing human labels explicit. These
seven cases are a working live-data baseline, **not** a comprehensive factual
accuracy score or a sample of real user prompts.

When expanding question coverage, review aggregate `tool=none` counts from
`GET /api/v1/chat/metrics` and the feedback summary, then obtain permission
before inspecting or adding any actual user wording to a private benchmark.
Never commit raw chat logs or confidential article content as evaluation data.

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
