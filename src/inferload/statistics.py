"""Statistical calculations, repetitions analysis, and uncertainty estimation."""

from __future__ import annotations

import math
from typing import Sequence
from pydantic import BaseModel, Field

# Two-tailed Student's t critical values for alpha=0.05 (95% confidence level)
# Keyed by degrees of freedom nu = N - 1
_STUDENT_T_95_TABLE: dict[int, float] = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.160,
    14: 2.145,
    15: 2.131,
    16: 2.120,
    17: 2.110,
    18: 2.101,
    19: 2.093,
    20: 2.086,
    21: 2.080,
    22: 2.074,
    23: 2.069,
    24: 2.064,
    25: 2.060,
    26: 2.056,
    27: 2.052,
    28: 2.048,
    29: 2.045,
    30: 2.042,
}


def get_student_t_critical(df: int) -> float:
    """Return Student's t critical value for 95% confidence interval given degrees of freedom."""
    if df < 1:
        return 1.960
    if df in _STUDENT_T_95_TABLE:
        return _STUDENT_T_95_TABLE[df]
    if df > 30:
        return 1.960
    return 2.042


class SampleStatistics(BaseModel):
    """Statistical summary and uncertainty estimates over repeated benchmark measurements."""

    sample_size: int
    mean: float | None = None
    median: float | None = None
    std_dev: float | None = None
    min: float | None = None
    max: float | None = None
    coefficient_of_variation_pct: float | None = None
    ci_95_lower: float | None = None
    ci_95_upper: float | None = None
    ci_95_margin: float | None = None

    @property
    def minimum(self) -> float | None:
        return self.min

    @property
    def maximum(self) -> float | None:
        return self.max


def compute_sample_statistics(values: Sequence[float]) -> SampleStatistics:
    """Compute mean, median, sample std dev (Bessel's correction), min, max, CV, and 95% CI.

    All computations are performed on unrounded 64-bit floating point numbers.
    """
    valid = [float(v) for v in values if v is not None and not math.isnan(v)]
    n = len(valid)

    if n == 0:
        return SampleStatistics(sample_size=0)

    val_min = min(valid)
    val_max = max(valid)
    sorted_vals = sorted(valid)

    # Median
    if n % 2 == 1:
        median = sorted_vals[n // 2]
    else:
        median = (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0

    mean = sum(valid) / n

    if n < 2:
        return SampleStatistics(
            sample_size=1,
            mean=mean,
            median=median,
            std_dev=None,
            min=val_min,
            max=val_max,
            coefficient_of_variation_pct=None,
            ci_95_lower=None,
            ci_95_upper=None,
            ci_95_margin=None,
        )

    # Sample standard deviation (Bessel's correction N - 1)
    variance = sum((x - mean) ** 2 for x in valid) / (n - 1)
    std_dev = math.sqrt(variance)

    # Coefficient of variation (CV)
    cv = (std_dev / abs(mean) * 100.0) if mean != 0.0 else None

    # Student's t 95% Confidence Interval
    se = std_dev / math.sqrt(n)
    t_crit = get_student_t_critical(n - 1)
    margin = t_crit * se
    ci_lower = mean - margin
    ci_upper = mean + margin

    return SampleStatistics(
        sample_size=n,
        mean=mean,
        median=median,
        std_dev=std_dev,
        min=val_min,
        max=val_max,
        coefficient_of_variation_pct=cv,
        ci_95_lower=ci_lower,
        ci_95_upper=ci_upper,
        ci_95_margin=margin,
    )
