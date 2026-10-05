#!/usr/bin/env bash
set -euo pipefail

broker="${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"
news_topics=(general sports tech economy politics entertainment health education world law)
week_ms=604800000
fortnight_ms=1209600000

for category in "${news_topics[@]}"; do
  kafka-topics --create --if-not-exists --bootstrap-server "$broker" \
    --partitions 3 --replication-factor 1 --config "retention.ms=$week_ms" \
    --topic "news.$category"
  kafka-configs --bootstrap-server "$broker" --entity-type topics \
    --entity-name "news.$category" --alter --add-config "retention.ms=$week_ms"
done

kafka-topics --create --if-not-exists --bootstrap-server "$broker" \
  --partitions 3 --replication-factor 1 --config "retention.ms=$week_ms" \
  --topic social_posts
kafka-configs --bootstrap-server "$broker" --entity-type topics \
  --entity-name social_posts --alter --add-config "retention.ms=$week_ms"
kafka-topics --create --if-not-exists --bootstrap-server "$broker" \
  --partitions 3 --replication-factor 1 --config "retention.ms=$fortnight_ms" \
  --topic newspulse.dlq
kafka-configs --bootstrap-server "$broker" --entity-type topics \
  --entity-name newspulse.dlq --alter --add-config "retention.ms=$fortnight_ms"

kafka-topics --list --bootstrap-server "$broker"
