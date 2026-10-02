# InferLoad Benchmark Result: vLLM GPU Validation (Phase 5)

> **Execution Status:** **PENDING REAL GPU HOST CONNECTION**  
> **Scientific Integrity Notice:** In strict adherence to Phase 5 requirements, **zero GPU benchmarks were fabricated**. The local system environment was audited and determined to lack NVIDIA CUDA hardware and an active vLLM instance. This document establishes the exact execution specification, environment comparison, and result schema ready for execution on a real Linux/CUDA host.

---

## 1. System Environment Audit & Hardware Assessment

Before initiating benchmark execution, InferLoad probed the execution environment:

| Component | Audited Specification on Current Host | Required GPU Host Specification |
| :--- | :--- | :--- |
| **Operating System** | Windows 11 (AMD64) | Linux (Ubuntu 22.04 LTS or newer) |
| **GPU Hardware** | AMD Radeon(TM) Graphics (512 MB VRAM, integrated) | NVIDIA Datacenter GPU (e.g., A100-80GB, H100, L40S) or RTX 4090 (24GB) |
| **NVIDIA Driver** | None (`nvidia-smi` not found) | >= 550.54.14 |
| **CUDA Runtime** | None (`nvcc` not found) | CUDA 12.1 / 12.4 |
| **Target Service** | Port 8000 probed (`connection refused`) | `vLLM` listening on `http://<GPU_HOST>:8000/v1` |

**Conclusion:** Benchmark halted prior to measurement to prevent data fabrication.

---

## 2. Configured Validation Workload Specification

The validation benchmark is pre-configured in `examples/vllm_gpu_baseline.yaml`:

### A. Target Configuration
- **Endpoint:** `http://<GPU_HOST>:8000/v1`
- **Model:** `Qwen/Qwen2.5-1.5B-Instruct` (configurable to any Hugging Face model identifier, e.g. `meta-llama/Meta-Llama-3-8B-Instruct`)
- **Timeout:** 120.0 seconds

### B. Workload Matrix
- **Concurrency Levels:** 1, 2, 4, 8 (closed-loop bounded worker pool)
- **Output Limits:** 64 tokens (short output) vs. 128 tokens (medium output)
- **Prompt Length Stratification:**
  - Short prompt (~10 tokens): basic definition lookup
  - Medium prompt (~40 tokens): batching architecture explanation
  - Long prompt (~120 tokens): PagedAttention and KV-cache dynamics
- **Sampling Controls:** `temperature: 0.0` (greedy decoding), `seed: 42`
- **Execution Warmup:** 10 requests (primes CUDA graphs and PagedAttention memory pools)
- **Repetitions:** 3 independent trials per point ($N=3$, unpooled)
- **Requests Per Point:** 30 requests per repetition ($30 \times 3 = 90$ total per point)

---

## 3. Cross-Environment Comparison: Local Ollama (CPU) vs. Prospective vLLM (GPU)

InferLoad already collected empirical baseline datasets on local Ollama (`results/ollama-qwen-run-ollama-c2.json` and `results/experiment-local-capacity-sweep-20261001-200531-e3f027`).

### Critical Methodological Warning on Comparative Claims:
**It is scientifically invalid to directly claim that vLLM or Ollama is "faster" without explicitly controlling for model architecture, quantization, hardware, and serving runtime.**

| Dimension | Local Ollama Baseline | Prospective vLLM GPU Baseline |
| :--- | :--- | :--- |
| **Hardware** | AMD Ryzen CPU (integrated RAM, no discrete tensor cores) | NVIDIA Tensor Core GPU (e.g. A100 SXM4 80GB HBM2e) |
| **Memory Bandwidth** | ~40–50 GB/s (System DDR) | ~1,500–2,000 GB/s (GPU HBM) |
| **Model Evaluated** | `qwen2.5:0.5b` (~0.49 billion parameters) | `Qwen/Qwen2.5-1.5B-Instruct` (~1.5B) or `meta-llama/Meta-Llama-3-8B-Instruct` (~8.0B) |
| **Quantization** | 4-bit integer quantized (Q4_K_M GGUF) | 16-bit brain floating point (`bfloat16`) or FP8 |
| **Batching Mechanism** | Sequential CPU worker thread pool | PagedAttention continuous iteration-level batching |
| **Prefill Speed** | CPU vector extensions (AVX2/AVX-512) | Parallel Tensor Core matrix multiplication |
| **Tail Latency Sensitivity** | Low memory fragmentation risk, high CPU thread scheduling jitter | High KV-cache memory pressure sensitivity, PagedAttention block allocation |

### Expected Performance Trends Upon GPU Validation:
1. **TTFT vs. Concurrency:**
   - Under local CPU Ollama, TTFT increased by 12.1x from $C=1$ to $C=2$ due to sequential CPU execution contention.
   - Under real vLLM continuous batching on GPU, prefill parallelization should maintain sub-100ms TTFT across $C=1$ to $C=4$, with queuing inflection appearing primarily when KV-cache allocation or batch slots saturate.
2. **Decode Throughput vs. Concurrency:**
   - On CPU, generation throughput flatlined at ~1.75 req/s across $C \ge 2$ because CPU memory bus bandwidth was completely saturated by a single worker.
   - On GPU, high HBM bandwidth allows continuous batching to aggregate decode token throughput linearly across $C=1, 2, 4$ before reaching memory-bandwidth plateau.

---

## 4. Server-Side Telemetry Correlation Plan

When executing the benchmark on a GPU host with vLLM's Prometheus exporter enabled (`:8000/metrics`), InferLoad captures point-in-time snapshots (`telemetry_before`, `telemetry_during`, `telemetry_after`):

| Client Observation (InferLoad) | Correlated Server Metric | Observational Correlation Interpretation |
| :--- | :--- | :--- |
| **TTFT Growth across concurrency** | `vllm:num_requests_waiting`, `vllm:request_queue_time_seconds` | Observes whether client TTFT increase coincides with elevated waiting-request count in scheduler queue. |
| **Throughput Plateau / Saturation** | `vllm:kv_cache_usage_perc`, `vllm:num_requests_running` | Observes concurrent KV cache occupancy alongside active worker execution. |
| **Tail Latency Spikes (p95/p99)** | `vllm:num_preemptions` | Observes whether cache pressure preemptions occurred during execution. |
| **Prefill vs. Decode Timing** | `vllm:request_prefill_time_seconds`, `vllm:request_decode_time_seconds` | Observes server-side computation breakdown alongside client-observed TTFT and total latency. |

> [!IMPORTANT]
> **Non-Causal Interpretation Guideline:**
> InferLoad explicitly avoids automatic causal inference. Reports state:
> *"Client TTFT increased while server waiting-request count also increased"* rather than *"Queueing caused the latency increase"*.
> Furthermore, Prometheus metric names evolve across vLLM versions (e.g. `vllm:kv_cache_usage_perc` vs. `vllm:gpu_cache_usage_factor`). Always verify the active metric schema by inspecting `http://<VLLM_HOST>:8000/metrics`.

---

## 5. Execution Instructions for GPU Host

To execute this validation benchmark on a Linux/CUDA machine:

```bash
# 1. Start vLLM with modern CLI syntax
vllm serve Qwen/Qwen2.5-1.5B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --gpu-memory-utilization 0.90 \
  --max-model-len 4096 \
  --dtype bfloat16

# 2. Run InferLoad sweep experiment with telemetry enabled
inferload experiment examples/vllm_gpu_baseline.yaml -o results

# 3. Perform deterministic capacity compliance evaluation
inferload capacity results/experiment-vllm-gpu-baseline-<id> --slo examples/slo_vllm.yaml
```

---

## 6. vLLM GPU Validation Checklist (22 Parameters)

Document all 22 required parameters when recording GPU validation results:

- [ ] **1. GPU Model:** (e.g., NVIDIA A100-SXM4-80GB, RTX 4090 24GB)
- [ ] **2. GPU Count:** (e.g., 1, 2, 4, 8)
- [ ] **3. Driver Version:** (e.g., NVIDIA 550.54.14)
- [ ] **4. CUDA Version:** (e.g., CUDA 12.4, nvcc release 12.4)
- [ ] **5. vLLM Version:** (e.g., vLLM 0.6.3)
- [ ] **6. Model Identifier:** (e.g., `Qwen/Qwen2.5-1.5B-Instruct`)
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

