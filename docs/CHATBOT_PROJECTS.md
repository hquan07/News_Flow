# Chatbot Projects (personal grouping MVP)

Projects organize conversations; they do not change the chatbot's answer context,
data-source permissions, or the `chat.use` requirement. Existing conversations
without a `project_id` remain in “Chưa phân loại”.

## API and ownership

- `POST /api/v1/chat/projects`, `GET /api/v1/chat/projects`,
  `PATCH /api/v1/chat/projects/{id}`, and `DELETE /api/v1/chat/projects/{id}`
  create, list, rename, and delete the authenticated user's Projects.
- `PATCH /api/v1/chat/conversations/{id}/project` moves one owned conversation;
  `project_id: null` removes its grouping. The destination Project must have
  the same owner. New conversations may specify `project_id` in either
  `POST /chat` or `POST /chat/conversations`.
- `GET /chat/conversations` supports optional `project_id` (or `unassigned`)
  and title search `q`; results remain owner-scoped and bounded by `limit`.
- Project names are unique case-insensitively per owner; each owner may have
  up to 100 Projects. Project IDs and conversation IDs are Mongo ObjectIds.

Deleting a Project sets its owned conversations' `project_id` to null. It
does **not** delete conversations or messages. Deleting an individual
conversation still permanently deletes its messages after UI confirmation.
Admins do not receive access to another user's personal Projects. Audit
records contain IDs and actions, not Project titles or message text.

The sidebar loads the 100 most recent conversations for its current
Project/search filter; changing either filter requests the server again,
so older matching chats can still be found. Project grouping alone never
retrieves messages from other chats as context. Shared/team Projects and
cross-chat retrieval require a separate authorization and consent design.
