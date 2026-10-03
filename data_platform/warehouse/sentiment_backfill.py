"""Backfill missing article sentiment with a bounded multiprocessing pool."""

import argparse
import multiprocessing
import os
import sys
import time

import clickhouse_connect

sys.path.append("/opt/spark-apps")

from spark.processing.sentiment_core import _get_pipeline, analyze_sentiment


def get_client():
    return clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "admin"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "admin123"),
        database=os.getenv("CLICKHOUSE_DB", "newspulse"),
    )


def _init_worker(worker_threads: int) -> None:
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    try:
        import torch

        torch.set_num_threads(worker_threads)
    except ImportError:
        pass
    _get_pipeline()


def _analyze_batch(batch):
    rows = []
    for url_hash, title, content in batch:
        text = f"{title or ''} {content or ''}".strip()
        sentiment = analyze_sentiment(text)
        rows.append([
            url_hash,
            sentiment["sentiment_score"],
            sentiment["sentiment_label"],
        ])
    return rows


def _missing_articles(client, limit: int):
    limit_clause = "LIMIT {limit:UInt32}" if limit else ""
    return client.query(
        f"""
        SELECT url_hash, title, content
        FROM newspulse.raw_articles FINAL
        WHERE url_hash NOT IN (
            SELECT url_hash FROM newspulse.raw_article_sentiment
        )
        ORDER BY publish_time DESC
        {limit_clause}
        """,
        parameters={"limit": limit} if limit else None,
    ).result_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workers",
        type=int,
        default=int(os.getenv("NLP_BACKFILL_WORKERS", "2")),
        help="Number of model processes. Keep this low because each process loads PhoBERT.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.getenv("NLP_BACKFILL_BATCH_SIZE", "20")),
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--threads-per-worker",
        type=int,
        default=int(os.getenv("NLP_BACKFILL_THREADS_PER_WORKER", "2")),
    )
    args = parser.parse_args()

    workers = max(1, min(args.workers, multiprocessing.cpu_count()))
    batch_size = max(1, args.batch_size)
    client = get_client()
    articles = _missing_articles(client, max(0, args.limit))
    batches = [articles[index:index + batch_size] for index in range(0, len(articles), batch_size)]

    if not batches:
        print("All articles already have sentiment data.", flush=True)
        client.close()
        return

    worker_threads = max(1, args.threads_per_worker)
    print(
        f"Backfilling {len(articles)} articles in {len(batches)} batches "
        f"with {workers} model process(es).",
        flush=True,
    )
    started_at = time.time()
    inserted = 0

    try:
        with multiprocessing.Pool(
            processes=workers,
            initializer=_init_worker,
            initargs=(worker_threads,),
        ) as pool:
            for batch_index, rows in enumerate(pool.imap_unordered(_analyze_batch, batches), start=1):
                client.insert(
                    "newspulse.raw_article_sentiment",
                    rows,
                    column_names=["url_hash", "sentiment_score", "sentiment_label"],
                )
                inserted += len(rows)
                elapsed = max(time.time() - started_at, 0.001)
                print(
                    f"Inserted batch {batch_index}/{len(batches)}: "
                    f"{inserted}/{len(articles)} articles ({inserted / elapsed:.2f}/s)",
                    flush=True,
                )
    finally:
        client.close()


if __name__ == "__main__":
    main()
