import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "infrastructure"))

from config.spark_config import KAFKA_DLQ_TOPIC, KAFKA_TOPICS  # noqa: E402
from kafka_utils import ALL_TOPICS  # noqa: E402


def test_topic_inventory_matches_producers_and_consumers():
    inventory = {}
    for line in (ROOT / "infrastructure/kafka_utils/topics.tsv").read_text().splitlines():
        parts = line.split()
        if parts and not parts[0].startswith("#"):
            inventory[parts[0]] = int(parts[1])
    assert set(inventory) == set(ALL_TOPICS) | set(KAFKA_TOPICS) | {KAFKA_DLQ_TOPIC}
    assert all(partitions == 3 for partitions in inventory.values())
