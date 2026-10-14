"""Retry selected raw HTML archives from the durable local MinIO copy."""

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import boto3
from airflow import DAG
from airflow.operators.python import PythonOperator
from pymongo import MongoClient

from integrations.cloudvault import CloudVaultClient, CloudVaultError
from integrations.cloudvault_raw_html import upload_raw_html_path


def _retry_delay(attempt: int) -> timedelta:
    return timedelta(minutes=min(6 * 60, 5 * (2 ** max(0, attempt - 1))))


def retry_raw_html_archives() -> dict:
    if os.getenv("CLOUDVAULT_RAW_HTML_ARCHIVE_ENABLED", "false").lower() != "true":
        return {"processed": 0, "uploaded": 0, "failed": 0, "disabled": True}

    now = datetime.utcnow()
    max_attempts = int(os.getenv("CLOUDVAULT_RAW_HTML_RETRY_MAX_ATTEMPTS", "5"))
    mongo = MongoClient(
        os.getenv("MONGO_URI", "mongodb://mongo:27017"),
        serverSelectionTimeoutMS=3000,
    )
    storage = boto3.client(
        "s3",
        endpoint_url=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
        aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "admin"),
        aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "admin123"),
    )
    cloudvault = CloudVaultClient.from_env()
    processed = uploaded_count = failed_count = 0
    try:
        collection = mongo[os.getenv("MONGO_DB", "newspulse")]["cloudvault_raw_html_archives"]
        pending = list(collection.find({
            "status": "retry_pending",
            "next_retry_at": {"$lte": now},
            "attempt_count": {"$lt": max_attempts},
        }).sort("next_retry_at", 1).limit(50))
        for record in pending:
            processed += 1
            attempt = int(record.get("attempt_count", 0)) + 1
            try:
                with tempfile.TemporaryDirectory(prefix="newspulse-html-retry-") as directory:
                    path = Path(directory) / f"{record['url_sha256']}.html"
                    with path.open("wb") as handle:
                        storage.download_fileobj(
                            record["local_bucket"], record["local_object_key"], handle
                        )
                    result = upload_raw_html_path(path, record, client=cloudvault)
            except CloudVaultError as error:
                terminal = attempt >= max_attempts or not error.retriable
                collection.update_one({"_id": record["_id"]}, {"$set": {
                    "status": "failed" if terminal else "retry_pending",
                    "attempt_count": attempt,
                    "next_retry_at": now + _retry_delay(attempt),
                    "last_error": {
                        "code": error.code,
                        "http_status": error.status_code,
                        "retriable": error.retriable,
                    },
                    "updated_at": now,
                }})
                failed_count += 1
                continue
            except Exception:
                terminal = attempt >= max_attempts
                collection.update_one({"_id": record["_id"]}, {"$set": {
                    "status": "failed" if terminal else "retry_pending",
                    "attempt_count": attempt,
                    "next_retry_at": now + _retry_delay(attempt),
                    "last_error": {"code": "LOCAL_OBJECT_UNAVAILABLE", "retriable": True},
                    "updated_at": now,
                }})
                failed_count += 1
                continue

            collection.update_one({"_id": record["_id"]}, {"$set": {
                **result,
                "attempt_count": attempt,
                "last_error": None,
                "updated_at": now,
            }})
            uploaded_count += 1
        return {"processed": processed, "uploaded": uploaded_count, "failed": failed_count}
    finally:
        mongo.close()


with DAG(
    dag_id="cloudvault_raw_html_retry",
    default_args={"owner": "newspulse", "retries": 0},
    description="Retry selected raw HTML archives without blocking crawlers",
    schedule_interval="*/15 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["cloudvault", "archive", "retry"],
) as dag:
    PythonOperator(
        task_id="retry_raw_html_archives",
        python_callable=retry_raw_html_archives,
        execution_timeout=timedelta(minutes=20),
    )
