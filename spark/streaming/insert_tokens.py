"""Stable ClickHouse insert identifiers for Spark batch retries."""

import hashlib


def insert_token(stream_id, table, batch_id, partition_id, chunk_index):
    identity = f"{stream_id}:{table}:{batch_id}:{partition_id}:{chunk_index}"
    return hashlib.sha256(identity.encode()).hexdigest()
