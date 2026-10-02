# InferLoad Benchmark Reproducibility Guide

> **A standardized protocol for achieving reproducible LLM inference benchmarks across engineers, environments, and serving engines.**

---

## 1. Overview & Core Philosophy

Benchmarking generative LLM inference is notoriously susceptible to measurement noise, configuration drift, and hidden server state. An identical command executed on two different days or on two different machines can yield wildly divergent results unless all environmental, server-side, network, and client-side variables are rigorously controlled and recorded.

InferLoad treats benchmarks as **empirical scientific experiments**. Every benchmark artifact produced by InferLoad records the full execution context to ensure that another engineer can reconstruct the exact conditions and replicate the experiment.

---

## 2. Pre-Benchmark Environment Control

Before executing an inference benchmark, verify and record the state of each layer in the stack:

### A. Server & Host Hardware Control
- [ ] **GPU Model and Count:** Record exact model names (e.g., `NVIDIA A100-SXM4-80GB`, `RTX 4090 24GB`) and interconnect topology (e.g., PCIe Gen4 vs. NVLink).
- [ ] **GPU Clock & Power State:** Verify GPU power cap and clock stability. GPUs under thermal throttling or variable boost clocks will introduce tail latency jitter.
  ```bash
  # Inspect GPU clocks, power, and thermal state on NVIDIA systems
  nvidia-smi --query-gpu=timestamp,name,pstate,temperature.gpu,utilization.gpu,utilization.memory,memory.total,memory.free,clocks.current.graphics,clocks.current.memory --format=csv -l 1
  ```
- [ ] **Host CPU & Memory:** Ensure sufficient CPU cores and RAM to prevent server host swapping. Record CPU architecture and thread counts.
- [ ] **Background Process Isolation:** Ensure no competing background processes (training runs, data ingestion, OS updates, other containers) share the CPU cores or GPU memory.

### B. Inference Serving Engine Configuration
- [ ] **Exact Model Revision:** Record the model identifier and precise HuggingFace commit hash (SHA) or weights checksum. Model weights are frequently updated or re-quantized.
- [ ] **Engine & Version:** Document the exact server engine version (e.g., `vLLM v0.6.2`, `TensorRT-LLM v0.12.0`, `Ollama 0.3.12`).
- [ ] **Engine Serving Arguments:** Document critical server launch arguments:
  - `--tensor-parallel-size` (TP)
  - `--pipeline-parallel-size` (PP)
  - `--gpu-memory-utilization` (determines KV-cache capacity)
  - `--max-model-len` (context window allocation ceiling)
  - `--block-size` / `--chunked-prefill` (chunked prefill and paging policies)
  - `--quantization` (e.g., `awq`, `gptq`, `fp8`, or unquantized `bfloat16`)

### C. Network & Proxy Topography
- [ ] **Network Distance:** Prefer colocated benchmarking (same LAN or localhost loopback). Avoid benchmarking across public Internet or congested VPNs where WAN packet jitter pollutes tail percentiles.
- [ ] **Proxy Buffering:** If benchmarking behind Nginx, Envoy, or Traefik, ensure streaming chunk buffering is explicitly disabled (`proxy_buffering off;`). Proxy buffering turns smooth streaming token generation into artificial delayed chunk bursts.
- [ ] **Keep-Alive & Connection Pooling:** Ensure HTTP keep-alive is enabled on intermediate gateways to avoid spurious TCP connection setup overhead during steady-state measurements.

### D. Client Host Integrity
- [ ] **Python Environment:** Use Python 3.12+ in an isolated virtual environment (`.venv`).
- [ ] **Client CPU Load:** Ensure the client machine executing InferLoad is not CPU-starved. Python `asyncio` event loop scheduling delays can introduce artificial latency measurement artifacts if the client host is running at 100% CPU utilization.

---

## 3. Workload Calibration & Determinism

To ensure identical load is generated across runs:

### A. Prompt Control & Prefill Length Homogeneity
- TTFT is compute-bound during the prefill phase and scales with prompt token length.
- Use explicit, standardized prompt lists (`prompts: [...]`) or named prompt profiles.
- Avoid mixing a 20-token prompt with a 4,000-token prompt in the same unstratified sweep point, as doing so inflates tail latency variance for reasons unrelated to server saturation.

### B. Sampling Parameters & Generation Control
- [ ] **Greedy Decoding:** Set `temperature: 0.0` to eliminate non-deterministic sampling variance and ensure identical token paths are generated for identical prompts.
- [ ] **Max Tokens Ceiling:** Set an explicit `max_tokens` (e.g. `128`) so that requests do not stop arbitrarily based on model output quirks.
- [ ] **Seed:** Set `seed: <int>` when using probabilistic prompt selection.

### C. Warmup Execution
- Always execute and discard at least **2 to 5 warmup requests** before recording benchmark metrics (`execution.warmup_requests: 3`).
- Warmup primes:
  - Client and server TCP connection pools and TLS handshakes.
  - CUDA graph captures and kernel compilation.
  - Initial KV-cache block allocation and PagedAttention tables.
- InferLoad automatically marks warmup requests (`is_warmup=True`) and strictly excludes them from summary statistics, percentiles, and throughput calculations.

---

## 4. Repetition & Statistical Integrity

Single-trial benchmarks are an anti-pattern. Transient network latency spikes, garbage collection pauses, or server-side thread preemption can distort p95 and p99 metrics.

1. **Configure Repetitions:** Configure `sweep.repetitions: 3` (or higher) in your experiment configuration.
2. **Never Pool Across Trials:** InferLoad computes request percentiles within each trial, then computes sample statistics ($\bar{x}$, $s$, 95% CI) across the independent trials.
3. **Report Uncertainty:** Always publish sample standard deviations and Student's $t$ confidence intervals alongside means.

---

## 5. Step-by-Step Reproduction Checklist

Use this checklist when publishing or verifying an InferLoad benchmark:

```markdown
### InferLoad Benchmark Reproduction Record (22-Parameter GPU Checklist)

#### 1. Hardware & Driver Environment
- [ ] 1. GPU Model: ___________________________________ (e.g. NVIDIA A100-SXM4-80GB)
- [ ] 2. GPU Count: ___________________________________ (e.g. 1, 2, 4, 8)
- [ ] 3. Driver Version: ______________________________ (e.g. 550.54.14)
- [ ] 4. CUDA Version: ________________________________ (e.g. CUDA 12.4, nvcc release 12.4)

#### 2. Serving Engine & Model Specification
- [ ] 5. vLLM Version: ________________________________ (e.g. vLLM 0.6.3)
- [ ] 6. Model Identifier: ____________________________ (e.g. Qwen/Qwen2.5-1.5B-Instruct)
- [ ] 7. Model Revision: ______________________________ (Hugging Face commit SHA)
- [ ] 8. Quantization: ________________________________ (None, fp8, awq, gptq)
- [ ] 9. Dtype: _______________________________________ (bfloat16, float16, auto)
- [ ] 10. GPU Memory Utilization: _____________________ (e.g. 0.90)
- [ ] 11. Maximum Model Length: _______________________ (e.g. 4096)
- [ ] 12. Maximum Number of Sequences: ________________ (max-num-seqs if set)
- [ ] 13. Tensor-Parallel Settings: ___________________ (tensor-parallel-size)
- [ ] 14. Data-Parallel Settings: _____________________ (if pipeline or multi-instance serving is used)

#### 3. InferLoad Workload Calibration
- [ ] 15. Seed: _______________________________________ (e.g. 42)
- [ ] 16. Temperature: ________________________________ (e.g. 0.0 for greedy decoding)
- [ ] 17. Prompt Lengths: _____________________________ (short, medium, long profiles)
- [ ] 18. Output Lengths (max_tokens): ________________ (e.g. 64, 128)
- [ ] 19. Concurrency Levels Tested: __________________ (e.g. 1, 2, 4, 8)
- [ ] 20. Warmup Requests: ____________________________ (e.g. 10 requests excluded)
- [ ] 21. Requests Per Point: _________________________ (e.g. 30 requests per repetition)
- [ ] 22. Repetitions: ________________________________ (e.g. 3 independent runs per point)

#### 4. Execution Commands
```bash
# Step 1: Validate configuration
inferload validate <config.yaml>

# Step 2: Run benchmark or sweep experiment
inferload experiment <experiment.yaml>

# Step 3: Run SLO capacity analysis (if applicable)
inferload capacity results/<experiment-dir> --slo <slo.yaml>
```

#### 5. Artifact Verification
- [ ] `summary.json` contains complete `environment` metadata block and telemetry if enabled.
- [ ] `points.csv` contains per-trial metrics without missing columns.
- [ ] `report.md` documents TTFT, latency, throughput, error rates, and non-causal telemetry observations.
- [ ] Raw request JSON files preserved under `raw/`.


---

## 6. How to Re-Run from an Existing Artifact

When given an existing experiment artifact directory (`results/experiment-<name>-<id>`):

1. **Inspect `summary.json`:** Open `summary.json` and review the `environment`, `target`, `workload_config`, `execution_config`, and `sweep_config` sections.
2. **Verify Server Match:** Confirm that the target server matches the model, endpoint, and engine specifications recorded in `summary.json`.
3. **Re-Execute the Sweep:**
   ```bash
   inferload experiment <original-config-or-reconstructed-config>.yaml -o results/reproduction-run
   ```
4. **Compare Directly:** Compare the original trial with the reproduction trial using InferLoad's comparison tool:
   ```bash
   inferload compare results/<original>/raw/c1-m128-rep1.json results/reproduction-run/raw/c1-m128-rep1.json
   ```
