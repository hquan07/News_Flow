import os
import glob
import psycopg2
from loguru import logger

from config.spark_config import (
    PG_HOST,
    PG_PORT,
    PG_DB,
    PG_USER,
    PG_PASSWORD,
)

MIGRATIONS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "migrations",
)


def get_connection():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
    )


def run_migrations():
    migration_files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))

    if not migration_files:
        logger.warning(f"No migration files found in {MIGRATIONS_DIR}")
        return

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for filepath in migration_files:
                filename = os.path.basename(filepath)
                logger.info(f"Running migration: {filename}")

                with open(filepath, "r") as f:
                    sql = f.read()

                cur.execute(sql)
                logger.info(f"  ✓ {filename} applied successfully")

            conn.commit()
            logger.info(f"All {len(migration_files)} migrations applied")

    except Exception as e:
        conn.rollback()
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_migrations()