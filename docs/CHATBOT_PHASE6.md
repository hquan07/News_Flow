# Chatbot Phase 6 — controlled actions

Chat text remains read-only. Actions use an explicit two-step API and a dedicated
panel in ChatView; saying “yes” in a conversation never executes an action.

| Action | Permission | Effect |
| --- | --- | --- |
| `acknowledge_alert` | `alerts.manage` | Marks a currently active volume alert acknowledged for this account only. |
| `trigger_crawler` | `crawler.run` | Queues exactly one allowlisted spider through Airflow; `all` is not allowed. |
| `generate_report` | `reports.export` | Creates an owner-scoped CSV with up to 50 source/category counts for 24 hours, 7 days, or 30 days. |

Workflow:

1. `POST /api/v1/chat/actions/preview` with one action and its validated fields.
   The response describes the impact and returns an `action_id` and a short-lived
   `confirmation_token` (five minutes). A preview does not perform the action.
2. Show the description to the user. Only an explicit click sends
   `POST /api/v1/chat/actions/confirm` with `action_id`, `confirmation_token`,
   and `confirm: true`.
3. The server rechecks the current role, account ownership, token, expiry, and
   action status. It atomically claims the action once across API workers,
   records an audit event before the side effect, performs the action, and
   records the outcome. Reusing a token returns HTTP 409.
4. For reports, an authenticated owner downloads from the returned URL.
   The CSV is limited and escapes spreadsheet formula prefixes. Reports expire
   after seven days. Download permission is rechecked.

`GET /api/v1/chat/actions/{action_id}` lets the owner inspect the ledger status
after a network error. The UI checks it before suggesting any further action.

Example preview body: `{"action":"trigger_crawler","spider_name":"vnexpress"}`.
Other examples: `{"action":"acknowledge_alert","alert_id":"volume:2026100108"}`
and `{"action":"generate_report","time_range":"7d","source":"vnexpress"}`.

The action ledger and audit log store identifiers and outcomes, never the
confirmation token or chat message. Pending tokens expire after five minutes.
If Airflow times out after accepting a run, the action is marked failed but is
not automatically replayed. Check Airflow for `chat__<action_id>` before
creating a fresh preview; this avoids duplicate runs from retrying the same
confirmation. Report generation depends on ClickHouse and alert validation
depends on the current alert query. No LLM or article content can invoke these
endpoints by itself.
