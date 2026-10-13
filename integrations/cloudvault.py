"""Bounded, project-scoped CloudVault client for generated artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import quote

import requests


DEFAULT_PROJECT_ID = "news-flow"
REQUIRED_METADATA = {"artifact_type", "logical_date", "source_run_id", "retention_class"}


class CloudVaultError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, code: str = "CLIENT_ERROR", retriable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.retriable = retriable


@dataclass(frozen=True)
class CloudVaultConfig:
    base_url: str
    service_token: str
    project_id: str = DEFAULT_PROJECT_ID
    connect_timeout: float = 5.0
    read_timeout: float = 60.0
    max_retries: int = 3
    retry_base_seconds: float = 0.5
    max_file_bytes: int = 100 * 1024 * 1024

    @classmethod
    def from_env(cls) -> "CloudVaultConfig":
        token = os.getenv("CLOUDVAULT_SERVICE_TOKEN", "").strip()
        if not token:
            raise CloudVaultError("CLOUDVAULT_SERVICE_TOKEN is required", code="CONFIG_ERROR")
        project_id = os.getenv("CLOUDVAULT_PROJECT_ID", DEFAULT_PROJECT_ID).strip()
        if project_id != DEFAULT_PROJECT_ID:
            raise CloudVaultError(f"CLOUDVAULT_PROJECT_ID must be {DEFAULT_PROJECT_ID}", code="CONFIG_ERROR")
        return cls(
            base_url=os.getenv("CLOUDVAULT_BASE_URL", "http://cloudvault-api").rstrip("/"),
            service_token=token,
            project_id=project_id,
            connect_timeout=float(os.getenv("CLOUDVAULT_CONNECT_TIMEOUT_SECONDS", "5")),
            read_timeout=float(os.getenv("CLOUDVAULT_READ_TIMEOUT_SECONDS", "60")),
            max_retries=int(os.getenv("CLOUDVAULT_MAX_RETRIES", "3")),
            retry_base_seconds=float(os.getenv("CLOUDVAULT_RETRY_BASE_SECONDS", "0.5")),
            max_file_bytes=int(os.getenv("CLOUDVAULT_MAX_FILE_BYTES", str(100 * 1024 * 1024))),
        )


class CloudVaultClient:
    def __init__(
        self,
        config: CloudVaultConfig,
        *,
        session: requests.Session | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        if not config.base_url.startswith(("http://", "https://")):
            raise CloudVaultError("CLOUDVAULT_BASE_URL must be an HTTP(S) URL", code="CONFIG_ERROR")
        if config.project_id != DEFAULT_PROJECT_ID:
            raise CloudVaultError(f"Client is restricted to project {DEFAULT_PROJECT_ID}", code="CONFIG_ERROR")
        if config.max_retries < 0 or config.max_file_bytes <= 0:
            raise CloudVaultError("Retry and file-size settings are invalid", code="CONFIG_ERROR")
        self.config = config
        self.session = session or requests.Session()
        self._sleep = sleeper
        self._jitter = jitter

    @property
    def _project_url(self) -> str:
        return f"{self.config.base_url}/api/v1/projects/{quote(self.config.project_id, safe='')}"

    def _headers(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.config.service_token}"}
        if extra:
            headers.update(extra)
        return headers

    @staticmethod
    def _error_from_response(response: requests.Response) -> CloudVaultError:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        detail = payload.get("detail", {}) if isinstance(payload, dict) else {}
        if isinstance(detail, dict):
            code = str(detail.get("code") or "HTTP_ERROR")
            message = str(detail.get("message") or f"CloudVault returned HTTP {response.status_code}")
        else:
            code = "HTTP_ERROR"
            message = str(detail or f"CloudVault returned HTTP {response.status_code}")
        retriable = response.status_code == 429 or response.status_code >= 500
        return CloudVaultError(message, status_code=response.status_code, code=code, retriable=retriable)

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", (self.config.connect_timeout, self.config.read_timeout))
        for attempt in range(self.config.max_retries + 1):
            for file_spec in (kwargs.get("files") or {}).values():
                if isinstance(file_spec, tuple) and len(file_spec) > 1 and hasattr(file_spec[1], "seek"):
                    file_spec[1].seek(0)
            try:
                response = self.session.request(method, url, **kwargs)
            except (requests.ConnectionError, requests.Timeout) as exc:
                error = CloudVaultError("CloudVault network request failed", code="NETWORK_ERROR", retriable=True)
                if attempt >= self.config.max_retries:
                    raise error from exc
            else:
                if response.ok:
                    return response
                error = self._error_from_response(response)
                if not error.retriable or attempt >= self.config.max_retries:
                    raise error
                response.close()
            delay = self.config.retry_base_seconds * (2**attempt)
            self._sleep(delay + min(delay * 0.25, self._jitter()))
        raise CloudVaultError("CloudVault retry loop exhausted", code="NETWORK_ERROR", retriable=True)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def upload_file(
        self,
        file_path: str | Path,
        *,
        metadata: Mapping[str, Any],
        idempotency_key: str,
        content_type: str = "application/octet-stream",
    ) -> dict[str, Any]:
        path = Path(file_path)
        if not path.is_file():
            raise CloudVaultError("Upload source is not a file", code="INVALID_FILE")
        size = path.stat().st_size
        if size == 0 or size > self.config.max_file_bytes:
            raise CloudVaultError("Upload source is empty or exceeds the client limit", code="INVALID_FILE")
        if not idempotency_key or len(idempotency_key) > 255:
            raise CloudVaultError("Idempotency key must contain 1-255 characters", code="INVALID_FILE")
        payload = dict(metadata)
        missing = REQUIRED_METADATA - payload.keys()
        if missing:
            raise CloudVaultError(f"Missing metadata fields: {', '.join(sorted(missing))}", code="INVALID_FILE")
        payload["checksum_sha256"] = self._sha256(path)
        with path.open("rb") as handle:
            response = self._request(
                "POST",
                f"{self._project_url}/files/upload",
                headers=self._headers({"Idempotency-Key": idempotency_key}),
                data={"metadata_json": json.dumps(payload, separators=(",", ":"), sort_keys=True)},
                files={"file": (path.name, handle, content_type)},
            )
        return response.json()

    def get_file(self, file_id: str) -> dict[str, Any]:
        response = self._request("GET", f"{self._project_url}/files/{quote(file_id, safe='')}", headers=self._headers())
        return response.json()

    def download_file(self, file_id: str, destination: str | Path) -> Path:
        metadata = self.get_file(file_id)
        expected_checksum = metadata.get("checksum_sha256")
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.part")
        response = self._request(
            "GET",
            f"{self._project_url}/files/{quote(file_id, safe='')}/download",
            headers=self._headers(),
            stream=True,
        )
        digest = hashlib.sha256()
        try:
            with temporary.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        digest.update(chunk)
                        handle.write(chunk)
            if expected_checksum and digest.hexdigest() != expected_checksum:
                raise CloudVaultError("Downloaded file checksum does not match metadata", code="CHECKSUM_MISMATCH")
            os.replace(temporary, target)
            return target
        finally:
            response.close()
            temporary.unlink(missing_ok=True)
