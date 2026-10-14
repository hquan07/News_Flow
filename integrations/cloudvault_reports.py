"""CloudVault export helpers for owner-scoped intelligence reports."""

from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping

from integrations.cloudvault import CloudVaultClient, CloudVaultError


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def owner_reference(owner_id: str) -> str:
    """Return a non-reversible owner reference safe for project metadata."""
    return hashlib.sha256(owner_id.encode("utf-8")).hexdigest()


def report_export_payload(report: Mapping[str, Any], owner_id: str) -> dict[str, Any]:
    """Build the portable report without exposing the News_Flow owner id."""
    payload = {
        key: value
        for key, value in report.items()
        if key not in {"_id", "owner_id", "cloudvault_archive"}
    }
    payload["id"] = str(report["_id"])
    payload["owner_ref"] = owner_reference(owner_id)
    return payload


def upload_intelligence_report(
    report: Mapping[str, Any],
    *,
    owner_id: str,
    logical_date: str,
    source_run_id: str,
    client: CloudVaultClient | None = None,
) -> dict[str, Any]:
    """Serialize and upload one report with a stable logical-run identity."""
    archive_client = client or CloudVaultClient.from_env()
    owner_ref = owner_reference(owner_id)
    saved_query_id = str(report["saved_query_id"])
    report_id = str(report["_id"])
    idempotency_key = (
        f"news-flow:intelligence-report:{owner_ref[:20]}:"
        f"{saved_query_id}:{logical_date}"
    )
    metadata = {
        "artifact_type": "intelligence_report",
        "logical_date": logical_date,
        "source_run_id": source_run_id,
        "retention_class": "report",
        "owner_ref": owner_ref,
        "visibility": "owner",
        "newsflow_report_id": report_id,
        "saved_query_id": saved_query_id,
    }
    payload = report_export_payload(report, owner_id)

    with tempfile.TemporaryDirectory(prefix="newspulse-cloudvault-report-") as directory:
        path = Path(directory) / f"intelligence-report-{report_id}.json"
        path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
                default=_json_default,
            ),
            encoding="utf-8",
        )
        response = archive_client.upload_file(
            path,
            metadata=metadata,
            idempotency_key=idempotency_key,
            content_type="application/json",
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
