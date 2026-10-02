"""Unit and integration tests for deterministic capacity analysis and SLO evaluation."""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from typer.testing import CliRunner

from inferload.capacity import (
    CapacityAnalysisResult,
    SLOConfig,
    analyze_capacity,
    format_capacity_report,
    load_slo_config,
)
from inferload.cli import app
from inferload.environment import EnvironmentMetadata
from inferload.experiment import ExperimentResult, PointSummary
from inferload.experiment_config import validate_benchmark_quality, ExperimentConfig
from inferload.statistics import SampleStatistics


def _dummy_stat(mean_val: float | None, std: float | None = 0.1) -> SampleStatistics:
    if mean_val is None:
        return SampleStatistics(sample_size=0)
    return SampleStatistics(
        sample_size=3,
        mean=mean_val,
        std_dev=std,
        minimum=mean_val - 0.1,
        maximum=mean_val + 0.1,
        coefficient_of_variation_pct=2.5,
    )


def _make_dummy_point(
    concurrency: int,
    throughput: float | None,
    ttft_p95: float | None,
    latency_p95: float | None,
    error_rate: float = 0.0,
) -> PointSummary:
    return PointSummary(
        concurrency=concurrency,
        max_tokens=32,
        repetitions=3,
        requests_per_point=20,
        ttft_p50=_dummy_stat(ttft_p95 * 0.8 if ttft_p95 is not None else None),
        ttft_p95=_dummy_stat(ttft_p95),
        ttft_p99=_dummy_stat(ttft_p95 * 1.1 if ttft_p95 is not None else None),
        latency_p50=_dummy_stat(latency_p95 * 0.8 if latency_p95 is not None else None),
        latency_p95=_dummy_stat(latency_p95),
        latency_p99=_dummy_stat(latency_p95 * 1.2 if latency_p95 is not None else None),
        throughput=_dummy_stat(throughput),
        tokens_per_second=_dummy_stat(throughput * 25.0 if throughput is not None else None),
        error_rate=_dummy_stat(error_rate, std=0.0),
    )


def _make_dummy_experiment(points: list[PointSummary]) -> ExperimentResult:
    return ExperimentResult(
        schema_version="0.2",
        experiment_id="exp-test-capacity-123456",
        name="test-capacity-experiment",
        description="Test experiment for capacity analysis",
        timestamp="2026-10-02T00:00:00Z",
        inferload_version="0.1.0",
        model="qwen2.5:0.5b",
        endpoint="http://127.0.0.1:11434/v1",
        concurrency_levels=[p.concurrency for p in points],
        requests_per_point=20,
        repetitions=3,
        warmup_requests=5,
        arrival_mode="closed",
        target={"base_url": "http://127.0.0.1:11434/v1", "model": "qwen2.5:0.5b"},
        environment=EnvironmentMetadata(
            os_system="Windows",
            os_release="11",
            os_version="10.0.26300",
            python_version="3.12.10",
            python_implementation="CPython",
            cpu_architecture="AMD64",
            cpu_model="AMD Ryzen",
            cpu_cores=16,
            ram_total_gb=16.0,
            gpu_info="gpu: unavailable",
        ),
        sweep_config={"concurrency": [p.concurrency for p in points]},
        points=points,
        saturation_findings=[],
        raw_run_ids=["run-1", "run-2"],
    )


def test_all_slos_satisfied() -> None:
    points = [
        _make_dummy_point(concurrency=1, throughput=1.5, ttft_p95=100.0, latency_p95=500.0, error_rate=0.0),
        _make_dummy_point(concurrency=2, throughput=2.8, ttft_p95=250.0, latency_p95=700.0, error_rate=0.0),
        _make_dummy_point(concurrency=4, throughput=4.2, ttft_p95=500.0, latency_p95=950.0, error_rate=0.0),
    ]
    exp = _make_dummy_experiment(points)
    slo = SLOConfig(
        max_ttft_p95_ms=1000.0,
        max_total_latency_p95_ms=1000.0,
        max_error_rate_pct=1.0,
        min_throughput_req_per_sec=1.0,
    )

    result = analyze_capacity(exp, slo)
    assert result.highest_compliant_concurrency == 4
    assert result.compliant_point is not None
    assert result.compliant_point.concurrency == 4
    assert len(result.warnings) == 0


def test_ttft_violation() -> None:
    points = [
        _make_dummy_point(concurrency=1, throughput=1.5, ttft_p95=200.0, latency_p95=500.0),
        _make_dummy_point(concurrency=2, throughput=2.5, ttft_p95=800.0, latency_p95=800.0),
        _make_dummy_point(concurrency=4, throughput=3.5, ttft_p95=1500.0, latency_p95=1600.0),  # Violates TTFT
    ]
    exp = _make_dummy_experiment(points)
    slo = SLOConfig(max_ttft_p95_ms=1000.0)

    result = analyze_capacity(exp, slo)
    assert result.highest_compliant_concurrency == 2
    assert not result.tested_points[2].compliant
    assert any("exceeds SLO maximum" in v for v in result.tested_points[2].violations)


def test_error_rate_violation() -> None:
    points = [
        _make_dummy_point(concurrency=1, throughput=1.5, ttft_p95=200.0, latency_p95=500.0, error_rate=0.0),
        _make_dummy_point(concurrency=2, throughput=2.0, ttft_p95=300.0, latency_p95=600.0, error_rate=0.05),  # 5% errors
    ]
    exp = _make_dummy_experiment(points)
    slo = SLOConfig(max_error_rate_pct=1.0)

    result = analyze_capacity(exp, slo)
    assert result.highest_compliant_concurrency == 1
    assert not result.tested_points[1].compliant
    assert any("Error rate (5.00%) exceeds SLO maximum" in v for v in result.tested_points[1].violations)


def test_throughput_violation() -> None:
    points = [
        _make_dummy_point(concurrency=1, throughput=0.75, ttft_p95=200.0, latency_p95=500.0),  # < 1.0 req/s
        _make_dummy_point(concurrency=2, throughput=1.6, ttft_p95=300.0, latency_p95=600.0),
    ]
    exp = _make_dummy_experiment(points)
    slo = SLOConfig(min_throughput_req_per_sec=1.0)

    result = analyze_capacity(exp, slo)
    assert result.highest_compliant_concurrency == 2
    assert not result.tested_points[0].compliant
    assert any("is below SLO minimum" in v for v in result.tested_points[0].violations)


def test_no_compliant_point() -> None:
    points = [
        _make_dummy_point(concurrency=1, throughput=1.0, ttft_p95=1200.0, latency_p95=2000.0),
        _make_dummy_point(concurrency=2, throughput=1.5, ttft_p95=1800.0, latency_p95=3000.0),
    ]
    exp = _make_dummy_experiment(points)
    slo = SLOConfig(max_ttft_p95_ms=1000.0)

    result = analyze_capacity(exp, slo)
    assert result.highest_compliant_concurrency is None
    assert result.compliant_point is None
    assert len(result.warnings) > 0
    assert "No tested concurrency point satisfied all configured SLO constraints" in result.warnings[0]


def test_multiple_compliant_points_selects_highest() -> None:
    points = [
        _make_dummy_point(concurrency=1, throughput=1.5, ttft_p95=100.0, latency_p95=400.0),
        _make_dummy_point(concurrency=2, throughput=2.5, ttft_p95=200.0, latency_p95=500.0),
        _make_dummy_point(concurrency=4, throughput=3.8, ttft_p95=400.0, latency_p95=700.0),
        _make_dummy_point(concurrency=8, throughput=4.5, ttft_p95=1400.0, latency_p95=1800.0),  # Violates TTFT
    ]
    exp = _make_dummy_experiment(points)
    slo = SLOConfig(max_ttft_p95_ms=1000.0)

    result = analyze_capacity(exp, slo)
    # Both 1, 2, 4 are compliant; highest tested concurrency is 4
    assert result.highest_compliant_concurrency == 4
    assert result.compliant_point is not None
    assert result.compliant_point.concurrency == 4


def test_incomplete_or_missing_metric_values() -> None:
    points = [
        _make_dummy_point(concurrency=1, throughput=1.5, ttft_p95=None, latency_p95=500.0),  # Missing TTFT
    ]
    exp = _make_dummy_experiment(points)
    slo = SLOConfig(max_ttft_p95_ms=1000.0)

    result = analyze_capacity(exp, slo)
    assert result.highest_compliant_concurrency is None
    assert not result.tested_points[0].compliant
    assert any("TTFT p95 measurement unavailable/missing" in v for v in result.tested_points[0].violations)


def test_format_capacity_report() -> None:
    points = [
        _make_dummy_point(concurrency=1, throughput=1.5, ttft_p95=100.0, latency_p95=500.0),
        _make_dummy_point(concurrency=2, throughput=2.5, ttft_p95=200.0, latency_p95=600.0),
    ]
    exp = _make_dummy_experiment(points)
    slo = SLOConfig(max_ttft_p95_ms=1000.0, max_error_rate_pct=1.0)

    result = analyze_capacity(exp, slo)
    text = format_capacity_report(result)
    assert "InferLoad Capacity Analysis" in text
    assert "TTFT p95 <= 1000.0 ms" in text
    assert "Highest Observed Compliant Tested Concurrency:" in text
    assert "2" in text
    assert "Capacity is limited to tested configurations and does not extrapolate" in text


def test_cli_capacity_command(tmp_path: Path) -> None:
    # Save a dummy summary.json
    points = [
        _make_dummy_point(concurrency=1, throughput=1.5, ttft_p95=100.0, latency_p95=500.0),
        _make_dummy_point(concurrency=2, throughput=2.5, ttft_p95=250.0, latency_p95=700.0),
    ]
    exp = _make_dummy_experiment(points)
    summary_file = tmp_path / "summary.json"
    summary_file.write_text(json.dumps(exp.model_dump(mode="json")), encoding="utf-8")

    # Save a dummy slo.yaml
    slo_file = tmp_path / "slo.yaml"
    slo_file.write_text("slo:\n  max_ttft_p95_ms: 1000.0\n  max_error_rate_pct: 1.0\n", encoding="utf-8")

    runner = CliRunner()
    res = runner.invoke(app, ["capacity", str(tmp_path), "--slo", str(slo_file)])
    assert res.exit_code == 0
    assert "InferLoad Capacity Analysis" in res.stdout
    assert "Highest Observed Compliant Tested Concurrency:" in res.stdout
    assert "2" in res.stdout


def test_benchmark_quality_validation_rules() -> None:
    from inferload.experiment_config import ExperimentMeta, SweepDefinition, ExperimentWorkload
    from inferload.config import TargetConfig, ExecutionConfig, ArrivalConfig

    # 1. Hard constraint failures
    cfg = ExperimentConfig(
        experiment=ExperimentMeta(name="t1"),
        target=TargetConfig(base_url="http://127.0.0.1:11434/v1", model="m"),
        workload=ExperimentWorkload(prompts=["p"]),
        sweep=SweepDefinition(concurrency=[1]),
        execution=ExecutionConfig(warmup_requests=0),
    )
    cfg.sweep.concurrency = []
    with pytest.raises(ValueError, match="Sweep must specify at least one concurrency level"):
        validate_benchmark_quality(cfg)

    cfg.sweep.concurrency = [0]
    with pytest.raises(ValueError, match="Concurrency values must be >= 1"):
        validate_benchmark_quality(cfg)

    # 2. Quality warnings emitted for small sample sizes without raising errors
    valid_small_cfg = ExperimentConfig(
        experiment=ExperimentMeta(name="t2"),
        target=TargetConfig(base_url="http://127.0.0.1:11434/v1", model="m"),
        workload=ExperimentWorkload(prompts=["p"], temperature=0.7, seed=None),
        sweep=SweepDefinition(concurrency=[1, 2], repetitions=2, requests_per_point=10),
        execution=ExecutionConfig(warmup_requests=0),
    )
    warnings = validate_benchmark_quality(valid_small_cfg)
    assert len(warnings) >= 3
    assert any("Tail-percentile measurements" in w for w in warnings)
    assert any("Repetitions count is 2 (< 3)" in w for w in warnings)
    assert any("Warmup requests count is 0" in w for w in warnings)
    assert any("deterministic random seed" in w for w in warnings)
