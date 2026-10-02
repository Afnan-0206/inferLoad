# InferLoad Controlled Performance Experiments

This document explains the experimental methodology, statistical models, arrival mechanics, and saturation analysis in InferLoad Phase 3.

---

## 1. Closed-Loop Concurrency vs. Open-Loop Arrival Rate

InferLoad supports two distinct workload generation modes:

### Closed-Loop Concurrency (Default)
In a closed-loop system, a fixed pool of $C$ workers is maintained:
- Each worker picks a request, awaits full completion (or timeout/failure), and only then dispatches the next request.
- **Physical property:** The arrival rate is **load-dependent**. If server latency degrades, the request dispatch rate automatically decelerates, preventing infinite queue growth.
- **Primary use:** Establishing the maximum sustainable throughput, capacity limits, and resource saturation ceilings.

### Open-Loop Arrival Rate (Experimental)
In an open-loop system, requests are scheduled according to an independent arrival process:
- Configured via `arrival.mode = "rate"` and `arrival.requests_per_second = R`.
- Dispatch occurs at deterministic intervals:
  $$\Delta t = \frac{1}{R}$$
  Request $k$ launches at $t_k = t_0 + k \cdot \Delta t$ regardless of whether prior requests have completed.
- **Physical property:** The arrival rate is **load-independent**. If the server's processing rate drops below $R$, in-flight requests accumulate, latency climbs unbounded, and server queueing or socket drops occur.
- **Primary use:** Simulating real-world uncoordinated user arrivals and observing degradation when arrival rates exceed capacity.

---

## 2. Parameter Sweeps and Repeated Trials

Single benchmark runs are subject to transient noise (garbage collection, CPU frequency scaling, network jitter). InferLoad expands sweeps into reproducible parameter grids:

$$\text{Trials} = |\text{concurrency}| \times |\text{max\_tokens}| \times |\text{prompt\_profiles}| \times \text{repetitions}$$

### Why Repetitions Matter
Measuring a single point once does not establish statistical confidence. InferLoad repeats each parameter point $N$ times (`repetitions: N`), preserving each trial's raw `BenchmarkResult` in `raw/<run_id>.json`.

---

## 3. Sample Size and Uncertainty Estimation

When reporting metrics across repeated trials ($N$ repetitions), InferLoad calculates:

1. **Mean ($\bar{x}$):**
   $$\bar{x} = \frac{1}{N} \sum_{i=1}^N x_i$$
2. **Sample Standard Deviation ($s$):**
   $$s = \sqrt{\frac{1}{N - 1} \sum_{i=1}^N (x_i - \bar{x})^2}$$
   Using Bessel's correction ($N - 1$) to provide an unbiased estimator.
3. **Coefficient of Variation ($CV$):**
   $$CV = \frac{s}{|\bar{x}|} \times 100\%$$
   Measures measurement stability and relative dispersion across trials.
4. **95% Confidence Interval ($CI_{95\%}$):**
   For small samples ($N < 30$), the normal distribution underestimates uncertainty. InferLoad uses **Student's $t$-distribution** with $\nu = N - 1$ degrees of freedom:
   $$\text{Margin of Error} = t_{0.025, \nu} \cdot \frac{s}{\sqrt{N}}$$
   $$CI_{95\%} = [\bar{x} - \text{Margin}, \bar{x} + \text{Margin}]$$

### Statistical Honesty
With $N = 3$, $t_{\text{crit}} = 4.303$. A wide confidence interval truthfully reflects sample uncertainty rather than projecting false precision.

---

## 4. Empirical Saturation Analysis

InferLoad evaluates parameter transitions to identify performance inflection points:

### Detection Criteria
Between adjacent load points $L_i$ and $L_{i+1}$ (where load increase $\ge 40\%$):
- Throughput change: $\Delta \text{RPS} = \frac{\text{RPS}_{i+1} - \text{RPS}_i}{\text{RPS}_i} \le 15\%$
- Tail latency growth: $\Delta \text{Lat}_{p95} = \frac{\text{Lat}_{p95, i+1} - \text{Lat}_{p95, i}}{\text{Lat}_{p95, i}} \ge 30\%$

When both conditions hold, InferLoad flags:
> **Observed saturation-like behavior:** throughput changed marginally while p95 latency surged significantly.

### Non-Causal Attribution Principle
Client-side benchmarking observes symptoms, not causes. InferLoad **strictly refrains** from asserting internal causes (e.g. "GPU saturated" or "KV-cache full") unless confirmed by direct server telemetry.

---

## 5. Artifact Directory Structure

Each experiment invocation produces an isolated, versioned directory under `results/`:

```
results/
  experiment-<name>-<timestamp>-<id>/
    summary.json   # Machine-readable experiment schema (v0.2)
    points.csv     # Tabular trial-by-trial metrics
    report.md      # Human-readable markdown analysis report
    raw/           # Unmodified individual trial JSON results
      c1-m64-rep1.json
      c1-m64-rep2.json
      c2-m64-rep1.json
      ...
    plots/         # Static matplotlib curves (DPI 150)
      concurrency_vs_ttft_p95.png
      concurrency_vs_throughput.png
      concurrency_vs_error_rate.png
      concurrency_vs_total_latency_p95.png
```

---

## 6. Within-Run Request Statistics vs. Across-Run Repetition Statistics

A fundamental rule of scientific benchmarking is the strict separation between within-run request statistics and across-run repetition statistics.

### Never Pool Requests Across Repetitions
InferLoad **never pools** all individual requests from different repetitions into a single synthetic sample to calculate variance or confidence intervals.

- **Within-Run Request Statistics:**
  During an individual trial $k$, $M$ requests are dispatched. InferLoad measures TTFT, ITL, and total latency across these $M$ requests, calculating within-run percentiles ($p50, p95, p99$) and throughput.
- **Across-Run Repetition Statistics:**
  When a sweep point is repeated $N$ times, InferLoad obtains $N$ distinct observations of each summary metric (e.g. $\{ \text{TTFT}_{p95}^{(1)}, \dots, \text{TTFT}_{p95}^{(N)} \}$). Sample mean, sample standard deviation ($s$), and Student's $t$ confidence intervals are calculated across these $N$ observations.

### Why Pooling Is Methodologically Flawed
1. **Violation of Independence:** Requests within a single trial share temporal correlation, server cache state, and local socket state. Pooling treats them as $N \times M$ independent observations, falsely deflating standard error by $\sqrt{M}$.
2. **Masking System Non-Stationarity:** Pooling obscures trial-to-trial drift, memory fragmentation, and background OS scheduling contention.

---

## 7. Deterministic Capacity Analysis & SLO Compliance

InferLoad provides empirical capacity analysis evaluated against user-defined Service Level Objectives (SLOs):

```yaml
slo:
  max_ttft_p95_ms: 1000.0
  max_total_latency_p95_ms: 2500.0
  max_error_rate_pct: 1.0
  min_throughput_req_per_sec: 1.0
```

### CLI Execution
```bash
inferload capacity results/experiment-<id> --slo examples/slo_local.yaml
```

### Strict Interpretation Rule
- **No Extrapolation:** The capacity analyzer evaluates only observed, measured points. It does not fit an unverified curve or extrapolate beyond tested values.
- **Cautious Terminology:** InferLoad reports the **"highest observed compliant tested concurrency"**, never speculative terms like "maximum system capacity".

---

## 8. Scientific Interpretation Checklist

When reviewing experiment results:
- [ ] Are warmup requests excluded from steady-state statistics?
- [ ] Are within-run request distributions kept separate from across-run repetition statistics?
- [ ] Is sample size ($N$) large enough to justify the precision claimed?
- [ ] Are tail latencies (p95, p99) reported alongside throughput?
- [ ] Is host environment metadata (OS, CPU, RAM, GPU availability) documented?
- [ ] Are causal claims avoided unless verified with server-side metrics?
- [ ] Is capacity scoped strictly to tested configurations without extrapolation?
