"""Experiment configuration schema and sweep definition."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel, Field, model_validator

from inferload.config import ArrivalConfig, ExecutionConfig, ExportConfig, TargetConfig, TelemetryConfig


class ExperimentMeta(BaseModel):
    """Metadata describing an experiment run."""

    name: str = Field(description="Descriptive identifier for the experiment")
    description: str = Field(default="", description="Optional context or research question")
    output_dir: str = Field(default="results", description="Root results directory")


class SweepDefinition(BaseModel):
    """Parameters to vary systematically across the experiment."""

    concurrency: list[int] = Field(default_factory=lambda: [1], description="Concurrency levels to test")
    max_tokens: list[int] | None = Field(default=None, description="Optional list of max token generation limits")
    prompt_profiles: list[str] | None = Field(default=None, description="Optional prompt profile keys to sweep")
    arrival_rates: list[float] | None = Field(default=None, description="Optional arrival rates for open-loop sweep")
    repetitions: int = Field(default=1, ge=1, description="Number of independent repetitions per parameter point")
    requests_per_point: int = Field(default=20, ge=1, description="Measured requests per repetition")

    @model_validator(mode="after")
    def validate_sweep(self) -> SweepDefinition:
        for c in self.concurrency:
            if c <= 0:
                raise ValueError(f"Concurrency values must be positive integers, got {c}")
        if self.max_tokens:
            for m in self.max_tokens:
                if m <= 0:
                    raise ValueError(f"max_tokens must be positive integers, got {m}")
        if self.arrival_rates:
            for r in self.arrival_rates:
                if r <= 0:
                    raise ValueError(f"arrival_rates must be positive numbers, got {r}")
        return self


class ExperimentWorkload(BaseModel):
    """Base workload template and prompt definitions for an experiment."""

    prompts: list[str] = Field(default_factory=list, description="Default prompts")
    prompt_profiles: dict[str, list[str]] = Field(default_factory=dict, description="Named prompt sets")
    max_tokens: int = Field(default=128, ge=1)
    temperature: float = Field(default=0.0, ge=0.0)
    stream: bool = Field(default=True)
    seed: int | None = Field(default=None)
    extra_params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def ensure_prompts_exist(self) -> ExperimentWorkload:
        if not self.prompts and not self.prompt_profiles:
            raise ValueError("Workload must define either 'prompts' or 'prompt_profiles'")
        return self


class ExperimentConfig(BaseModel):
    """Root configuration for a multi-point performance experiment sweep."""

    experiment: ExperimentMeta
    target: TargetConfig
    workload: ExperimentWorkload
    sweep: SweepDefinition
    arrival: ArrivalConfig = Field(default_factory=ArrivalConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)



def validate_benchmark_quality(config: ExperimentConfig) -> list[str]:
    """Validate benchmark experiment configuration and emit quality warnings.

    Enforces hard constraints:
    - warmup_requests >= 0
    - repetitions >= 1
    - requests_per_point >= 1
    - all concurrency values >= 1

    Emits warnings for small sample sizes and non-deterministic workloads
    without blocking execution.
    """
    # Hard validation checks
    if config.execution.warmup_requests < 0:
        raise ValueError(f"Warmup requests must be >= 0, got {config.execution.warmup_requests}")
    if config.sweep.repetitions < 1:
        raise ValueError(f"Repetitions must be >= 1, got {config.sweep.repetitions}")
    if config.sweep.requests_per_point < 1:
        raise ValueError(f"Requests per point must be >= 1, got {config.sweep.requests_per_point}")
    if not config.sweep.concurrency:
        raise ValueError("Sweep must specify at least one concurrency level.")
    for c in config.sweep.concurrency:
        if c < 1:
            raise ValueError(f"Concurrency values must be >= 1, got {c}")

    warnings: list[str] = []

    # Sample size warnings for tail percentiles
    if config.sweep.requests_per_point < 30:
        warnings.append(
            f"Sample size per point is {config.sweep.requests_per_point} (< 30). "
            f"Tail-percentile measurements (p95, p99) exhibit high empirical variance on small sample sizes."
        )

    if config.sweep.repetitions < 3:
        warnings.append(
            f"Repetitions count is {config.sweep.repetitions} (< 3). "
            f"Cross-run uncertainty estimates (sample standard deviation, Student's t 95% confidence intervals) "
            f"require multiple trials to assess repeatability across runs."
        )

    if config.execution.warmup_requests == 0:
        warnings.append(
            "Warmup requests count is 0. Initial cold-start, TCP handshake, or engine model caching "
            "may contaminate measurement results."
        )

    if config.workload.temperature > 0.0 and config.workload.seed is None:
        warnings.append(
            f"Temperature is {config.workload.temperature} (> 0.0) without a deterministic random seed. "
            f"Generation lengths and token content may vary across repetitions."
        )

    return warnings


def load_experiment_config(path: str | Path) -> ExperimentConfig:
    """Load and validate an ExperimentConfig from a YAML file."""
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Experiment configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Experiment YAML must be a mapping, got {type(data).__name__}")

    config = ExperimentConfig.model_validate(data)
    # Perform benchmark quality validation (will raise ValueError on hard constraint violations)
    validate_benchmark_quality(config)
    return config

