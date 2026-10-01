# Chatbot Phase 4 — hybrid retrieval from article content

Phase 4 adds optional RAG retrieval for questions such as “Tóm tắt nội dung về lãi suất”.
It does **not** call an LLM or generate a synthetic summary: the answer shows verified
extracts from articles, numbered to match the existing `sources` response field.

## Run

1. Keep a valid `JWT_SECRET_KEY` and ClickHouse credentials in the root `.env`.
2. Build and start the optional services: `docker compose -f infrastructure/docker/docker-compose.yml --profile rag up -d --build qdrant embeddings rag-indexer`.
3. Set `RAG_ENABLED=true` in the root `.env`, then recreate `api` with the same Compose file. Without this flag, content questions fall back to labeled ClickHouse keyword search; semantic retrieval remains disabled.
4. The indexer scans the newest articles published in the last 30 days, up to 2,000 per pass, every five minutes. For an explicit backfill when that cap is too small, run `docker compose -f infrastructure/docker/docker-compose.yml --profile rag run --rm rag-indexer python -m api.services.rag_indexer --since-days 90 --limit 10000`. This can take time and requires sufficient CPU, memory, and network for the first embedding-image build.

The embedding service runs a local multilingual model; it and Qdrant have no published ports.
Qdrant stores article chunks and filter metadata, and Mongo `rag_index_state` stores
content fingerprints. The indexer skips unchanged articles and replaces chunks after
article edits. Current ClickHouse rows are always rechecked before a result is cited,
including source, category and date. Deleted or changed article text is never quoted
from an old vector payload. Search combines vector and keyword candidates using
reciprocal-rank fusion.

`dashboard.read` is required before calling either retrieval service. The RAG index
contains only the public article table, not admin/audit/conversation data. Any future
per-source authorization rules must be enforced at the final ClickHouse recheck as
well as the initial vector filter; the current app does not have per-source ACLs.

If semantic retrieval is disabled, or the embedding service or Qdrant is unavailable, content search
falls back to labeled keyword-only retrieval. If ClickHouse is unavailable, the
dependency error remains HTTP 503. The existing analytics tools remain independent. The model download
is fixed at image build time, and the service runs offline afterward. For a production
rollout, benchmark recall and latency on real Vietnamese questions, monitor index lag,
and backfill articles older than 30 days separately. Rebuilding the vector collection
after changing the embedding model requires a new collection name and reindex.
