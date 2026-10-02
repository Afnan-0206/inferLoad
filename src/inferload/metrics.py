"""Statistical metrics calculation and aggregation for InferLoad."""

from __future__ import annotations

import math
from typing import Sequence

from inferload.models import BenchmarkSummary, MetricStats, RequestRecord


def calculate_percentile(values: Sequence[float], percentile: float) -> float | None:
    """Calculate a percentile value using standard linear interpolation (Type 7).

    Given sorted values x_0, x_1, ..., x_{N-1}:
    Rank index r = (percentile / 100.0) * (N - 1)
    k = floor(r), d = r - k
    result = x_k + d * (x_{k+1} - x_k)
    """
    if not values:
        return None

    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]

    p = max(0.0, min(100.0, percentile))
    rank = (p / 100.0) * (n - 1)
    k = int(math.floor(rank))
    d = rank - k

    if k >= n - 1:
        return float(sorted_vals[-1])

    return float(sorted_vals[k] + d * (sorted_vals[k + 1] - sorted_vals[k]))


def calculate_metric_stats(values: Sequence[float]) -> MetricStats:
    """Compute count, min, max, mean, median, p50, p95, p99 for a list of floats without premature rounding."""
    if not values:
        return MetricStats(count=0)

    count = len(values)
    val_min = float(min(values))
    val_max = float(max(values))
    val_mean = float(sum(values) / count)
    val_p50 = calculate_percentile(values, 50.0)
    val_p95 = calculate_percentile(values, 95.0)
    val_p99 = calculate_percentile(values, 99.0)

    return MetricStats(
        count=count,
        min=val_min,
        max=val_max,
        mean=val_mean,
        median=val_p50,
        p50=val_p50,
        p95=val_p95,
        p99=val_p99,
    )


def aggregate_benchmark_results(
    records: Sequence[RequestRecord],
    total_duration_s: float | None = None,
) -> BenchmarkSummary:
    """Aggregate a sequence of RequestRecords into a BenchmarkSummary.

    Warmup requests must be filtered out before calling this function or will be ignored.
    Failed requests are explicitly tracked in error breakdown and failure counts.
    """
    # Filter out warmup requests to ensure only measured benchmark requests are aggregated
    bench_records = [r for r in records if not r.is_warmup]
    total_count = len(bench_records)

    successful = [r for r in bench_records if r.success]
    failed = [r for r in bench_records if not r.success]

    success_count = len(successful)
    failure_count = len(failed)
    error_rate = (failure_count / total_count) if total_count > 0 else 0.0

    # Calculate overall duration if not provided
    if total_duration_s is None or total_duration_s <= 0:
        if bench_records:
            earliest_start = min(r.start_time for r in bench_records)
            latest_end = max(r.end_time for r in bench_records)
            total_duration_s = max(0.0001, latest_end - earliest_start)
        else:
            total_duration_s = 0.0001

    requests_per_second = (total_count / total_duration_s) if total_duration_s > 0 else 0.0
    successful_requests_per_second = (success_count / total_duration_s) if total_duration_s > 0 else 0.0

    # Total latency stats for successful requests
    latencies = [r.total_latency_ms for r in successful]
    latency_stats = calculate_metric_stats(latencies)

    # TTFT stats (only where TTFT was measured)
    ttfts = [r.ttft_ms for r in successful if r.ttft_ms is not None]
    ttft_stats = calculate_metric_stats(ttfts) if ttfts else None

    # Inter-token / inter-chunk latency stats
    inter_tokens = [r.inter_token_latency_ms for r in successful if r.inter_token_latency_ms is not None]
    inter_token_stats = calculate_metric_stats(inter_tokens) if inter_tokens else None

    # Output tokens per second per request
    tps_list = [r.output_tokens_per_second for r in successful if r.output_tokens_per_second is not None]
    tps_stats = calculate_metric_stats(tps_list) if tps_list else None

    # Aggregate token counts
    input_token_counts = [r.input_tokens for r in successful if r.input_tokens is not None]
    output_token_counts = [r.output_tokens for r in successful if r.output_tokens is not None]

    agg_input_tokens = sum(input_token_counts) if input_token_counts else None
    agg_output_tokens = sum(output_token_counts) if output_token_counts else None

    agg_tokens_per_second = None
    if agg_output_tokens is not None and total_duration_s > 0:
        agg_tokens_per_second = agg_output_tokens / total_duration_s

    # Error breakdown
    error_breakdown: dict[str, int] = {}
    for r in failed:
        etype = r.error_type or "UnknownError"
        error_breakdown[etype] = error_breakdown.get(etype, 0) + 1

    return BenchmarkSummary(
        total_requests=total_count,
        success_count=success_count,
        failure_count=failure_count,
        error_rate=error_rate,
        total_duration_s=total_duration_s,
        requests_per_second=requests_per_second,
        successful_requests_per_second=successful_requests_per_second,
        ttft_ms=ttft_stats,
        total_latency_ms=latency_stats,
        inter_token_latency_ms=inter_token_stats,
        inter_chunk_latency_ms=inter_token_stats,
        output_tokens_per_second=tps_stats,
        aggregate_input_tokens=agg_input_tokens,
        aggregate_output_tokens=agg_output_tokens,
        aggregate_tokens_per_second=agg_tokens_per_second,
        error_breakdown=error_breakdown,
    )
