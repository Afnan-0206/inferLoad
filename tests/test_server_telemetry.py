"""Unit tests for optional server telemetry collection, Prometheus parsing, and correlation reporting."""

from __future__ import annotations

from pathlib import Path
import pytest
import yaml

from inferload.config import BenchmarkConfig, TelemetryConfig
from inferload.environment import EnvironmentMetadata
from inferload.experiment import ExperimentRunner, PointSummary
from inferload.experiment_config import (
    ExperimentConfig,
    ExperimentMeta,
    ExperimentWorkload,
    SweepDefinition,
)
from inferload.models import BenchmarkResult
from inferload.server_telemetry import (
    ExperimentTelemetry,
    ServerTelemetryCollector,
    ServerTelemetrySnapshot,
    build_non_causal_correlation_notes,
    extract_telemetry_metrics,
    parse_prometheus_text,
    render_telemetry_correlation_markdown,
)
from inferload.statistics import compute_sample_statistics


def test_parse_prometheus_text_known_and_histogram() -> None:
    """Verify parsing of standard gauges and histogram sums/counts."""
    raw_prom = """
    # HELP vllm:num_requests_running Number of requests currently running on GPU.
    # TYPE vllm:num_requests_running gauge
    vllm:num_requests_running{model_name="Qwen/Qwen2.5-1.5B-Instruct"} 4.0
    # HELP vllm:num_requests_waiting Number of requests waiting in iteration queue.
    # TYPE vllm:num_requests_waiting gauge
    vllm:num_requests_waiting{model_name="Qwen/Qwen2.5-1.5B-Instruct"} 6.0
    # HELP vllm:kv_cache_usage_perc Percentage of KV cache used.
    # TYPE vllm:kv_cache_usage_perc gauge
    vllm:kv_cache_usage_perc{model_name="Qwen/Qwen2.5-1.5B-Instruct"} 32.5
    # HELP vllm:request_queue_time_seconds Queue time histogram.
    # TYPE vllm:request_queue_time_seconds histogram
    vllm:request_queue_time_seconds_sum 0.150
    vllm:request_queue_time_seconds_count 10
    # Prefill and decode timing histograms
    vllm:request_prefill_time_seconds_sum 0.600
    vllm:request_prefill_time_seconds_count 12
    vllm:request_decode_time_seconds_sum 1.800
    vllm:request_decode_time_seconds_count 15
    vllm:num_preemptions 2.0
    """
    metrics = parse_prometheus_text(raw_prom)
    assert metrics["vllm:num_requests_running"] == 4.0
    assert metrics["vllm:num_requests_waiting"] == 6.0
    assert metrics["vllm:kv_cache_usage_perc"] == 32.5
    assert metrics["vllm:num_preemptions"] == 2.0

    snapshot = extract_telemetry_metrics(metrics, server_version="vLLM 0.6.3")
    assert snapshot.available is True
    assert snapshot.running_requests == 4.0
    assert snapshot.waiting_requests == 6.0
    assert snapshot.kv_cache_usage_pct == 32.5
    assert snapshot.num_preemptions == 2.0
    assert snapshot.queue_time_seconds_avg == pytest.approx(0.015)
    assert snapshot.prefill_time_seconds_avg == pytest.approx(0.050)
    assert snapshot.decode_time_seconds_avg == pytest.approx(0.120)
    assert snapshot.server_version == "vLLM 0.6.3"


def test_parse_prometheus_malformed_response() -> None:
    """Verify that unparseable or malformed Prometheus lines do not cause exceptions."""
    malformed = """
    # This is a comment
    INVALID_LINE_WITHOUT_VALUE
    incomplete_line_with_brace{bad_label=
    metric_with_invalid_float NOT_A_NUMBER
    # Another comment
    valid_gauge 42.0
    """
    metrics = parse_prometheus_text(malformed)
    assert "valid_gauge" in metrics
    assert metrics["valid_gauge"] == 42.0
    # Malformed lines are cleanly skipped
    assert "INVALID_LINE_WITHOUT_VALUE" not in metrics
    assert "metric_with_invalid_float" not in metrics

    snapshot = extract_telemetry_metrics(metrics)
    assert snapshot.available is True
    assert snapshot.running_requests is None
    assert snapshot.waiting_requests is None


def test_unknown_and_missing_metrics() -> None:
    """Verify handling when inference server metrics are absent or legacy formats are provided."""
    unrelated_metrics = {
        "process_virtual_memory_bytes": 1024.0,
        "python_info": 1.0,
    }
    snap = extract_telemetry_metrics(unrelated_metrics)
    assert snap.running_requests is None
    assert snap.waiting_requests is None
    assert snap.kv_cache_usage_pct is None
    assert snap.queue_time_seconds_avg is None

    # Test legacy cache factor conversion (0.0 to 1.0 -> 0 to 100%)
    legacy_metrics = {
        "vllm:gpu_cache_usage_factor": 0.45,
    }
    legacy_snap = extract_telemetry_metrics(legacy_metrics)
    assert legacy_snap.kv_cache_usage_pct == pytest.approx(45.0)


@pytest.mark.asyncio
async def test_telemetry_unavailable_handling() -> None:
    """Verify that attempting to poll an unreachable telemetry endpoint fails safely without crashing."""
    # Port 65534 on localhost is unreachable
    collector = ServerTelemetryCollector(
        metrics_url="http://127.0.0.1:65534/metrics",
        enabled=True,
        timeout_seconds=0.5,
    )
    snapshot = await collector.capture_snapshot()
    assert snapshot.available is False
    assert snapshot.error_message is not None
    assert "Failed to fetch telemetry" in snapshot.error_message or "Connect" in snapshot.error_message


@pytest.mark.asyncio
async def test_telemetry_disabled_or_empty_url() -> None:
    """Verify that disabled telemetry returns available=False immediately."""
    collector = ServerTelemetryCollector(metrics_url=None, enabled=False)
    snapshot = await collector.capture_snapshot()
    assert snapshot.available is False
    assert "disabled" in (snapshot.error_message or "").lower()


def test_optional_telemetry_configuration_and_backward_compatibility(tmp_path: Path) -> None:
    """Verify backward compatibility: configs without telemetry section load with defaults."""
    legacy_yaml = """
    experiment:
      name: "legacy-test"
    target:
      base_url: "http://localhost:8000/v1"
      model: "Qwen/Qwen2.5-1.5B-Instruct"
    workload:
      prompts: ["Hello world"]
      max_tokens: 32
    sweep:
      concurrency: [1]
      repetitions: 1
      requests_per_point: 5
    """
    cfg_file = tmp_path / "legacy.yaml"
    cfg_file.write_text(legacy_yaml, encoding="utf-8")

    with open(cfg_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    exp_cfg = ExperimentConfig.model_validate(data)
    assert exp_cfg.telemetry.enabled is False
    assert exp_cfg.telemetry.metrics_url is None
    assert exp_cfg.telemetry.server_version is None

    # Now verify telemetry block can be explicitly configured
    with_telemetry_yaml = legacy_yaml + """
    telemetry:
      enabled: true
      metrics_url: "http://localhost:8000/metrics"
      server_version: "vLLM 0.6.3"
    """
    data_telemetry = yaml.safe_load(with_telemetry_yaml)
    exp_cfg2 = ExperimentConfig.model_validate(data_telemetry)
    assert exp_cfg2.telemetry.enabled is True
    assert exp_cfg2.telemetry.metrics_url == "http://localhost:8000/metrics"
    assert exp_cfg2.telemetry.server_version == "vLLM 0.6.3"


def _build_mock_point_summary(concurrency: int, ttft95: float, lat95: float, thru: float) -> PointSummary:
    """Helper to construct synthetic PointSummary for report rendering tests."""
    return PointSummary(
        concurrency=concurrency,
        max_tokens=64,
        prompt_profile=None,
        arrival_rate=None,
        repetitions=1,
        requests_per_point=10,
        ttft_p50=compute_sample_statistics([ttft95 * 0.8]),
        ttft_p95=compute_sample_statistics([ttft95]),
        ttft_p99=compute_sample_statistics([ttft95 * 1.2]),
        latency_p50=compute_sample_statistics([lat95 * 0.8]),
        latency_p95=compute_sample_statistics([lat95]),
        latency_p99=compute_sample_statistics([lat95 * 1.2]),
        throughput=compute_sample_statistics([thru]),
        tokens_per_second=compute_sample_statistics([thru * 30.0]),
        error_rate=compute_sample_statistics([0.0]),
    )


def test_report_rendering_without_telemetry() -> None:
    """Verify that reports without telemetry clearly state unavailability and proceed normally."""
    points = [_build_mock_point_summary(1, 50.0, 500.0, 2.0)]
    telemetry = ExperimentTelemetry(enabled=False, available=False)
    lines = render_telemetry_correlation_markdown(telemetry, points)
    rendered = "\n".join(lines)
    assert "Server Telemetry & Client Metric Correlation" in rendered
    assert "Server telemetry was not enabled" in rendered
    assert "client measurements proceeded normally" in rendered


def test_report_rendering_with_telemetry_and_non_causal_wording() -> None:
    """Verify report rendering with active telemetry adheres to non-causal observational phrasing."""
    points = [
        _build_mock_point_summary(1, 45.0, 400.0, 2.5),
        _build_mock_point_summary(4, 180.0, 950.0, 4.2),
    ]

    snap_before = ServerTelemetrySnapshot(
        timestamp="2026-10-02T00:00:00Z",
        available=True,
        running_requests=0.0,
        waiting_requests=0.0,
        kv_cache_usage_pct=2.0,
    )
    snap_during = ServerTelemetrySnapshot(
        timestamp="2026-10-02T00:01:00Z",
        available=True,
        running_requests=4.0,
        waiting_requests=3.0,
        kv_cache_usage_pct=42.0,
        queue_time_seconds_avg=0.035,
        prefill_time_seconds_avg=0.040,
        decode_time_seconds_avg=0.110,
    )
    snap_after = ServerTelemetrySnapshot(
        timestamp="2026-10-02T00:02:00Z",
        available=True,
        running_requests=0.0,
        waiting_requests=0.0,
        kv_cache_usage_pct=5.0,
    )

    notes = build_non_causal_correlation_notes(points, snap_before, snap_during, snap_after)
    telemetry = ExperimentTelemetry(
        enabled=True,
        available=True,
        endpoint_url="http://localhost:8000/metrics",
        server_version="vLLM 0.6.3",
        telemetry_before=snap_before,
        telemetry_during=snap_during,
        telemetry_after=snap_after,
        correlation_notes=notes,
    )

    lines = render_telemetry_correlation_markdown(telemetry, points)
    rendered = "\n".join(lines)

    # 1. Structure verification
    assert "### Client Observations" in rendered
    assert "### Server Observations (Snapshots)" in rendered
    assert "### Correlation Observations (Non-Causal)" in rendered
    assert "Reported Server Version:** `vLLM 0.6.3`" in rendered

    # 2. Strict non-causal wording check
    assert "Client TTFT p95 increased from 45.0 ms to 180.0 ms while server waiting-request count was observed at 3" in rendered
    # Must NOT claim direct causality
    assert "caused the latency increase" not in rendered.lower()
    assert "due to queueing" not in rendered.lower()

    # 3. Snapshot methodology limitation check
    assert "Point-in-Time Snapshot Methodology Limitation" in rendered
    assert "A point snapshot is not equivalent to continuous per-request tracing" in rendered
