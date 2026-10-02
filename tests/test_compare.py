"""Tests for benchmark comparison logic and CLI compare command."""

from pathlib import Path
import json
import pytest
from typer.testing import CliRunner

from inferload.cli import app
from inferload.compare import compare_benchmarks, compare_files, format_comparison_table
from inferload.models import BenchmarkResult, BenchmarkSummary, MetricStats, RequestRecord


def _build_dummy_result(
    run_id: str,
    ttft_p50: float,
    lat_p50: float,
    req_per_sec: float,
    tokens_per_sec: float,
    success_count: int = 10,
    failure_count: int = 0,
    model: str = "test-model",
    endpoint: str = "http://localhost:8000/v1",
) -> BenchmarkResult:
    total = success_count + failure_count
    err_rate = failure_count / total if total > 0 else 0.0

    summary = BenchmarkSummary(
        total_requests=total,
        success_count=success_count,
        failure_count=failure_count,
        error_rate=err_rate,
        total_duration_s=total / req_per_sec if req_per_sec > 0 else 1.0,
        requests_per_second=req_per_sec,
        successful_requests_per_second=req_per_sec * (1 - err_rate),
        ttft_ms=MetricStats(
            count=success_count,
            min=ttft_p50 * 0.8,
            max=ttft_p50 * 1.5,
            mean=ttft_p50,
            median=ttft_p50,
            p50=ttft_p50,
            p95=ttft_p50 * 1.3,
            p99=ttft_p50 * 1.45,
        ),
        total_latency_ms=MetricStats(
            count=success_count,
            min=lat_p50 * 0.8,
            max=lat_p50 * 1.5,
            mean=lat_p50,
            median=lat_p50,
            p50=lat_p50,
            p95=lat_p50 * 1.3,
            p99=lat_p50 * 1.45,
        ),
        aggregate_input_tokens=100,
        aggregate_output_tokens=500,
        aggregate_tokens_per_second=tokens_per_sec,
    )

    return BenchmarkResult(
        schema_version="0.1",
        run_id=run_id,
        timestamp="2026-10-02T00:00:00Z",
        inferload_version="0.1.0",
        endpoint=endpoint,
        model=model,
        concurrency=4,
        request_count=total,
        warmup_count=2,
        streaming=True,
        target={"base_url": endpoint, "model": model},
        workload={"requests": total, "concurrency": 4},
        execution={"warmup_requests": 2},
        summary=summary,
        requests=[],
    )


def test_compare_benchmarks_deterministic_diffs() -> None:
    # Baseline: TTFT=120ms, Latency=800ms, RPS=5.0, Tok/s=100.0
    baseline = _build_dummy_result("run-base", ttft_p50=120.0, lat_p50=800.0, req_per_sec=5.0, tokens_per_sec=100.0)

    # Candidate: TTFT=100ms (-20ms / -16.67%), Latency=720ms (-80ms / -10%), RPS=6.0 (+1.0 / +20%), Tok/s=120.0 (+20%)
    candidate = _build_dummy_result("run-cand", ttft_p50=100.0, lat_p50=720.0, req_per_sec=6.0, tokens_per_sec=120.0)

    comp = compare_benchmarks(baseline, candidate)

    assert comp.baseline_run_id == "run-base"
    assert comp.candidate_run_id == "run-cand"

    # Check TTFT p50
    ttft_comp = comp.get_metric("TTFT p50")
    assert ttft_comp is not None
    assert ttft_comp.baseline == 120.0
    assert ttft_comp.candidate == 100.0
    assert ttft_comp.diff == -20.0
    assert pytest.approx(ttft_comp.pct_change, 0.01) == -16.67

    # Check Total Latency p50
    lat_comp = comp.get_metric("Total Latency p50")
    assert lat_comp is not None
    assert lat_comp.baseline == 800.0
    assert lat_comp.candidate == 720.0
    assert lat_comp.diff == -80.0
    assert pytest.approx(lat_comp.pct_change, 0.01) == -10.0

    # Check Throughput
    thru_comp = comp.get_metric("Throughput")
    assert thru_comp is not None
    assert thru_comp.baseline == 5.0
    assert thru_comp.candidate == 6.0
    assert thru_comp.diff == 1.0
    assert pytest.approx(thru_comp.pct_change, 0.01) == 20.0

    # Check Output Tokens/s
    tok_comp = comp.get_metric("Output Tokens/s")
    assert tok_comp is not None
    assert tok_comp.baseline == 100.0
    assert tok_comp.candidate == 120.0
    assert tok_comp.diff == 20.0
    assert pytest.approx(tok_comp.pct_change, 0.01) == 20.0

    # Format table check
    table_str = format_comparison_table(comp)
    assert "InferLoad Benchmark Comparison" in table_str
    assert "run-base" in table_str
    assert "run-cand" in table_str
    assert "-20.00 ms" in table_str
    assert "-16.67%" in table_str
    assert "+1.00 req/s" in table_str


def test_compare_with_zero_and_none_values() -> None:
    # Baseline with no TTFT (e.g. non-streaming)
    base = _build_dummy_result("run-base", ttft_p50=100.0, lat_p50=500.0, req_per_sec=2.0, tokens_per_sec=50.0, failure_count=0)
    base.summary.ttft_ms = None

    # Candidate with TTFT and 20% errors
    cand = _build_dummy_result("run-cand", ttft_p50=80.0, lat_p50=400.0, req_per_sec=2.5, tokens_per_sec=60.0, success_count=8, failure_count=2)

    comp = compare_benchmarks(base, cand)

    # TTFT baseline is None -> diff is None
    ttft = comp.get_metric("TTFT p50")
    assert ttft is not None
    assert ttft.baseline is None
    assert ttft.candidate == 80.0
    assert ttft.diff is None
    assert ttft.pct_change is None

    # Error rate: base=0%, cand=20% -> diff = +20%
    err = comp.get_metric("Error Rate")
    assert err is not None
    assert err.baseline == 0.0
    assert err.candidate == 20.0
    assert err.diff == 20.0
    # From 0 to 20%, pct_change is None (avoid divide by zero)
    assert err.pct_change is None


def test_compare_files_and_cli(tmp_path: Path) -> None:
    base = _build_dummy_result("run-1", ttft_p50=100.0, lat_p50=600.0, req_per_sec=4.0, tokens_per_sec=80.0)
    cand = _build_dummy_result("run-2", ttft_p50=90.0, lat_p50=540.0, req_per_sec=4.5, tokens_per_sec=90.0)

    base_file = tmp_path / "base.json"
    cand_file = tmp_path / "cand.json"

    base_file.write_text(json.dumps(base.model_dump(mode="json")), encoding="utf-8")
    cand_file.write_text(json.dumps(cand.model_dump(mode="json")), encoding="utf-8")

    # Python API test
    comparison = compare_files(base_file, cand_file)
    assert comparison.baseline_run_id == "run-1"
    assert comparison.candidate_run_id == "run-2"

    # CLI test (table output)
    runner = CliRunner()
    result = runner.invoke(app, ["compare", str(base_file), str(cand_file)])
    assert result.exit_code == 0
    assert "InferLoad Benchmark Comparison" in result.stdout
    assert "run-1" in result.stdout
    assert "run-2" in result.stdout

    # CLI test (JSON output)
    result_json = runner.invoke(app, ["compare", str(base_file), str(cand_file), "--json"])
    assert result_json.exit_code == 0
    parsed = json.loads(result_json.stdout)
    assert parsed["baseline_run_id"] == "run-1"
    assert parsed["candidate_run_id"] == "run-2"
