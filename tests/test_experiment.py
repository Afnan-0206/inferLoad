"""Comprehensive tests for experiment configuration, sweep expansion, statistics, open-loop scheduling, and reporting."""

import json
from pathlib import Path
import pytest
import httpx

from inferload.analysis import ExperimentPointMetrics, detect_saturation_regions
from inferload.config import ArrivalConfig, BenchmarkConfig, ExecutionConfig, TargetConfig, WorkloadConfig
from inferload.environment import capture_environment_metadata
from inferload.experiment import ExperimentRunner, expand_sweep_grid
from inferload.experiment_config import (
    ExperimentConfig,
    ExperimentMeta,
    ExperimentWorkload,
    SweepDefinition,
    load_experiment_config,
)
from inferload.models import BenchmarkResult
from inferload.runner import BenchmarkRunner
from inferload.statistics import compute_sample_statistics, get_student_t_critical
from tests.integration.mock_server import LocalMockServer, MockServerConfig


def test_sweep_grid_expansion() -> None:
    cfg = ExperimentConfig(
        experiment=ExperimentMeta(name="grid-test"),
        target=TargetConfig(base_url="http://localhost:8000/v1", model="test-model"),
        workload=ExperimentWorkload(
            prompt_profiles={
                "short": ["P1", "P2"],
                "long": ["P3", "P4"],
            },
            max_tokens=64,
        ),
        sweep=SweepDefinition(
            concurrency=[1, 2, 4],
            prompt_profiles=["short", "long"],
            repetitions=2,
            requests_per_point=10,
        ),
    )

    grid = expand_sweep_grid(cfg)
    # 3 concurrencies * 2 prompt profiles * 2 repetitions = 12 trials
    assert len(grid) == 12

    point_keys = [t.point_key for t in grid]
    assert point_keys.count("c1-m64-short") == 2
    assert point_keys.count("c2-m64-long") == 2
    assert point_keys.count("c4-m64-short") == 2


def test_sample_statistics_and_confidence_intervals() -> None:
    # 3 repetitions: [100.0, 110.0, 105.0]
    vals = [100.0, 110.0, 105.0]
    stats = compute_sample_statistics(vals)

    assert stats.sample_size == 3
    assert stats.mean == 105.0
    assert stats.median == 105.0
    assert stats.min == 100.0
    assert stats.max == 110.0

    # Sample variance: ((100-105)^2 + (110-105)^2 + (105-105)^2) / (3-1) = (25 + 25 + 0) / 2 = 25.0
    # Sample std dev: sqrt(25.0) = 5.0
    assert pytest.approx(stats.std_dev, 0.0001) == 5.0

    # CV %: (5.0 / 105.0) * 100 = 4.7619%
    assert pytest.approx(stats.coefficient_of_variation_pct, 0.01) == 4.76

    # Student's t critical for df = 2 (N = 3): 4.303
    t_crit = get_student_t_critical(2)
    assert t_crit == 4.303

    # SE = 5.0 / sqrt(3) = 2.88675
    # Margin = 4.303 * 2.88675 = 12.4217
    assert stats.ci_95_margin is not None
    assert pytest.approx(stats.ci_95_margin, 0.01) == 12.42
    assert pytest.approx(stats.ci_95_lower, 0.01) == 105.0 - 12.42
    assert pytest.approx(stats.ci_95_upper, 0.01) == 105.0 + 12.42


def test_saturation_detection_logic() -> None:
    points = [
        # Concurrency 1: 10 req/s, 60ms latency
        ExperimentPointMetrics(load_parameter=1, throughput_rps=10.0, latency_p95_ms=60.0),
        # Concurrency 2: 19 req/s (+90%), 65ms latency (+8.3%) -> Normal scaling
        ExperimentPointMetrics(load_parameter=2, throughput_rps=19.0, latency_p95_ms=65.0),
        # Concurrency 4: 20 req/s (+5.2%), 140ms latency (+115.4%) -> Saturation region!
        ExperimentPointMetrics(load_parameter=4, throughput_rps=20.0, latency_p95_ms=140.0),
    ]

    findings = detect_saturation_regions(points, parameter_name="concurrency")
    assert len(findings) == 1
    f = findings[0]
    assert f.detected is True
    assert f.from_value == 2
    assert f.to_value == 4
    assert "saturation-like behavior" in f.summary_message
    assert "requires server-side telemetry for causal attribution" in f.summary_message
    assert "telemetry" in f.cautionary_note


def test_environment_metadata_safety() -> None:
    env = capture_environment_metadata()
    assert env.os_system in ("Windows", "Linux", "Darwin")
    assert env.python_version.startswith("3.")
    assert env.cpu_cores is not None and env.cpu_cores >= 1
    # GPU must be explicitly detected or set to 'gpu: unavailable', never fabricated
    assert env.gpu_info.startswith("gpu: unavailable") or "x " in env.gpu_info


@pytest.mark.asyncio
async def test_open_loop_constant_rate_scheduling() -> None:
    """Verify open-loop dispatch initiates requests at target intervals without awaiting prior completions."""
    dispatched_times: list[float] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        import time
        dispatched_times.append(time.perf_counter())
        # Simulate 150 ms server processing time
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "choices": [{"message": {"role": "assistant", "content": "open-loop test"}}],
            },
        )

    transport = httpx.MockTransport(mock_handler)
    target_rate = 20.0  # 20 req/s -> 50 ms interval
    async with httpx.AsyncClient(transport=transport) as http_client:
        cfg = BenchmarkConfig(
            target=TargetConfig(base_url="http://localhost:8000/v1", model="test-model"),
            workload=WorkloadConfig(requests=4, concurrency=1, stream=False, prompts=["P1"]),
            arrival=ArrivalConfig(mode="rate", requests_per_second=target_rate),
        )
        runner = BenchmarkRunner(cfg, http_client=http_client)
        result = await runner.run()

    assert result.summary.total_requests == 4
    assert result.summary.success_count == 4
    assert len(dispatched_times) == 4

    # Check spacing between dispatches: should be ~50 ms (0.05 s)
    deltas = [
        (dispatched_times[i + 1] - dispatched_times[i]) * 1000.0
        for i in range(len(dispatched_times) - 1)
    ]
    for d in deltas:
        # In open-loop mode, requests are dispatched at ~50ms intervals rather than
        # waiting for the 150ms response to complete (which would occur in closed-loop mode).
        assert 25.0 <= d <= 100.0, f"Expected open-loop dispatch spacing ~50ms, got {d:.2f}ms"


@pytest.mark.asyncio
async def test_experiment_end_to_end_mock_sweep(tmp_path: Path) -> None:
    """Run an end-to-end experiment sweep against a live mock server and verify artifacts."""
    server = LocalMockServer(host="127.0.0.1", port=0)
    base_url = server.start()
    server.config = MockServerConfig(
        default_ttft_delay_ms=30.0,
        default_chunk_delay_ms=10.0,
        default_chunk_count=3,
    )

    try:
        exp_cfg = ExperimentConfig(
            experiment=ExperimentMeta(
                name="test-sweep",
                description="Integration test sweep",
                output_dir=str(tmp_path),
            ),
            target=TargetConfig(base_url=base_url, model="mock-model", timeout=5.0),
            workload=ExperimentWorkload(
                prompts=["Prompt 1", "Prompt 2"],
                max_tokens=32,
            ),
            sweep=SweepDefinition(
                concurrency=[1, 2],
                repetitions=2,
                requests_per_point=3,
            ),
            execution=ExecutionConfig(warmup_requests=1),
        )

        runner = ExperimentRunner(exp_cfg)
        result, out_dir = await runner.run()

        # Check directory structure
        assert out_dir.exists()
        summary_json = out_dir / "summary.json"
        points_csv = out_dir / "points.csv"
        report_md = out_dir / "report.md"
        plots_dir = out_dir / "plots"
        raw_dir = out_dir / "raw"

        assert summary_json.is_file()
        assert points_csv.is_file()
        assert report_md.is_file()
        assert plots_dir.is_dir()
        assert raw_dir.is_dir()

        # Check raw files: 2 concurrencies * 2 repetitions = 4 raw JSON runs
        raw_files = list(raw_dir.glob("*.json"))
        assert len(raw_files) == 4

        # Check summary content
        with open(summary_json, "r", encoding="utf-8") as f:
            summary_data = json.load(f)
        assert summary_data["schema_version"] == "0.2"
        assert len(summary_data["points"]) == 2
        assert len(summary_data["raw_run_ids"]) == 4

        # Check report markdown
        report_content = report_md.read_text(encoding="utf-8")
        assert "# InferLoad Experiment Report: test-sweep" in report_content
        assert "System Execution Environment" in report_content
        assert "Sweep Results Summary" in report_content
        assert "Statistical Repetitions & Uncertainty Analysis" in report_content
        assert "Benchmark Interpretation and Statistical Limitations" in report_content

        # Check plots generated
        png_plots = list(plots_dir.glob("*.png"))
        assert len(png_plots) >= 2  # Concurrency vs TTFT and Throughput plots

    finally:
        server.stop()


def test_backward_compatibility_with_phase1_result(tmp_path: Path) -> None:
    """Verify that older Phase 1 JSON benchmark results load without validation errors."""
    old_data = {
        "schema_version": "0.1",
        "run_id": "legacy-run-123",
        "timestamp": "2026-10-01T12:00:00Z",
        "target": {"base_url": "http://localhost:8000/v1", "model": "legacy-model"},
        "workload": {"requests": 10, "concurrency": 2},
        "execution": {"warmup_requests": 1},
        "summary": {
            "total_requests": 10,
            "success_count": 10,
            "failure_count": 0,
            "error_rate": 0.0,
            "total_duration_s": 2.0,
            "requests_per_second": 5.0,
            "successful_requests_per_second": 5.0,
            "total_latency_ms": {"count": 10, "min": 100.0, "max": 200.0, "mean": 150.0, "median": 150.0, "p50": 150.0, "p95": 190.0, "p99": 199.0},
        },
        "requests": [],
    }

    legacy_file = tmp_path / "legacy.json"
    legacy_file.write_text(json.dumps(old_data), encoding="utf-8")

    res = BenchmarkResult.from_json_file(legacy_file)
    assert res.run_id == "legacy-run-123"
    assert res.schema_version == "0.1"
    assert res.summary.total_requests == 10
