"""Small, bounded operational query exported separately from HTTP metrics."""

import asyncio

from api.config import get_ch_client


def _warehouse_counts() -> tuple[int, int, int]:
    result = get_ch_client().query("""
        SELECT
            toUnixTimestamp(max(loaded_at)) AS latest_loaded,
            countIf(loaded_at >= now() - INTERVAL 24 HOUR) AS current_24h,
            countIf(loaded_at >= now() - INTERVAL 48 HOUR
                    AND loaded_at < now() - INTERVAL 24 HOUR) AS previous_24h
        FROM newspulse.raw_articles
    """)
    latest, current, previous = result.result_rows[0]
    return int(latest or 0), int(current), int(previous)


async def warehouse_metrics_payload() -> str:
    latest, current, previous = await asyncio.wait_for(
        asyncio.to_thread(_warehouse_counts), timeout=10
    )
    return (
        "# TYPE newspulse_warehouse_last_article_timestamp_seconds gauge\n"
        f"newspulse_warehouse_last_article_timestamp_seconds {latest}\n"
        "# TYPE newspulse_warehouse_articles_24h gauge\n"
        f"newspulse_warehouse_articles_24h {current}\n"
        "# TYPE newspulse_warehouse_articles_previous_24h gauge\n"
        f"newspulse_warehouse_articles_previous_24h {previous}\n"
    )
