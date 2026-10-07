# Chatbot priority 5 — grounded generation and real streaming

Natural synthesis is optional and disabled by default. The deterministic tools,
permissions, source/date filters, citations, and extractive fallback remain the
authority. Only `search_article_content` answers with at least one verified source
are eligible for generation.

Configure an OpenAI-compatible endpoint with `CHAT_LLM_ENABLED=true`,
`CHAT_LLM_URL`, and `CHAT_LLM_MODEL`. `CHAT_LLM_API_KEY` is optional for a local
endpoint and must be supplied through the environment when needed. The API sends
only the current question and bounded, already verified excerpts. It instructs the
model to treat both as untrusted data and ignore instructions embedded in them.

Generated output is buffered one sentence at a time. A sentence is emitted only
when it contains citation numbers that exist in the current source list. If the
model is unavailable or produces no valid sentence, the existing extractive answer
is returned. The safe extractive answer is persisted before generation starts; a
completed generated stream replaces it atomically. An interrupted stream therefore
does not erase the fallback answer.

The frontend posts to `/api/v1/chat/stream` and incrementally renders `delta`
events. The final `done` event supplies the persisted message ID, sources, scope,
chart, query time, and evidence metadata. Do not enable the LLM in production until
the retrieval and citation evaluation gates pass on reviewed questions.
