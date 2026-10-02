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
