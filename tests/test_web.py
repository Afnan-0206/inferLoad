"""Tests for InferLoad local FastAPI web console and REST API routes."""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from inferload.web import app, _jobs, ExperimentJobState, JobStatus


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_web_health_endpoint(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "inferload_version" in data
    assert "environment" in data
    assert "ollama" in data
    assert "os_system" in data["environment"]


def test_web_index_serves_html(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "InferLoad" in resp.text
    assert "Run a New Benchmark" in resp.text or "benchmark-form" in resp.text


def test_web_validate_valid_config(client: TestClient) -> None:
    payload = {
        "name": "test-sweep",
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "qwen2.5:0.5b",
        "concurrency": [1, 2],
        "repetitions": 2,
        "requests_per_point": 3,
        "prompts": ["What is caching?"],
        "max_tokens": 16,
        "slo": {
            "max_ttft_p95_ms": 1000.0,
            "max_total_latency_p95_ms": 2500.0,
            "max_error_rate_pct": 1.0,
            "min_throughput_req_per_sec": 1.0,
        }
    }
    resp = client.post("/api/validate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["errors"] == []


def test_web_validate_invalid_config(client: TestClient) -> None:
    payload = {
        "base_url": "not-a-valid-url",
        "model": "",
        "concurrency": [0, -1],
        "requests_per_point": 0,
        "repetitions": 0,
        "prompts": ["   "],
    }
    resp = client.post("/api/validate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False
    assert len(data["errors"]) >= 4


def test_web_create_experiment_invalid_payload_rejected(client: TestClient) -> None:
    payload = {
        "base_url": "bad-url",
        "model": "",
        "concurrency": [],
    }
    resp = client.post("/api/experiments", json=payload)
    assert resp.status_code == 400


def test_web_experiment_status_not_found(client: TestClient) -> None:
    resp = client.get("/api/experiments/non-existent-job-id")
    assert resp.status_code == 404


def test_web_history_endpoint(client: TestClient) -> None:
    resp = client.get("/api/history")
    assert resp.status_code == 200
    history = resp.json()
    assert isinstance(history, list)
    if history:
        first = history[0]
        assert "experiment_id" in first
        assert "model" in first
        assert "concurrency_levels" in first


def test_web_artifact_path_traversal_safety(client: TestClient, tmp_path: Path) -> None:
    # Set up mock job state
    mock_job_id = "test-job-security"
    fake_exp_dir = tmp_path / "exp-sec-test"
    fake_exp_dir.mkdir(parents=True)
    (fake_exp_dir / "summary.json").write_text('{"test": true}', encoding="utf-8")

    _jobs[mock_job_id] = ExperimentJobState(
        job_id=mock_job_id,
        experiment_id="exp-sec-test",
        status=JobStatus.COMPLETED,
        artifacts_dir=str(fake_exp_dir),
    )

    # 1. Normal access to valid artifact
    valid_resp = client.get(f"/api/experiments/{mock_job_id}/artifacts/summary.json")
    assert valid_resp.status_code == 200
    assert valid_resp.json() == {"test": True}

    # 2. Path traversal attempt should fail with 403 or 404
    traversal_resp = client.get(f"/api/experiments/{mock_job_id}/artifacts/../../pyproject.toml")
    assert traversal_resp.status_code in [403, 404]

    # Clean up
    _jobs.pop(mock_job_id, None)


def test_web_report_endpoint(client: TestClient, tmp_path: Path) -> None:
    mock_job_id = "test-job-report"
    fake_exp_dir = tmp_path / "exp-report-test"
    fake_exp_dir.mkdir(parents=True)
    (fake_exp_dir / "report.md").write_text("# Test Report Content", encoding="utf-8")

    _jobs[mock_job_id] = ExperimentJobState(
        job_id=mock_job_id,
        experiment_id="exp-report-test",
        status=JobStatus.COMPLETED,
        artifacts_dir=str(fake_exp_dir),
    )

    resp = client.get(f"/api/experiments/{mock_job_id}/report")
    assert resp.status_code == 200
    assert resp.json()["report_markdown"] == "# Test Report Content"

    _jobs.pop(mock_job_id, None)


def test_web_logs_endpoint(client: TestClient) -> None:
    mock_job_id = "test-job-logs"
    _jobs[mock_job_id] = ExperimentJobState(
        job_id=mock_job_id,
        status=JobStatus.RUNNING,
        logs=["[12:00:00] Job started", "[12:00:01] Running trial [1/2]"],
    )

    resp = client.get(f"/api/experiments/{mock_job_id}/logs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == mock_job_id
    assert len(data["logs"]) == 2
    assert "Job started" in data["logs"][0]

    _jobs.pop(mock_job_id, None)


def test_web_historical_report_resolution(client: TestClient) -> None:
    # Use existing historical experiment in results/ if present
    res_dir = Path("results")
    exp_dirs = [d for d in res_dir.iterdir() if d.is_dir() and d.name.startswith("experiment-") and (d / "report.md").is_file()]
    if exp_dirs:
        target_dir = exp_dirs[0].name
        resp = client.get(f"/api/experiments/historical-{target_dir}/report")
        assert resp.status_code == 200
        assert "report_markdown" in resp.json()


def test_web_auth_status_open_mode(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INFERLOAD_AUTH_TOKEN", raising=False)
    resp = client.get("/api/auth/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["auth_required"] is False
    assert data["authenticated"] is True
    assert data["mode"] == "permissive"


def test_web_auth_enforcement_when_token_configured(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INFERLOAD_AUTH_TOKEN", "enterprise-secret-key-123")

    # 1. Auth status without token
    resp = client.get("/api/auth/status")
    assert resp.status_code == 200
    assert resp.json()["auth_required"] is True
    assert resp.json()["authenticated"] is False

    # 2. Auth status with token
    resp_authed = client.get("/api/auth/status", headers={"Authorization": "Bearer enterprise-secret-key-123"})
    assert resp_authed.status_code == 200
    assert resp_authed.json()["authenticated"] is True

    # 3. Mutation endpoint rejected without token
    payload = {
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "qwen2.5:0.5b",
        "concurrency": [1],
    }
    unauth_resp = client.post("/api/validate", json=payload)
    assert unauth_resp.status_code == 401

    # 4. Mutation endpoint allowed with token
    auth_resp = client.post(
        "/api/validate",
        json=payload,
        headers={"Authorization": "Bearer enterprise-secret-key-123"},
    )
    assert auth_resp.status_code == 200


def test_web_telemetry_test_endpoint_invalid_url(client: TestClient) -> None:
    resp = client.post("/api/telemetry/test", json={"metrics_url": "ftp://bad-url"})
    assert resp.status_code == 200
    assert resp.json()["valid"] is False


def test_web_experiment_sse_stream(client: TestClient) -> None:
    mock_job_id = "test-job-sse"
    _jobs[mock_job_id] = ExperimentJobState(
        job_id=mock_job_id,
        status=JobStatus.COMPLETED,
    )
    try:
        resp = client.get(f"/api/experiments/{mock_job_id}/stream")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        assert "initial_state" in resp.text
    finally:
        _jobs.pop(mock_job_id, None)


def test_web_experiment_websocket(client: TestClient) -> None:
    mock_job_id = "test-job-ws"
    _jobs[mock_job_id] = ExperimentJobState(
        job_id=mock_job_id,
        status=JobStatus.COMPLETED,
    )
    try:
        with client.websocket_connect(f"/ws/experiments/{mock_job_id}") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "initial_state"
            assert data["job"]["job_id"] == mock_job_id
    finally:
        _jobs.pop(mock_job_id, None)

