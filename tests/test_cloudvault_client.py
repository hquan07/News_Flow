import hashlib
import json

import pytest

from integrations.cloudvault import (
    DEFAULT_PROJECT_ID,
    CloudVaultClient,
    CloudVaultConfig,
    CloudVaultError,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, body=b""):
        self.status_code = status_code
        self._payload = payload or {}
        self._body = body
        self.closed = False

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        return self._payload

    def close(self):
        self.closed = True

    def iter_content(self, chunk_size):
        yield self._body


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


def config(**overrides):
    values = {
        "base_url": "http://cloudvault-api",
        "service_token": "not-a-real-token",
        "project_id": DEFAULT_PROJECT_ID,
        "retry_base_seconds": 0,
    }
    values.update(overrides)
    return CloudVaultConfig(**values)


def test_upload_sends_scoped_auth_idempotency_and_checksum(tmp_path):
    source = tmp_path / "report.json"
    source.write_bytes(b'{"ok":true}')
    session = FakeSession([FakeResponse(201, {"id": "file-1"})])
    client = CloudVaultClient(config(), session=session, sleeper=lambda _: None, jitter=lambda: 0)

    result = client.upload_file(
        source,
        idempotency_key="daily-report:2026-10-14",
        content_type="application/json",
        metadata={
            "artifact_type": "daily_report",
            "logical_date": "2026-10-14",
            "source_run_id": "run-1",
            "retention_class": "report",
        },
    )

    assert result["id"] == "file-1"
    method, url, kwargs = session.calls[0]
    assert method == "POST"
    assert url.endswith(f"/projects/{DEFAULT_PROJECT_ID}/files/upload")
    assert kwargs["headers"] == {
        "Authorization": "Bearer not-a-real-token",
        "Idempotency-Key": "daily-report:2026-10-14",
    }
    metadata = json.loads(kwargs["data"]["metadata_json"])
    assert metadata["checksum_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_retries_only_transient_http_errors(tmp_path):
    source = tmp_path / "report.txt"
    source.write_text("ready")
    session = FakeSession([
        FakeResponse(503, {"detail": {"code": "STORAGE_UNAVAILABLE", "message": "retry"}}),
        FakeResponse(201, {"id": "file-2"}),
    ])
    sleeps = []
    client = CloudVaultClient(config(), session=session, sleeper=sleeps.append, jitter=lambda: 0)
    result = client.upload_file(
        source,
        idempotency_key="report:retry",
        metadata={
            "artifact_type": "report",
            "logical_date": "2026-10-14",
            "source_run_id": "run-2",
            "retention_class": "report",
        },
    )
    assert result["id"] == "file-2"
    assert len(session.calls) == 2
    assert len(sleeps) == 1


def test_does_not_retry_authentication_errors():
    session = FakeSession([
        FakeResponse(401, {"detail": {"code": "INVALID_CREDENTIAL", "message": "invalid"}}),
    ])
    client = CloudVaultClient(config(), session=session, sleeper=lambda _: None)
    with pytest.raises(CloudVaultError) as caught:
        client.get_file("file-1")
    assert caught.value.code == "INVALID_CREDENTIAL"
    assert len(session.calls) == 1


def test_download_verifies_checksum_before_atomic_replace(tmp_path):
    body = b"verified artifact"
    checksum = hashlib.sha256(body).hexdigest()
    session = FakeSession([
        FakeResponse(200, {"id": "file-1", "checksum_sha256": checksum}),
        FakeResponse(200, body=body),
    ])
    client = CloudVaultClient(config(), session=session, sleeper=lambda _: None)
    destination = tmp_path / "artifact.bin"
    assert client.download_file("file-1", destination) == destination
    assert destination.read_bytes() == body


def test_client_rejects_cross_project_configuration():
    with pytest.raises(CloudVaultError) as caught:
        CloudVaultClient(config(project_id="another-project"))
    assert caught.value.code == "CONFIG_ERROR"
