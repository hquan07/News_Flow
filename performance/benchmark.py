import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

from loguru import logger

# Config
PG_CONN_PARAMS = {
    "host": os.getenv("PG_HOST", "localhost"),
    "port": int(os.getenv("PG_PORT", "5432")),
    "user": os.getenv("PG_USER", "newspulse"),
    "password": os.getenv("PG_PASSWORD", "newspulse"),
    "dbname": os.getenv("PG_DB", "newspulse"),
}


# Dashboard query patterns — mirroring actual dashboard queries
BENCHMARK_QUERIES = [
    # ── Overview Dashboard ──
    {
        "name": "overview_daily_article_count",
        "description": "Số bài theo ngày × nguồn × category (30 ngày gần nhất)",
        "query": """
            SELECT dt.full_date, ds.name, dc.name, COUNT(*)
            FROM warehouse.fact_article fa
            JOIN warehouse.dim_time dt ON fa.time_id = dt.time_id
            JOIN warehouse.dim_source ds ON fa.source_id = ds.source_id
            JOIN warehouse.dim_category dc ON fa.category_id = dc.category_id
            WHERE dt.full_date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY dt.full_date, ds.name, dc.name
            ORDER BY dt.full_date DESC
        """,
    },
    {
        "name": "overview_hourly_distribution",
        "description": "Phân bố bài viết theo giờ",
        "query": """
            SELECT publish_hour, ds.name, COUNT(*)
            FROM warehouse.fact_article fa
            JOIN warehouse.dim_source ds ON fa.source_id = ds.source_id
            WHERE publish_hour IS NOT NULL
            GROUP BY publish_hour, ds.name
            ORDER BY publish_hour
        """,
    },
    {
        "name": "overview_source_speed",
        "description": "Tốc độ ra bài theo nguồn (hôm nay)",
        "query": """
            SELECT ds.name, COUNT(*), MAX(fa.publish_time)
            FROM warehouse.fact_article fa
            JOIN warehouse.dim_source ds ON fa.source_id = ds.source_id
            JOIN warehouse.dim_time dt ON fa.time_id = dt.time_id
            WHERE dt.full_date = CURRENT_DATE
            GROUP BY ds.name
        """,
    },

    # ── Trending Dashboard ──
    {
        "name": "trending_top_keywords_7d",
        "description": "Top 20 keyword trong 7 ngày",
        "query": """
            SELECT dk.keyword, dk.total_count, COUNT(DISTINCT bak.article_id) AS articles
            FROM warehouse.dim_keyword dk
            JOIN warehouse.bridge_article_keyword bak ON dk.keyword_id = bak.keyword_id
            JOIN warehouse.fact_article fa ON bak.article_id = fa.article_id
            JOIN warehouse.dim_time dt ON fa.time_id = dt.time_id
            WHERE dt.full_date >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY dk.keyword_id, dk.keyword, dk.total_count
            ORDER BY articles DESC
            LIMIT 20
        """,
    },
    {
        "name": "trending_keyword_timeline",
        "description": "Tần suất một keyword theo ngày (30 ngày)",
        "query": """
            SELECT dt.full_date, COUNT(*)
            FROM warehouse.bridge_article_keyword bak
            JOIN warehouse.fact_article fa ON bak.article_id = fa.article_id
            JOIN warehouse.dim_time dt ON fa.time_id = dt.time_id
            JOIN warehouse.dim_keyword dk ON bak.keyword_id = dk.keyword_id
            WHERE dk.keyword_id = 1
              AND dt.full_date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY dt.full_date
            ORDER BY dt.full_date
        """,
    },

    # ── Source Comparison Dashboard ──
    {
        "name": "source_category_distribution",
        "description": "Tỷ trọng category theo nguồn",
        "query": """
            SELECT ds.name, dc.name, COUNT(*),
                   ROUND(COUNT(*)::NUMERIC / SUM(COUNT(*)) OVER (PARTITION BY ds.name) * 100, 1) AS pct
            FROM warehouse.fact_article fa
            JOIN warehouse.dim_source ds ON fa.source_id = ds.source_id
            JOIN warehouse.dim_category dc ON fa.category_id = dc.category_id
            GROUP BY ds.name, dc.name
            ORDER BY ds.name, pct DESC
        """,
    },
    {
        "name": "source_avg_word_count",
        "description": "Độ dài trung bình bài viết theo nguồn × category",
        "query": """
            SELECT ds.name, dc.name, AVG(fa.word_count)::INTEGER, COUNT(*)
            FROM warehouse.fact_article fa
            JOIN warehouse.dim_source ds ON fa.source_id = ds.source_id
            JOIN warehouse.dim_category dc ON fa.category_id = dc.category_id
            GROUP BY ds.name, dc.name
            ORDER BY ds.name, dc.name
        """,
    },

    # ── Entity Analysis ──
    {
        "name": "top_entities_by_type",
        "description": "Top 10 entities theo từng type",
        "query": """
            SELECT de.entity, de.entity_type, de.mention_count,
                   COUNT(DISTINCT bae.article_id) AS article_count
            FROM warehouse.dim_entity de
            JOIN warehouse.bridge_article_entity bae ON de.entity_id = bae.entity_id
            GROUP BY de.entity_id, de.entity, de.entity_type, de.mention_count
            ORDER BY article_count DESC
            LIMIT 30
        """,
    },

    # ── Alerts / Spike Detection ──
    {
        "name": "spike_detection_hourly",
        "description": "Spike detection — số bài/giờ vượt 2× trung bình",
        "query": """
            WITH hourly AS (
                SELECT DATE_TRUNC('hour', publish_time) AS hour_slot,
                       COUNT(*) AS cnt
                FROM warehouse.fact_article
                WHERE publish_time >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY hour_slot
            ),
            stats AS (
                SELECT AVG(cnt) AS avg_cnt, STDDEV(cnt) AS std_cnt FROM hourly
            )
            SELECT h.hour_slot, h.cnt, s.avg_cnt::INTEGER
            FROM hourly h, stats s
            WHERE h.cnt > s.avg_cnt + 2 * s.std_cnt
            ORDER BY h.hour_slot DESC
        """,
    },

    # ── Materialized View queries (after optimization) ──
    {
        "name": "mv_daily_overview_query",
        "description": "Query materialized view — daily overview",
        "query": """
            SELECT full_date, source_name, category_name, article_count
            FROM mart.mv_daily_overview
            WHERE full_date >= CURRENT_DATE - INTERVAL '30 days'
            ORDER BY full_date DESC, source_name
        """,
    },
]


# Benchmark runner
def run_benchmark(show_explain: bool = False) -> dict:
    import psycopg2

    conn = psycopg2.connect(**PG_CONN_PARAMS)
    conn.set_session(autocommit=True)
    cur = conn.cursor()

    results = []

    for bm in BENCHMARK_QUERIES:
        # Warm-up: run once to populate cache
        try:
            cur.execute(bm["query"])
            cur.fetchall()
        except Exception:
            pass

        # Timed run (3 iterations, take median)
        times = []
        row_count = 0
        error = None

        for _ in range(3):
            try:
                start = time.monotonic()
                cur.execute(bm["query"])
                rows = cur.fetchall()
                elapsed = (time.monotonic() - start) * 1000  # ms
                times.append(elapsed)
                row_count = len(rows)
            except Exception as e:
                error = str(e)
                break

        # EXPLAIN ANALYZE (optional)
        explain_output = None
        if show_explain and not error:
            try:
                cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) {bm['query']}")
                explain_output = "\n".join(row[0] for row in cur.fetchall())
            except Exception:
                pass

        if times:
            times.sort()
            median_ms = times[len(times) // 2]
        else:
            median_ms = None

        result = {
            "name": bm["name"],
            "description": bm["description"],
            "median_ms": round(median_ms, 2) if median_ms else None,
            "min_ms": round(min(times), 2) if times else None,
            "max_ms": round(max(times), 2) if times else None,
            "rows": row_count,
        }

        if error:
            result["error"] = error
        if explain_output:
            result["explain"] = explain_output

        results.append(result)

    cur.close()
    conn.close()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "benchmark_count": len(results),
        "results": results,
    }


def print_report(report: dict) -> None:
    print("\n" + "=" * 80)
    print(f"  NewsPulse Query Benchmark — {report['timestamp']}")
    print("=" * 80)
    print(f"  {'Query':<35} {'Median':>10} {'Min':>10} {'Max':>10} {'Rows':>8}")
    print("  " + "-" * 73)

    for r in report["results"]:
        name = r["name"][:35]
        if r.get("error"):
            print(f"  {name:<35} {'ERROR':>10}")
        else:
            median = f"{r['median_ms']:.1f}ms"
            min_t = f"{r['min_ms']:.1f}ms"
            max_t = f"{r['max_ms']:.1f}ms"
            print(f"  {name:<35} {median:>10} {min_t:>10} {max_t:>10} {r['rows']:>8}")

        if r.get("explain"):
            print(f"\n  EXPLAIN ANALYZE:")
            for line in r["explain"].split("\n"):
                print(f"    {line}")
            print()

    print("=" * 80 + "\n")


def compare_reports(before_path: str, after_path: str) -> None:
    with open(before_path) as f:
        before = json.load(f)
    with open(after_path) as f:
        after = json.load(f)

    before_map = {r["name"]: r for r in before["results"]}
    after_map = {r["name"]: r for r in after["results"]}

    print("\n" + "=" * 85)
    print("  Performance Comparison: Before vs After Optimization")
    print("=" * 85)
    print(f"  {'Query':<32} {'Before':>10} {'After':>10} {'Speedup':>10} {'Status':>8}")
    print("  " + "-" * 70)

    for name in before_map:
        b = before_map[name]
        a = after_map.get(name, {})

        b_ms = b.get("median_ms")
        a_ms = a.get("median_ms")

        if b_ms and a_ms:
            speedup = b_ms / a_ms
            status = "✅" if speedup > 1.2 else ("➖" if speedup > 0.8 else "⚠️")
            print(f"  {name[:32]:<32} {b_ms:>8.1f}ms {a_ms:>8.1f}ms {speedup:>9.1f}x {status:>8}")
        else:
            print(f"  {name[:32]:<32} {'N/A':>10} {'N/A':>10}")

    print("=" * 85 + "\n")


# CLI
def main():
    parser = argparse.ArgumentParser(description="NewsPulse Query Benchmark")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--explain", action="store_true", help="Show EXPLAIN ANALYZE")
    parser.add_argument("--save", type=str, help="Save results to JSON file")
    parser.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"),
                        help="Compare two saved benchmark files")
    args = parser.parse_args()

    if args.compare:
        compare_reports(args.compare[0], args.compare[1])
        return

    report = run_benchmark(show_explain=args.explain)

    if args.save:
        with open(args.save, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Results saved to {args.save}")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)


if __name__ == "__main__":
    main()