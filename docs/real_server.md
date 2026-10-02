# Benchmarking Real Inference Servers (vLLM Target Guide)

This guide documents how to benchmark a real, production-grade LLM inference server using InferLoad, with **vLLM** as the primary reference target.

---

## 1. Why vLLM is the Primary Target

vLLM is the industry standard open-source serving engine for large language models, known for:
- **PagedAttention:** Dynamic non-contiguous virtual memory allocation for KV caches, minimizing memory fragmentation.
- **Continuous (Iteration-Level) Batching:** Dynamically batches incoming requests at each token iteration rather than waiting for request-level synchronization.
- **Full OpenAI-Compatible API:** Exposes standard `/v1/chat/completions` endpoints supporting streaming Server-Sent Events (SSE).
- **High Concurrency Scalability:** Highly sensitive to concurrency levels, KV-cache pressure, and prefill/decode contention.

InferLoad measures how continuous batching and PagedAttention behave when saturated under controlled loads.

---

## 2. Server Environment Requirements

vLLM requires a high-performance compute host (typically Linux with an NVIDIA or AMD ROCm GPU).

### Recommended Server Specs
- **OS:** Linux (Ubuntu 22.04 LTS or later)
- **CUDA:** 12.1 / 12.4
- **Python:** 3.10 – 3.12
- **GPU:** NVIDIA A100 (40GB/80GB), H100, L40S, RTX 4090 (24GB), or RTX 3090 (24GB)
- **Host RAM:** 64 GB+ system memory
- **Storage:** High-speed NVMe SSD for fast model weight page-in

---

## 3. Starting the vLLM Server

### Installation
On the GPU host:
```bash
pip install vllm
```

### Launching the OpenAI-Compatible Server
Start vLLM with the modern official CLI command `vllm serve`. InferLoad supports any Hugging Face model identifier; for initial validation, a small baseline model like `Qwen/Qwen2.5-1.5B-Instruct` is recommended:

```bash
vllm serve Qwen/Qwen2.5-1.5B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --gpu-memory-utilization 0.90 \
  --max-model-len 4096 \
  --dtype bfloat16 \
  --api-key your-secret-api-key  # Optional
```

*Note: For larger GPUs or production evaluation, substitute any model identifier (e.g., `meta-llama/Meta-Llama-3-8B-Instruct`). Quantized variants can be served via `--quantization awq`, `--quantization gptq`, or `--quantization fp8`.*


### Verify Server Health
Ensure the server is running and healthy:
```bash
curl http://localhost:8000/v1/models
```

---

## 4. Configuring InferLoad for vLLM

Create or edit your workload configuration (see `examples/vllm.yaml`):

```yaml
target:
  base_url: "http://<VLLM_HOST>:8000/v1"
  api_key: "your-secret-api-key"   # Set to null or "EMPTY" if no key is required
  model: "meta-llama/Meta-Llama-3-8B-Instruct"
  timeout: 60.0

workload:
  requests: 40
  concurrency: 4
  stream: true

  prompts:
    - "Explain the concept of PagedAttention and how it mitigates memory fragmentation."
    - "What is continuous batching and how does it differ from static request batching?"
    - "Explain the difference between Time to First Token (TTFT) and decode latency in LLMs."
    - "Describe the primary memory bottlenecks during large-context transformer generation."

  max_tokens: 128
  temperature: 0.0

execution:
  warmup_requests: 3   # Crucial to initialize KV-cache blocks and CUDA graphs

export:
  output_dir: "results"
  formats:
    - "json"
    - "csv"
  prefix: "vllm-llama3-c4"
```

---

## 5. Expected Benchmark Workflow

### Step 1: Validate Configuration
Verify that the configuration file is structurally sound:
```bash
inferload validate examples/vllm.yaml
```

### Step 2: Run Baseline Benchmark
Execute a baseline benchmark at low or standard concurrency (e.g. concurrency = 2):
```bash
inferload run examples/vllm.yaml --concurrency 2 --output-dir results --run-id baseline-c2
```

### Step 3: Run High-Concurrency Stress Benchmark
Execute the candidate benchmark under higher concurrency (e.g. concurrency = 8):
```bash
inferload run examples/vllm.yaml --concurrency 8 --output-dir results --run-id candidate-c8
```

### Step 4: Compare Benchmark Runs
Compare the baseline and candidate runs to identify latency degradation, throughput inflection points, and tail degradation:
```bash
inferload compare results/vllm-llama3-c4-baseline-c2.json results/vllm-llama3-c4-candidate-c8.json
```

---

## 6. Critical Measurement Dynamics in Real LLM Servers

When benchmarking a real vLLM instance, keep the following architectural factors in mind:

### 1. Client-Side TTFT vs. Server Execution
InferLoad measures **client-observed TTFT** from the instant the request packet leaves the client socket until the first non-empty text chunk arrives. This duration incorporates:
- Client network transmission and socket buffering.
- Server TCP accept and request deserialization.
- **Server queue wait time** (if existing batches occupy GPU memory).
- GPU prefill phase execution.
- SSE stream serialization and network return.

### 2. Server Queueing & Prometheus Telemetry Correlation
OpenAI-compatible APIs do not expose internal scheduler queue states over `/v1/chat/completions`. However, vLLM exposes a Prometheus-compatible metrics endpoint (typically `http://<VLLM_HOST>:8000/metrics`).

InferLoad provides an optional telemetry adapter (`src/inferload/server_telemetry.py`) capable of capturing snapshots before, during, and after benchmark execution.

#### Documented Current vLLM Metrics:
| Metric Identifier | Metric Type | Description |
| :--- | :--- | :--- |
| `vllm:num_requests_running` | Gauge | Number of requests currently running on GPU. |
| `vllm:num_requests_waiting` | Gauge | Number of requests waiting in the iteration queue. |
| `vllm:kv_cache_usage_perc` | Gauge | Percentage of KV cache currently occupied (0–100%). |
| `vllm:time_to_first_token_seconds` | Histogram | Time from request arrival to generation of first token. |
| `vllm:inter_token_latency_seconds` | Histogram | Inter-token generation latency within decoding loop. |
| `vllm:e2e_request_latency_seconds` | Histogram | End-to-end processing time per request. |
| `vllm:request_queue_time_seconds` | Histogram | Time spent by request waiting in scheduler queue. |
| `vllm:request_prefill_time_seconds` | Histogram | Wall time spent in initial prompt prefill computation. |
| `vllm:request_decode_time_seconds` | Histogram | Wall time spent in auto-regressive decode generation. |
| `vllm:num_preemptions` | Counter | Total number of request preemptions due to cache pressure. |

> [!IMPORTANT]
> **Metric Name Version Advisory:**
> Prometheus metric names evolve across vLLM versions (e.g. `vllm:kv_cache_usage_perc` vs. legacy `vllm:gpu_cache_usage_factor`, or `vllm:num_preemptions` vs. `vllm:num_preemptions_total`). Versions may differ; always verify the active metric schema by inspecting `http://<VLLM_HOST>:8000/metrics` directly.

### 3. Inter-Chunk Latency vs. Per-Token Latency
vLLM streams tokens as they are generated. However, intermediate reverse proxies (e.g. Traefik, Nginx, Cloudflare) or TCP socket buffers can coalesce consecutive tokens into a single chunk. InferLoad faithfully measures **inter-chunk delay**. When 1 token is emitted per chunk, this equals inter-token latency (ITL).

### 4. Warmup Handling is Mandatory
vLLM initializes CUDA graphs (e.g., PyTorch CUDAGraph capture for fixed batch sizes) during initial requests. Cold requests will exhibit latencies an order of magnitude higher than warm requests. Always configure `execution.warmup_requests >= 3` to prime the engine and exclude initialization artifacts from steady-state statistics.

### 5. Closed-Loop Concurrency Model
InferLoad operates primarily as a **closed-loop system**: exactly $C$ workers make requests concurrently, and a new request is dispatched only after a prior request terminates. This measures maximum sustainable saturation capacity without causing runaway client memory exhaustion.

### 6. Hardware & Configuration Factors
Inference latencies are heavily influenced by:
- **Tensor Parallelism:** Running across multiple GPUs (`--tensor-parallel-size 2` or `4`) reduces per-GPU compute time but introduces inter-GPU NCCL communication overhead.
- **KV-Cache Allocation:** The `--gpu-memory-utilization` setting determines how many tokens can reside in memory before preemption or request rejection occurs.

---

## 7. vLLM GPU Benchmark Checklist

Whenever executing, reporting, or replicating an InferLoad benchmark on a GPU host, document all 22 required operational parameters:

- [ ] **1. GPU Model:** (e.g., NVIDIA A100-SXM4-80GB, RTX 4090 24GB)
- [ ] **2. GPU Count:** (e.g., 1, 2, 4, 8)
- [ ] **3. Driver Version:** (e.g., NVIDIA 550.54.14)
- [ ] **4. CUDA Version:** (e.g., CUDA 12.4, nvcc release 12.4)
- [ ] **5. vLLM Version:** (e.g., vLLM 0.6.3)
- [ ] **6. Model Identifier:** (e.g., `Qwen/Qwen2.5-1.5B-Instruct` or `meta-llama/Meta-Llama-3-8B-Instruct`)
- [ ] **7. Model Revision:** (Git commit SHA from Hugging Face repository)
- [ ] **8. Quantization:** (e.g., `None`, `fp8`, `awq`, `gptq`)
- [ ] **9. Dtype:** (e.g., `bfloat16`, `float16`, `auto`)
- [ ] **10. GPU Memory Utilization (`gpu-memory-utilization`):** (e.g., `0.90`)
- [ ] **11. Maximum Model Length (`max-model-len`):** (e.g., `4096`)
- [ ] **12. Maximum Number of Sequences (`max-num-seqs`):** (if explicitly set, e.g., `256`)
- [ ] **13. Tensor-Parallel Settings (`tensor-parallel-size`):** (e.g., `1` or `2`)
- [ ] **14. Data-Parallel Settings:** (if data-parallel pipeline or multi-instance serving is used)
- [ ] **15. Seed:** (e.g., `42`)
- [ ] **16. Temperature:** (e.g., `0.0` for deterministic greedy decoding)
- [ ] **17. Prompt Lengths:** (e.g., short ~10 tokens, medium ~40 tokens, long ~120 tokens)
- [ ] **18. Output Lengths (`max_tokens`):** (e.g., `64` or `128`)
- [ ] **19. Concurrency Levels Tested:** (e.g., `[1, 2, 4, 8]`)
- [ ] **20. Warmup Requests:** (e.g., `10` requests excluded from measurement)
- [ ] **21. Requests Per Point:** (e.g., `30` requests per repetition)
- [ ] **22. Repetitions:** (e.g., `3` independent runs per parameter point)

