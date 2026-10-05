#!/usr/bin/env bash
set -euo pipefail

broker="${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"
inventory="/etc/kafka/topics.tsv"

while read -r topic partitions retention_ms; do
  [[ -z "$topic" || "$topic" == \#* ]] && continue
  kafka-topics --create --if-not-exists --bootstrap-server "$broker" \
    --partitions "$partitions" --replication-factor 1 \
    --config "retention.ms=$retention_ms" --topic "$topic"
  kafka-configs --bootstrap-server "$broker" --entity-type topics \
    --entity-name "$topic" --alter --add-config "retention.ms=$retention_ms"
done < "$inventory"

kafka-topics --list --bootstrap-server "$broker"
