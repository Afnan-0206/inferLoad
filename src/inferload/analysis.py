"""Empirical performance analysis and saturation detection without speculative causal claims."""

from __future__ import annotations

from typing import Sequence
from pydantic import BaseModel, Field


class SaturationFinding(BaseModel):
    """Observation of saturation-like behavior across sweep parameter points."""

    detected: bool
    parameter_name: str
    from_value: float
    to_value: float
    throughput_change_pct: float
    latency_p95_change_pct: float
    summary_message: str
    cautionary_note: str = (
        "Observation indicates empirical inflection only. "
        "Requires server-side telemetry (e.g. GPU SM occupancy, KV-cache allocation, "
        "engine queue depth) for causal attribution."
    )


class ExperimentPointMetrics(BaseModel):
    """Essential metrics at a single sweep point used for saturation analysis."""

    load_parameter: float  # e.g., concurrency or arrival rate
    throughput_rps: float
    latency_p95_ms: float
    error_rate: float = 0.0


def detect_saturation_regions(
    points: Sequence[ExperimentPointMetrics],
    parameter_name: str = "concurrency",
    min_load_increase_ratio: float = 0.40,
    max_throughput_gain_ratio: float = 0.15,
    min_p95_latency_growth_ratio: float = 0.30,
) -> list[SaturationFinding]:
    """Detect regions where increasing load yields marginal throughput gains but substantial p95 latency growth.

    Strict scientific principle:
    Uses strictly cautious, non-causal language ('observed saturation-like behavior',
    'possible contention', 'requires server-side telemetry for causal attribution').
    """
    findings: list[SaturationFinding] = []
    if len(points) < 2:
        return findings

    # Sort strictly by load parameter
    sorted_pts = sorted(points, key=lambda p: p.load_parameter)

    for i in range(len(sorted_pts) - 1):
        p1 = sorted_pts[i]
        p2 = sorted_pts[i + 1]

        if p1.load_parameter <= 0:
            continue

        load_increase = (p2.load_parameter - p1.load_parameter) / p1.load_parameter
        if load_increase < min_load_increase_ratio:
            continue

        if p1.throughput_rps > 0:
            thru_change = (p2.throughput_rps - p1.throughput_rps) / p1.throughput_rps
        else:
            thru_change = 0.0

        if p1.latency_p95_ms > 0:
            lat_change = (p2.latency_p95_ms - p1.latency_p95_ms) / p1.latency_p95_ms
        else:
            lat_change = 0.0

        # Saturation condition: throughput gains are marginal or negative while tail latency surges
        if thru_change <= max_throughput_gain_ratio and lat_change >= min_p95_latency_growth_ratio:
            thru_pct = thru_change * 100.0
            lat_pct = lat_change * 100.0
            msg = (
                f"Observed saturation-like behavior when {parameter_name} increased from "
                f"{p1.load_parameter:g} to {p2.load_parameter:g}: "
                f"throughput changed by {thru_pct:+.1f}%, while p95 latency grew by {lat_pct:+.1f}%. "
                f"This pattern indicates possible contention; "
                f"requires server-side telemetry for causal attribution."
            )
            findings.append(
                SaturationFinding(
                    detected=True,
                    parameter_name=parameter_name,
                    from_value=p1.load_parameter,
                    to_value=p2.load_parameter,
                    throughput_change_pct=thru_pct,
                    latency_p95_change_pct=lat_pct,
                    summary_message=msg,
                )
            )

    return findings
