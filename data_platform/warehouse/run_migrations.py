import os
import glob
import hashlib
import psycopg2
from loguru import logger

PG_HOST = os.getenv("PG_HOST", os.getenv("POSTGRES_HOST", "postgres"))
PG_PORT = int(os.getenv("PG_PORT", os.getenv("POSTGRES_PORT", "5432")))
PG_DB = os.getenv("PG_DB", os.getenv("POSTGRES_DB", "newspulse"))
PG_USER = os.getenv("PG_USER", os.getenv("POSTGRES_USER", "newspulse"))
PG_PASSWORD = os.getenv("PG_PASSWORD", os.getenv("POSTGRES_PASSWORD", "newspulse"))

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


def _migration_sort_key(filepath):
    filename = os.path.basename(filepath)
    prefix = filename.split("_", 1)[0]
    return (0, int(prefix), filename) if prefix.isdigit() else (1, 0, filename)


def run_migrations():
    migration_files = sorted(
        glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")),
        key=_migration_sort_key,
    )

    if not migration_files:
        logger.warning(f"No migration files found in {MIGRATIONS_DIR}")
        return

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.schema_migrations (
                    filename TEXT PRIMARY KEY,
                    checksum_sha256 TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("SELECT pg_advisory_lock(hashtext('newspulse_schema_migrations'))")
            conn.commit()

            applied_count = 0
            for filepath in migration_files:
                filename = os.path.basename(filepath)
                with open(filepath, "r", encoding="utf-8") as f:
                    sql = f.read()
                checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()

                cur.execute(
                    "SELECT checksum_sha256 FROM public.schema_migrations WHERE filename = %s",
                    (filename,),
                )
                existing = cur.fetchone()
                if existing:
                    if existing[0] != checksum:
                        raise RuntimeError(
                            f"Migration {filename} changed after it was applied"
                        )
                    logger.info(f"Skipping applied migration: {filename}")
                    continue

                logger.info(f"Running migration: {filename}")
                cur.execute(sql)
                cur.execute(
                    """
                    INSERT INTO public.schema_migrations (filename, checksum_sha256)
                    VALUES (%s, %s)
                    """,
                    (filename, checksum),
                )
                conn.commit()
                applied_count += 1
                logger.info(f"  ✓ {filename} applied successfully")

            logger.info(
                f"Migration run complete: {applied_count} applied, "
                f"{len(migration_files) - applied_count} already current"
            )

    except Exception as e:
        conn.rollback()
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(hashtext('newspulse_schema_migrations'))")
            conn.commit()
        except Exception:
            conn.rollback()
        conn.close()


if __name__ == "__main__":
    run_migrations()
