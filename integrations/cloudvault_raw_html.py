"""Selection and upload helpers for opt-in raw HTML archives."""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

from integrations.cloudvault import CloudVaultClient, CloudVaultError


def _csv_set(value: str) -> frozenset[str]:
    return frozenset(item.strip().casefold() for item in value.split(",") if item.strip())


def canonicalize_url(value: str) -> str:
    parts = urlsplit(value.strip())
    scheme = parts.scheme.lower()
    hostname = (parts.hostname or "").lower()
    port = parts.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        hostname = f"{hostname}:{port}"
    path = parts.path or "/"
    return urlunsplit((scheme, hostname, path, parts.query, ""))


def raw_html_object_name(url: str, source: str) -> str:
    """Match the existing local MinIO key contract."""
    url_md5 = hashlib.md5(url.encode("utf-8")).hexdigest()  # nosec B324 - legacy object key only
    return f"{source}/{url_md5}.html"


@dataclass(frozen=True)
class RawHtmlArchivePolicy:
    enabled: bool
    sources: frozenset[str]
    categories: frozenset[str]
    max_bytes: int
    daily_limit: int
    retention_days: int

    @classmethod
    def from_env(cls) -> "RawHtmlArchivePolicy":
        return cls(
            enabled=os.getenv("CLOUDVAULT_RAW_HTML_ARCHIVE_ENABLED", "false").lower() == "true",
            sources=_csv_set(os.getenv("CLOUDVAULT_RAW_HTML_SOURCES", "")),
            categories=_csv_set(os.getenv("CLOUDVAULT_RAW_HTML_CATEGORIES", "")),
            max_bytes=int(os.getenv("CLOUDVAULT_RAW_HTML_MAX_BYTES", str(1024 * 1024))),
            daily_limit=int(os.getenv("CLOUDVAULT_RAW_HTML_DAILY_LIMIT", "100")),
            retention_days=int(os.getenv("CLOUDVAULT_RAW_HTML_RETENTION_DAYS", "14")),
        )

    def allows(self, *, source: str, category: str | None, size_bytes: int) -> bool:
        if not self.enabled or not self.sources:
            return False
        if source.casefold() not in self.sources:
            return False
        if self.categories and (category or "").casefold() not in self.categories:
            return False
        return 0 < size_bytes <= self.max_bytes


def build_archive_record(
    item: Mapping[str, Any],
    *,
    policy: RawHtmlArchivePolicy,
    now: datetime | None = None,
) -> tuple[dict[str, Any], bytes]:
    raw_html = item.get("raw_html") or ""
    content = raw_html.encode("utf-8") if isinstance(raw_html, str) else bytes(raw_html)
    source = str(item.get("source") or "").strip()
    url = str(item.get("url") or "").strip()
    canonical_url = canonicalize_url(url)
    url_sha256 = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()
    content_sha256 = hashlib.sha256(content).hexdigest()
    selected_at = now or datetime.now(timezone.utc)
    crawled_at = item.get("crawl_time") or selected_at
    if hasattr(crawled_at, "isoformat"):
        crawled_at = crawled_at.isoformat()
    else:
        crawled_at = str(crawled_at)
    logical_date = str(crawled_at)[:10]
    record = {
        "url_sha256": url_sha256,
        "content_sha256": content_sha256,
        "canonical_url": canonical_url,
        "source_url": url,
        "source": source,
        "category": item.get("category"),
        "crawled_at": str(crawled_at),
        "logical_date": logical_date,
        "source_run_id": f"crawl:{source}:{url_sha256[:16]}:{content_sha256[:16]}",
        "idempotency_key": f"news-flow:raw-html:{url_sha256}:{content_sha256}",
        "retention_class": "raw_html",
        "expires_at": selected_at + timedelta(days=policy.retention_days),
        "selected_at": selected_at,
        "local_bucket": os.getenv("MINIO_BUCKET", "raw-html"),
        "local_object_key": raw_html_object_name(
            url, str(item.get("_spider_name") or source)
        ),
        "size_bytes": len(content),
    }
    return record, content


def _metadata(record: Mapping[str, Any]) -> dict[str, Any]:
    expires_at = record["expires_at"]
    if hasattr(expires_at, "isoformat"):
        expires_at = expires_at.isoformat()
    return {
        "artifact_type": "selected_raw_html",
        "logical_date": str(record["logical_date"]),
        "source_run_id": str(record["source_run_id"]),
        "retention_class": str(record.get("retention_class") or "raw_html"),
        "source": str(record["source"]),
        "category": record.get("category"),
        "canonical_url": str(record["canonical_url"]),
        "url_sha256": str(record["url_sha256"]),
        "content_sha256": str(record["content_sha256"]),
        "crawled_at": str(record["crawled_at"]),
        "expires_at": str(expires_at),
    }


def upload_raw_html_bytes(
    content: bytes,
    record: Mapping[str, Any],
    *,
    client: CloudVaultClient | None = None,
) -> dict[str, Any]:
    archive_client = client or CloudVaultClient.from_env()
    with tempfile.TemporaryDirectory(prefix="newspulse-cloudvault-html-") as directory:
        path = Path(directory) / f"{record['url_sha256']}.html"
        path.write_bytes(content)
        return upload_raw_html_path(path, record, client=archive_client)


def upload_raw_html_path(
    path: str | Path,
    record: Mapping[str, Any],
    *,
    client: CloudVaultClient | None = None,
) -> dict[str, Any]:
    archive_client = client or CloudVaultClient.from_env()
    response = archive_client.upload_file(
        path,
        metadata=_metadata(record),
        idempotency_key=str(record["idempotency_key"]),
        content_type="text/html",
    )
    file_id = response.get("file_id") or response.get("id")
    if not file_id:
        raise CloudVaultError(
            "CloudVault upload response did not include file_id",
            code="INVALID_RESPONSE",
        )
    return {
        "status": "uploaded",
        "file_id": str(file_id),
        "checksum_sha256": response.get("checksum_sha256"),
        "retention_until": response.get("retention_until"),
        "idempotent_replay": bool(response.get("idempotent_replay", False)),
    }
