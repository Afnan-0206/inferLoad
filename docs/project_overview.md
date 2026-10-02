# InferLoad — Full Project Blueprint & Architectural Thesis

> **“Think of InferLoad as a laboratory for testing an LLM server. It sits outside the model-serving system and sends controlled traffic to it, measures exactly what happens from the client side, optionally reads server telemetry, and then turns all that data into a benchmark + SLO/capacity report.”**

---

## 1. The Core Idea & Central Thesis

Instead of asking a generic API question:
> *“Does my endpoint return HTTP 200?”*

InferLoad asks the critical capacity and serving question:
> **“How does this LLM inference server behave as workload, concurrency, prompt size, and output size change—and at what tested operating point do its latency and throughput stop meeting my requirements?”**

InferLoad is **not** a chatbot, **not** an LLM wrapper, and **not** a generic HTTP load generator with an AI badge. It is an empirical measurement laboratory built to quantify how inference servers behave under controlled concurrent workloads, varying prompt lengths, generation lengths, and streaming conditions.

---

## 2. The Fundamental Problem: Why Generic Load Testing Fails for LLMs

Standard HTTP load testing tools (wrk, ab, Locust, k6) treat endpoints as static request-response systems:

```text
Standard API:   Request ──────────────────► Server ──────────────────► Response (Total Latency)
```

Generative LLM serving operates under a completely different two-phase pipeline:

```text
LLM Inference:  Request ──► Queue ──► Prefill ──► First Token ──► Auto-regressive Decode ──► Stream Chunks ──► [DONE]
                              (Wait)   (Compute-Bound)   (TTFT)           (Memory-Bandwidth Bound)       (ITL)
```

User perceived responsiveness is governed by **when generation starts (Time to First Token)** and **generation fluidity (Inter-Token Latency)**, not merely total completion latency.

InferLoad measures:
- **Time to First Token (TTFT):** Client-observed duration until the first streamed chunk containing non-empty content (`delta.content != ""`).
- **First Byte Latency:** Network round-trip and TCP/TLS connection time.
- **Total Latency:** Wall time from dispatch to completion.
- **Inter-Chunk Latency:** Interval between successive streamed chunks (avoids falsely assuming 1 SSE chunk equals exactly 1 token due to reverse proxy coalescing).
- **Throughput:** Requests per second and output tokens per second (from verified server usage metadata).
- **Tail Latency Distributions:** Unrounded p50, p95, p99 percentiles.
- **Failure Classification:** Preserves and classifies HTTP 429, 500, timeouts, and malformed streams without silent drops.

---

## 3. The Whole Working in One Flow

```text
          YOU DEFINE AN EXPERIMENT
                    │
                    ▼
             YAML Configuration
                    │
                    ▼
             Workload Generator
                    │
                    ▼
             InferLoad Runner
                    │
          ┌─────────┴─────────┐
          │                   │
    Closed-loop          Open-loop
    concurrency          arrival rate
          │                   │
          └─────────┬─────────┘
                    ▼
             LLM Endpoint
        ┌───────────────────────┐
        │ Ollama / vLLM / etc.  │
        └───────────┬───────────┘
                    │
              streamed response
                    ▼
             Metric Collection
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
      TTFT       Latency      Throughput
       │            │            │
       └────────────┼────────────┘
                    ▼
             Statistics Engine
                    │
                    ▼
            Experiment Analysis
                    │
             ┌──────┴──────┐
             ▼             ▼
       Saturation       SLO Check
        analysis             │
             │               ▼
             └────────► Capacity Report
```

---

## 4. The 17-Step Operational Lifecycle

### 1. You Define the Workload
You don't hard-code the benchmark. You define a reproducible YAML configuration:

```yaml
target:
  base_url: "http://server:8000/v1"
  model: "Qwen/Qwen2.5-1.5B-Instruct"

workload:
  prompts:
    - "Explain CPU caching."
    - "Explain latency versus throughput."
  max_tokens: 128
  temperature: 0.0
  seed: 42

sweep:
  concurrency: [1, 2, 4, 8]
  repetitions: 3
  requests_per_point: 30
```

This tells InferLoad: test concurrency 1, then 2, then 4, then 8. At each point, run 30 measured requests, repeating that experiment 3 times under a fixed seed. The benchmark is controlled and reproducible.

### 2. InferLoad Generates Requests
The workload generator creates individual requests from configured prompts using deterministic, seeded prompt selection. Another run with the same seed will reproduce the exact same workload sequence.

### 3. The Runner Controls Concurrency
InferLoad provides two mathematically distinct load-generation mechanisms:
- **Closed-Loop Mode:** Bounded worker pool. At `concurrency = 4`, InferLoad maintains at most 4 active requests. When Worker 2 finishes, it becomes free, and Request 5 starts. InferLoad does *not* start unlimited requests.
- **Open-Loop Mode:** Time-driven dispatch rate (`requests_per_second = 5`). Requests are scheduled at $t = 0.0, 0.2, 0.4, 0.6, 0.8\text{ s}$. Even if earlier requests are still running, new requests dispatch on schedule. This enables studying server queue accumulation when offered load exceeds service capacity.

### 4. It Sends the Request to the LLM Server
InferLoad connects to OpenAI-compatible inference endpoints (`/v1/chat/completions`), targeting vLLM, Ollama, TensorRT-LLM, TGI, or other compatible serving engines.

### 5. Streaming Measurement
For an LLM, InferLoad does not simply record request sent and response finished. It streams SSE chunks and records monotonic timestamps throughout:
```text
request started ──► first response bytes ──► first usable streamed content ──► chunk 2 ──► chunk 3 ──► ... ──► completion
```

### 6. TTFT is Calculated
Time to First Token (TTFT) represents the duration from request start until the first usable streamed content arrives:
$$\text{TTFT} = t_{\text{first usable content}} - t_{\text{request start}}$$
InferLoad deliberately ignores an initial role-only SSE chunk (`{"role": "assistant"}` with empty content), preventing distorted, artificially low TTFT readings.

### 7. Total Latency is Calculated
$$\text{Total Latency} = t_{\text{completion}} - t_{\text{request start}}$$

### 8. Inter-Chunk Timing is Measured
InferLoad records intervals between successive streamed chunks ($\Delta t = t_k - t_{k-1}$). Crucially, InferLoad documents this as *inter-chunk latency*, deliberately avoiding claiming it is exact token-level latency because SSE chunks may coalesce multiple tokens or be buffered by intermediate proxies.

### 9. Tokens/Second Calculation
When the serving engine returns valid token usage metadata:
$$\text{Tokens/sec} = \frac{\text{output tokens}}{\text{generation duration}}$$
If the server does not return token counts, InferLoad marks token metrics as `None` rather than guessing with synthetic approximations.

### 10. Every Request Becomes a Raw Record
Each request yields a structured, granular execution record:
```json
{
  "request_id": "abc123",
  "start_time": "2026-10-02T11:00:00.000Z",
  "first_content_time": "2026-10-02T11:00:00.082Z",
  "end_time": "2026-10-02T11:00:00.648Z",
  "ttft_ms": 82.4,
  "total_latency_ms": 648.2,
  "output_tokens": 64,
  "status": "success"
}
```
Failures (timeouts, HTTP 429, HTTP 500, network disconnects, malformed streams) are preserved with error codes, contributing honestly to error rates rather than disappearing.

### 11. Request Aggregation & Percentiles
For each run, InferLoad calculates non-parametric percentiles: `min`, `max`, `mean`, `median`, `p50`, `p95`, `p99`. While an average might look acceptable (e.g. 300 ms), tail latency percentiles (e.g. p95 at 1.8 s, p99 at 4.2 s) expose severe serving tail degradation.

### 12. Repeated Experiments Measure Stability
Across repeated trials (e.g. 3 repetitions at concurrency 4), InferLoad treats each run as an independent benchmark trial. It computes unpooled across-run statistics: mean, sample standard deviation ($s$ with Bessel's correction $N - 1$), coefficient of variation ($CV$), and Student's $t$ 95% confidence intervals, separating within-run request variance from run-to-run system instability.

### 13. The Experiment Layer
InferLoad automates multi-dimensional sweep matrices, testing concurrency levels, prompt profiles, and token bounds. This reveals the empirical relationship between load, throughput, and tail latency (e.g. concurrency increases from 1 to 4 $\rightarrow$ throughput increases only 4% while p95 TTFT increases 35x).

### 14. Saturation Analysis
InferLoad algorithmically detects contention inflection points:
- Throughput growth flattens ($\Delta \text{throughput} < 5\%$)
- Tail latency explodes ($\text{p95 TTFT} \gg \text{baseline}$)
InferLoad flags this strictly as **“Observed saturation-like behavior”**. It does not assert “GPU compute is saturated,” because client-side observations alone cannot prove internal root causes.

### 15. Capacity / SLO Analysis
You supply explicit Service Level Objectives:
```yaml
slo:
  max_ttft_p95_ms: 1000
  max_latency_p95_ms: 2500
  max_error_rate_pct: 1.0
  min_throughput_req_per_sec: 1.0
```
InferLoad verifies compliance at every tested operating point and outputs:
> **Highest Observed Compliant Tested Concurrency: 2**

It intentionally does not declare “Maximum system capacity = 2,” because untested concurrency levels (e.g. 3) were not evaluated.

### 16. Optional Server Telemetry Correlation
InferLoad can optionally poll Prometheus metrics (e.g. `/metrics` on vLLM) capturing boundary snapshots before, during, and after runs. Metrics include:
- `vllm:num_requests_waiting`
- `vllm:num_requests_running`
- `vllm:gpu_cache_usage_factor`
Adheres strictly to **Correlation $\neq$ Causation**: *“Client TTFT increased while server waiting-request count was observed at 4.”*

### 17. Structured Final Output Artifacts
Every experiment outputs a complete evidence bundle:
```text
results/
└── experiment/
    ├── summary.json
    ├── points.csv
    ├── report.md
    ├── raw/
    │   ├── run-c1-rep1.json
    │   ├── run-c1-rep2.json
    │   ├── run-c2-rep1.json
    │   └── ...
    └── plots/
        ├── concurrency_vs_ttft_p95.png
        ├── concurrency_vs_throughput.png
        ├── concurrency_vs_error_rate.png
        └── concurrency_vs_total_latency_p95.png
```

---

## 5. The Entire Project in One Real Example

Imagine you have:
- Model: `Qwen/Qwen2.5-1.5B-Instruct`
- Runtime: `vLLM` (`vllm serve Qwen/Qwen2.5-1.5B-Instruct --port 8000`)
- Hardware: Linux GPU Host (NVIDIA CUDA)

You tell InferLoad:
> Test concurrency 1, 2, 4, 8. 50 requests per point. 3 repetitions. 10 warmups.

InferLoad executes:
1. Generates reproducible workload from seeded prompts
2. Sends requests through closed-loop or open-loop runners
3. Measures streaming timestamps at sub-millisecond precision
4. Records every request, preserving failures
5. Repeats the experiment across 3 independent trials
6. Calculates unpooled p50, p95, p99 percentiles and confidence intervals
7. Compares concurrency levels across the sweep
8. Evaluates SLO compliance at each tested point
9. Flags empirical saturation-like behavior
10. Optionally correlates server telemetry boundary snapshots
11. Generates publication-grade charts, CSVs, and Markdown reports

**The fundamental question answered:**
> **“Under this exact workload and environment, how does this LLM serving system behave as load increases, and which tested operating point meets my latency/throughput/error requirements?”**

---

## 6. Critical Evaluation & Methodological Rigor

### Why This Fails (The Trivial Load Tester Trap)
InferLoad fails if it degrades into:
```text
send 100 requests ──► calculate average ──► show chart
```
That is a basic HTTP load tester. InferLoad succeeds because it treats LLM serving as a specialized systems engineering problem: measuring TTFT separately from decode, tracking inter-chunk timing, handling token metadata honestly, distinguishing closed-loop from open-loop queueing, and keeping repeated trials statistically unpooled.

### Weak Assumptions
Client-observed latency is **not** identical to internal GPU execution time. Network round-trip time, client-side event loops, and reverse-proxy buffering introduce client-side variance. InferLoad explicitly documents these boundaries and isolates first-byte network latency.

### What Must Be Proven First
The critical validation milestone:
```text
InferLoad ──► Real Linux/CUDA GPU + vLLM ──► Real Workload ──► Client Measurements + Server Telemetry ──► Reproducible Capacity Conclusion
```
No GPU benchmark results may ever be fabricated. When a live CUDA host is not connected, the codebase stands fully prepared and verified against local endpoints (such as Ollama) and synthetic mock servers.

### Go / Kill / Pivot Decision
**GO.**
The core working model is proven and mathematically sound:
$$\text{Generate controlled load} \longrightarrow \text{Measure LLM behavior} \longrightarrow \text{Statistically analyze} \longrightarrow \text{Detect performance boundaries} \longrightarrow \text{Evaluate SLOs} \longrightarrow \text{Report Highest Observed Compliant Tested Concurrency}$$

---

## 7. Current Project Status & Verification Matrix

| Component | Status | Implementation Details |
| :--- | :---: | :--- |
| **Measurement Engine** | ✅ **COMPLETE** | Non-empty chunk TTFT, ITL, total latency, request throughput, output tok/s |
| **OpenAI-Compatible Endpoint** | ✅ **COMPLETE** | Full support for `/v1/chat/completions` streaming SSE APIs |
| **Failure Accounting** | ✅ **COMPLETE** | Preserves and classifies 429, 500, timeouts, malformed chunks |
| **Closed-Loop Load** | ✅ **COMPLETE** | Bounded worker pool with backpressure |
| **Open-Loop Constant Rate** | ✅ **COMPLETE** | Time-driven dispatch interval ($\Delta t = 1/R$) |
| **Benchmark Experiments** | ✅ **COMPLETE** | Multi-point parameter sweeps across concurrency, tokens, prompts |
| **Repeated Trials & Statistics** | ✅ **COMPLETE** | Unpooled trials, sample std dev, CV, Student's $t$ 95% confidence intervals |
| **Benchmark Comparison** | ✅ **COMPLETE** | Direct regression analysis and metric delta tables |
| **SLO Capacity Analysis** | ✅ **COMPLETE** | Evaluates compliance, reports Highest Observed Compliant Tested Concurrency |
| **Static Visualizations** | ✅ **COMPLETE** | Matplotlib curves generated under `plots/` |
| **Reproducibility Metadata** | ✅ **COMPLETE** | OS, CPU, RAM, GPU optional fields, 22-item operational checklist |
| **Server Telemetry Adapter** | ✅ **COMPLETE** | Prometheus `/metrics` polling with non-causal boundary snapshots |
| **vLLM GPU Preparation** | ✅ **COMPLETE** | Audited startup (`vllm serve`), configurable models, modern metrics documented |
| **Real Ollama Validation** | ✅ **COMPLETE** | Validated against local `qwen2.5:0.5b` with clean zero-error benchmark artifacts |
| **Local Web UI & API** | ✅ **COMPLETE** | Interactive engineering browser UI (`inferload web`), live job progress, SLO capacity views, historical experiment loader |
| **Real GPU/vLLM Validation** | ⏳ **READY** | Full protocol and YAML prepared; awaits connection to physical CUDA host |
