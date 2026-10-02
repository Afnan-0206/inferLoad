# InferLoad Benchmark Methodology

This document outlines the engineering methodology, timing mechanics, and statistical principles behind InferLoad. InferLoad is designed as an empirical load-testing laboratory for LLM inference endpoints.

---

## 1. What TTFT Actually Means in InferLoad

In LLM performance benchmarking, **Time to First Token (TTFT)** is frequently misquoted or conflated with HTTP response time. InferLoad enforces a strict operational definition:

$$\text{TTFT} = T_{\text{first\_usable\_content}} - T_{\text{request\_start}}$$

Where:
- $T_{\text{request\_start}}$: The exact timestamp when `httpx` dispatches the HTTP request over the socket using `time.perf_counter()`.
- $T_{\text{first\_usable\_content}}$: The exact timestamp when the client receives, reads, and parses the first Server-Sent Event (SSE) chunk containing **non-empty content** (e.g. `delta.content` is non-empty).

### Distinguishing TTFT from First-Byte Latency
InferLoad explicitly separates **First-Byte Latency** from **TTFT**:
- **First-Byte Latency ($T_{\text{first\_byte}} - T_{\text{request\_start}}$):** Captures the moment the HTTP response status line and headers (`HTTP/1.1 200 OK`, `Content-Type: text/event-stream`) arrive. This isolates the initial network Round-Trip Time (RTT) and socket handshake from server inference.
- **Initial SSE Metadata Chunks:** Many inference engines (including OpenAI, vLLM, and TGI) emit an initial chunk defining `delta.role = "assistant"` with an empty `delta.content`. InferLoad **does not** count this metadata chunk as TTFT. TTFT is recorded only when actual generated text content arrives.

```
Request Start (T0)
  │
  ├─> HTTP 200 Headers Arrive (T_first_byte)    [Network RTT + HTTP processing]
  │
  ├─> SSE Role Chunk (delta.role="assistant")   [Ignored for TTFT]
  │
  ├─> First Content Token (T_first_token)       [TTFT = T_first_token - T0]
  │     │
  │     ├─> Chunk 1 Delta (t1 - T_first_token)
  │     ├─> Chunk 2 Delta (t2 - t1)
  │     └─> ...                                 [Inter-Chunk Latency (ITL)]
  │
  └─> Stream Completed (T_end)                  [Total Latency = T_end - T0]
```

---

## 2. Why First Streamed Chunk != Guaranteed Single Token

A fundamental nuance of OpenAI-compatible streaming endpoints is that **an SSE chunk does not guarantee a 1:1 mapping with a single BPE/WordPiece token**:

1. **Chunk Coalescing / Token Batching:** High-performance serving engines (vLLM, TensorRT-LLM) or reverse proxies (Nginx, Envoy, Cloudflare) may coalesce multiple generated tokens into a single TCP packet or SSE chunk under load to amortize serialization overhead.
2. **Sub-Word and Multi-Byte Characters:** Complex scripts or emojis consist of multi-byte UTF-8 sequences. An inference engine might emit partial byte sequences or aggregate multi-token words into one emission.
3. **Chunk Arrival vs. Token Generation:** InferLoad measures chunk inter-arrival time over the network. If the server emits 1 token per chunk, inter-chunk latency corresponds directly to inter-token latency (ITL). If the server buffers or coalesces tokens, inter-chunk latency reflects the server's chunk flush frequency rather than individual model forward passes.

**Engineering Integrity Rule:** InferLoad documents these timings as **chunk inter-arrival delays** and **TTFT (time to first usable content chunk)** rather than inventing speculative per-token intervals when the endpoint only provides chunked streams.

---

## 3. What Can and Cannot Be Measured from an OpenAI-Compatible Endpoint

InferLoad is a client-side black-box benchmarking tool. It is essential to distinguish what can be measured empirically versus what cannot be inferred without server-side instrumentation:

### What CAN Be Measured
- **Client-Observed TTFT:** End-to-end elapsed time before the client receives the first token chunk.
- **Client-Observed Total Latency:** Total wall duration from request dispatch until the final `data: [DONE]` chunk.
- **Inter-Chunk Arrival Timing:** The time distribution between subsequent SSE chunks.
- **Request Throughput:** Number of requests completed per unit time at specified concurrency.
- **Explicit Token Counts:** Total prompt tokens and completion tokens **if and only if** the serving engine returns an explicit `usage` object (e.g. via OpenAI's `stream_options: {"include_usage": true}`).
- **Client-Side Failure Rates:** HTTP 429 (rate limits), 500/502/503 (server errors), socket timeouts, and malformed JSON streams.

### What CANNOT Be Measured (Without Server Telemetry)
- **Server Queue Wait Time:** The time a request spent waiting in the server's scheduling queue before prefill began (unless the server provides custom diagnostic headers such as `X-Queue-Time-Ms`).
- **Prefill vs. Queue Disambiguation:** A high TTFT could mean the prefill compute took 500 ms, or it could mean the request was queued for 480 ms and prefill took 20 ms.
- **Internal GPU Utilization:** SM execution occupancy, memory bus bandwidth, tensor core saturation, and thermal throttling.
- **KV-Cache Memory Dynamics:** KV-cache block fragmentation, PagedAttention block allocation latency, or host-to-device memory swapping.
- **True Internal Model Forward Pass Times:** Jitter introduced by TCP buffers, reverse proxies, and operating system scheduling cannot be disentangled from GPU compute time.

---

## 4. Warmup and Connection Priming

### Why Warmup is Necessary
When benchmarking an inference service, initial requests experience transient latencies caused by:
- TCP three-way handshakes and TLS negotiation.
- HTTP connection pool establishment and keep-alive setup.
- Inference engine dynamic allocation (KV-cache initialization, PagedAttention block allocation, CUDA context creation).
- Model weight page-in or cold kernels.

If measured together with steady-state traffic, initial requests skew p95 and p99 percentiles significantly.

### InferLoad Warmup Mechanics
- Configured via `execution.warmup_requests`.
- Warmup requests are executed before the benchmark window begins.
- Warmup requests are tagged (`is_warmup=True`) and **strictly excluded** from summary percentile calculations and throughput aggregations.

---

## 5. Cold Start vs. Steady State

- **Cold Start:** The system is evaluated when GPU caches, model weights, or workers have been idle or uninitialized.
- **Steady State:** The system is evaluated under continuous load where memory pools, KV caches, and connections are fully warm.

InferLoad Phase 1 focuses on steady-state saturation and concurrency behavior. To measure cold starts, set `warmup_requests: 0` and inspect individual request records in the generated CSV/JSON exports.

---

## 6. Concurrency and Load Generation

### Controlled Concurrency Model
InferLoad enforces strict bounded concurrency using an asynchronous worker pool pattern backed by `asyncio.Queue`:
- A fixed pool of $C$ workers is instantiated ($C = \text{concurrency}$).
- Each worker picks a request specification, sends it over HTTP, awaits response completion, and then picks the next specification.
- This guarantees that at any instant $t$, active in-flight requests never exceed $C$.

### Concurrency vs. Arrival Rate (Closed vs. Open System)
- **Closed System (Concurrency Model):** A new request is only dispatched when a prior request completes.
- **Open System (Arrival Rate / Poisson):** Requests arrive at fixed or random intervals regardless of whether previous requests have completed, causing queue build-up when service capacity is saturated.

Phase 1 implements the closed concurrency model to establish the upper bound on server capacity and throughput without inducing uncontrolled client-side memory exhaustion.

---

## 7. Request Distribution and Prompt/Output Variance

### Prompt Length (Prefill Phase)
The prompt length directly influences the **Time to First Token (TTFT)**. The prefill stage is compute-bound and processed in parallel across prompt tokens. Comparing TTFT across workloads with varying prompt lengths without normalizing can be misleading.

### Output Length (Generation Phase)
The generation stage is memory-bandwidth bound (auto-regressive token generation). Total latency scales linearly with generated token count.

### InferLoad Workload Strategy
- Deterministic cycling (round-robin) across provided prompts ensures equal weighting.
- Optional seeded random selection (`seed: <int>`) enables reproducible probabilistic selection.
- Workload configurations explicitly specify `max_tokens` and `temperature` to control output length variance.

---

## 8. Clock and Timing Mechanics

### Monotonic Clocks
- Wall-clock time (`time.time()`) is subject to system clock adjustments (NTP sync, leap seconds, manual changes).
- All interval measurements (TTFT, total latency, inter-chunk deltas) are captured using **`time.perf_counter()`**, a monotonic high-resolution clock with nanosecond precision.
- Wall-clock UTC timestamps are recorded only for correlation and run identification.

### Precision Preservation
- No intermediate timings or durations are rounded. Raw 64-bit floating-point millisecond values are retained throughout collection and aggregation.
- Rounding is applied solely when formatting CLI tables and final text displays.

---

## 9. Percentile Calculation Method

InferLoad implements standard **linear interpolation between closest ranks** (Type 7 / numpy / scipy standard):

For a sorted sample $X = [x_0, x_1, \dots, x_{N-1}]$ and percentile $p \in [0, 100]$:
1. Rank index: $r = \frac{p}{100} \times (N - 1)$
2. Integer part: $k = \lfloor r \rfloor$
3. Fractional part: $d = r - k$
4. Result:
   $$P_p = x_k + d \cdot (x_{k+1} - x_k)$$

### Why Not Nearest-Rank?
Nearest-rank produces stepped, discontinuous jumps on small sample sizes. Linear interpolation produces smooth, monotonic percentile estimates.

---

## 10. Why p95 and p99 Matter

In LLM serving systems, averages (mean) hide critical pathological behaviors:
- **Head-of-Line Blocking:** A single request generating 2,048 tokens can monopolize an inference batch slot, starving short 30-token queries.
- **KV-Cache Eviction / Swapping:** When memory pressure peaks, the server pauses generation or swaps cache blocks to host memory, introducing dramatic latency spikes visible only in the 95th and 99th percentiles.
- **Continuous Batching Jitter:** Continuous batching engines (vLLM, TensorRT-LLM, TGI) introduce iteration-level scheduling variations that manifest in tail latencies.

---

## 11. Why Tokens/Sec Alone is Insufficient

Quoting aggregate tokens per second alone is a misleading metric for LLM inference:
1. **Prefill vs. Decode Disparity:** A server processing a 4,000-token prompt in 200 ms delivers 20,000 prefill tokens/sec, whereas generating 50 tokens at 25 ms/token yields 40 decode tokens/sec. Aggregating both into a single number obscures whether the bottleneck is compute or memory bandwidth.
2. **User Experience Decoupling:** A system generating 100 tok/s across 10 concurrent requests (10 tok/s per user) has identical aggregate throughput to a system serving 1 request at 100 tok/s, yet provides a completely different user experience.
3. **Queue Time Concealment:** High aggregate throughput can coexist with intolerable TTFT if requests spend hundreds of milliseconds queued before scheduling.

---

## 12. Limitations of Client-Side Benchmarking

Benchmarking from a client host entails inherent physical and environmental limitations:
- **Network RTT and Jitter:** Client-side TTFT includes round-trip time between client and server, socket write buffers, and OS network stack overhead.
- **Client CPU & Event Loop Contention:** If the client host is CPU-saturated or experiences Python `asyncio` event loop delays, chunk timestamping may experience jitter.
- **Socket and Response Buffering:** Operating system socket buffers or intermediate reverse proxies (e.g., Nginx, Envoy) can buffer streaming responses unless `proxy_buffering off` is configured, creating artificial bursts of chunks.
