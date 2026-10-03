# InferLoad — LLM Inference Load Testing & Capacity Planner

> **“InferLoad is a performance-testing and capacity-analysis tool specifically for LLM inference systems. Think of it like k6 / Locust + observability + benchmark analysis, designed around the unique execution mechanics of LLM serving.”**

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Render](https://img.shields.io/badge/Render-Live%20Demo-46E3B7?logo=render&logoColor=white)](https://inferload.onrender.com/)

🌐 **Live Production Console:** [https://inferload.onrender.com/](https://inferload.onrender.com/)

For the complete architectural thesis and project vision, see [docs/project_overview.md](docs/project_overview.md).

---

## 1. What InferLoad Is

**Think of InferLoad as a laboratory for testing an LLM server.**

It sits **outside** the model-serving system and sends controlled traffic to it, measures exactly what happens from the client side, optionally reads server telemetry, and then turns all that data into a benchmark + SLO/capacity report.

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

Instead of simply asking *“Does my API work?”*, InferLoad asks:
> **“How does this LLM inference server behave as workload, concurrency, prompt size, and output size change—and at what tested operating point do its latency and throughput stop meeting my requirements?”**

InferLoad is **not** a chatbot, **not** an LLM wrapper, and **not** a generic HTTP load generator with an AI sticker. It is an empirical measurement laboratory built to quantify how inference servers behave under controlled concurrent workloads, varying prompt lengths, generation lengths, and streaming conditions.


---

## 2. Why It Exists

Standard HTTP load testing tools (such as wrk, ab, Locust, or k6) treat endpoints as static request-response systems. They measure request-level round-trip latency, which completely obscures the fundamental dynamics of generative inference:
- **Two distinct execution phases:** Compute-bound prefill (prompt ingestion) vs. memory-bandwidth-bound decode (auto-regressive token generation).
- **Time to First Token (TTFT):** Critical for user perceived responsiveness.
- **Inter-Token Latency (ITL):** Fluidity of streaming generation.
- **Continuous batching jitter & KV-cache starvation:** Failures that manifest primarily in tail latencies (p95, p99).

InferLoad was built to measure these mechanics cleanly, honestly, and reproducibly without inventing synthetic token counts or dropping failed requests.

---

## 3. What It Measures

For every individual request, InferLoad collects:
- **Time to First Token (TTFT):** Time from request dispatch to arrival and decoding of the first non-empty token chunk.
- **First Byte Latency:** Time from request dispatch to receipt of initial HTTP headers (isolating network RTT).
- **Total Latency:** End-to-end response completion time.
- **Inter-Token Latency (ITL):** Time deltas between consecutive token arrivals.
- **Token Counts:** Prompt and completion tokens (when returned by server usage metadata).
- **Tokens Per Second:** Generation throughput per request and aggregate throughput across the system.
- **Request Throughput:** Total and successful requests per second.
- **Error Rate & Classification:** Granular breakdown of HTTP status codes, network timeouts, and stream malformations.
- **Statistical Distributions:** `count`, `min`, `max`, `mean`, `median`, `p50`, `p95`, `p99` computed with linear interpolation on unrounded values.

---

## 4. Installation

InferLoad requires **Python 3.12+**.

### Clone and Install
```bash
git clone https://github.com/inferload/inferload.git
cd inferLoad

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

# Install in editable mode with development dependencies
pip install -e ".[dev]"
```

Alternatively, install using `uv`:
```bash
uv pip install -e ".[dev]"
```

---

## 5. Configuration

Workloads are defined in YAML configuration files.

Example (`examples/basic.yaml`):

```yaml
target:
  base_url: "http://localhost:8000/v1"
  api_key: "optional-token"
  model: "llama-3-8b-instruct"
  timeout: 60.0

workload:
  requests: 20
  concurrency: 4
  stream: true

  prompts:
    - "Explain what a database index is in simple terms."
    - "Explain how TCP differs from UDP."
    - "What is a hash table?"

  max_tokens: 128
  temperature: 0.0
  seed: 42  # Optional: for reproducible prompt sampling

execution:
  warmup_requests: 2  # Dispatched before measurement window to prime sockets/caches

export:
  output_dir: "results"
  formats:
    - "json"
    - "csv"
  prefix: "run"
```

---

## 6. Running a Benchmark

### Validate Configuration
Check that your configuration schema, prompt sets, and target URLs are valid:
```bash
inferload validate examples/basic.yaml
```

### Execute Benchmark
```bash
inferload run examples/basic.yaml
```

### CLI Options
- `--output-dir, -o`: Override results output directory.
- `--requests, -n`: Override total number of requests.
- `--concurrency, -c`: Override concurrent worker count.

```bash
inferload run examples/basic.yaml --concurrency 8 --requests 50
```

---

## 7. Web UI — Local Interactive Benchmark Console

InferLoad includes a local browser interface for configuring, running, monitoring, and inspecting LLM inference benchmarks and SLO capacity reports without needing to juggle terminal commands, CSV files, and markdown viewers.

> **Crucial Rule:** The Web UI is a client to the existing InferLoad Python engine. It does **not** duplicate benchmark logic, does **not** compute separate SLO results in JavaScript, and contains **zero** hard-coded or fabricated numbers. All results, tables, curves, and reports are loaded directly from the authoritative Python experiment runner and filesystem artifacts.

### Starting the Web UI

```bash
# Start on default address (http://127.0.0.1:8000)
inferload web

# Or specify host and port:
inferload web --host 127.0.0.1 --port 8080
```

When started, InferLoad prints:
```text
InferLoad Web UI
Running at: http://127.0.0.1:8000
Press Ctrl+C to stop.
```

Open `http://127.0.0.1:8000` (or access the live deployment at [https://inferload.onrender.com/](https://inferload.onrender.com/)) in any modern web browser.

### Key Web UI Capabilities

1. **Target & Model Discovery:**
   - Pre-configured target endpoints (`http://127.0.0.1:11434/v1` for Ollama, `http://127.0.0.1:8000/v1` for vLLM).
   - Dynamic local model autodetection (e.g. queries local Ollama and renders one-click selectable model chips).
2. **Workload & Sweep Configuration:**
   - Multi-concurrency sweeps (e.g., `1, 2, 4`), repetitions per point, requests per point, warmup counts.
   - Sampling parameters: `max_tokens`, `temperature`, `seed`, streaming toggle (`ON`/`OFF`), arrival mode (`closed`/`open`).
   - Dynamic benchmark prompts management (add/remove custom prompt strings; passed directly to the workload generator without hidden defaults).
3. **SLO Configuration:**
   - Configurable ceilings for TTFT p95, total latency p95, error rate, and throughput minimum.
   - Evaluated by the existing Python capacity analysis module.
4. **Pre-Flight Validation:**
   - Validates endpoint URLs, concurrency values, prompt sets, and SLO numbers against Pydantic schemas before launching.
5. **Non-Blocking Background Benchmark Execution:**
   - Runs experiments asynchronously in the background so the browser never freezes.
   - Live progress status bar showing current trial count, active concurrency, repetition, and elapsed execution time.
6. **Executive Results & Capacity Determination:**
   - Prominently displays the **Highest Observed Compliant Tested Concurrency** (strictly adhering to empirical testing terminology).
   - Latency & throughput percentiles table (TTFT p50/p95/p99, Latency p50/p95/p99, Throughput req/s, Error rate %, SLO compliance).
   - SLO breakdown table detailing each tested point's compliance or exact violation reasons.
   - Empirical saturation-like observations derived from load inflection analysis.
7. **Performance Curves & Artifacts:**
   - Embedded static performance curves generated by InferLoad (Concurrency vs. TTFT p95, Latency p95, Throughput, Error Rate).
   - Rendered Markdown report tab (no need to open external text editors).
   - Direct download links for `summary.json`, `points.csv`, `report.md`, and plot images.
   - Request-level raw evidence inspection for full auditability.
   - Host environment panel (OS, Python version, CPU cores, RAM, GPU/CUDA detection).
8. **Historical Experiment Inspection:**
   - Slide-out History drawer automatically discovers previous experiment runs from `results/`.
   - Clicking any previous experiment immediately loads its authoritative report, tables, and plots.

---

## 8. Example Output

```text
Loaded config from examples/basic.yaml
Executing benchmark: 20 requests at concurrency 4 against http://localhost:8000/v1/chat/completions (stream=True)...

InferLoad Benchmark
-------------------
Target: http://localhost:8000/v1
Model: example-model

Requests: 20
Concurrency: 4
Success: 20
Errors: 0

TTFT
p50: 124.50 ms
p95: 182.10 ms
p99: 210.05 ms

Total Latency
p50: 842.10 ms
p95: 1250.40 ms
p99: 1410.20 ms

Throughput
Requests/s: 4.62
Output tok/s: 184.20

Export:
results/run-20261002-005600-abcdef.json
results/run-20261002-005600-abcdef.csv
```

---

## 9. Architecture

InferLoad adheres strictly to decoupled engineering principles:
1. **Separation of Workload from Execution:** Workload generators produce `RequestSpec` queues independently of HTTP clients.
2. **Separation of Event Collection from Aggregation:** Raw monotonic timestamps (`time.perf_counter()`) and response metadata are preserved intact in `RequestRecord` instances before any metric reduction.
3. **No Silent Drops:** Timeouts, 4xx/5xx HTTP codes, and malformed chunks are recorded explicitly with full error messages.
4. **No Premature Rounding:** Percentiles (p50, p95, p99) are computed via linear interpolation on raw float values.

See [docs/architecture.md](docs/architecture.md) for full architectural diagrams and [docs/methodology.md](docs/methodology.md) for benchmarking methodology.

---

## 10. Testing

The test suite covers configuration validation, URL sanity, bounded concurrency, streaming SSE chunk parsing, timeouts, HTTP errors, malformed streams, percentile accuracy, and throughput calculation using both mock HTTP transports and live loopback HTTP servers.

Run all tests:
```bash
pytest -v
```

---

## 11. Validated Against Local Test Server

InferLoad's measurement accuracy has been empirically validated against an integrated local mock OpenAI-compatible HTTP server (`tests/integration/mock_server.py`).

### Verification Architecture
The mock server runs over real TCP sockets on `127.0.0.1` and emits streaming Server-Sent Events with controlled, nanosecond-precise sleep delays. It tracks active requests and maximum concurrent connections server-side.

### Key Verified Results
1. **Timing Accuracy vs. Injected Delays:**
   - **Injected TTFT delay:** `100.0 ms` $\to$ **Observed p50 TTFT:** `~116 ms` (the ~16 ms delta corresponds accurately to TCP loopback handshaking, HTTP header generation, and SSE line decoding).
   - **Injected inter-chunk delay:** `20.0 ms` $\to$ **Observed p50 ITL:** `~20.1 ms`.
   - **Injected total duration:** $100\text{ ms} + (4 \times 20\text{ ms}) = 180\text{ ms}$ $\to$ **Observed p50 Total Latency:** `~205 ms`.
2. **Server-Side Concurrency Boundedness:**
   - When configured with `concurrency: 2` across 12 requests, server telemetry confirmed `max_concurrency == 2` at all times. In-flight requests never exceeded the target ceiling.
3. **Warmup Request Isolation:**
   - Warmup requests are confirmed dispatched to the server but strictly omitted from summary throughput, percentiles, and request counts.
4. **Resilience & Fault Accounting:**
   - Verified that HTTP 429 (rate limits), HTTP 500 (internal server errors), timeouts, and malformed SSE chunks (`MalformedStreamChunk`) are preserved, properly classified, and accounted for in the error breakdown without crashing or dropping requests.

### Running the Standalone End-to-End Benchmark
You can run this self-contained validation benchmark directly:
```bash
python scripts/run_local_benchmark.py --config examples/integration.yaml
```

---

## 12. Controlled Performance Experiments (Phase 3)

InferLoad supports multi-point parameter sweeps with independent repetitions, statistical uncertainty estimation, and static curve generation:

```bash
# Execute concurrency sweep experiment
inferload experiment examples/concurrency_sweep.yaml

# Render human-readable Markdown analysis report
inferload report results/experiment-concurrency-sweep-<id>
```

### Experiment Capabilities
- **Multi-Parameter Sweeps:** Sweep across concurrency levels, prompt profiles, max tokens, or open-loop arrival rates.
- **Statistical Repetitions:** Calculates mean, median, sample standard deviation (Bessel's correction), coefficient of variation ($CV$), and Student's $t$ 95% confidence intervals across repeated trials.
- **Dual Arrival Models:**
  - **Closed-Loop Concurrency:** Bounded worker pool where arrival rate adapts to server response time.
  - **Open-Loop Constant Rate:** Independent request arrival schedule ($\Delta t = 1/R$) simulating uncoordinated client arrivals.
- **Empirical Saturation Detection:** Flags inflection points where load increases substantially but throughput gains flatten while tail latencies surge (strictly without claiming unmeasured internal causes).
- **Static Curve Generation:** Emits publication-quality PNG plots under `results/<experiment>/plots/` (concurrency vs. TTFT p95, throughput, error rate, etc.).
- **Regression Analysis:** Compare baseline and candidate runs via `inferload compare <run1.json> <run2.json>`.

See [docs/experiments.md](docs/experiments.md) for full experimental methodology and statistical details.

---

## 13. Empirical Capacity Analysis & SLO Compliance (Phase 4)

InferLoad evaluates tested benchmark sweep points against explicit, user-configured Service Level Objectives (SLOs):

```yaml
# slo.yaml
slo:
  max_ttft_p95_ms: 1000.0          # Time to first token p95 ceiling
  max_total_latency_p95_ms: 2500.0 # Total response completion ceiling
  max_error_rate_pct: 1.0          # Maximum acceptable error percentage
  min_throughput_req_per_sec: 1.0  # Minimum required throughput
```

### Run Capacity Analysis
```bash
inferload capacity results/experiment-local-capacity-sweep-<id> --slo examples/slo_local.yaml
```

### Deterministic Compliance Output
```text
InferLoad Capacity Analysis
---------------------------

Configured SLO Constraints:
  - TTFT p95 <= 1000.0 ms
  - Total Latency p95 <= 2500.0 ms
  - Error Rate <= 1.00%
  - Throughput >= 1.00 req/s

Tested Concurrency Levels:
  1, 2, 4

Highest Observed Compliant Tested Concurrency:
  2

Performance at Compliant Point:
  - Observed Throughput : 1.75 req/s
  - TTFT p95            : 643.3 ms
  - Total Latency p95   : 1243.1 ms
  - Error Rate          : 0.00%

Detailed Tested Points Breakdown:
  * Concurrency 1: [COMPLIANT] (Throughput: 1.68 req/s, TTFT p95: 52.9 ms, Latency p95: 649.6 ms, Errors: 0.0%)
  * Concurrency 2: [COMPLIANT] (Throughput: 1.75 req/s, TTFT p95: 643.3 ms, Latency p95: 1243.1 ms, Errors: 0.0%)
  * Concurrency 4: [VIOLATION] (Throughput: 1.76 req/s, TTFT p95: 1859.0 ms, Latency p95: 2411.8 ms, Errors: 0.0%)
      - TTFT p95 (1859.0 ms) exceeds SLO maximum (1000.0 ms)

Important Interpretation Notice:
  Capacity is limited to tested configurations and does not extrapolate beyond 
  observed measurements. This represents the highest observed compliant tested 
  concurrency, not theoretical or maximum system capacity.
```

---

## 14. Real GPU Validation & vLLM Telemetry Correlation (Phase 5 & 5.5)

InferLoad includes production protocols for evaluating high-performance accelerated inference engines such as **vLLM**:

```bash
# 1. Start vLLM with modern CLI syntax and a configurable baseline model:
vllm serve Qwen/Qwen2.5-1.5B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --gpu-memory-utilization 0.90 \
  --max-model-len 4096 \
  --dtype bfloat16

# 2. Run InferLoad validation sweep with optional Prometheus telemetry correlation:
inferload experiment examples/vllm_gpu_baseline.yaml

# 3. Analyze SLO compliance:
inferload capacity results/experiment-vllm-gpu-baseline-<id> --slo examples/slo_vllm.yaml
```

- **Configurable Models:** Any Hugging Face model identifier can be benchmarked (`Qwen/Qwen2.5-1.5B-Instruct` is documented as the default lightweight baseline).
- **Optional Server Telemetry Correlation:** Non-blocking adapter polls Prometheus `/metrics` for waiting requests, running requests, KV cache occupancy, and queue/prefill/decode timings without coupling the runner to vLLM.
- **Scientific Reproducibility Checklist:** Standardized 22-parameter checklist covering hardware, CUDA, engine flags, and sampling controls.
- **Non-Causal Reporting:** Formulates observational statements ("Client TTFT increased while server waiting-request count also increased") without jumping to unverified causal conclusions.

See [docs/real_server.md](docs/real_server.md), [docs/gpu-validation.md](docs/gpu-validation.md), and [docs/reproducibility.md](docs/reproducibility.md).

---

## 15. Enterprise Scale & Concurrency Calibration ($c > 256$)

> [!IMPORTANT]
> **Single-Instance Calibration Operating Envelope:** InferLoad's high-precision Python `asyncio` runner is calibrated for concurrent worker pools of **$c \le 128$** (and up to $c \le 256$ on tuned Linux systems with `uvloop`). Beyond $c = 256$, single-threaded event loop tick overhead and coordinated omission can induce client-side latency inflation when running on a single host.

| Concurrency Tier | Calibration Status | Recommended Infrastructure | Expected Timing Accuracy |
| :--- | :--- | :--- | :--- |
| **$c \in [1, 64]$** | **Scientific Gold Standard** | Single laptop, workstation, or cloud VM | Sub-millisecond TTFT jitter (<0.3ms) |
| **$c \in [65, 128]$** | **Production Capacity Grade** | Single 4+ core cloud instance | High-fidelity saturation knee discovery |
| **$c \in [129, 256]$** | **Calibrated Stress Envelope** | Linux host + `uvloop` + `ulimit -n 65536` | Accurate throughput; minor P99 jitter |
| **$c > 256$ to $10,000+$** | **Distributed Enterprise** | Multi-node Kubernetes DaemonSet (Rust/Go) | Coordinated Omission Corrected |

For large-scale enterprise load generation ($c \ge 500$ to $10,000+$ concurrent streams), refer to our comprehensive architecture blueprint:
👉 **[Enterprise Scaling Architecture & Distributed Blueprint](docs/enterprise_scaling_architecture.md)**

---

## 16. Current Limitations

InferLoad is focused on measurement accuracy and scientific integrity. The following remain deliberate design constraints:
- **Client-Side Tokenization Fallbacks:** If the server does not return `usage.completion_tokens`, InferLoad reports `output_tokens: None` rather than guessing token counts without the exact tokenizer.
- **Single Host Generation:** Single-instance load generation is bound to $c \le 128$ for gold-standard precision; multi-node distributed agent architecture is documented in [docs/enterprise_scaling_architecture.md](docs/enterprise_scaling_architecture.md).
- **Single Endpoint Type:** Supports OpenAI-compatible `/chat/completions` only.
- **Point-in-Time Telemetry Snapshots:** Captures boundary metrics before, during, and after benchmark execution; does not trace individual internal request lifetimes.

---

## 17. Roadmap

- **Future Phases:**
  - Poisson and Gamma open-loop arrival distributions.
  - Client-side tokenization fallbacks via HuggingFace `tokenizers` / `tiktoken`.
  - Multi-turn conversation load emulation with accumulating KV-cache state.
  - Distributed multi-worker client generation (Go/Rust worker agents) for ultra-high throughput testing.
  - Automated capacity planning recommendation engine.

