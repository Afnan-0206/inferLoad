# Graph Report - inferLoad  (2026-10-03)

## Corpus Check
- 53 files · ~50,598 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 7 file(s) not represented in the graph (top: (none) 5, .css 1, .ico 1)

## Summary
- 836 nodes · 1651 edges · 47 communities (34 shown, 13 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 237 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ad090990`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- RequestRecord
- cli.py
- BenchmarkRunner
- test_web.py
- InferLoad Benchmark Methodology
- InferLoad Controlled Performance Experiments
- ExperimentJobState
- InferLoad Results Interpretation Guide
- InferLoad Benchmark Reproducibility Guide
- run_local_benchmark.py
- BenchmarkResult
- rules/graphify.md
- workflows/graphify.md
- inferload
- Benchmarking Real Inference Servers (vLLM Target Guide)
- InferLoad — LLM Inference Load Testing & Capacity Planner
- environment.py
- experiment_config.py
- .run
- app.js
- capture_environment_metadata
- InferLoad Real GPU & vLLM Validation Protocol
- 4. The 17-Step Operational Lifecycle
- expand_sweep_grid
- runner.py
- InferLoad Benchmark Result: vLLM GPU Validation (Phase 5)
- TargetConfig
- compare.py
- InferLoad — Full Project Blueprint & Architectural Thesis
- 4. UI Capabilities Walkthrough
- .from_json_file
- 6. Critical Evaluation & Methodological Rigor
- test_open_loop_constant_rate_scheduling
- MockServerConfig
- 2. Pre-Benchmark Environment Control
- _resolve_artifacts_dir
- README.md
- reproducibility.md
- test_optional_telemetry_configuration_and_backward_compatibility
- test_cli.py
- create_app
- web.py
- experiment.py
- vercel.json
- _run_experiment_task

## God Nodes (most connected - your core abstractions)
1. `TargetConfig` - 38 edges
2. `BenchmarkRunner` - 34 edges
3. `BenchmarkConfig` - 31 edges
4. `RequestRecord` - 28 edges
5. `WorkloadConfig` - 26 edges
6. `BenchmarkResult` - 26 edges
7. `analyze_capacity()` - 21 edges
8. `ExperimentRunner` - 21 edges
9. `ExperimentConfig` - 21 edges
10. `RequestSpec` - 20 edges

## Surprising Connections (you probably didn't know these)
- `Why Repetitions Matter` --references--> `BenchmarkResult`  [INFERRED]
  docs/experiments.md → src/inferload/models.py
- `9. Artifact Integrity Verification` --references--> `BenchmarkResult`  [INFERRED]
  docs/gpu-validation.md → src/inferload/models.py
- `3. Data Flow` --references--> `load_config()`  [INFERRED]
  docs/architecture.md → src/inferload/config.py
- `3. Data Flow` --references--> `export_results()`  [INFERRED]
  docs/architecture.md → src/inferload/exporters.py
- `2. Component Responsibilities` --references--> `RequestSpec`  [INFERRED]
  docs/architecture.md → src/inferload/models.py

## Import Cycles
- None detected.

## Communities (47 total, 13 thin omitted)

### Community 0 - "RequestRecord"
Cohesion: 0.05
Nodes (17): 3. Data Flow, 9. Architecture, InferenceClient, aggregate_benchmark_results(), calculate_metric_stats(), calculate_percentile(), BenchmarkSummary, MetricStats (+9 more)

### Community 1 - "cli.py"
Cohesion: 0.06
Nodes (37): 2. Component Responsibilities, analyze_capacity(), CapacityAnalysisResult, format_capacity_report(), load_slo_config(), PointCompliance, SLOConfig, capacity() (+29 more)

### Community 2 - "BenchmarkRunner"
Cohesion: 0.13
Nodes (21): BenchmarkConfig, WorkloadConfig, BenchmarkRunner, make_chat_completion_json(), make_sse_stream_chunks(), test_benchmark_result_reproducibility_metadata(), handler(), test_concurrency_limits() (+13 more)

### Community 3 - "test_web.py"
Cohesion: 0.23
Nodes (9): client(), test_web_create_experiment_invalid_payload_rejected(), test_web_experiment_status_not_found(), test_web_health_endpoint(), test_web_historical_report_resolution(), test_web_history_endpoint(), test_web_index_serves_html(), test_web_validate_invalid_config() (+1 more)

### Community 4 - "InferLoad Benchmark Methodology"
Cohesion: 0.08
Nodes (26): 10. Why p95 and p99 Matter, 11. Why Tokens/Sec Alone is Insufficient, 12. Limitations of Client-Side Benchmarking, 1. What TTFT Actually Means in InferLoad, 2. Why First Streamed Chunk != Guaranteed Single Token, 3. What Can and Cannot Be Measured from an OpenAI-Compatible Endpoint, 4. Warmup and Connection Priming, 5. Cold Start vs. Steady State (+18 more)

### Community 5 - "InferLoad Controlled Performance Experiments"
Cohesion: 0.10
Nodes (19): 1. Closed-Loop Concurrency vs. Open-Loop Arrival Rate, 2. Parameter Sweeps and Repeated Trials, 3. Sample Size and Uncertainty Estimation, 4. Empirical Saturation Analysis, 5. Artifact Directory Structure, 6. Within-Run Request Statistics vs. Across-Run Repetition Statistics, 7. Deterministic Capacity Analysis & SLO Compliance, 8. Scientific Interpretation Checklist (+11 more)

### Community 6 - "ExperimentJobState"
Cohesion: 0.31
Nodes (5): ExperimentJobState, JobStatus, test_web_artifact_path_traversal_safety(), test_web_logs_endpoint(), test_web_report_endpoint()

### Community 7 - "InferLoad Results Interpretation Guide"
Cohesion: 0.11
Nodes (18): 1. Introduction: The Physics of Generative Inference, 2. What the Numbers Mean, 3. What the Numbers Do NOT Mean (Avoiding Overreach), 4. Client-Side vs. Server-Side Measurements, 5. Why Tail Latency Matters (The Tyranny of p95 and p99), 6. Why Throughput Flattens (The Knee of the Saturation Curve), 7. Small-N Uncertainty and Statistical Honesty, A. Time to First Token (TTFT) / First Usable Content Timing (+10 more)

### Community 8 - "InferLoad Benchmark Reproducibility Guide"
Cohesion: 0.25
Nodes (8): 1. Overview & Core Philosophy, 3. Workload Calibration & Determinism, 4. Repetition & Statistical Integrity, 5. Step-by-Step Reproduction Checklist, A. Prompt Control & Prefill Length Homogeneity, B. Sampling Parameters & Generation Control, C. Warmup Execution, InferLoad Benchmark Reproducibility Guide

### Community 9 - "run_local_benchmark.py"
Cohesion: 0.06
Nodes (5): main(), LocalMockServer, MockOpenAIHandler, MockServerStats, mock_server()

### Community 10 - "BenchmarkResult"
Cohesion: 0.24
Nodes (8): export_csv(), export_json(), export_results(), BenchmarkResult, _make_dummy_result(), test_export_all_results(), test_export_csv(), test_export_json()

### Community 15 - "Benchmarking Real Inference Servers (vLLM Target Guide)"
Cohesion: 0.08
Nodes (23): 1. Client-Side TTFT vs. Server Execution, 1. Why vLLM is the Primary Target, 2. Server Environment Requirements, 2. Server Queueing & Prometheus Telemetry Correlation, 3. Inter-Chunk Latency vs. Per-Token Latency, 3. Starting the vLLM Server, 4. Configuring InferLoad for vLLM, 4. Warmup Handling is Mandatory (+15 more)

### Community 16 - "InferLoad — LLM Inference Load Testing & Capacity Planner"
Cohesion: 0.07
Nodes (28): 10. Testing, 11. Validated Against Local Test Server, 12. Controlled Performance Experiments (Phase 3), 13. Empirical Capacity Analysis & SLO Compliance (Phase 4), 14. Real GPU Validation & vLLM Telemetry Correlation (Phase 5 & 5.5), 15. Current Limitations, 16. Roadmap, 1. What InferLoad Is (+20 more)

### Community 18 - "experiment_config.py"
Cohesion: 0.11
Nodes (13): ArrivalConfig, ExecutionConfig, ExportConfig, TelemetryConfig, ExperimentConfig, ExperimentMeta, ExperimentWorkload, SweepDefinition (+5 more)

### Community 19 - ".run"
Cohesion: 0.05
Nodes (20): detect_saturation_regions(), ExperimentPointMetrics, SaturationFinding, ExperimentRunner, build_non_causal_correlation_notes(), ExperimentTelemetry, extract_telemetry_metrics(), parse_prometheus_text() (+12 more)

### Community 20 - "app.js"
Cohesion: 0.08
Nodes (50): appendLog(), attachPromptDelete(), buildPayload(), cachedHistory, discoveredModels, downloadJsonFile(), drawInteractiveChart(), extractNormalizedPoints() (+42 more)

### Community 21 - "capture_environment_metadata"
Cohesion: 0.25
Nodes (5): capture_environment_metadata(), _get_gpu_details(), _get_ram_total_gb(), get_health(), test_environment_metadata_safety()

### Community 22 - "InferLoad Real GPU & vLLM Validation Protocol"
Cohesion: 0.07
Nodes (27): 1. Objectives & Validation Principles, 2. Linux & CUDA Prerequisites, 3. Hardware & Software Information to Record, 4. Starting and Verifying the vLLM Server, 5. Benchmark Calibration & Methodology, 6. What InferLoad Measures vs. What Requires Server-Side Telemetry, 7. Capacity Analysis Protocol (SLO Evaluation), 8. vLLM GPU Validation & Reproduction Checklist (+19 more)

### Community 23 - "4. The 17-Step Operational Lifecycle"
Cohesion: 0.11
Nodes (18): 10. Every Request Becomes a Raw Record, 11. Request Aggregation & Percentiles, 12. Repeated Experiments Measure Stability, 13. The Experiment Layer, 14. Saturation Analysis, 15. Capacity / SLO Analysis, 16. Optional Server Telemetry Correlation, 17. Structured Final Output Artifacts (+10 more)

### Community 26 - "InferLoad Benchmark Result: vLLM GPU Validation (Phase 5)"
Cohesion: 0.17
Nodes (11): 1. System Environment Audit & Hardware Assessment, 2. Configured Validation Workload Specification, 3. Cross-Environment Comparison: Local Ollama (CPU) vs. Prospective vLLM (GPU), 4. Server-Side Telemetry Correlation Plan, 5. Execution Instructions for GPU Host, 6. vLLM GPU Validation Checklist (22 Parameters), A. Target Configuration, B. Workload Matrix (+3 more)

### Community 27 - "TargetConfig"
Cohesion: 0.18
Nodes (6): TargetConfig, test_target_config_already_has_chat_completions(), test_target_config_invalid_urls(), test_target_config_trailing_slash(), test_target_config_valid(), test_workload_config_validation()

### Community 29 - "compare.py"
Cohesion: 0.13
Nodes (10): BenchmarkComparison, _calc_diff_and_pct(), compare_benchmarks(), add_comparison(), compare_files(), MetricComparison, _build_dummy_result(), test_compare_benchmarks_deterministic_diffs() (+2 more)

### Community 30 - "InferLoad — Full Project Blueprint & Architectural Thesis"
Cohesion: 0.33
Nodes (6): 1. The Core Idea & Central Thesis, 2. The Fundamental Problem: Why Generic Load Testing Fails for LLMs, 3. The Whole Working in One Flow, 5. The Entire Project in One Real Example, 7. Current Project Status & Verification Matrix, InferLoad — Full Project Blueprint & Architectural Thesis

### Community 31 - "4. UI Capabilities Walkthrough"
Cohesion: 0.18
Nodes (10): 1. Quick Start, 2. Architecture & Design Principles, 3. Web API Specification, 4. UI Capabilities Walkthrough, InferLoad Web UI — Local Interactive Benchmark Console, Results Presentation, SLO & Capacity Criteria, Start Web Server (+2 more)

### Community 33 - "6. Critical Evaluation & Methodological Rigor"
Cohesion: 0.40
Nodes (5): 6. Critical Evaluation & Methodological Rigor, Go / Kill / Pivot Decision, Weak Assumptions, What Must Be Proven First, Why This Fails (The Trivial Load Tester Trap)

### Community 35 - "MockServerConfig"
Cohesion: 0.18
Nodes (6): MockServerConfig, test_concurrency_bounded_verification(), test_malformed_chunk_live_stream(), test_non_streaming_timing_correctness(), test_timing_correctness_streaming(), test_warmup_exclusion_and_fault_injection()

### Community 36 - "2. Pre-Benchmark Environment Control"
Cohesion: 0.40
Nodes (5): 2. Pre-Benchmark Environment Control, A. Server & Host Hardware Control, B. Inference Serving Engine Configuration, C. Network & Proxy Topography, D. Client Host Integrity

### Community 37 - "_resolve_artifacts_dir"
Cohesion: 0.40
Nodes (3): get_experiment_artifact(), get_experiment_report(), _resolve_artifacts_dir()

### Community 38 - "README.md"
Cohesion: 0.25
Nodes (3): 1. ASCII Architecture Diagram, 4. Versioned Result Schema (`schema_version: "0.1"`), InferLoad Architecture

### Community 39 - "reproducibility.md"
Cohesion: 0.50
Nodes (3): Step 1: Validate configuration, Step 2: Run benchmark or sweep experiment, Step 3: Run SLO capacity analysis (if applicable)

### Community 42 - "create_app"
Cohesion: 0.17
Nodes (6): create_app(), get_historical_experiment(), list_experiment_history(), mock_chat_completions(), start_experiment(), validate_configuration()

### Community 46 - "experiment.py"
Cohesion: 0.11
Nodes (5): generate_experiment_plots(), compute_sample_statistics(), get_student_t_critical(), SampleStatistics, test_sample_statistics_and_confidence_intervals()

### Community 47 - "vercel.json"
Cohesion: 0.50
Nodes (3): builds, routes, version

### Community 49 - "_run_experiment_task"
Cohesion: 0.67
Nodes (3): _run_experiment_task(), _log(), on_progress()

## Knowledge Gaps
- **164 isolated node(s):** `inferload`, `discoveredModels`, `cachedHistory`, `lastRenderedPoints`, `lastRenderedOptions` (+159 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 404 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `InferLoad — LLM Inference Load Testing & Capacity Planner` connect `InferLoad — LLM Inference Load Testing & Capacity Planner` to `RequestRecord`, `README.md`?**
  _High betweenness centrality (0.170) - this node is a cross-community bridge._
- **Why does `9. Architecture` connect `RequestRecord` to `InferLoad — LLM Inference Load Testing & Capacity Planner`?**
  _High betweenness centrality (0.159) - this node is a cross-community bridge._
- **Why does `RequestRecord` connect `RequestRecord` to `cli.py`, `BenchmarkRunner`, `BenchmarkResult`, `runner.py`, `models.py`?**
  _High betweenness centrality (0.117) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `TargetConfig` (e.g. with `InferenceClient` and `ExperimentConfig`) actually correct?**
  _`TargetConfig` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `BenchmarkRunner` (e.g. with `main()` and `run()`) actually correct?**
  _`BenchmarkRunner` has 25 INFERRED edges - model-reasoned connections that need verification._
- **Are the 21 inferred relationships involving `BenchmarkConfig` (e.g. with `ExperimentRunner` and `BenchmarkRunner`) actually correct?**
  _`BenchmarkConfig` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `RequestRecord` (e.g. with `2. Component Responsibilities` and `9. Architecture`) actually correct?**
  _`RequestRecord` has 9 INFERRED edges - model-reasoned connections that need verification._