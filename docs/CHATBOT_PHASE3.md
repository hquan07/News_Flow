# Chatbot Phase 3 — analysis, follow-ups, and dashboard

Phase 3 extends the read-only chat API with two tools:

- Source comparison: article counts and average word count per source.
- Entity analysis: most mentioned entities, or entities co-occurring with a named entity.

Both tools use fixed ClickHouse queries, parameter binding, the selected
time range, and optional source/category filters where supported. They require
the existing dashboard.read permission. Co-occurrence means appearing in
the same article; it is not evidence of a direct relationship.

Responses can now include a bounded bar-chart payload with type, title, unit,
and points. Chart points are derived from the same rows used for the text
answer. The payload is persisted with the assistant message and included
in the SSE done event.

The assistant stores its resolved intent and filters with each answer. A
follow-up such as “Còn 30 ngày qua?” reuses the previous answer's subject
and reruns the authorized tool over the new period. It does not reuse prior
data rows, and each turn checks the current role again. Follow-up context is
read only from the authenticated user's conversation. This is limited
rule-based context handling, not open-ended language understanding.

The News dashboard now has a Chat Assistant tab for accounts with chat.use.
It shows conversation history, source links, saved charts, and query errors.
The UI submits ordinary JSON requests; the SSE endpoint remains available
for clients that need streamed delivery.

Example questions:

- “So sánh nguồn VnExpress và Tuổi Trẻ”
- “Thực thể nào xuất hiện nhiều trong 7 ngày qua?”
- “Thực thể nào liên quan đến VinFast?”
- “Tìm bài viết về AI” → “Còn 30 ngày qua?”

Phase 3 still uses factual templates. It does not infer causes from
co-occurrence, summarize article bodies, or use a language model.
