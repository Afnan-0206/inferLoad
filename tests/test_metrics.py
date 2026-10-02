"""Tests for percentile calculations, statistical aggregations, and summary generation."""

import pytest

from inferload.metrics import (
    aggregate_benchmark_results,
    calculate_metric_stats,
    calculate_percentile,
)
from inferload.models import RequestRecord


def test_percentile_empty_and_single() -> None:
    assert calculate_percentile([], 50.0) is None
    assert calculate_percentile([42.0], 50.0) == 42.0
    assert calculate_percentile([42.0], 99.0) == 42.0


def test_percentile_linear_interpolation() -> None:
    # 2 elements: [10.0, 20.0]
    # p50 rank = 0.5 * (2 - 1) = 0.5 -> 10 + 0.5 * 10 = 15.0
    assert calculate_percentile([10.0, 20.0], 50.0) == 15.0
    assert calculate_percentile([10.0, 20.0], 0.0) == 10.0
    assert calculate_percentile([10.0, 20.0], 100.0) == 20.0

    # 10 elements: 1..10
    # rank for p50: 0.5 * 9 = 4.5 -> values[4] + 0.5 * (values[5] - values[4]) = 5 + 0.5 * 1 = 5.5
    data = [float(i) for i in range(1, 11)]
    assert calculate_percentile(data, 50.0) == 5.5

    # p90: 0.9 * 9 = 8.1 -> values[8] + 0.1 * (values[9] - values[8]) = 9 + 0.1 = 9.1
    assert pytest.approx(calculate_percentile(data, 90.0), 0.001) == 9.1

    # p95: 0.95 * 9 = 8.55 -> values[8] + 0.55 * 1 = 9.55
    assert pytest.approx(calculate_percentile(data, 95.0), 0.001) == 9.55


def test_calculate_metric_stats() -> None:
    data = [10.0, 20.0, 30.0, 40.0, 50.0]
    stats = calculate_metric_stats(data)

    assert stats.count == 5
    assert stats.min == 10.0
    assert stats.max == 50.0
    assert stats.mean == 30.0
    assert stats.median == 30.0
    assert stats.p50 == 30.0
    assert stats.p95 is not None and stats.p95 > 45.0
    assert stats.p99 is not None and stats.p99 > stats.p95


def test_aggregate_benchmark_results_all_successful() -> None:
    records = [
        RequestRecord(
            request_id="req-1",
            index=0,
            is_warmup=False,
            prompt="Hello",
            start_time=100.0,
            end_time=101.0,
            latency_to_first_byte_ms=100.0,
            latency_to_first_token_ms=150.0,
            duration_ms=1000.0,
            status="success",
            http_status=200,
            input_text_length=5,
            output_text="World",
            output_text_length=5,
            input_tokens=10,
            output_tokens=20,
            streaming=True,
            chunk_count=4,
            chunk_delays_ms=[50.0, 40.0, 45.0],
        ),
        RequestRecord(
            request_id="req-2",
            index=1,
            is_warmup=False,
            prompt="How are you?",
            start_time=100.5,
            end_time=102.0,
            latency_to_first_byte_ms=120.0,
            latency_to_first_token_ms=180.0,
            duration_ms=1500.0,
            status="success",
            http_status=200,
            input_text_length=12,
            output_text="Fine, thank you.",
            output_text_length=16,
            input_tokens=15,
            output_tokens=30,
            streaming=True,
            chunk_count=5,
            chunk_delays_ms=[60.0, 50.0, 55.0, 45.0],
        ),
    ]

    summary = aggregate_benchmark_results(records, total_duration_s=2.0)

    assert summary.total_requests == 2
    assert summary.success_count == 2
    assert summary.failure_count == 0
    assert summary.error_rate == 0.0
    assert summary.requests_per_second == 1.0
    assert summary.successful_requests_per_second == 1.0

    # TTFT stats
    assert summary.ttft_ms is not None
    assert summary.ttft_ms.count == 2
    assert summary.ttft_ms.min == 150.0
    assert summary.ttft_ms.max == 180.0
    assert summary.ttft_ms.p50 == 165.0

    # Total latency
    assert summary.total_latency_ms.count == 2
    assert summary.total_latency_ms.min == 1000.0
    assert summary.total_latency_ms.max == 1500.0
    assert summary.total_latency_ms.p50 == 1250.0

    # Tokens
    assert summary.aggregate_input_tokens == 25
    assert summary.aggregate_output_tokens == 50
    assert summary.aggregate_tokens_per_second == 25.0  # 50 tokens / 2.0 s


def test_aggregate_benchmark_results_with_failures_and_warmup() -> None:
    records = [
        # Warmup request: should be completely ignored from summary
        RequestRecord(
            request_id="warmup-1",
            index=0,
            is_warmup=True,
            prompt="Warmup",
            start_time=90.0,
            end_time=95.0,
            duration_ms=5000.0,
            status="success",
            input_text_length=6,
            streaming=True,
        ),
        # Successful request
        RequestRecord(
            request_id="req-1",
            index=1,
            is_warmup=False,
            prompt="Normal 1",
            start_time=100.0,
            end_time=101.0,
            duration_ms=1000.0,
            latency_to_first_token_ms=200.0,
            status="success",
            http_status=200,
            input_text_length=8,
            output_tokens=10,
            streaming=True,
        ),
        # Failed request: HTTP 500
        RequestRecord(
            request_id="req-2",
            index=2,
            is_warmup=False,
            prompt="Normal 2",
            start_time=100.2,
            end_time=100.8,
            duration_ms=600.0,
            status="error",
            http_status=500,
            input_text_length=8,
            streaming=True,
            error_type="HTTP_500",
            error_message="HTTP 500: Internal Server Error",
        ),
        # Timed out request
        RequestRecord(
            request_id="req-3",
            index=3,
            is_warmup=False,
            prompt="Normal 3",
            start_time=100.5,
            end_time=102.5,
            duration_ms=2000.0,
            status="timeout",
            input_text_length=8,
            streaming=True,
            error_type="ReadTimeout",
            error_message="Read timed out",
        ),
    ]

    summary = aggregate_benchmark_results(records, total_duration_s=2.5)

    assert summary.total_requests == 3  # excludes warmup
    assert summary.success_count == 1
    assert summary.failure_count == 2
    assert pytest.approx(summary.error_rate, 0.001) == 2.0 / 3.0
    assert summary.error_breakdown == {"HTTP_500": 1, "ReadTimeout": 1}
    assert summary.successful_requests_per_second == 1 / 2.5
    assert summary.requests_per_second == 3 / 2.5


def test_metric_aliases_inter_chunk_and_content_timing() -> None:
    req = RequestRecord(
        request_id="req-test",
        index=0,
        prompt="Test",
        start_time=10.0,
        end_time=11.0,
        latency_to_first_byte_ms=45.0,
        latency_to_first_token_ms=85.0,
        duration_ms=1000.0,
        status="success",
        http_status=200,
        input_text_length=4,
        output_text="Response",
        output_tokens=10,
        streaming=True,
        chunk_count=3,
        chunk_delays_ms=[25.0, 35.0],
    )

    # Verification of scientific aliases
    assert req.latency_to_first_content_ms == req.latency_to_first_token_ms == 85.0
    assert req.inter_chunk_latency_ms == req.inter_token_latency_ms == 30.0

    summary = aggregate_benchmark_results([req], total_duration_s=1.0)
    assert summary.inter_chunk_latency_ms is not None
    assert summary.inter_chunk_latency_ms.p50 == 30.0
    assert summary.inter_token_latency_ms is not None
    assert summary.inter_token_latency_ms.p50 == 30.0
