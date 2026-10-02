# InferLoad Results Interpretation Guide

> **A scientific guide to understanding, evaluating, and drawing sound conclusions from LLM inference benchmark results.**

---

## 1. Introduction: The Physics of Generative Inference

Benchmarking Large Language Model (LLM) serving systems differs fundamentally from traditional web service load testing. A standard REST endpoint performs a database lookup or compute task whose duration is predominantly static or log-normal. 

In contrast, generative LLM inference consists of two entirely distinct phases governed by different hardware constraints:

1. **The Prefill Phase (Prompt Ingestion):**
   - The server ingests the entire prompt in parallel.
   - Heavily **compute-bound** (matrix multiplication across tokens in the prompt).
   - Governs the **Time to First Token (TTFT)**.

2. **The Decode Phase (Auto-Regressive Generation):**
   - The model emits tokens sequentially, one at a time, feeding each generated token back into the next iteration.
   - Heavily **memory-bandwidth-bound** (reading all model weights from GPU HBM to SRAM for every individual token generated).
   - Governs **Inter-Chunk / Inter-Token Latency (ITL)** and total generation duration.

InferLoad is designed to isolate and measure these dynamics from the client's perspective. Understanding what these metrics mean—and what they do *not* mean—is essential for accurate performance engineering.

---

## 2. What the Numbers Mean

### A. Time to First Token (TTFT) / First Usable Content Timing
- **Formula:** $T_{\text{first\_usable\_content}} - T_{\text{request\_start}}$
- **What it measures:** The elapsed wall time from the moment InferLoad sends the HTTP request across the TCP socket until the client receives, decodes, and parses the first Server-Sent Event (SSE) chunk containing non-empty text content (`delta.content != ""`).
- **Why it matters:** TTFT dictates perceived interactive responsiveness for end users. If TTFT is high, users experience the system as sluggish or unresponsive, regardless of how fast subsequent tokens stream.

### B. Total Latency
- **Formula:** $T_{\text{request\_end}} - T_{\text{request\_start}}$
- **What it measures:** The complete end-to-end duration from request dispatch until the final SSE stream termination signal (`data: [DONE]`) or full HTTP response closure.
- **Why it matters:** Total latency reflects overall request turnaround time. For non-streaming requests or background batch jobs, total latency is the primary Service Level Objective (SLO).

### C. Inter-Chunk Latency vs. Inter-Token Latency (ITL)
- **Formula:** $\frac{1}{K-1} \sum_{i=1}^{K-1} (t_{i+1} - t_i)$ across streaming chunks.
- **What it measures:** The time interval between consecutive streaming content chunk arrivals over the network.
- **Scientific distinction:** If the server emits exactly 1 token per chunk, inter-chunk latency equals **Inter-Token Latency (ITL)** (or Time Per Output Token, TPOT). If intermediate reverse proxies (e.g. Nginx, Envoy) buffer chunks or the server coalesces tokens, this measures **chunk delivery interval**.

### D. Tokens per Second (Throughput)
- **Per-Request Output Tokens/s:** $\frac{\text{output\_tokens}}{\text{total\_latency\_s}}$ for an individual request.
- **Aggregate Output Tokens/s:** $\frac{\sum \text{output\_tokens}}{T_{\text{total\_benchmark\_duration\_s}}}$.
- **Important note on token counts:** InferLoad extracts token counts **exclusively** from server-returned usage metadata (e.g., `stream_options: {"include_usage": true}`). If the server omits usage metadata, InferLoad reports `output_tokens: None` rather than fabricating token counts using an uncalibrated third-party tokenizer.

### E. Request Throughput (Requests per Second, RPS)
- **Formula:** $\frac{N_{\text{completed}}}{T_{\text{total\_duration\_s}}}$
- **What it measures:** The frequency at which complete inference requests are processed by the serving system under the specified load.

### F. Within-Run Request Percentiles (p50, p95, p99)
- **Formula:** Linear interpolation between closest ranks (Type 7).
- **What they measure:** The distribution of individual request timings within a single trial:
  - **p50 (Median):** Typical experience of the 50th percentile of requests.
  - **p95 / p99 (Tail Latencies):** The experience of requests in the upper 5% and 1% of the latency distribution.

---

## 3. What the Numbers Do NOT Mean (Avoiding Overreach)

A client-side load generator is an external, black-box instrument. Drawing unverified conclusions about internal server components without server-side telemetry is methodologically unsound:

```
┌─────────────────────────────────────────────────────────────┐
│                 Client-Observed Measurement                 │
│                                                             │
│  [Network RTT] + [Server Queueing] + [GPU Prefill/Decode]  │
└─────────────────────────────────────────────────────────────┘
                               ▲
           Client sees ONLY the aggregated sum!
           Cannot isolate components without server telemetry.
```

1. **A surge in TTFT does NOT prove slow GPU prefill compute:**
   - Under concurrency, incoming requests frequently sit in the inference engine's scheduling queue waiting for KV-cache blocks or batch slots to free up.
   - A TTFT of 2,000 ms could mean 100 ms of prefill compute preceded by 1,900 ms of queue wait time. Without server telemetry (`vllm:num_requests_waiting`), the client cannot disambiguate compute from queuing.

2. **Client latency does NOT equal pure GPU compute time:**
   - Client-measured latency includes client event loop processing, local socket buffers, network transit round trips, server HTTP deserialization, and JSON serialization.

3. **Inter-chunk interval does NOT guarantee single-token forward pass time:**
   - TCP packet coalescing, Nginx buffering, or engine-level token batching can deliver 3 tokens in a single chunk every 60 ms rather than 1 token every 20 ms.

4. **Throughput flattening does NOT prove GPU core saturation:**
   - When throughput plateaus as concurrency increases, the bottleneck could be:
     - GPU compute saturation (rare during decode).
     - GPU memory bandwidth saturation (common during decode).
     - KV-cache memory exhaustion triggering request preemption.
     - Server CPU bottleneck (HTTP handling / token serialization).
     - Operating system socket connection limits.

5. **Compliant tested concurrency does NOT predict unmeasured capacity:**
   - Reporting that concurrency 4 satisfies an SLO does **not** imply concurrency 5 or 6 will. InferLoad strictly reports the **"highest observed compliant tested concurrency"** and never extrapolates beyond tested boundaries.

---

## 4. Client-Side vs. Server-Side Measurements

| Metric Dimension | Client-Side (InferLoad) | Server-Side (e.g. vLLM Prometheus) |
| :--- | :--- | :--- |
| **Perspective** | End-to-end reality perceived by clients/users | Internal engine execution stages |
| **TTFT** | Request dispatch $\to$ First content chunk | Prefill execution time (excluding queue wait) |
| **Queue Time** | Inferred as tail latency inflation | Measured directly (`vllm:request_queue_time`) |
| **Memory State** | Inferred from sudden latency inflection | Measured directly (`vllm:gpu_cache_usage_factor`) |
| **Preemption** | Manifests as extreme tail latency outliers | Measured directly (`vllm:num_preemptions_total`) |
| **Network Jitter** | Included in all measurements | Excluded |

### Recommended Practice: Correlate Client and Server Metrics
When conducting deep-dive performance characterizations, capture server Prometheus metrics concurrently with an InferLoad experiment to align client-observed symptoms with internal causes.

---

## 5. Why Tail Latency Matters (The Tyranny of p95 and p99)

In standard software benchmarks, engineers frequently focus on average (mean) latency. In LLM serving, **averages are dangerously misleading**:

1. **Continuous Batching Contention:**
   Modern inference engines continuously insert newly arrived prompts into ongoing generation batches. When a large prompt arrives, the prefill compute temporarily preempts or stretches the iteration times of all active decode streams, creating latency spikes that appear only in the 95th and 99th percentiles.

2. **KV-Cache Fragmentation & Preemption:**
   When GPU memory runs low, the serving engine may pause a request and swap its KV-cache blocks to system RAM, or abort and recompute it later. This creates catastrophic multi-second outliers for the affected requests while the median remains calm.

3. **Variable Generation Lengths:**
   If 9 requests generate 20 tokens and 1 request generates 500 tokens, the average latency reflects neither typical user experience nor true capacity limits. Tail percentiles (p95, p99) expose these disparities.

---

## 6. Why Throughput Flattens (The Knee of the Saturation Curve)

A universal signature observed during concurrency sweeps is the **throughput saturation knee**:

```
Throughput (req/s)
    ▲
    │                     Saturation Knee
    │                           ┌─────────────── (Throughput flatlines)
    │                         * │ *   *   *
    │                       *   │
    │                     *     │
    │                   *       │
    │                 *         │
    │               *           │
    │             *             │
    │           *               │
    │         *                 │   Tail Latency Explosive Surge
    │       *                   │   ============================>
    └─────*─────────────────────┼─────────────────────────────► Concurrency
        Linear Scaling Zone     │       Overload Zone
```

### The Two Regimes:
1. **Linear Scaling Zone (Low Concurrency):**
   - The GPU memory bandwidth and compute cores are underutilized.
   - Increasing concurrency from 1 to 2 to 4 increases throughput almost linearly without significant latency degradation.
2. **Overload Zone (High Concurrency):**
   - The memory bus or batch slots become saturated.
   - By Little's Law ($L = \lambda W$), when maximum throughput ($\lambda_{\max}$) is reached, adding more concurrent requests ($L$) **cannot increase throughput further**.
   - Instead, the excess load forces the average response time ($W$) to inflate proportionally.
   - In this zone, tail latency (p95, p99) explodes exponentially.

---

## 7. Small-N Uncertainty and Statistical Honesty

When executing repeated experiment trials, the number of repetitions ($N$) is typically modest ($N = 3, 5, \text{ or } 10$) due to the high cost of GPU compute.

### Why Small-N Uncertainty Matters:
- In small samples, the standard normal distribution ($Z = 1.96$) severely underestimates error margins.
- InferLoad employs **Student's $t$-distribution** with $\nu = N - 1$ degrees of freedom:
  - For $N = 3$ ($\nu = 2$): $t_{\text{crit}} = 4.303$
  - For $N = 5$ ($\nu = 4$): $t_{\text{crit}} = 2.776$
  - For $N = 10$ ($\nu = 9$): $t_{\text{crit}} = 2.262$
- With $N = 3$, a standard deviation of 100 ms yields a 95% confidence margin of:
  $$\text{Margin} = 4.303 \times \frac{100}{\sqrt{3}} \approx \pm 248.4\text{ ms}$$
- Wide confidence intervals truthfully convey that $N = 3$ is sufficient to spot gross regressions, but insufficient to claim sub-millisecond precision.

### Why Repetitions Must Never Be Pooled:
- InferLoad **never pools** raw requests from different runs into a single synthetic population.
- Requests inside a single trial share temporal, memory, and network correlation. Pooling artificially multiplies $N$ by the number of requests per trial, falsely deflating the standard error and projecting an illusion of statistical certainty that violates basic statistical methodology.
