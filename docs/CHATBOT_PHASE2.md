# Chatbot Phase 2 — read-only question answering

Phase 2 adds `POST /api/v1/chat` and `POST /api/v1/chat/stream` to the
owner-scoped conversation API from Phase 1. Both require `chat.use`.

Example request:

```json
{
  "message": "Tìm bài viết về AI hôm nay",
  "conversation_id": null,
  "time_range": "today",
  "source": "vnexpress",
  "category": null,
  "query": "AI"
}
```

`conversation_id` may be omitted to create a conversation. Supported time
ranges are `today`, `7d` (default), and `30d`. The optional `query` explicitly
filters article titles, sentiment analysis by article title, or trending by
keyword. Source and category are exact match filters. They select data but
do not grant or narrow account permissions. Questions are routed to bounded read-only
tools for recent articles, keyword frequency, sentiment distribution, and
volume alerts. Article answers include source links. `queried_at` is when the
query completed, **not** the publication or warehouse freshness time.

Alerts require `alerts.read`; article, trending, and sentiment questions
require `dashboard.read`. A denied request does not query the data source or
create a conversation. The alert tool currently shows only unfiltered volume
alerts over seven days. It rejects explicit filters and other date ranges.

Responses are factual templates based on returned rows, not LLM output. The
tool does not yet summarize article bodies, analyze why a trend changed, or
support arbitrary conversational questions. For ambiguous questions it states
what it can answer. Keyword frequency is not claimed as growth rate.

The stream route emits SSE `delta` events with answer text followed by one
`done` event containing conversation ID, tool name, source links, query time,
and time range. Data retrieval and persistence finish before streaming starts;
this is streamed delivery, not token-by-token model generation.
