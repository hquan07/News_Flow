# Chatbot Phase 1 — foundation

Phase 1 provides authenticated, owner-scoped conversation storage. It does not
generate answers or query news data yet.

## API

All routes use the existing Bearer token or session cookie and require
`chat.use`. Every current role has this permission. A conversation belongs to
the authenticated account that created it, including when the actor is an
admin. Other owners receive a 404 for lookup and deletion.

- `POST /api/v1/chat/conversations` with `{"title": "Optional title"}` creates a conversation.
- `GET /api/v1/chat/conversations?limit=50` lists the caller's conversations, newest activity first.
- `GET /api/v1/chat/conversations/{id}` returns the conversation and the 200 most recent messages, in chronological order.
- `DELETE /api/v1/chat/conversations/{id}` removes the conversation and messages.

The internal `chat_store.append_message` method prepares the message contract
for Phase 2. No public endpoint accepts assistant messages. Content is limited
to 16,000 characters per message. Message bodies are stored in MongoDB's
`chat_messages` collection; conversation metadata is stored in
`chat_conversations`. The existing `audit_logs` collection records creation,
message addition, and deletion, with actor, conversation ID, timestamp, and
request ID. It never records the message body. Indexes are created during API
startup.

Phase 2 must enforce each data tool's existing permission (for example,
`alerts.read`) before querying data and apply any future source/topic scopes at
the query layer. The `chat.use` permission only grants access to one's own
conversation records.
