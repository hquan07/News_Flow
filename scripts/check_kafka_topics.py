"""Audit Kafka topic topology and retained offsets without changing broker state."""

import argparse
from pathlib import Path

from kafka import KafkaConsumer, TopicPartition


INVENTORY = Path(__file__).resolve().parents[1] / "infrastructure/kafka_utils/topics.tsv"


def expected_topics():
    for line in INVENTORY.read_text().splitlines():
        fields = line.split()
        if not fields or fields[0].startswith("#"):
            continue
        yield fields[0], int(fields[1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap-servers", default="localhost:29092")
    args = parser.parse_args()
    consumer = KafkaConsumer(bootstrap_servers=args.bootstrap_servers)
    mismatches = []
    try:
        for topic, expected in expected_topics():
            partitions = consumer.partitions_for_topic(topic)
            if not partitions or len(partitions) != expected:
                mismatches.append(topic)
                print(f"{topic}: expected {expected} partitions, found {len(partitions or [])}")
                continue
            tps = [TopicPartition(topic, index) for index in sorted(partitions)]
            starts = consumer.beginning_offsets(tps)
            ends = consumer.end_offsets(tps)
            retained = [ends[tp] - starts[tp] for tp in tps]
            print(f"{topic}: partitions={len(tps)} retained_messages={retained}")
    finally:
        consumer.close()
    if mismatches:
        raise SystemExit(f"Topic topology mismatch: {', '.join(mismatches)}")


if __name__ == "__main__":
    main()
