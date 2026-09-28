# NewsPulse Release Checklist

Use this checklist for the Phase 6 release candidate and subsequent production
deployments. A release is ready only when every mandatory item is verified in
the target environment.

## 1. Source and build integrity

- [ ] Working tree is clean and the release commit is pushed.
- [ ] Backend test suite passes without failures.
- [ ] Frontend ESLint and TypeScript checks pass.
- [ ] API and frontend production images build successfully.
- [ ] Database migrations are applied before the new application containers.
- [ ] Runtime secrets come from environment or secret storage, not source files.

## 2. Dependencies and data

- [ ] Readiness reports ClickHouse, MongoDB, and PostgreSQL as healthy.
- [ ] Latest ingestion timestamp is within the expected freshness threshold.
- [ ] NLP coverage is within the agreed operational target.
- [ ] Synthetic/demo records display the `Synthetic data` badge.
- [ ] Alert thresholds match the environment's expected values.

## 3. Critical user journeys

- [ ] Admin login succeeds and non-admin users cannot access admin endpoints.
- [ ] Latest News and System Articles title search return matching articles.
- [ ] Source, category, and date filters combine correctly and reset pagination.
- [ ] Live Stream Debug connects, pauses, resumes, and copies an event payload.
- [ ] Crisis, viral cluster, and volume-spike cards open their detail views.
- [ ] “Why this alert?” explains the active threshold.
- [ ] Volume spike drill-down opens Latest News with the correct time filter.
- [ ] Pin and acknowledge survive page refresh for the same administrator.
- [ ] Interaction trends switch between 15-minute and one-hour buckets.

## 4. Alert operations and observability

- [ ] Alert freshness updates from REST or SSE and stale data is clearly marked.
- [ ] `GET /api/v1/alerts/metrics` returns 401 without authentication.
- [ ] The same endpoint returns telemetry for an administrator.
- [ ] Admin Dashboard displays alert requests, failures, missing details, uptime,
      outcomes, and latency without console errors.
- [ ] A known detail request increments the corresponding telemetry counter.
- [ ] Operators understand that counters are process-local and reset on restart.

## 5. Accessibility and responsive checks

- [ ] All alert actions are keyboard reachable with visible focus.
- [ ] Dialog focus is trapped, Escape closes it, and focus returns to the card.
- [ ] Status and error updates are announced by screen readers.
- [ ] Reduced-motion preference disables non-essential movement.
- [ ] No horizontal overflow occurs at 320, 375, 768, and 1024 px.
- [ ] Pin/acknowledge controls retain an adequate mobile touch target.

## 6. Deployment and rollback

- [ ] Record the previous image tags and database migration version.
- [ ] Deploy API before frontend when a response contract changes.
- [ ] Run smoke tests through the same reverse-proxy URL users access.
- [ ] Monitor dependency health, alert failure rate, and API logs after rollout.
- [ ] Roll back application images if critical journeys fail. Do not reverse a
      database migration until its rollback safety has been explicitly checked.

## Sign-off

Record release commit, image tags, verifier, timestamp, known limitations, and
rollback owner in the deployment record. The detailed operational response is
documented in [Alert Operations Runbook](ALERT_OPERATIONS_RUNBOOK.md).
