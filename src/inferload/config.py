"""Configuration schema and validation for InferLoad."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class TargetConfig(BaseModel):
    """Target inference endpoint configuration."""

    base_url: str = Field(description="Base URL of OpenAI-compatible API, e.g. http://localhost:8000/v1")
    api_key: str | None = Field(default=None, description="API authorization key if required")
    model: str = Field(description="Model identifier to test")
    timeout: float = Field(default=60.0, gt=0, description="Per-request HTTP timeout in seconds")
    headers: dict[str, str] = Field(default_factory=dict, description="Additional custom HTTP headers")

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        v = v.strip()
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Invalid URL scheme '{parsed.scheme}': base_url must start with http:// or https://")
        if not parsed.netloc:
            raise ValueError("base_url must include a valid host/domain name and port if applicable")
        return v.rstrip("/")

    @property
    def chat_completions_url(self) -> str:
        """Derive the full /chat/completions endpoint URL."""
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"


class WorkloadConfig(BaseModel):
    """Workload definition: prompts, concurrency, request volume, sampling."""

    requests: int = Field(gt=0, description="Total number of measured requests to execute")
    concurrency: int = Field(gt=0, description="Number of concurrent worker requests")
    stream: bool = Field(default=True, description="Whether to request streaming (SSE)")
    prompts: list[str] = Field(min_length=1, description="List of prompt strings to cycle or sample from")
    max_tokens: int | None = Field(default=128, ge=1, description="Maximum tokens to generate")
    temperature: float | None = Field(default=0.0, ge=0.0, description="Sampling temperature")
    seed: int | None = Field(default=None, description="Random seed for reproducible prompt selection")
    extra_params: dict[str, Any] = Field(default_factory=dict, description="Extra OpenAI payload parameters")

    @field_validator("prompts")
    @classmethod
    def validate_prompts(cls, v: list[str]) -> list[str]:
        cleaned = [p.strip() for p in v if p.strip()]
        if not cleaned:
            raise ValueError("prompts list must contain at least one non-empty string")
        return cleaned


class ExecutionConfig(BaseModel):
    """Execution options: warmup, delay, limits."""

    warmup_requests: int = Field(default=0, ge=0, description="Number of unmeasured warmup requests before benchmark")
    delay_between_requests_ms: float = Field(default=0.0, ge=0.0, description="Delay between worker request dispatches")


class ExportConfig(BaseModel):
    """Export configuration for benchmark output artifacts."""

    output_dir: str = Field(default="results", description="Directory to write result artifacts")
    formats: list[str] = Field(default_factory=lambda: ["json", "csv"], description="List of export formats")
    prefix: str = Field(default="run", description="Filename prefix for output files")

    @field_validator("formats")
    @classmethod
    def validate_formats(cls, v: list[str]) -> list[str]:
        valid = {"json", "csv"}
        cleaned = [fmt.lower().strip() for fmt in v]
        for fmt in cleaned:
            if fmt not in valid:
                raise ValueError(f"Unsupported export format '{fmt}'. Allowed: {sorted(valid)}")
        return cleaned


class ArrivalConfig(BaseModel):
    """Arrival process configuration: closed-loop concurrency vs open-loop rate."""

    mode: str = Field(default="closed", description="'closed' (bounded worker pool) or 'rate' (open-loop constant rate)")
    requests_per_second: float | None = Field(default=None, gt=0, description="Dispatch rate for open-loop mode")

    @model_validator(mode="after")
    def validate_arrival(self) -> ArrivalConfig:
        mode_clean = self.mode.lower().strip()
        if mode_clean not in ("closed", "rate"):
            raise ValueError(f"Unsupported arrival mode '{self.mode}'. Allowed: 'closed', 'rate'")
        self.mode = mode_clean
        if self.mode == "rate" and (self.requests_per_second is None or self.requests_per_second <= 0):
            raise ValueError("requests_per_second must be provided and > 0 when arrival mode is 'rate'")
        return self


class TelemetryConfig(BaseModel):
    """Optional configuration for collecting server-side Prometheus metrics."""

    enabled: bool = Field(default=False, description="Whether to collect server-side telemetry snapshots")
    metrics_url: str | None = Field(default=None, description="Prometheus-compatible /metrics or /vmetrics endpoint URL")
    headers: dict[str, str] = Field(default_factory=dict, description="Headers to include with metrics requests")
    timeout: float = Field(default=5.0, gt=0, description="Timeout for telemetry requests in seconds")
    server_version: str | None = Field(default=None, description="Explicit server version, e.g. vLLM 0.6.3")



class BenchmarkConfig(BaseModel):
    """Root configuration for an InferLoad benchmark run."""

    target: TargetConfig
    workload: WorkloadConfig
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    arrival: ArrivalConfig = Field(default_factory=ArrivalConfig)
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)



def load_config(path: str | Path) -> BenchmarkConfig:
    """Load, parse, and validate a BenchmarkConfig from a YAML file."""
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw_data = yaml.safe_load(f)

    if not isinstance(raw_data, dict):
        raise ValueError(f"YAML configuration must define a mapping, got {type(raw_data).__name__}")

    return BenchmarkConfig.model_validate(raw_data)
