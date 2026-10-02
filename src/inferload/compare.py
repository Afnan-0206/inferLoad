"""Benchmark comparison logic for evaluating regressions and capacity differences."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

from inferload.models import BenchmarkResult


class MetricComparison(BaseModel):
    """Comparison of a single metric between baseline and candidate benchmark runs."""

    name: str
    unit: str
    baseline: float | None = None
    candidate: float | None = None
    diff: float | None = None
    pct_change: float | None = None
    lower_is_better: bool = True


class BenchmarkComparison(BaseModel):
    """Structured comparison result between baseline and candidate benchmarks."""

    baseline_run_id: str
    candidate_run_id: str
    baseline_model: str
    candidate_model: str
    baseline_endpoint: str
    candidate_endpoint: str
    metrics: list[MetricComparison] = Field(default_factory=list)

    def get_metric(self, name: str) -> MetricComparison | None:
        """Retrieve a specific metric comparison by name."""
        for m in self.metrics:
            if m.name.lower() == name.lower():
                return m
        return None


def _calc_diff_and_pct(
    b: float | None,
    c: float | None,
) -> tuple[float | None, float | None]:
    """Calculate absolute difference (candidate - baseline) and percentage change."""
    if b is None or c is None:
        return None, None

    diff = c - b
    if b == 0.0:
        pct = 0.0 if c == 0.0 else None
    else:
        pct = (diff / abs(b)) * 100.0

    return diff, pct


def compare_benchmarks(
    baseline: BenchmarkResult,
    candidate: BenchmarkResult,
) -> BenchmarkComparison:
    """Compare two BenchmarkResult instances deterministically."""
    b_sum = baseline.summary
    c_sum = candidate.summary

    metrics: list[MetricComparison] = []

    def add_comparison(
        name: str,
        unit: str,
        val_base: float | None,
        val_cand: float | None,
        lower_is_better: bool,
    ) -> None:
        diff, pct = _calc_diff_and_pct(val_base, val_cand)
        metrics.append(
            MetricComparison(
                name=name,
                unit=unit,
                baseline=val_base,
                candidate=val_cand,
                diff=diff,
                pct_change=pct,
                lower_is_better=lower_is_better,
            )
        )

    # 1. TTFT percentiles (lower is better)
    b_ttft = b_sum.ttft_ms
    c_ttft = c_sum.ttft_ms
    add_comparison("TTFT p50", "ms", b_ttft.p50 if b_ttft else None, c_ttft.p50 if c_ttft else None, lower_is_better=True)
    add_comparison("TTFT p95", "ms", b_ttft.p95 if b_ttft else None, c_ttft.p95 if c_ttft else None, lower_is_better=True)
    add_comparison("TTFT p99", "ms", b_ttft.p99 if b_ttft else None, c_ttft.p99 if c_ttft else None, lower_is_better=True)

    # 2. Total latency percentiles (lower is better)
    b_lat = b_sum.total_latency_ms
    c_lat = c_sum.total_latency_ms
    add_comparison("Total Latency p50", "ms", b_lat.p50, c_lat.p50, lower_is_better=True)
    add_comparison("Total Latency p95", "ms", b_lat.p95, c_lat.p95, lower_is_better=True)
    add_comparison("Total Latency p99", "ms", b_lat.p99, c_lat.p99, lower_is_better=True)

    # 3. Throughput & tokens/sec (higher is better)
    add_comparison("Throughput", "req/s", b_sum.requests_per_second, c_sum.requests_per_second, lower_is_better=False)
    add_comparison("Output Tokens/s", "tok/s", b_sum.aggregate_tokens_per_second, c_sum.aggregate_tokens_per_second, lower_is_better=False)

    # 4. Success and error rates
    b_success_rate = (b_sum.success_count / b_sum.total_requests * 100.0) if b_sum.total_requests > 0 else 0.0
    c_success_rate = (c_sum.success_count / c_sum.total_requests * 100.0) if c_sum.total_requests > 0 else 0.0
    add_comparison("Success Rate", "%", b_success_rate, c_success_rate, lower_is_better=False)

    b_err_rate = b_sum.error_rate * 100.0
    c_err_rate = c_sum.error_rate * 100.0
    add_comparison("Error Rate", "%", b_err_rate, c_err_rate, lower_is_better=True)

    # Extract target metadata safely
    b_endpoint = baseline.endpoint or baseline.target.get("base_url", "unknown")
    c_endpoint = candidate.endpoint or candidate.target.get("base_url", "unknown")
    b_model = baseline.model or baseline.target.get("model", "unknown")
    c_model = candidate.model or candidate.target.get("model", "unknown")

    return BenchmarkComparison(
        baseline_run_id=baseline.run_id,
        candidate_run_id=candidate.run_id,
        baseline_model=b_model,
        candidate_model=c_model,
        baseline_endpoint=b_endpoint,
        candidate_endpoint=c_endpoint,
        metrics=metrics,
    )


def compare_files(
    baseline_path: str | Path,
    candidate_path: str | Path,
) -> BenchmarkComparison:
    """Load two benchmark JSON export files and produce a comparison."""
    b_res = BenchmarkResult.from_json_file(baseline_path)
    c_res = BenchmarkResult.from_json_file(candidate_path)
    return compare_benchmarks(b_res, c_res)


def format_comparison_table(comparison: BenchmarkComparison) -> str:
    """Format a BenchmarkComparison into a readable ASCII table."""
    lines: list[str] = [
        "InferLoad Benchmark Comparison",
        "------------------------------",
        f"Baseline:  {comparison.baseline_run_id} (model: {comparison.baseline_model}, endpoint: {comparison.baseline_endpoint})",
        f"Candidate: {comparison.candidate_run_id} (model: {comparison.candidate_model}, endpoint: {comparison.candidate_endpoint})",
        "",
        f"{'Metric':<22} {'Baseline':<14} {'Candidate':<14} {'Diff':<14} {'% Change':<10}",
        "-" * 76,
    ]

    for m in comparison.metrics:
        b_str = f"{m.baseline:.2f} {m.unit}" if m.baseline is not None else "N/A"
        c_str = f"{m.candidate:.2f} {m.unit}" if m.candidate is not None else "N/A"

        if m.diff is not None:
            sign = "+" if m.diff > 0 else ""
            diff_str = f"{sign}{m.diff:.2f} {m.unit}"
        else:
            diff_str = "N/A"

        if m.pct_change is not None:
            sign = "+" if m.pct_change > 0 else ""
            pct_str = f"{sign}{m.pct_change:.2f}%"
        else:
            pct_str = "N/A"

        lines.append(f"{m.name:<22} {b_str:<14} {c_str:<14} {diff_str:<14} {pct_str:<10}")

    return "\n".join(lines)
