# Kafka topology and partition review

The local broker has 12 application topics, each with three partitions and one
replica. `infrastructure/kafka_utils/topics.tsv` is the creation inventory.
The news and social topics retain seven days; the dead letter topic retains
fourteen days. Existing topics retain their partition count when `kafka-init`
runs; its script only updates retention.

The article producer keys records by a stable hash of URL. Records for the same
URL therefore enter the same partition while a topic keeps its partition count.
Increasing partitions changes the mapping of keys to partitions, so review
ordering requirements before increasing them. Kafka cannot decrease the
partition count of an existing topic.

Audit the deployed topology with `python3 scripts/check_kafka_topics.py` from
the host, or use `--bootstrap-servers` for another listener. The printed
`retained_messages` counts are *not* consumer lag. Review Spark progress,
processing time, broker disk use, and per-topic traffic before changing the
three-partition baseline. Increase a hot topic only when the processing backlog
grows persistently and workers have spare capacity. Retune Spark parallelism
after any change.

Spark Structured Streaming resumes from its checkpoint; `startingOffsets`
only applies to a new checkpoint. The raw query starts at `latest` by default,
whereas NLP and social start at `earliest`. Do not remove or rename checkpoints
without a replay plan. `KAFKA_FAIL_ON_DATA_LOSS=true` stops the stream when
required offsets have expired; investigate and backfill before restarting.
The article parser accepts unversioned legacy messages during transition,
while unknown non-null versions go to `newspulse.dlq`.

The Spark driver serves query progress at `spark-streaming:9189/metrics` inside
the Compose network. Record the input rate, processed rate, trigger duration,
Kafka lag, and ClickHouse write time during a representative crawl before
changing `RAW_MAX_OFFSETS_PER_TRIGGER`, `NLP_MAX_OFFSETS_PER_TRIGGER`,
`SOCIAL_MAX_OFFSETS_PER_TRIGGER`, or `NLP_PROCESSING_PARTITIONS`. A trigger that
consistently takes longer than its interval indicates an accumulating backlog.
The raw and NLP queries keep independent checkpoints so NLP can lag without
blocking raw article storage.

Streaming inserts into ClickHouse use a token derived from query, Spark batch,
sink partition, and chunk. The sink fixes its repartition count and row order
before insertion. `non_replicated_deduplication_window=10000` is applied to the
streaming tables when `clickhouse-init` runs. This protects retries while their
tokens remain in ClickHouse's finite history; it is not permanent exactly-once
delivery. Retain Spark checkpoints and keep `CLICKHOUSE_SINK_PARTITIONS` stable
until all in-flight batches have completed. Raw articles also store the Kafka
topic, partition, offset, and stable event ID for replay investigation.

With the monitoring profile enabled, Prometheus scrapes the Spark driver at
`spark-streaming:9189/metrics`. Alert rules cover query availability, reported
Kafka lag, malformed-record rate, broker count, partition leadership and
replication, and host disk use. Spark's checkpoint offsets are the relevant
source of lag for these queries; Kafka consumer-group lag is not used.

For a cold backup or restart, stop the Airflow scheduler and Spark streaming
after active crawl tasks finish. Keep the Kafka, ZooKeeper, Spark checkpoint,
and ClickHouse volumes together as one recovery point. Start ZooKeeper, wait
for Kafka health, run `kafka-init` to completion, and run `clickhouse-init`
after ClickHouse is healthy. Start the Spark master and worker before Spark
streaming. The Compose dependencies now require `kafka-init` for Spark
streaming and the Airflow scheduler, and `clickhouse-init` for Spark streaming.
Do not remove checkpoint or broker volumes when a service is unhealthy.
