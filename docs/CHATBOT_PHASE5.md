# Chatbot Phase 5 — production hardening

This phase hardens the existing read-only chatbot. It does not add admin actions
or a generative LLM. The RAG answer still consists of verified article excerpts.

## Controls

- Answer-producing `POST /api/v1/chat` and `/chat/stream` requests share a
  per-account, MongoDB-backed fixed window (default 20/minute). The counter is
  atomic across API workers and returns HTTP 429 with `Retry-After` when exceeded.
  Mongo failure fails closed with HTTP 503. Conversation ownership is checked
  before using tools; rejected requests do not query article data or persist a
  new message. `CHAT_RATE_LIMIT_PER_MINUTE` configures the limit. The global
  IP-based API limit remains an additional, process-local layer.
- Only query embeddings are cached in memory (default 120 seconds, 256 entries
  per worker), keyed by a hash of endpoint and text. Article results and access
  decisions are never cached. Every result still passes the current ClickHouse
  date/source/category recheck. Tune `CHAT_EMBED_CACHE_TTL_SECONDS` and
  `CHAT_EMBED_CACHE_MAX_ITEMS`; set either to zero to disable caching.
- When Qdrant or the embedding service fails, RAG falls back to ClickHouse
  keyword search and labels the answer as degraded. It never silently treats
  a keyword result as a semantic match. If ClickHouse is unavailable, the
  existing dependency error remains HTTP 503.
- Chat metrics count requests by tool and outcome, total latency, and answers
  with sources. They are stored in MongoDB for seven days, without prompts,
  answer text, user IDs, or article URLs. Operators/admins can call
  `GET /api/v1/chat/metrics?hours=24`; regular users receive HTTP 403.

## Evaluation

Run offline intent, scope, clarification, and role checks:

```bash
python3 scripts/evaluate_chatbot.py
```

For a live API, set `CHAT_EVAL_TOKEN_USER`, `CHAT_EVAL_TOKEN_ANALYST`, and
`CHAT_EVAL_TOKEN_OPERATOR`, then run:

```bash
python3 scripts/evaluate_chatbot.py --live-url http://localhost:8001
```

The live runner calls the real chat endpoint and creates conversations; use
test accounts and a staging deployment. It checks status, tool selection,
resolved time/source/category scope, clarification behavior, and citation URL
shape without printing question/answer text. The 41 hand-written cases at
`eval/chatbot_cases.json` are a regression benchmark, not an accuracy
certification. They do not evaluate answer facts or citation relevance. Before
production, extend this with 100–300 anonymized real Vietnamese questions and
reviewed ground truth, including source/date scope, RAG relevance,
authorization, prompt injection, empty data, and service outage. See
`eval/README.md` for the labeling and review process.

The unit/integration tests in `tests/test_chat_phase5.py` cover atomic account
limits, 429 before data access, cache expiry, degraded retrieval, metrics
permission, and action-like prompts that must remain read-only.

## Rollout and alerting

Watch the metrics endpoint for errors, 429s, source coverage, and latency;
set deployment-specific thresholds after measuring baseline traffic. Test
Qdrant and embedding outages in staging and verify the explicit keyword
fallback. Keep Mongo and ClickHouse health checks active. This phase does not
provide load testing or a live RAG relevance score: both require production-like
services and data.
