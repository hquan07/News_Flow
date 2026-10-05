# NewsPulse monitoring

## Start and verify

The monitoring stack is an opt-in Docker Compose profile. Set a unique
`GRAFANA_ADMIN_PASSWORD` in `.env`, and set a numeric `TELEGRAM_CHAT_ID` if
Telegram delivery is wanted. The existing Telegram bot token is reused by
Alertmanager. Empty notification credentials leave alerts visible in Grafana
and Alertmanager without sending messages.

```bash
docker compose --env-file .env -f infrastructure/docker/docker-compose.yml --profile monitoring --profile backups config --quiet
docker compose --env-file .env -f infrastructure/docker/docker-compose.yml --profile monitoring --profile backups up -d
```

Prometheus: `http://localhost:9090/targets`; Grafana: `http://localhost:3001`;
Alertmanager: `http://localhost:9093`. These UI ports bind to loopback only.
Run Compose from the repository root with `--env-file .env`: the Compose file
lives in a subdirectory, so otherwise interpolation can silently use defaults
(including Grafana's `admin` password). On a pre-existing Grafana data volume,
changing the environment variable alone does not reset the admin account;
reset its password explicitly before exposing the UI.
Check every target is `UP`, then inspect `/alerts` in Prometheus. The API also
exposes `/metrics` and `/metrics/data`; the latter returns 503 if ClickHouse
cannot answer its bounded operational query.

Prometheus scrapes node exporter, cAdvisor, FastAPI, two PostgreSQL exporters,
MongoDB exporter, Kafka exporter, and ClickHouse's native endpoint. MinIO
scraping is deferred until authenticated access is configured; do not enable
anonymous MinIO metrics on a published service port. Grafana provisions Prometheus as its default data source.
The stack uses pinned image tags. Prometheus retains 15 days of metrics.

## Alert policy

| Severity | Delivery when configured | Typical conditions |
| --- | --- | --- |
| info | Dashboard only | Informational events |
| warning | Telegram after two minute grouping | CPU 70%, disk 70%, API 5xx 1%, volume drop |
| critical | Telegram and optional email | Disk 85%, stale data, backup failure, API 5xx 5% |
| emergency | Telegram, optional email and PagerDuty | Disk 95% |

Alerts are grouped by alert name, component, and instance. Matching higher
severity alerts inhibit the corresponding lower severity alerts for CPU,
memory, disk, API and Kafka lag. `for` durations prevent transient spikes from
paging. Team specific Telegram chats can be set with the `MONITORING_*_CHAT_ID`
variables in `.env`; otherwise `TELEGRAM_CHAT_ID` receives alerts. The rendered
Alertmanager config and secret files are stored in its Docker volume. Recreate
`alertmanager-config` and `alertmanager` after changing notification settings.
Do not print the rendered config or secret files in logs.

## Backups

The `backups` profile runs daily archive jobs for the NewsPulse PostgreSQL
database, the Airflow PostgreSQL database, and MongoDB. PostgreSQL checks each
archive's table of contents. Both database types perform a full restore into a
uniquely named temporary database every seven days. They remove that temporary
database after the test. Backup
success, failed attempts, and restore test timestamps are exported through the
node exporter textfile collector. Alerts fire when a backup is older than 26
hours or a restore test is older than eight days.

Backups are stored in local Docker volumes. They are **not off-host disaster
recovery**. Before using this in production, copy archives to encrypted off-site
storage, choose and test a retention policy, and ensure free disk space for a
full temporary restore. These jobs connect with database administrator accounts
and the restore tests add load to the live database servers. Test the schedule
and storage headroom on a staging copy first. ClickHouse and MinIO backup jobs
are not included yet; configure them before treating all data as protected.

## Coverage notes

- Kafka exporter reports lag only for consumer groups with committed offsets.
  Spark Structured Streaming uses checkpoint offsets and may not appear as a
  stable consumer group. `WarehouseDataStale` detects a stalled downstream
  result, but it does not identify the exact Kafka partition at fault.
- Disk forecasts use 24 hours of history at a 15 second scrape interval. They
  need more than 5,000 samples and assume approximately linear growth. Review
  forecasts after a cleanup, ingestion burst, or mount change.
- MongoDB's standalone server backup is not an atomic cross-collection
  snapshot. Use a replica set and oplog aware backup for a production RPO.
- MinIO metrics are not yet scraped. Its API port 9000 is published by this
  Compose file. Configure an authenticated Prometheus scrape before enabling
  MinIO alerting; do not expose anonymous metrics on that port.
- Redis is not deployed here, so Redis alerts do not apply. Container restart
  count, Spark job progress, Airflow task failure metrics, and ClickHouse/MinIO
  restore coverage still need dedicated instrumentation.

## Checks before production

```bash
docker compose --env-file .env -f infrastructure/docker/docker-compose.yml --profile monitoring --profile backups config --quiet
docker compose --env-file .env -f infrastructure/docker/docker-compose.yml --profile monitoring --profile backups ps
```

Review the Prometheus target list and a sample alert in Alertmanager. Confirm a
real backup archive exists for each enabled backup service and that its restore
timestamp advances. Alertmanager will show missing backup metric alerts if the
monitoring profile is enabled without the backups profile.
