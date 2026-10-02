# InferLoad Real GPU & vLLM Validation Protocol

> **A rigorous engineering methodology for validating LLM inference performance against real Linux/CUDA hosts running vLLM.**

---

## 1. Objectives & Validation Principles

The purpose of real GPU validation in InferLoad is to transition from synthetic and local development environments (e.g. CPU mock servers and local Ollama) to a **production-grade accelerated inference environment**.

### Core Validation Rules:
1. **Never Fabricate GPU Results:** If a real GPU host running vLLM is not physically or over the network accessible, all preparation must be executed, documented, and verified, but benchmark completion must never be simulated or claimed without real execution.
2. **Zero Hardcoded Dependencies:** InferLoad does not mandate proprietary NVIDIA tools or host agents. GPU metadata capture is purely optional, standard-library based, and non-blocking.
3. **Causal Decoupling:** Client-side measurements observe outward black-box phenomena (latency inflection, throughput plateau). InferLoad explicitly distinguishes empirical observation from internal causal diagnosis.

---

## 2. Linux & CUDA Prerequisites

To run vLLM and achieve valid, reproducible benchmarks, the target GPU host should satisfy:

| Component | Minimum Specification | Recommended Production Specification |
| :--- | :--- | :--- |
| **Operating System** | Linux (Ubuntu 22.04 LTS or newer) | Ubuntu 22.04 LTS (Kernel 5.15+ / 6.5+) |
| **NVIDIA Driver** | >= 535.86.10 | >= 550.54.14 |
| **CUDA Toolkit** | 12.1 or 12.4 | 12.4 with latest cuDNN |
| **Python** | 3.10 – 3.12 | 3.12 in dedicated virtual environment |
| **Serving Engine** | vLLM >= 0.6.0 | Latest stable vLLM release |
| **GPU Hardware** | NVIDIA GPU with >= 16 GB VRAM (RTX 4090, RTX 3090, A10G) | Datacenter GPU (NVIDIA A100 80GB, H100 80GB, L40S) |
| **Host System Memory** | >= 32 GB DDR4/DDR5 | >= 128 GB ECC RAM |
| **Storage** | High-speed SSD | NVMe PCIe Gen4 (for fast model weight page-in) |

---

## 3. Hardware & Software Information to Record

Every GPU validation benchmark report must record the exact parameters of the execution environment:

### A. GPU Hardware Parameters
- **GPU Model:** Exact name (e.g., `NVIDIA A100-SXM4-80GB`).
- **GPU Count & Interconnect:** Single GPU, or multiple GPUs linked via NVLink / NVSwitch vs. PCIe Gen4 bus.
- **VRAM Total:** Total physical memory available per GPU.
- **Clock & Power State:** GPU boost clock frequency, power cap, and thermal status.
  ```bash
  nvidia-smi --query-gpu=name,driver_version,memory.total,power.limit,clocks.max.sm --format=csv
  ```

### B. Software & Runtime Stack
- **OS & Kernel:** `uname -a` and Linux distribution release.
- **NVIDIA Driver Version:** Recorded from `nvidia-smi`.
- **CUDA Version:** CUDA driver version and runtime version (`nvcc --version`).
- **Python Version:** Version of the Python interpreter running vLLM.
- **Inference Engine Version:** Exact vLLM version (`pip show vllm`).

### C. Model & Weights Provenance
- **Model Identifier:** Full repository ID (e.g. `meta-llama/Meta-Llama-3-8B-Instruct`).
- **Commit SHA:** Specific Git commit SHA of the weights from HuggingFace Hub.
- **Precision / Format:** `bfloat16`, `float16`, `fp8`, or quantized format (`awq`, `gptq`).

### D. vLLM Engine Launch Configuration
Document all command-line arguments passed to `vllm serve`:
- `--tensor-parallel-size` (TP)
- `--pipeline-parallel-size` (PP)
- `--gpu-memory-utilization` (fraction of VRAM dedicated to KV-cache; default 0.90)
- `--max-model-len` (context window capacity ceiling)
- `--block-size` (PagedAttention block allocation size; e.g. 16 or 32)
- `--swap-space` (CPU swap memory per GPU in GiB)
- `--enable-chunked-prefill` (whether chunked prefill is active)
- `--enforce-eager` (eager PyTorch vs. CUDA graph capture)

---

## 4. Starting and Verifying the vLLM Server

### Installation on GPU Host
```bash
pip install vllm
```

### Launching the OpenAI-Compatible API
Use the official modern CLI syntax `vllm serve <model>`. Any Hugging Face model identifier can be used; `Qwen/Qwen2.5-1.5B-Instruct` is documented as the lightweight baseline model for initial GPU validation:

```bash
vllm serve Qwen/Qwen2.5-1.5B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --gpu-memory-utilization 0.90 \
  --max-model-len 4096 \
  --dtype bfloat16
```


### Verifying Service Readiness
```bash
# Verify model registration
curl -s http://localhost:8000/v1/models | jq .

# Verify basic completion
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Meta-Llama-3-8B-Instruct",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 10
  }' | jq .
```

---

## 5. Benchmark Calibration & Methodology

InferLoad validates vLLM using the baseline configuration in `examples/vllm_gpu_baseline.yaml`:

### A. Concurrency Matrix
```yaml
sweep:
  concurrency:
    - 1
    - 2
    - 4
    - 8
```
- **Concurrency 1:** Establishes single-stream latency baseline and single-user ITL.
- **Concurrency 2 – 4:** Measures continuous batching efficiency and linear scaling regime.
- **Concurrency 8:** Exposes continuous batching contention, memory-bandwidth saturation, and tail latency inflation.

### B. Repetitions & Statistical Integrity
```yaml
  repetitions: 3
  requests_per_point: 30
```
- **3 Repetitions:** Each parameter point is evaluated in 3 independent trials. InferLoad computes the mean, sample standard deviation ($s$ with Bessel's correction $N - 1$), and Student's $t$ 95% confidence intervals across trials.
- **30 Requests Per Point:** $N = 30$ ensures sample size is sufficient for stable within-run p95 and p99 percentile estimates.
- **No Pooling:** Repetitions are never pooled into a synthetic population; within-run request distributions and across-run trial statistics remain strictly separated.

### C. Prompt & Output Controls
- **Prompt Length Stratification:**
  - **Short (~10 tokens):** Low prefill compute, immediate transition to decode.
  - **Medium (~40 tokens):** Standard conversational turn.
  - **Long (~120 tokens):** Substantial prefill compute; highlights prefill-decode interference in continuous batching.
- **Output Length Variation:**
  - `max_tokens: 64` (short generation) vs. `max_tokens: 128` (medium generation).
- **Sampling Determinism:**
  - `temperature: 0.0` ensures greedy decoding and reproducible token generation paths across repetitions.
  - `seed: 42` guarantees deterministic prompt ordering.

### D. Mandatory Warmup Procedure
```yaml
execution:
  warmup_requests: 10
```
- vLLM utilizes CUDA graph capture (`CUDAGraph`) for fixed batch size decoding. Initial requests compile kernels and initialize PagedAttention block tables.
- InferLoad executes 10 warmup requests, tags them (`is_warmup=True`), and strictly excludes them from summary metrics and percentiles.

---

## 6. What InferLoad Measures vs. What Requires Server-Side Telemetry

### What InferLoad Measures (Client-Side Black-Box Reality)
1. **Time to First Token (TTFT):** Client-perceived elapsed time until the first non-empty content chunk is decoded (`delta.content != ""`).
2. **Total Latency:** Wall time from request dispatch to final `data: [DONE]` chunk.
3. **Inter-Chunk Latency:** Time intervals between successive streaming chunks over the network.
4. **Request Throughput (RPS):** Completed requests per second.
5. **Output Tokens per Second:** Computed strictly from server usage metadata (`usage.completion_tokens`).
6. **Error Rate & Classification:** Granular tracking of HTTP 429, 500, timeouts, and malformed streams.

### What Requires Server-Side Telemetry (Causal Attribution)
Client-side measurements alone **cannot** diagnose internal hardware or engine bottlenecks:

| Client-Observed Symptom | Potential Internal Mechanism | Relevant vLLM Prometheus Metric |
| :--- | :--- | :--- |
| **TTFT Surge at higher concurrency** | Request queued waiting for free iteration slots vs. heavy prefill batching | `vllm:num_requests_waiting`, `vllm:request_queue_time_seconds`, `vllm:request_prefill_time_seconds` |
| **Throughput Plateau / Saturation** | Memory bus bandwidth limits vs. KV-cache capacity ceiling vs. active batch limit | `vllm:kv_cache_usage_perc`, `vllm:num_requests_running` |
| **Tail Latency Inflation (p95/p99)** | Request preemption / KV-cache swapping under memory pressure | `vllm:num_preemptions` |
| **Streaming Inter-chunk Jitter** | TCP socket buffering vs. engine decode step duration | `vllm:inter_token_latency_seconds`, `vllm:request_decode_time_seconds` |
| **End-to-End Latency Growth** | Combined queueing, prefill, and multi-token decode duration | `vllm:e2e_request_latency_seconds`, `vllm:time_to_first_token_seconds` |

> [!IMPORTANT]
> **Prometheus Metric Version Advisory:**
> Modern vLLM releases expose metrics such as `vllm:kv_cache_usage_perc` (percentage), `vllm:num_requests_running`, and `vllm:num_requests_waiting`. In older vLLM releases, cache utilization was published as `vllm:gpu_cache_usage_factor` (0.0–1.0 float), and preemptions under `vllm:num_preemptions_total`. Always inspect `http://<VLLM_HOST>:8000/metrics` directly to verify the exact schema active on your deployed version.

### Non-Causal Telemetry Correlation Protocol
InferLoad's server telemetry adapter (`src/inferload/server_telemetry.py`) captures point-in-time snapshots (`telemetry_before`, `telemetry_during`, `telemetry_after`).
- **Do not infer causality automatically.**
- Wording in reports must remain strictly observational:
  - *Correct:* "Client TTFT increased from 82.1 ms to 245.0 ms while server waiting-request count was observed at 4 during peak execution."
  - *Incorrect:* "Queueing caused the latency increase."

---

## 7. Capacity Analysis Protocol (SLO Evaluation)

Evaluate compliant concurrency against explicit Service Level Objectives:

```bash
inferload capacity results/experiment-vllm-gpu-baseline-<id> --slo examples/slo_vllm.yaml
```

### Strict Terminology Rules:
- InferLoad reports:
  `"Highest Observed Compliant Tested Concurrency"`
- InferLoad **never** reports or extrapolates:
  `"maximum capacity"` or `"system capacity"`.
- Compliance is evaluated exclusively at measured points ($C \in \{1, 2, 4, 8\}$).

---

## 8. vLLM GPU Validation & Reproduction Checklist

Before executing or publishing a real GPU validation benchmark, verify and document all 22 required parameters:

- [ ] **1. GPU Model:** (e.g., NVIDIA A100-SXM4-80GB, RTX 4090 24GB)
- [ ] **2. GPU Count:** (e.g., 1, 2, 4, 8)
- [ ] **3. Driver Version:** (e.g., NVIDIA 550.54.14)
- [ ] **4. CUDA Version:** (e.g., CUDA 12.4, nvcc release 12.4)
- [ ] **5. vLLM Version:** (e.g., vLLM 0.6.3)
- [ ] **6. Model Identifier:** (e.g., `Qwen/Qwen2.5-1.5B-Instruct` or `meta-llama/Meta-Llama-3-8B-Instruct`)
- [ ] **7. Model Revision:** (Hugging Face commit SHA)
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

### Execution Commands:
```bash
# 1. Verify vLLM server is responsive
curl -s http://localhost:8000/v1/models

# 2. Validate benchmark configuration
inferload validate examples/vllm_gpu_baseline.yaml

# 3. Execute controlled sweep experiment
inferload experiment examples/vllm_gpu_baseline.yaml -o results

# 4. View generated markdown analysis report
inferload report results/experiment-vllm-gpu-baseline-<timestamp>-<id>

# 5. Perform deterministic SLO capacity evaluation
inferload capacity results/experiment-vllm-gpu-baseline-<timestamp>-<id> --slo examples/slo_vllm.yaml
```


---

## 9. Artifact Integrity Verification

Verify that the experiment directory contains all required artifacts:
- `summary.json`: Contains full `environment` metadata (OS, Python, CPU, RAM, GPU information) and top-level workload fields.
- `points.csv`: Tabular per-trial records for independent verification.
- `report.md`: Markdown report detailing execution environment, sweep tables, Student's $t$ confidence intervals, and limitations.
- `raw/*.json`: Unmodified per-trial `BenchmarkResult` files.
- `plots/*.png`: Matplotlib curves for throughput, TTFT p95, total latency p95, and error rates.
