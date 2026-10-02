# InferLoad Architecture

This document describes the architectural layout, component separation, and data flow of InferLoad.

---

## 1. ASCII Architecture Diagram

```
                 +--------------------------------+
                 |    Workload / Experiment YAML  |
                 +--------------------------------+
                                 │
                                 ▼
                     +───────────────────────+
                     |  inferload.config /   |
                     |  experiment_config    |
                     +───────────────────────+
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
       +───────────────────+           +───────────────────+
       |   inferload.cli   |           |inferload.experim. |
       | (Thin Typer CLI)  |           | (Sweep Expansion) |
       +───────────────────+           +───────────────────+
                 │                               │
                 │                     ┌─────────┴─────────┐
                 ▼                     ▼                   ▼
       +───────────────────+  +─────────────────+ +─────────────────+
       |inferload.compare  |  |inferload.runner | |inferload.environ|
       |(Regression Engine)|  |(Async Orchestr.)| |(Host Metadata)  |
       +───────────────────+  +─────────────────+ +─────────────────+
                                       │
                       ┌───────────────┴───────────────┐
                       ▼                               ▼
             [Closed-Loop Concurrency]       [Open-Loop Arrival Rate]
             (Bounded Worker Pool C)         (Fixed Interval 1/R)
                       │                               │
                       └───────────────┬───────────────┘
                                       ▼
                           +───────────────────────+
                           |   inferload.client    |
                           |   (HTTPX SSE Client)  |
                           +───────────────────────+
                                       │
                                       ▼
                           +───────────────────────+
                           |  Target LLM Endpoint  |
                           |  (/chat/completions)  |
                           +───────────────────────+
                                       │
                                       ▼ Raw RequestRecords
                           +───────────────────────+
                           |   inferload.metrics   |
                           | (Percentiles & Stats) |
                           +───────────────────────+
                                       │
                                       ▼
                 ┌─────────────────────┼─────────────────────┐
                 ▼                     ▼                     ▼
       +───────────────────+ +───────────────────+ +───────────────────+
       |inferload.statist. | |inferload.analysis | | inferload.plots   |
       |(Student t 95% CI) | |(Saturation Detect)| |  (Static Curves)  |
       +───────────────────+ +───────────────────+ +───────────────────+
                                       │
                                       ▼
                           +───────────────────────+
                           |  Experiment Artifacts |
                           | (summary.json, CSV,   |
                           |  report.md, plots/)   |
                           +───────────────────────+
```

---

## 2. Component Responsibilities

| Module | Responsibility | Key Invariants |
| :--- | :--- | :--- |
| `config.py` | Validates YAML configuration using Pydantic models. | Ensures non-empty prompts, valid URLs, positive requests and concurrency. |
| `workload.py` | Generates reproducible `RequestSpec` sequences for warmup and benchmark phases. | Never executes HTTP calls. Supports deterministic round-robin or seeded sampling. |
| `client.py` | Executes single requests using `httpx.AsyncClient` and captures raw timestamps. | Distinguishes first-byte from first-token (TTFT). Never drops failed requests. Preserves full float precision. |
| `runner.py` | Orchestrates warmup, bounded concurrency execution, and progress notifications. | Uses `asyncio.Queue` worker pool. Guarantees in-flight requests $\le \text{concurrency}$. |
| `metrics.py` | Aggregates `RequestRecord` sequences into statistical distributions (`MetricStats`) and `BenchmarkSummary`. | Excludes warmup requests. Never calculates percentiles from rounded values. Uses linear rank interpolation. |
| `capacity.py` | Deterministic capacity evaluation against configured SLO constraints. | Strictly limits assessment to tested configurations. Reports highest observed compliant tested concurrency without extrapolation. |
| `exporters.py` | Serializes benchmark results to versioned JSON and tabular CSV files. | Creates target directories if missing. Formats cleanly without loss of raw data. |
| `cli.py` | Provides user-facing CLI commands (`run`, `experiment`, `capacity`, `compare`, `report`, `validate`, `version`). | Thin wrapper over core library. Suitable for scripting and CI/CD pipelines. |

---

## 3. Data Flow

1. **Configuration:** The user supplies a YAML file. `load_config()` parses and validates target, workload, execution, and export specifications.
2. **Workload Generation:** `WorkloadGenerator` creates a deterministic queue of `RequestSpec` objects.
3. **Warmup Phase (Optional):** If `execution.warmup_requests > 0`, unmeasured warmup requests are dispatched to prime sockets and caches.
4. **Benchmark Execution:** `concurrency` concurrent workers consume `RequestSpec` items from an `asyncio.Queue` and invoke `InferenceClient.execute_request()`.
5. **Event Recording:** `InferenceClient` streams Server-Sent Events, measuring $T_0$, $T_{\text{first\_byte}}$, $T_{\text{first\_token}}$ (TTFT), inter-chunk delays, and $T_{\text{end}}$ using `time.perf_counter()`.
6. **Aggregation:** `aggregate_benchmark_results()` calculates p50, p95, p99, throughput, and error breakdown.
7. **Export & Display:** `export_results()` writes `run-<id>.json` and `run-<id>.csv`. The CLI renders a formatted terminal summary.

---

## 4. Versioned Result Schema (`schema_version: "0.1"`)

```json
{
  "schema_version": "0.1",
  "run_id": "run-20261002-005600-abcdef",
  "timestamp": "2026-10-02T00:56:00.000000+00:00",
  "target": {
    "base_url": "http://localhost:8000/v1",
    "api_key": null,
    "model": "example-model",
    "timeout": 60.0,
    "headers": {}
  },
  "workload": {
    "requests": 20,
    "concurrency": 4,
    "stream": true,
    "prompts": ["..."],
    "max_tokens": 128,
    "temperature": 0.0,
    "seed": null,
    "extra_params": {}
  },
  "execution": {
    "warmup_requests": 2,
    "delay_between_requests_ms": 0.0
  },
  "summary": {
    "total_requests": 20,
    "success_count": 20,
    "failure_count": 0,
    "error_rate": 0.0,
    "total_duration_s": 4.32,
    "requests_per_second": 4.63,
    "successful_requests_per_second": 4.63,
    "ttft_ms": {
      "count": 20,
      "min": 110.2,
      "max": 220.5,
      "mean": 135.4,
      "median": 124.5,
      "p50": 124.5,
      "p95": 182.1,
      "p99": 210.05
    },
    "total_latency_ms": {
      "count": 20,
      "min": 750.0,
      "max": 1450.0,
      "mean": 860.2,
      "median": 842.1,
      "p50": 842.1,
      "p95": 1250.4,
      "p99": 1410.2
    },
    "inter_token_latency_ms": { ... },
    "output_tokens_per_second": { ... },
    "aggregate_input_tokens": 600,
    "aggregate_output_tokens": 2560,
    "aggregate_tokens_per_second": 592.59,
    "error_breakdown": {}
  },
  "requests": [
    {
      "request_id": "req-1-a1b2c3d4",
      "index": 0,
      "is_warmup": false,
      "prompt": "...",
      "start_time": 1759363200.123456,
      "end_time": 1759363200.987654,
      "latency_to_first_byte_ms": 85.3,
      "latency_to_first_token_ms": 124.5,
      "duration_ms": 864.2,
      "status": "success",
      "http_status": 200,
      "input_text_length": 45,
      "output_text": "...",
      "output_text_length": 512,
      "input_tokens": 30,
      "output_tokens": 128,
      "streaming": true,
      "chunk_count": 32,
      "chunk_delays_ms": [24.1, 23.9, 25.0],
      "error_type": null,
      "error_message": null,
      "ttft_ms": 124.5,
      "total_latency_ms": 864.2,
      "inter_token_latency_ms": 24.33,
      "output_tokens_per_second": 148.11,
      "success": true
    }
  ]
}
```
