"""Tests for JSON and CSV exporters."""

import csv
import json
from pathlib import Path

from inferload.exporters import export_csv, export_json, export_results
from inferload.models import BenchmarkResult, BenchmarkSummary, MetricStats, RequestRecord


def _make_dummy_result() -> BenchmarkResult:
    req = RequestRecord(
        request_id="req-1",
        index=0,
        is_warmup=False,
        prompt="Sample prompt",
        start_time=100.0,
        end_time=101.5,
        latency_to_first_byte_ms=120.0,
        latency_to_first_token_ms=150.0,
        duration_ms=1500.0,
        status="success",
        http_status=200,
        input_text_length=13,
        output_text="Sample response",
        output_text_length=15,
        input_tokens=10,
        output_tokens=25,
        streaming=True,
        chunk_count=3,
        chunk_delays_ms=[50.0, 50.0],
    )
    summary = BenchmarkSummary(
        total_requests=1,
        success_count=1,
        failure_count=0,
        error_rate=0.0,
        total_duration_s=1.5,
        requests_per_second=0.67,
        successful_requests_per_second=0.67,
        ttft_ms=MetricStats(count=1, min=150.0, max=150.0, mean=150.0, median=150.0, p50=150.0, p95=150.0, p99=150.0),
        total_latency_ms=MetricStats(count=1, min=1500.0, max=1500.0, mean=1500.0, median=1500.0, p50=1500.0, p95=1500.0, p99=1500.0),
        aggregate_input_tokens=10,
        aggregate_output_tokens=25,
        aggregate_tokens_per_second=16.67,
    )
    return BenchmarkResult(
        schema_version="0.1",
        run_id="run-test-123",
        timestamp="2026-10-02T00:00:00Z",
        target={"base_url": "http://localhost:8000/v1", "model": "test-model"},
        workload={"requests": 1, "concurrency": 1},
        execution={"warmup_requests": 0},
        summary=summary,
        requests=[req],
    )


def test_export_json(tmp_path: Path) -> None:
    res = _make_dummy_result()
    out_file = tmp_path / "result.json"
    exported = export_json(res, out_file)

    assert exported.exists()
    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["schema_version"] == "0.1"
    assert data["run_id"] == "run-test-123"
    assert data["summary"]["total_requests"] == 1
    assert len(data["requests"]) == 1
    assert data["requests"][0]["request_id"] == "req-1"


def test_export_csv(tmp_path: Path) -> None:
    res = _make_dummy_result()
    out_file = tmp_path / "result.csv"
    exported = export_csv(res, out_file)

    assert exported.exists()
    with open(out_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 1
    row = rows[0]
    assert row["request_id"] == "req-1"
    assert row["status"] == "success"
    assert row["http_status"] == "200"
    assert float(row["ttft_ms"]) == 150.0
    assert float(row["total_latency_ms"]) == 1500.0
    assert row["input_tokens"] == "10"
    assert row["output_tokens"] == "25"


def test_export_all_results(tmp_path: Path) -> None:
    res = _make_dummy_result()
    exported = export_results(res, output_dir=tmp_path, prefix="bench", formats=["json", "csv"])

    assert "json" in exported
    assert "csv" in exported
    assert exported["json"].name == "bench-run-test-123.json"
    assert exported["csv"].name == "bench-run-test-123.csv"
    assert exported["json"].exists()
    assert exported["csv"].exists()
