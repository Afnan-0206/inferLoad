"""Optional server telemetry adapter for Prometheus-compatible inference metrics endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any
import httpx
from pydantic import BaseModel, Field


class ServerTelemetrySnapshot(BaseModel):
    """Point-in-time snapshot of inference server telemetry metrics."""

    timestamp: str
    available: bool = True
    error_message: str | None = None
    server_version: str | None = None
    running_requests: float | None = None
    waiting_requests: float | None = None
    kv_cache_usage_pct: float | None = None
    num_preemptions: float | None = None
    queue_time_seconds_avg: float | None = None
    prefill_time_seconds_avg: float | None = None
    decode_time_seconds_avg: float | None = None
    raw_metrics: dict[str, float] = Field(default_factory=dict)


class ExperimentTelemetry(BaseModel):
    """Container for experiment telemetry snapshots and non-causal correlation notes."""

    enabled: bool = False
    available: bool = False
    endpoint_url: str | None = None
    server_version: str | None = None
    error_message: str | None = None
    telemetry_before: ServerTelemetrySnapshot | None = None
    telemetry_during: ServerTelemetrySnapshot | None = None
    telemetry_after: ServerTelemetrySnapshot | None = None
    correlation_notes: list[str] = Field(default_factory=list)


def parse_prometheus_text(text: str) -> dict[str, float]:
    """Parse Prometheus text exposition format into a name-value mapping.

    Handles comments (# HELP, # TYPE), empty lines, labels ({...}),
    and floating point values (including inf, -inf, nan).
    """
    metrics: dict[str, float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        try:
            # Handle labels: metric_name{label="val",...} value [timestamp]
            if "{" in line:
                metric_name = line[: line.find("{")].strip()
                rest = line[line.find("}") + 1 :].strip()
                tokens = rest.split()
                if tokens:
                    metrics[metric_name] = float(tokens[0])
            else:
                tokens = line.split()
                if len(tokens) >= 2:
                    metrics[tokens[0]] = float(tokens[1])
        except (ValueError, IndexError):
            # Gracefully ignore malformed metric lines
            continue

    return metrics


def extract_telemetry_metrics(
    metrics: dict[str, float],
    server_version: str | None = None,
) -> ServerTelemetrySnapshot:
    """Extract standard inference metrics from parsed Prometheus metrics dictionary.

    Supports vLLM standard metric names and common inference server conventions.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Running requests
    running = (
        metrics.get("vllm:num_requests_running")
        if "vllm:num_requests_running" in metrics
        else metrics.get("vllm_num_requests_running")
        if "vllm_num_requests_running" in metrics
        else metrics.get("num_requests_running")
    )

    # 2. Waiting requests
    waiting = (
        metrics.get("vllm:num_requests_waiting")
        if "vllm:num_requests_waiting" in metrics
        else metrics.get("vllm_num_requests_waiting")
        if "vllm_num_requests_waiting" in metrics
        else metrics.get("num_requests_waiting")
    )

    # 3. KV cache usage percentage
    kv_pct = (
        metrics.get("vllm:kv_cache_usage_perc")
        if "vllm:kv_cache_usage_perc" in metrics
        else metrics.get("vllm_kv_cache_usage_perc")
        if "vllm_kv_cache_usage_perc" in metrics
        else metrics.get("kv_cache_usage_perc")
    )
    if kv_pct is None:
        # Legacy vLLM cache usage factor (0.0 to 1.0)
        legacy_factor = metrics.get("vllm:gpu_cache_usage_factor", metrics.get("vllm_gpu_cache_usage_factor"))
        if legacy_factor is not None:
            kv_pct = legacy_factor * 100.0 if legacy_factor <= 1.0 else legacy_factor

    # 4. Preemptions
    preemptions = (
        metrics.get("vllm:num_preemptions")
        if "vllm:num_preemptions" in metrics
        else metrics.get("vllm:num_preemptions_total")
        if "vllm:num_preemptions_total" in metrics
        else metrics.get("vllm_num_preemptions_total")
    )

    # 5. Queue time (histogram sum / count)
    q_sum = metrics.get("vllm:request_queue_time_seconds_sum", metrics.get("vllm_request_queue_time_seconds_sum"))
    q_cnt = metrics.get("vllm:request_queue_time_seconds_count", metrics.get("vllm_request_queue_time_seconds_count"))
    queue_avg = (q_sum / q_cnt) if (q_sum is not None and q_cnt is not None and q_cnt > 0) else None

    # 6. Prefill time (histogram sum / count)
    pf_sum = metrics.get(
        "vllm:request_prefill_time_seconds_sum",
        metrics.get(
            "vllm_request_prefill_time_seconds_sum",
            metrics.get("vllm:time_to_first_token_seconds_sum", metrics.get("vllm_time_to_first_token_seconds_sum")),
        ),
    )
    pf_cnt = metrics.get(
        "vllm:request_prefill_time_seconds_count",
        metrics.get(
            "vllm_request_prefill_time_seconds_count",
            metrics.get("vllm:time_to_first_token_seconds_count", metrics.get("vllm_time_to_first_token_seconds_count")),
        ),
    )
    prefill_avg = (pf_sum / pf_cnt) if (pf_sum is not None and pf_cnt is not None and pf_cnt > 0) else None

    # 7. Decode time (histogram sum / count)
    dec_sum = metrics.get(
        "vllm:request_decode_time_seconds_sum",
        metrics.get(
            "vllm_request_decode_time_seconds_sum",
            metrics.get("vllm:time_per_output_token_seconds_sum", metrics.get("vllm_time_per_output_token_seconds_sum")),
        ),
    )
    dec_cnt = metrics.get(
        "vllm:request_decode_time_seconds_count",
        metrics.get(
            "vllm_request_decode_time_seconds_count",
            metrics.get("vllm:time_per_output_token_seconds_count", metrics.get("vllm_time_per_output_token_seconds_count")),
        ),
    )
    decode_avg = (dec_sum / dec_cnt) if (dec_sum is not None and dec_cnt is not None and dec_cnt > 0) else None

    return ServerTelemetrySnapshot(
        timestamp=now_iso,
        available=True,
        error_message=None,
        server_version=server_version,
        running_requests=running,
        waiting_requests=waiting,
        kv_cache_usage_pct=kv_pct,
        num_preemptions=preemptions,
        queue_time_seconds_avg=queue_avg,
        prefill_time_seconds_avg=prefill_avg,
        decode_time_seconds_avg=decode_avg,
        raw_metrics=metrics,
    )


class ServerTelemetryCollector:
    """Non-blocking collector for Prometheus-compatible inference server metrics."""

    def __init__(
        self,
        metrics_url: str | None,
        enabled: bool = True,
        server_version: str | None = None,
        timeout_seconds: float = 3.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.metrics_url = metrics_url
        self.enabled = enabled and bool(metrics_url)
        self.server_version = server_version
        self.timeout_seconds = timeout_seconds
        self._external_client = http_client

    async def capture_snapshot(self) -> ServerTelemetrySnapshot:
        """Poll the configured metrics endpoint and return a structured snapshot.

        Never raises exceptions; captures failure states with available=False.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        if not self.enabled or not self.metrics_url:
            return ServerTelemetrySnapshot(
                timestamp=now_iso,
                available=False,
                error_message="Server telemetry disabled or metrics URL not configured",
                server_version=self.server_version,
            )

        try:
            if self._external_client is not None:
                resp = await self._external_client.get(self.metrics_url, timeout=self.timeout_seconds)
            else:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(self.metrics_url, timeout=self.timeout_seconds)

            if resp.status_code != 200:
                return ServerTelemetrySnapshot(
                    timestamp=now_iso,
                    available=False,
                    error_message=f"HTTP {resp.status_code} from telemetry endpoint",
                    server_version=self.server_version,
                )

            metrics = parse_prometheus_text(resp.text)
            return extract_telemetry_metrics(metrics, server_version=self.server_version)
        except Exception as exc:
            return ServerTelemetrySnapshot(
                timestamp=now_iso,
                available=False,
                error_message=f"Failed to fetch telemetry: {exc}",
                server_version=self.server_version,
            )


def build_non_causal_correlation_notes(
    points: list[Any],
    snap_before: ServerTelemetrySnapshot | None,
    snap_during: ServerTelemetrySnapshot | None,
    snap_after: ServerTelemetrySnapshot | None,
) -> list[str]:
    """Generate strictly observational correlation notes without inferring causality."""
    notes: list[str] = []
    if not points:
        return notes

    first_point = points[0]
    last_point = points[-1]

    # Client observations
    low_c = first_point.concurrency
    high_c = last_point.concurrency
    low_ttft = first_point.ttft_p95.mean if first_point.ttft_p95 else None
    high_ttft = last_point.ttft_p95.mean if last_point.ttft_p95 else None
    low_lat = first_point.latency_p95.mean if first_point.latency_p95 else None
    high_lat = last_point.latency_p95.mean if last_point.latency_p95 else None

    during = snap_during if (snap_during and snap_during.available) else (snap_after if (snap_after and snap_after.available) else None)

    if low_ttft is not None and high_ttft is not None and during:
        if high_ttft > low_ttft and during.waiting_requests is not None and during.waiting_requests > 0:
            notes.append(
                f"Client TTFT p95 increased from {low_ttft:.1f} ms to {high_ttft:.1f} ms while server waiting-request count was observed at {during.waiting_requests:.0f} during execution."
            )
        elif high_ttft > low_ttft:
            notes.append(
                f"Client TTFT p95 increased from {low_ttft:.1f} ms to {high_ttft:.1f} ms between concurrency {low_c} and {high_c}."
            )

    if low_lat is not None and high_lat is not None and during:
        if high_lat > low_lat and during.running_requests is not None:
            notes.append(
                f"Client total latency p95 increased from {low_lat:.1f} ms to {high_lat:.1f} ms while server running-request count was observed at {during.running_requests:.0f}."
            )

    if during and during.kv_cache_usage_pct is not None:
        notes.append(
            f"Server KV cache utilization was recorded at {during.kv_cache_usage_pct:.1f}% during benchmark load."
        )

    if during and during.queue_time_seconds_avg is not None:
        notes.append(
            f"Server reported average request queue time of {during.queue_time_seconds_avg * 1000.0:.1f} ms."
        )

    if during and during.prefill_time_seconds_avg is not None:
        notes.append(
            f"Server reported average prefill time of {during.prefill_time_seconds_avg * 1000.0:.1f} ms."
        )

    if during and during.decode_time_seconds_avg is not None:
        notes.append(
            f"Server reported average decode time of {during.decode_time_seconds_avg * 1000.0:.1f} ms."
        )

    return notes


def render_telemetry_correlation_markdown(
    telemetry: ExperimentTelemetry | None,
    points: list[Any],
) -> list[str]:
    """Render markdown section for server telemetry correlation report."""
    lines: list[str] = [
        "## 12. Server Telemetry & Client Metric Correlation",
        "",
    ]


    if not telemetry or not telemetry.enabled:
        lines.extend([
            "Server telemetry was not enabled for this benchmark run.",
            "",
            "> [!NOTE]",
            "> *InferLoad client measurements proceeded normally without server telemetry.*",
            "",
        ])
        return lines

    if not telemetry.available:
        err = telemetry.error_message or "server telemetry unavailable"
        lines.extend([
            f"**Status:** Server telemetry unavailable ({err}).",
            "",
            "> [!NOTE]",
            "> *The benchmark completed successfully. Server telemetry polling failed or the endpoint was unreachable.*",
            "",
        ])
        return lines

    # Summary of Client Observations
    lines.extend([
        "### Client Observations",
        "",
        "| Metric | First Tested Point | Highest Tested Point |",
        "| :--- | :--- | :--- |",
    ])
    if points:
        p_first = points[0]
        p_last = points[-1]
        ttft_f = f"{p_first.ttft_p95.mean:.1f} ms" if p_first.ttft_p95 and p_first.ttft_p95.mean is not None else "N/A"
        ttft_l = f"{p_last.ttft_p95.mean:.1f} ms" if p_last.ttft_p95 and p_last.ttft_p95.mean is not None else "N/A"
        lat_f = f"{p_first.latency_p95.mean:.1f} ms" if p_first.latency_p95 and p_first.latency_p95.mean is not None else "N/A"
        lat_l = f"{p_last.latency_p95.mean:.1f} ms" if p_last.latency_p95 and p_last.latency_p95.mean is not None else "N/A"
        thru_f = f"{p_first.throughput.mean:.2f} req/s" if p_first.throughput and p_first.throughput.mean is not None else "N/A"
        thru_l = f"{p_last.throughput.mean:.2f} req/s" if p_last.throughput and p_last.throughput.mean is not None else "N/A"

        lines.extend([
            f"| **Concurrency Level** | {p_first.concurrency} | {p_last.concurrency} |",
            f"| **TTFT p95** | {ttft_f} | {ttft_l} |",
            f"| **Total Latency p95** | {lat_f} | {lat_l} |",
            f"| **Throughput** | {thru_f} | {thru_l} |",
        ])
    lines.append("")

    # Server Observations across snapshots
    lines.extend([
        "### Server Observations (Snapshots)",
        "",
        f"**Configured Telemetry Endpoint:** `{telemetry.endpoint_url}`  ",
    ])
    if telemetry.server_version:
        lines.append(f"**Reported Server Version:** `{telemetry.server_version}`  ")
    lines.append("")

    def _fmt_val(val: float | None, unit: str = "", decimals: int = 1) -> str:
        if val is None:
            return "N/A"
        return f"{val:.{decimals}f}{unit}"

    b = telemetry.telemetry_before
    d = telemetry.telemetry_during
    a = telemetry.telemetry_after

    lines.extend([
        "| Telemetry Metric | Before Run | During Run | After Run |",
        "| :--- | :--- | :--- | :--- |",
        f"| **Running Requests** | {_fmt_val(b.running_requests if b else None, decimals=0)} | {_fmt_val(d.running_requests if d else None, decimals=0)} | {_fmt_val(a.running_requests if a else None, decimals=0)} |",
        f"| **Waiting Requests** | {_fmt_val(b.waiting_requests if b else None, decimals=0)} | {_fmt_val(d.waiting_requests if d else None, decimals=0)} | {_fmt_val(a.waiting_requests if a else None, decimals=0)} |",
        f"| **KV Cache Usage** | {_fmt_val(b.kv_cache_usage_pct if b else None, '%')} | {_fmt_val(d.kv_cache_usage_pct if d else None, '%')} | {_fmt_val(a.kv_cache_usage_pct if a else None, '%')} |",
        f"| **Preemptions Count** | {_fmt_val(b.num_preemptions if b else None, decimals=0)} | {_fmt_val(d.num_preemptions if d else None, decimals=0)} | {_fmt_val(a.num_preemptions if a else None, decimals=0)} |",
        f"| **Queue Time (avg)** | {_fmt_val(b.queue_time_seconds_avg * 1000.0 if b and b.queue_time_seconds_avg else None, ' ms')} | {_fmt_val(d.queue_time_seconds_avg * 1000.0 if d and d.queue_time_seconds_avg else None, ' ms')} | {_fmt_val(a.queue_time_seconds_avg * 1000.0 if a and a.queue_time_seconds_avg else None, ' ms')} |",
        f"| **Prefill Time (avg)** | {_fmt_val(b.prefill_time_seconds_avg * 1000.0 if b and b.prefill_time_seconds_avg else None, ' ms')} | {_fmt_val(d.prefill_time_seconds_avg * 1000.0 if d and d.prefill_time_seconds_avg else None, ' ms')} | {_fmt_val(a.prefill_time_seconds_avg * 1000.0 if a and a.prefill_time_seconds_avg else None, ' ms')} |",
        f"| **Decode Time (avg)** | {_fmt_val(b.decode_time_seconds_avg * 1000.0 if b and b.decode_time_seconds_avg else None, ' ms')} | {_fmt_val(d.decode_time_seconds_avg * 1000.0 if d and d.decode_time_seconds_avg else None, ' ms')} | {_fmt_val(a.decode_time_seconds_avg * 1000.0 if a and a.decode_time_seconds_avg else None, ' ms')} |",
        "",
    ])

    # Observational Correlation Notes
    lines.extend([
        "### Correlation Observations (Non-Causal)",
        "",
    ])
    if telemetry.correlation_notes:
        for note in telemetry.correlation_notes:
            lines.append(f"- {note}")
    else:
        lines.append("- No substantial correlation signals identified in snapshot data.")
    lines.append("")

    # Snapshot methodology limitation
    lines.extend([
        "> [!IMPORTANT]",
        "> **Point-in-Time Snapshot Methodology Limitation:**",
        "> Telemetry snapshots capture discrete point-in-time boundary measurements (before, during, and after execution). "
        "> A point snapshot is not equivalent to continuous per-request tracing or server-side profiling. "
        "> InferLoad does not automatically assert that server queueing or cache pressure caused client latency degradation; "
        "> observations document concurrent system states without claiming unverified causal mechanisms.",
        "",
    ])

    return lines
