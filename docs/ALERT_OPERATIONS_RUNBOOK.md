# Alert Operations Runbook

This runbook describes the production behavior introduced across Phases 1–5
for alert investigation, operator workflow state, real-time delivery, freshness,
and troubleshooting.

## Operator workflow

1. Open **System Alerts** and check the freshness badge before acting.
2. Select a crisis, viral cluster, or volume spike to inspect the evidence and
   the “Why this alert?” threshold explanation.
3. Pin an alert while investigating it. Acknowledge it after review; both states
   are stored per administrator in MongoDB.
4. From a volume spike, open **Latest News** to apply the exact publication
   window. Refine the result with title, source, category, and date filters.
5. Use the 15-minute trend for incident response and the one-hour trend for a
   broader pattern.

## Alert identifiers and clustering

- Crisis: `crisis:<source>`
- Volume: `volume:<UTC hour slot>`
- Viral post: `viral:<post id>`
- Viral cluster: `cluster:<source>:<normalized topic key>`

Viral cards are clustered by source and the first four meaningful normalized
title words. Missing titles use `unlabelled`. Cluster state therefore applies to
the cluster, while the detail modal still exposes every contributing post.

## Freshness contract

`GET /api/v1/alerts/social` includes an ISO-8601 `generated_at` value. SSE alert
snapshots include the equivalent `timestamp`. The dashboard shows the newest of
these values and marks alert data stale after 90 seconds without a fresh
snapshot. A stale badge means operators should verify API/SSE health before
treating the cards as current.

## Operator telemetry

Administrators can query:

```text
GET /api/v1/alerts/metrics
Authorization: Bearer <admin token>
```

The response reports requests, successes, not-found responses, errors, average
latency, and maximum latency for alert snapshots, detail drill-downs, trends,
state reads/writes, and emitted SSE snapshots.

Telemetry is deliberately **process-local**. It resets on API restart and each
API worker has its own counters. For multi-worker production, scrape and
aggregate this endpoint externally or replace the service with a shared metrics
backend.

## Troubleshooting

### Freshness badge is stale

1. Check API health and the `/stream` response through the reverse proxy.
2. Confirm the browser receives `update` heartbeats and `alert` events.
3. Inspect API logs using the `X-Request-ID` returned with REST responses.
4. Check ClickHouse availability if `social_snapshot`, `crisis_detail`, or
   `viral_detail` errors are increasing.

### Pin or acknowledge fails

1. Confirm the session belongs to an administrator and the token is current.
2. Check MongoDB health and the `alert_states` collection.
3. Inspect `state_query` and `state_update` telemetry.
4. Retry after connectivity returns; the UI rolls failed optimistic updates
   back to their prior value.

### Live Stream Debug reconnects continuously

1. Confirm `/api/v1/stream` is not buffered by the proxy
   (`X-Accel-Buffering: no`).
2. Check that heartbeat events arrive at least every five seconds.
3. Verify browser and proxy idle timeouts exceed the heartbeat interval.
4. Use pause/resume to inspect buffered events and **Copy payload** when sharing
   an event for diagnosis.

## Release verification

Before deployment, run the backend tests, frontend lint/type check, and both
production container builds. After deployment, verify:

- `/api/v1/alerts/social` returns `generated_at`.
- `/api/v1/alerts/metrics` rejects anonymous users and works for admins.
- the dashboard freshness badge updates from REST or SSE.
- keyboard focus is visible on alert cards and pin/acknowledge controls.
- alert cards and configuration controls fit a 360 px viewport.
