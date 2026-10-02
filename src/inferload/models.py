"""Data models for InferLoad benchmark requests, records, metrics, and results."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
from pydantic import BaseModel, Field, computed_field


from inferload.environment import EnvironmentMetadata


class RequestSpec(BaseModel):
    """Specification of an individual benchmark request to execute."""

    request_id: str
    index: int
    is_warmup: bool = False
    prompt: str
    max_tokens: int | None = 128
    temperature: float | None = 0.0
    stream: bool = True
    extra_params: dict[str, Any] = Field(default_factory=dict)


class RequestRecord(BaseModel):
    """Raw data and timings captured for an executed request."""

    request_id: str
    index: int
    is_warmup: bool = False
    prompt: str
    start_time: float  # Unix epoch timestamp in seconds
    end_time: float  # Unix epoch timestamp in seconds

    # High-precision monotonic elapsed offsets (in milliseconds)
    # Measured via time.perf_counter()
    latency_to_first_byte_ms: float | None = None
    latency_to_first_token_ms: float | None = None  # TTFT / First content arrival
    duration_ms: float  # Total latency

    status: Literal["success", "error", "timeout"]
    http_status: int | None = None
    input_text_length: int
    output_text: str = ""
    output_text_length: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    streaming: bool = True
    chunk_count: int = 0
    chunk_delays_ms: list[float] = Field(default_factory=list)

    error_type: str | None = None
    error_message: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def success(self) -> bool:
        return self.status == "success"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ttft_ms(self) -> float | None:
        """Client-perceived Time to First Token (TTFT) in milliseconds.

        Measured from request dispatch until receipt and parsing of the first
        chunk containing non-empty generated text.
        """
        return self.latency_to_first_token_ms

    @computed_field  # type: ignore[prop-decorator]
    @property
    def latency_to_first_content_ms(self) -> float | None:
        """First usable content timing in milliseconds (synonym for client-perceived TTFT)."""
        return self.latency_to_first_token_ms

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_latency_ms(self) -> float:
        """Total latency in milliseconds."""
        return self.duration_ms

    @computed_field  # type: ignore[prop-decorator]
    @property
    def inter_token_latency_ms(self) -> float | None:
        """Mean inter-token/inter-chunk latency in milliseconds.

        Calculated from chunk arrival deltas after the first token.
        When 1 token per chunk is emitted, this equals true ITL.
        """
        if not self.chunk_delays_ms:
            return None
        return sum(self.chunk_delays_ms) / len(self.chunk_delays_ms)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def inter_chunk_latency_ms(self) -> float | None:
        """Mean inter-chunk latency in milliseconds (exact scientific descriptor for SSE chunk deltas)."""
        return self.inter_token_latency_ms

    @computed_field  # type: ignore[prop-decorator]
    @property
    def output_tokens_per_second(self) -> float | None:
        """Output tokens per second for this individual request.

        If explicit token counts are unavailable from the server, returns None (we avoid inventing tokens).
        """
        if self.output_tokens is None or self.duration_ms <= 0:
            return None
        return self.output_tokens / (self.duration_ms / 1000.0)


class MetricStats(BaseModel):
    """Statistical aggregation for a numeric distribution."""

    count: int
    min: float | None = None
    max: float | None = None
    mean: float | None = None
    median: float | None = None
    p50: float | None = None
    p95: float | None = None
    p99: float | None = None


class BenchmarkSummary(BaseModel):
    """Aggregated benchmark statistics across all non-warmup requests."""

    total_requests: int
    success_count: int
    failure_count: int
    error_rate: float
    total_duration_s: float
    requests_per_second: float
    successful_requests_per_second: float

    ttft_ms: MetricStats | None = None
    total_latency_ms: MetricStats
    inter_token_latency_ms: MetricStats | None = None
    inter_chunk_latency_ms: MetricStats | None = None
    output_tokens_per_second: MetricStats | None = None

    aggregate_input_tokens: int | None = None
    aggregate_output_tokens: int | None = None
    aggregate_tokens_per_second: float | None = None
    error_breakdown: dict[str, int] = Field(default_factory=dict)


class BenchmarkResult(BaseModel):
    """Versioned schema representing an entire benchmark run."""

    schema_version: str = "0.1"
    run_id: str
    timestamp: str  # ISO 8601 UTC string
    inferload_version: str = "0.1.0"
    endpoint: str = ""
    model: str = ""
    concurrency: int = 1
    request_count: int = 1
    warmup_count: int = 0
    warmup_requests: int = 0
    repetitions: int = 1
    max_tokens: int | None = None
    temperature: float | None = None
    seed: int | None = None
    streaming: bool = True
    environment: EnvironmentMetadata | None = None
    target: dict[str, Any]
    workload: dict[str, Any]
    execution: dict[str, Any]
    arrival: dict[str, Any] = Field(default_factory=dict)
    summary: BenchmarkSummary
    requests: list[RequestRecord]

    @classmethod
    def from_json_file(cls, path: str | Path) -> BenchmarkResult:
        """Load and parse a BenchmarkResult from a JSON file."""
        import json
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)


