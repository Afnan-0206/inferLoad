"""Deterministic capacity analysis against measured benchmark Service Level Objectives (SLOs).

Strict scientific principle:
This module performs empirical compliance evaluation over observed benchmark points.
It does NOT extrapolate, predict, or claim unmeasured maximum system capacity.
All conclusions are strictly scoped as 'highest observed compliant tested concurrency'.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel, Field

from inferload.experiment import ExperimentResult


class SLOConfig(BaseModel):
    """Target Service Level Objectives (SLOs) for inference capacity assessment."""

    max_ttft_p95_ms: float | None = Field(default=None, description="Maximum acceptable TTFT p95 in milliseconds")
    max_total_latency_p95_ms: float | None = Field(default=None, description="Maximum acceptable Total Latency p95 in milliseconds")
    max_error_rate_pct: float | None = Field(default=None, description="Maximum acceptable error rate in percent (e.g. 1.0 = 1%)")
    min_throughput_req_per_sec: float | None = Field(default=None, description="Minimum acceptable request throughput (req/s)")


class PointCompliance(BaseModel):
    """Compliance assessment for a single tested benchmark parameter point."""

    concurrency: int
    load_parameter: float
    throughput_rps: float | None = None
    ttft_p95_ms: float | None = None
    total_latency_p95_ms: float | None = None
    error_rate_pct: float = 0.0
    compliant: bool
    violations: list[str] = Field(default_factory=list)


class CapacityAnalysisResult(BaseModel):
    """Deterministic capacity analysis outcome over observed benchmark sweep points."""

    slo: SLOConfig
    tested_concurrencies: list[int]
    tested_points: list[PointCompliance]
    highest_compliant_concurrency: int | None = None
    compliant_point: PointCompliance | None = None
    warnings: list[str] = Field(default_factory=list)
    interpretation_note: str = (
        "Capacity is limited to tested configurations and does not extrapolate "
        "beyond observed measurements. This represents the highest observed "
        "compliant tested concurrency, not theoretical or maximum system capacity."
    )


def load_slo_config(path: str | Path) -> SLOConfig:
    """Load and parse an SLO configuration from a YAML file."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"SLO configuration file not found: {p}")

    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"SLO YAML must be a mapping, got {type(data).__name__}")

    raw_slo = data.get("slo", data)
    if not isinstance(raw_slo, dict):
        raise ValueError(f"SLO section must be a mapping, got {type(raw_slo).__name__}")

    return SLOConfig.model_validate(raw_slo)


def analyze_capacity(
    experiment_result: ExperimentResult,
    slo: SLOConfig,
) -> CapacityAnalysisResult:
    """Evaluate tested benchmark points against configured SLO constraints.

    Identifies the highest tested concurrency point where all configured SLOs
    are satisfied simultaneously.
    """
    tested_points: list[PointCompliance] = []
    concurrencies: list[int] = []

    for pt in experiment_result.points:
        concurrencies.append(pt.concurrency)
        thru = pt.throughput.mean
        ttft_p95 = pt.ttft_p95.mean
        lat_p95 = pt.latency_p95.mean
        err_pct = (pt.error_rate.mean or 0.0) * 100.0

        violations: list[str] = []

        # 1. TTFT p95 constraint
        if slo.max_ttft_p95_ms is not None:
            if ttft_p95 is None:
                violations.append("TTFT p95 measurement unavailable/missing")
            elif ttft_p95 > slo.max_ttft_p95_ms:
                violations.append(
                    f"TTFT p95 ({ttft_p95:.1f} ms) exceeds SLO maximum ({slo.max_ttft_p95_ms:.1f} ms)"
                )

        # 2. Total Latency p95 constraint
        if slo.max_total_latency_p95_ms is not None:
            if lat_p95 is None:
                violations.append("Total latency p95 measurement unavailable/missing")
            elif lat_p95 > slo.max_total_latency_p95_ms:
                violations.append(
                    f"Total latency p95 ({lat_p95:.1f} ms) exceeds SLO maximum ({slo.max_total_latency_p95_ms:.1f} ms)"
                )

        # 3. Error rate constraint
        if slo.max_error_rate_pct is not None:
            if err_pct > slo.max_error_rate_pct:
                violations.append(
                    f"Error rate ({err_pct:.2f}%) exceeds SLO maximum ({slo.max_error_rate_pct:.2f}%)"
                )

        # 4. Minimum throughput constraint
        if slo.min_throughput_req_per_sec is not None:
            if thru is None:
                violations.append("Throughput measurement unavailable/missing")
            elif thru < slo.min_throughput_req_per_sec:
                violations.append(
                    f"Throughput ({thru:.2f} req/s) is below SLO minimum ({slo.min_throughput_req_per_sec:.2f} req/s)"
                )

        is_compliant = len(violations) == 0
        tested_points.append(
            PointCompliance(
                concurrency=pt.concurrency,
                load_parameter=float(pt.concurrency if not pt.arrival_rate else pt.arrival_rate),
                throughput_rps=thru,
                ttft_p95_ms=ttft_p95,
                total_latency_p95_ms=lat_p95,
                error_rate_pct=err_pct,
                compliant=is_compliant,
                violations=violations,
            )
        )

    # Filter compliant points
    compliant_points = [p for p in tested_points if p.compliant]
    warnings: list[str] = []

    if compliant_points:
        # Highest tested concurrency among compliant points
        # If multiple points share the same concurrency, choose highest throughput
        compliant_points.sort(key=lambda p: (p.concurrency, p.throughput_rps or 0.0), reverse=True)
        best_point = compliant_points[0]
        highest_c = best_point.concurrency
    else:
        best_point = None
        highest_c = None
        warnings.append(
            "No tested concurrency point satisfied all configured SLO constraints. "
            "Server experienced latency, throughput, or error-rate violations across the entire tested sweep."
        )

    return CapacityAnalysisResult(
        slo=slo,
        tested_concurrencies=sorted(set(concurrencies)),
        tested_points=tested_points,
        highest_compliant_concurrency=highest_c,
        compliant_point=best_point,
        warnings=warnings,
    )


def format_capacity_report(result: CapacityAnalysisResult) -> str:
    """Format the capacity analysis output into a clean, human-readable report."""
    lines: list[str] = [
        "InferLoad Capacity Analysis",
        "---------------------------",
        "",
        "Configured SLO Constraints:",
    ]

    slo = result.slo
    has_slo = False
    if slo.max_ttft_p95_ms is not None:
        lines.append(f"  - TTFT p95 <= {slo.max_ttft_p95_ms:.1f} ms")
        has_slo = True
    if slo.max_total_latency_p95_ms is not None:
        lines.append(f"  - Total Latency p95 <= {slo.max_total_latency_p95_ms:.1f} ms")
        has_slo = True
    if slo.max_error_rate_pct is not None:
        lines.append(f"  - Error Rate <= {slo.max_error_rate_pct:.2f}%")
        has_slo = True
    if slo.min_throughput_req_per_sec is not None:
        lines.append(f"  - Throughput >= {slo.min_throughput_req_per_sec:.2f} req/s")
        has_slo = True

    if not has_slo:
        lines.append("  (No SLO constraints configured)")

    lines.extend([
        "",
        "Tested Concurrency Levels:",
        f"  {', '.join(str(c) for c in result.tested_concurrencies)}",
        "",
    ])

    if result.highest_compliant_concurrency is not None and result.compliant_point is not None:
        cp = result.compliant_point
        lines.extend([
            "Highest Observed Compliant Tested Concurrency:",
            f"  {result.highest_compliant_concurrency}",
            "",
            "Performance at Compliant Point:",
            f"  - Observed Throughput : {cp.throughput_rps:.2f} req/s" if cp.throughput_rps is not None else "  - Observed Throughput : N/A",
            f"  - TTFT p95            : {cp.ttft_p95_ms:.1f} ms" if cp.ttft_p95_ms is not None else "  - TTFT p95            : N/A",
            f"  - Total Latency p95   : {cp.total_latency_p95_ms:.1f} ms" if cp.total_latency_p95_ms is not None else "  - Total Latency p95   : N/A",
            f"  - Error Rate          : {cp.error_rate_pct:.2f}%",
        ])
    else:
        lines.extend([
            "Highest Observed Compliant Tested Concurrency:",
            "  None (No tested point satisfied all SLO constraints)",
        ])

    if result.warnings:
        lines.extend(["", "Violations / Warnings:"])
        for w in result.warnings:
            lines.append(f"  ! {w}")

    # Detailed tested point breakdown
    lines.extend([
        "",
        "Detailed Tested Points Breakdown:",
    ])
    for pt in result.tested_points:
        status = "[COMPLIANT]" if pt.compliant else "[VIOLATION]"
        thru_str = f"{pt.throughput_rps:.2f} req/s" if pt.throughput_rps is not None else "N/A"
        ttft_str = f"{pt.ttft_p95_ms:.1f} ms" if pt.ttft_p95_ms is not None else "N/A"
        lat_str = f"{pt.total_latency_p95_ms:.1f} ms" if pt.total_latency_p95_ms is not None else "N/A"
        lines.append(
            f"  * Concurrency {pt.concurrency}: {status} "
            f"(Throughput: {thru_str}, TTFT p95: {ttft_str}, Latency p95: {lat_str}, Errors: {pt.error_rate_pct:.1f}%)"
        )
        for v in pt.violations:
            lines.append(f"      - {v}")

    lines.extend([
        "",
        "Important Interpretation Notice:",
        f"  {result.interpretation_note}",
    ])

    return "\n".join(lines)
