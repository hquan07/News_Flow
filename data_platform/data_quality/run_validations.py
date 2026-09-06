import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

from loguru import logger


# Config
PG_HOST = os.getenv("PG_HOST", "postgres")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_USER = os.getenv("PG_USER", "newspulse")
PG_PASSWORD = os.getenv("PG_PASSWORD", "newspulse")
PG_DB = os.getenv("PG_DB", "newspulse")
PG_CONN = os.getenv(
    "PG_CONN_STRING",
    f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}",
)
MONGO_HOST = os.getenv("MONGO_HOST", "mongo")
MONGO_PORT = os.getenv("MONGO_PORT", "27017")
MONGO_URI = os.getenv("MONGO_URI", f"mongodb://{MONGO_HOST}:{MONGO_PORT}")
MONGO_DB = os.getenv("MONGO_DB", "newspulse")


# SQL-based validators
def get_pg_connection():
    import psycopg2
    from urllib.parse import urlparse

    parsed = urlparse(PG_CONN.replace("postgresql+psycopg2://", "postgresql://"))
    return psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        dbname=parsed.path.lstrip("/"),
    )


def run_sql_check(conn, name: str, query: str, expected: str = "pass") -> dict:
    cur = conn.cursor()
    try:
        cur.execute(query)
        result = cur.fetchone()
        value = result[0] if result else None

        if expected == "pass":
            passed = bool(value)
        elif expected == "non_zero":
            passed = value is not None and value > 0
        elif expected == "zero":
            passed = value == 0
        else:
            passed = value == expected

        return {
            "check": name,
            "passed": passed,
            "value": value,
        }
    except Exception as e:
        return {
            "check": name,
            "passed": False,
            "error": str(e),
        }
    finally:
        cur.close()


# Layer-specific validation checks
RAW_CHECKS = [
    (
        "raw.articles row count > 0",
        "SELECT COUNT(*) > 0 FROM raw.articles",
        "pass",
    ),
    (
        "raw.articles no null url",
        "SELECT COUNT(*) FROM raw.articles WHERE url IS NULL",
        "zero",
    ),
    (
        "raw.articles no null url_hash",
        "SELECT COUNT(*) FROM raw.articles WHERE url_hash IS NULL",
        "zero",
    ),
    (
        "raw.articles no null title",
        "SELECT COUNT(*) FROM raw.articles WHERE title IS NULL",
        "zero",
    ),
    (
        "raw.articles url_hash unique",
        """SELECT COUNT(*) FROM (
            SELECT url_hash FROM raw.articles
            GROUP BY url_hash HAVING COUNT(*) > 1
        ) dupes""",
        "zero",
    ),
    (
        "raw.articles valid sources",
        """SELECT COUNT(*) FROM raw.articles
        WHERE source NOT IN ('vnexpress','tuoitre','thanhnien','VnExpress','Tuổi Trẻ','Thanh Niên')
        AND source IS NOT NULL""",
        "zero",
    ),
    (
        "raw.articles valid categories",
        """SELECT COUNT(*) FROM raw.articles
        WHERE category NOT IN ('sports','tech','economy','politics','general',
                               'entertainment','health','education','world','law')
        AND category IS NOT NULL""",
        "zero",
    ),
    (
        "raw.articles valid publish_hour (0-23)",
        "SELECT COUNT(*) FROM raw.articles WHERE publish_hour < 0 OR publish_hour > 23",
        "zero",
    ),
    (
        "raw.articles word_count non-negative",
        "SELECT COUNT(*) FROM raw.articles WHERE word_count < 0",
        "zero",
    ),
    (
        "raw.articles valid URL format",
        "SELECT COUNT(*) FROM raw.articles WHERE url NOT LIKE 'http%'",
        "zero",
    ),
    (
        "raw.article_keywords has data",
        "SELECT COUNT(*) > 0 FROM raw.article_keywords",
        "pass",
    ),
    (
        "raw.article_entities has data",
        "SELECT COUNT(*) > 0 FROM raw.article_entities",
        "pass",
    ),
]

STAGING_CHECKS = [
    (
        "staging.articles row count > 0",
        "SELECT COUNT(*) > 0 FROM staging.articles",
        "pass",
    ),
    (
        "staging.articles no null url",
        "SELECT COUNT(*) FROM staging.articles WHERE url IS NULL",
        "zero",
    ),
    (
        "staging.articles no null source",
        "SELECT COUNT(*) FROM staging.articles WHERE source IS NULL",
        "zero",
    ),
    (
        "staging.articles no null category",
        "SELECT COUNT(*) FROM staging.articles WHERE category IS NULL",
        "zero",
    ),
    (
        "staging.articles url_hash unique",
        """SELECT COUNT(*) FROM (
            SELECT url_hash FROM staging.articles
            GROUP BY url_hash HAVING COUNT(*) > 1
        ) dupes""",
        "zero",
    ),
    (
        "staging.articles normalized sources (lowercase)",
        """SELECT COUNT(*) FROM staging.articles
        WHERE source NOT IN ('vnexpress','tuoitre','thanhnien')""",
        "zero",
    ),
    (
        "staging.articles all 10 categories",
        """SELECT COUNT(*) FROM staging.articles
        WHERE category NOT IN ('sports','tech','economy','politics','general',
                               'entertainment','health','education','world','law')""",
        "zero",
    ),
    (
        "staging.articles HTTPS URLs",
        "SELECT COUNT(*) FROM staging.articles WHERE url NOT LIKE 'https://%'",
        "zero",
    ),
    (
        "staging.articles content coverage > 90%",
        """SELECT CASE
            WHEN COUNT(*) = 0 THEN TRUE
            ELSE (COUNT(content)::FLOAT / COUNT(*)::FLOAT) > 0.9
        END FROM staging.articles""",
        "pass",
    ),
    (
        "staging vs raw row count (no data loss)",
        """SELECT (SELECT COUNT(*) FROM staging.articles) >=
               (SELECT COUNT(*) FROM raw.articles) * 0.95""",
        "pass",
    ),
]

WAREHOUSE_CHECKS = [
    (
        "warehouse.fact_article row count > 0",
        "SELECT COUNT(*) > 0 FROM warehouse.fact_article",
        "pass",
    ),
    (
        "warehouse.fact_article url_hash unique",
        """SELECT COUNT(*) FROM (
            SELECT url_hash FROM warehouse.fact_article
            GROUP BY url_hash HAVING COUNT(*) > 1
        ) dupes""",
        "zero",
    ),
    (
        "warehouse.fact_article no null source_id",
        "SELECT COUNT(*) FROM warehouse.fact_article WHERE source_id IS NULL",
        "zero",
    ),
    (
        "warehouse.fact_article no null category_id",
        "SELECT COUNT(*) FROM warehouse.fact_article WHERE category_id IS NULL",
        "zero",
    ),
    (
        "warehouse.fact_article valid source_id (FK integrity)",
        """SELECT COUNT(*) FROM warehouse.fact_article fa
        WHERE NOT EXISTS (SELECT 1 FROM warehouse.dim_source ds WHERE ds.source_id = fa.source_id)""",
        "zero",
    ),
    (
        "warehouse.fact_article valid category_id (FK integrity)",
        """SELECT COUNT(*) FROM warehouse.fact_article fa
        WHERE NOT EXISTS (SELECT 1 FROM warehouse.dim_category dc WHERE dc.category_id = fa.category_id)""",
        "zero",
    ),
    (
        "warehouse.fact_article valid time_id (FK integrity)",
        """SELECT COUNT(*) FROM warehouse.fact_article fa
        WHERE fa.time_id IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM warehouse.dim_time dt WHERE dt.time_id = fa.time_id)""",
        "zero",
    ),
    (
        "warehouse.fact_article valid author_id (FK integrity)",
        """SELECT COUNT(*) FROM warehouse.fact_article fa
        WHERE fa.author_id IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM warehouse.dim_author da WHERE da.author_id = fa.author_id)""",
        "zero",
    ),
    (
        "warehouse.dim_source has 3 sources",
        "SELECT COUNT(*) >= 3 FROM warehouse.dim_source",
        "pass",
    ),
    (
        "warehouse.dim_category has 10 categories",
        "SELECT COUNT(*) >= 10 FROM warehouse.dim_category",
        "pass",
    ),
    (
        "warehouse.dim_time covers 2024-2026",
        "SELECT COUNT(*) >= 1000 FROM warehouse.dim_time",
        "pass",
    ),
    (
        "warehouse.dim_time valid day_of_week (1-7 ISO)",
        "SELECT COUNT(*) FROM warehouse.dim_time WHERE day_of_week < 1 OR day_of_week > 7",
        "zero",
    ),
    (
        "warehouse.dim_time is_weekend matches day_of_week",
        """SELECT COUNT(*) FROM warehouse.dim_time
        WHERE (day_of_week IN (6,7) AND is_weekend = FALSE)
           OR (day_of_week NOT IN (6,7) AND is_weekend = TRUE)""",
        "zero",
    ),
    (
        "warehouse.dim_entity valid types",
        """SELECT COUNT(*) FROM warehouse.dim_entity
        WHERE entity_type NOT IN ('person','location','organization','PER','LOC','ORG')""",
        "zero",
    ),
    (
        "warehouse.bridge_article_keyword FK integrity",
        """SELECT COUNT(*) FROM warehouse.bridge_article_keyword bak
        WHERE NOT EXISTS (SELECT 1 FROM warehouse.fact_article fa WHERE fa.article_id = bak.article_id)""",
        "zero",
    ),
    (
        "warehouse.bridge_article_entity FK integrity",
        """SELECT COUNT(*) FROM warehouse.bridge_article_entity bae
        WHERE NOT EXISTS (SELECT 1 FROM warehouse.fact_article fa WHERE fa.article_id = bae.article_id)""",
        "zero",
    ),
    (
        "warehouse vs staging row count (no data loss)",
        """SELECT (SELECT COUNT(*) FROM warehouse.fact_article) >=
               (SELECT COUNT(*) FROM staging.articles) * 0.90""",
        "pass",
    ),
]

LAYER_CHECKS = {
    "raw": RAW_CHECKS,
    "staging": STAGING_CHECKS,
    "warehouse": WAREHOUSE_CHECKS,
}


# Runner
def run_layer(conn, layer: str) -> dict:
    checks = LAYER_CHECKS.get(layer, [])
    if not checks:
        return {"layer": layer, "error": f"Unknown layer: {layer}"}

    results = []
    passed_count = 0
    failed_count = 0

    for name, query, expected in checks:
        result = run_sql_check(conn, name, query, expected)
        results.append(result)
        if result["passed"]:
            passed_count += 1
        else:
            failed_count += 1

    return {
        "layer": layer,
        "total": len(results),
        "passed": passed_count,
        "failed": failed_count,
        "success_rate": round(passed_count / len(results) * 100, 1) if results else 0,
        "checks": results,
    }


def run_all(layers: list[str] | None = None) -> dict:
    if layers is None:
        layers = ["raw", "staging", "warehouse"]

    conn = get_pg_connection()
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "layers": {},
    }

    total_passed = 0
    total_failed = 0

    for layer in layers:
        layer_result = run_layer(conn, layer)
        report["layers"][layer] = layer_result
        total_passed += layer_result.get("passed", 0)
        total_failed += layer_result.get("failed", 0)

    conn.close()

    report["summary"] = {
        "total_checks": total_passed + total_failed,
        "passed": total_passed,
        "failed": total_failed,
        "overall": "PASS" if total_failed == 0 else "FAIL",
    }

    return report


# Console output
def print_report(report: dict) -> None:
    summary = report["summary"]
    icon = "✅" if summary["overall"] == "PASS" else "❌"

    print("\n" + "=" * 65)
    print(f"  NewsPulse Data Quality Report — {report['timestamp']}")
    print(f"  Overall: {icon} {summary['overall']} "
          f"({summary['passed']}/{summary['total_checks']} checks passed)")
    print("=" * 65)

    for layer_name, layer_data in report["layers"].items():
        status = "✅" if layer_data["failed"] == 0 else "❌"
        print(f"\n  {status} {layer_name.upper()} layer — "
              f"{layer_data['passed']}/{layer_data['total']} passed "
              f"({layer_data['success_rate']}%)")

        for check in layer_data["checks"]:
            c_icon = "  ✓" if check["passed"] else "  ✗"
            line = f"    {c_icon} {check['check']}"
            if not check["passed"]:
                if "error" in check:
                    line += f"  [ERROR: {check['error']}]"
                else:
                    line += f"  [value={check.get('value')}]"
            print(line)

    print("\n" + "=" * 65 + "\n")


# Airflow-callable
def airflow_validate_raw(**kwargs):
    report = run_all(["raw"])
    kwargs.get("ti", {}) and kwargs["ti"].xcom_push(key="dq_raw", value=report)
    if report["summary"]["overall"] != "PASS":
        failed = [c["check"] for c in report["layers"]["raw"]["checks"] if not c["passed"]]
        raise RuntimeError(f"Raw layer DQ failed:\n" + "\n".join(f"  - {f}" for f in failed))


def airflow_validate_staging(**kwargs):
    report = run_all(["staging"])
    kwargs.get("ti", {}) and kwargs["ti"].xcom_push(key="dq_staging", value=report)
    if report["summary"]["overall"] != "PASS":
        failed = [c["check"] for c in report["layers"]["staging"]["checks"] if not c["passed"]]
        raise RuntimeError(f"Staging layer DQ failed:\n" + "\n".join(f"  - {f}" for f in failed))


def airflow_validate_warehouse(**kwargs):
    report = run_all(["warehouse"])
    kwargs.get("ti", {}) and kwargs["ti"].xcom_push(key="dq_warehouse", value=report)
    if report["summary"]["overall"] != "PASS":
        failed = [c["check"] for c in report["layers"]["warehouse"]["checks"] if not c["passed"]]
        raise RuntimeError(f"Warehouse layer DQ failed:\n" + "\n".join(f"  - {f}" for f in failed))


# CLI
def main():
    parser = argparse.ArgumentParser(description="NewsPulse Data Quality Validator")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--layer", "-l",
        choices=["raw", "staging", "warehouse"],
        nargs="+",
        help="Validate specific layer(s)",
    )
    args = parser.parse_args()

    report = run_all(layers=args.layer)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print_report(report)

    sys.exit(0 if report["summary"]["overall"] == "PASS" else 1)


if __name__ == "__main__":
    main()