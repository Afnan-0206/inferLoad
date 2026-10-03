# Graph Report - inferLoad  (2026-10-03)

## Corpus Check
- 54 files · ~54,468 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 7 file(s) not represented in the graph (top: (none) 5, .css 1, .ico 1)

## Summary
- 883 nodes · 1752 edges · 50 communities (36 shown, 14 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 242 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `12797b11`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- RequestRecord
- test_capacity.py
- TargetConfig
- test_web.py
- InferLoad Benchmark Methodology
- InferLoad Controlled Performance Experiments
- .run
- InferLoad Results Interpretation Guide
- InferLoad Benchmark Reproducibility Guide
- mock_server.py
- BenchmarkResult
- rules/graphify.md
- workflows/graphify.md
- inferload
- Benchmarking Real Inference Servers (vLLM Target Guide)
- InferLoad — LLM Inference Load Testing & Capacity Planner
- environment.py
- experiment_config.py
- ExperimentTelemetry
- app.js
- Enterprise Scaling Architecture: Event Loops, Coordinated Omission & Distributed Topology
- InferLoad Real GPU & vLLM Validation Protocol
- 4. The 17-Step Operational Lifecycle
- test_sweep_grid_expansion
- InferLoad Benchmark Result: vLLM GPU Validation (Phase 5)
- test_config.py
- compare.py
- plots.py
- 4. UI Capabilities Walkthrough
- .from_json_file
- get_auth_token_from_request
- test_telemetry_disabled_or_empty_url
- 11. Validated Against Local Test Server
- 2. Pre-Benchmark Environment Control
- 6. Running a Benchmark
- ArrivalConfig
- README.md
- test_optional_telemetry_configuration_and_backward_compatibility
- test_cli.py
- create_app
- 13. Empirical Capacity Analysis & SLO Compliance (Phase 4)
- web.py
- 7. Web UI — Local Interactive Benchmark Console
- experiment.py
- vercel.json
- _run_experiment_task

## God Nodes (most connected - your core abstractions)
1. `TargetConfig` - 38 edges
2. `BenchmarkRunner` - 34 edges
3. `BenchmarkConfig` - 31 edges
4. `RequestRecord` - 28 edges
5. `create_app()` - 27 edges
6. `WorkloadConfig` - 26 edges
7. `BenchmarkResult` - 26 edges
8. `analyze_capacity()` - 21 edges
9. `ExperimentRunner` - 21 edges
10. `ExperimentConfig` - 21 edges

## Surprising Connections (you probably didn't know these)
- `Why Repetitions Matter` --references--> `BenchmarkResult`  [INFERRED]
  docs/experiments.md → src/inferload/models.py
- `9. Artifact Integrity Verification` --references--> `BenchmarkResult`  [INFERRED]
  docs/gpu-validation.md → src/inferload/models.py
- `2. Component Responsibilities` --references--> `compare()`  [INFERRED]
  docs/architecture.md → src/inferload/cli.py
- `2. Component Responsibilities` --references--> `experiment()`  [INFERRED]
  docs/architecture.md → src/inferload/cli.py
- `2. Component Responsibilities` --references--> `capacity()`  [INFERRED]
  docs/architecture.md → src/inferload/cli.py

## Import Cycles
- None detected.

## Communities (50 total, 14 thin omitted)

### Community 0 - "RequestRecord"
Cohesion: 0.06
Nodes (18): 1. ASCII Architecture Diagram, 2. Component Responsibilities, 3. Data Flow, 4. Versioned Result Schema (`schema_version: "0.1"`), InferLoad Architecture, 9. Architecture, InferenceClient, aggregate_benchmark_results() (+10 more)

### Community 1 - "test_capacity.py"
Cohesion: 0.12
Nodes (21): analyze_capacity(), CapacityAnalysisResult, format_capacity_report(), load_slo_config(), PointCompliance, SLOConfig, capacity(), ExperimentResult (+13 more)

### Community 2 - "TargetConfig"
Cohesion: 0.06
Nodes (34): main(), BenchmarkConfig, ExecutionConfig, TargetConfig, WorkloadConfig, BenchmarkRunner, WorkloadGenerator, make_chat_completion_json() (+26 more)

### Community 3 - "test_web.py"
Cohesion: 0.13
Nodes (19): ExperimentJobState, JobStatus, client(), test_web_artifact_path_traversal_safety(), test_web_auth_enforcement_when_token_configured(), test_web_auth_status_open_mode(), test_web_create_experiment_invalid_payload_rejected(), test_web_experiment_sse_stream() (+11 more)

### Community 4 - "InferLoad Benchmark Methodology"
Cohesion: 0.08
Nodes (26): 10. Why p95 and p99 Matter, 11. Why Tokens/Sec Alone is Insufficient, 12. Limitations of Client-Side Benchmarking, 1. What TTFT Actually Means in InferLoad, 2. Why First Streamed Chunk != Guaranteed Single Token, 3. What Can and Cannot Be Measured from an OpenAI-Compatible Endpoint, 4. Warmup and Connection Priming, 5. Cold Start vs. Steady State (+18 more)

### Community 5 - "InferLoad Controlled Performance Experiments"
Cohesion: 0.10
Nodes (19): 1. Closed-Loop Concurrency vs. Open-Loop Arrival Rate, 2. Parameter Sweeps and Repeated Trials, 3. Sample Size and Uncertainty Estimation, 4. Empirical Saturation Analysis, 5. Artifact Directory Structure, 6. Within-Run Request Statistics vs. Across-Run Repetition Statistics, 7. Deterministic Capacity Analysis & SLO Compliance, 8. Scientific Interpretation Checklist (+11 more)

### Community 6 - ".run"
Cohesion: 0.18
Nodes (3): ExportConfig, ExperimentRunner, ServerTelemetryCollector

### Community 7 - "InferLoad Results Interpretation Guide"
Cohesion: 0.11
Nodes (18): 1. Introduction: The Physics of Generative Inference, 2. What the Numbers Mean, 3. What the Numbers Do NOT Mean (Avoiding Overreach), 4. Client-Side vs. Server-Side Measurements, 5. Why Tail Latency Matters (The Tyranny of p95 and p99), 6. Why Throughput Flattens (The Knee of the Saturation Curve), 7. Small-N Uncertainty and Statistical Honesty, A. Time to First Token (TTFT) / First Usable Content Timing (+10 more)

### Community 8 - "InferLoad Benchmark Reproducibility Guide"
Cohesion: 0.25
Nodes (8): 1. Overview & Core Philosophy, 3. Workload Calibration & Determinism, 4. Repetition & Statistical Integrity, 5. Step-by-Step Reproduction Checklist, A. Prompt Control & Prefill Length Homogeneity, B. Sampling Parameters & Generation Control, C. Warmup Execution, InferLoad Benchmark Reproducibility Guide

### Community 9 - "mock_server.py"
Cohesion: 0.06
Nodes (4): LocalMockServer, MockOpenAIHandler, MockServerStats, mock_server()

### Community 10 - "BenchmarkResult"
Cohesion: 0.13
Nodes (10): export_csv(), export_json(), export_results(), BenchmarkResult, BenchmarkSummary, MetricStats, _make_dummy_result(), test_export_all_results() (+2 more)

### Community 15 - "Benchmarking Real Inference Servers (vLLM Target Guide)"
Cohesion: 0.08
Nodes (23): 1. Client-Side TTFT vs. Server Execution, 1. Why vLLM is the Primary Target, 2. Server Environment Requirements, 2. Server Queueing & Prometheus Telemetry Correlation, 3. Inter-Chunk Latency vs. Per-Token Latency, 3. Starting the vLLM Server, 4. Configuring InferLoad for vLLM, 4. Warmup Handling is Mandatory (+15 more)

### Community 16 - "InferLoad — LLM Inference Load Testing & Capacity Planner"
Cohesion: 0.13
Nodes (15): 10. Testing, 12. Controlled Performance Experiments (Phase 3), 14. Real GPU Validation & vLLM Telemetry Correlation (Phase 5 & 5.5), 15. Enterprise Scale & Concurrency Calibration ($c > 256$), 16. Current Limitations, 17. Roadmap, 1. What InferLoad Is, 2. Why It Exists (+7 more)

### Community 17 - "environment.py"
Cohesion: 0.12
Nodes (6): capture_environment_metadata(), EnvironmentMetadata, _get_gpu_details(), _get_ram_total_gb(), get_health(), test_environment_metadata_safety()

### Community 18 - "experiment_config.py"
Cohesion: 0.18
Nodes (9): TelemetryConfig, ExperimentConfig, ExperimentMeta, ExperimentWorkload, SweepDefinition, validate_benchmark_quality(), build_experiment_config(), test_benchmark_quality_validation_rules() (+1 more)

### Community 19 - "ExperimentTelemetry"
Cohesion: 0.09
Nodes (11): build_non_causal_correlation_notes(), ExperimentTelemetry, render_telemetry_correlation_markdown(), ServerTelemetrySnapshot, compute_sample_statistics(), get_student_t_critical(), SampleStatistics, test_sample_statistics_and_confidence_intervals() (+3 more)

### Community 20 - "app.js"
Cohesion: 0.07
Nodes (60): appendLog(), attachPromptDelete(), buildPayload(), cachedHistory, checkAuthStatus(), connectLiveExperimentStream(), cleanup(), handleStreamPayload() (+52 more)

### Community 21 - "Enterprise Scaling Architecture: Event Loops, Coordinated Omission & Distributed Topology"
Cohesion: 0.22
Nodes (9): 1. Executive Summary, 2. Client-Side Bottlenecking Mechanics at $c > 256$, 3. Concurrency Calibration Envelopes, 4. Fortune 500 Enterprise Distributed Topology Blueprint, 5. Host Operating System Tuning for Single-Instance High Load ($c \le 256$), A. The Python Global Interpreter Lock (GIL) & Event Loop Ticks, B. Coordinated Omission (The Gil Tene Problem), Components of the Distributed Architecture (+1 more)

### Community 22 - "InferLoad Real GPU & vLLM Validation Protocol"
Cohesion: 0.07
Nodes (27): 1. Objectives & Validation Principles, 2. Linux & CUDA Prerequisites, 3. Hardware & Software Information to Record, 4. Starting and Verifying the vLLM Server, 5. Benchmark Calibration & Methodology, 6. What InferLoad Measures vs. What Requires Server-Side Telemetry, 7. Capacity Analysis Protocol (SLO Evaluation), 8. vLLM GPU Validation & Reproduction Checklist (+19 more)

### Community 23 - "4. The 17-Step Operational Lifecycle"
Cohesion: 0.07
Nodes (29): 10. Every Request Becomes a Raw Record, 11. Request Aggregation & Percentiles, 12. Repeated Experiments Measure Stability, 13. The Experiment Layer, 14. Saturation Analysis, 15. Capacity / SLO Analysis, 16. Optional Server Telemetry Correlation, 17. Structured Final Output Artifacts (+21 more)

### Community 24 - "test_sweep_grid_expansion"
Cohesion: 0.25
Nodes (3): expand_sweep_grid(), SweepPointSpec, test_sweep_grid_expansion()

### Community 26 - "InferLoad Benchmark Result: vLLM GPU Validation (Phase 5)"
Cohesion: 0.17
Nodes (11): 1. System Environment Audit & Hardware Assessment, 2. Configured Validation Workload Specification, 3. Cross-Environment Comparison: Local Ollama (CPU) vs. Prospective vLLM (GPU), 4. Server-Side Telemetry Correlation Plan, 5. Execution Instructions for GPU Host, 6. vLLM GPU Validation Checklist (22 Parameters), A. Target Configuration, B. Workload Matrix (+3 more)

### Community 27 - "test_config.py"
Cohesion: 0.07
Nodes (18): experiment(), _format_metric_val(), _print_benchmark_summary(), report(), run(), validate(), version(), web() (+10 more)

### Community 29 - "compare.py"
Cohesion: 0.11
Nodes (12): compare(), BenchmarkComparison, _calc_diff_and_pct(), compare_benchmarks(), add_comparison(), compare_files(), format_comparison_table(), MetricComparison (+4 more)

### Community 31 - "4. UI Capabilities Walkthrough"
Cohesion: 0.18
Nodes (10): 1. Quick Start, 2. Architecture & Design Principles, 3. Web API Specification, 4. UI Capabilities Walkthrough, InferLoad Web UI — Local Interactive Benchmark Console, Results Presentation, SLO & Capacity Criteria, Start Web Server (+2 more)

### Community 33 - "get_auth_token_from_request"
Cohesion: 0.33
Nodes (3): get_auth_status(), get_auth_token_from_request(), require_auth()

### Community 35 - "11. Validated Against Local Test Server"
Cohesion: 0.50
Nodes (4): 11. Validated Against Local Test Server, Key Verified Results, Running the Standalone End-to-End Benchmark, Verification Architecture

### Community 36 - "2. Pre-Benchmark Environment Control"
Cohesion: 0.40
Nodes (5): 2. Pre-Benchmark Environment Control, A. Server & Host Hardware Control, B. Inference Serving Engine Configuration, C. Network & Proxy Topography, D. Client Host Integrity

### Community 37 - "6. Running a Benchmark"
Cohesion: 0.50
Nodes (4): 6. Running a Benchmark, CLI Options, Execute Benchmark, Validate Configuration

### Community 39 - "README.md"
Cohesion: 0.25
Nodes (3): Step 1: Validate configuration, Step 2: Run benchmark or sweep experiment, Step 3: Run SLO capacity analysis (if applicable)

### Community 42 - "create_app"
Cohesion: 0.06
Nodes (21): extract_telemetry_metrics(), parse_prometheus_text(), create_app(), _do_validate_configuration(), experiment_sse_stream(), event_generator(), experiment_websocket(), get_experiment_artifact() (+13 more)

### Community 43 - "13. Empirical Capacity Analysis & SLO Compliance (Phase 4)"
Cohesion: 0.67
Nodes (3): 13. Empirical Capacity Analysis & SLO Compliance (Phase 4), Deterministic Compliance Output, Run Capacity Analysis

### Community 45 - "7. Web UI — Local Interactive Benchmark Console"
Cohesion: 0.67
Nodes (3): 7. Web UI — Local Interactive Benchmark Console, Key Web UI Capabilities, Starting the Web UI

### Community 46 - "experiment.py"
Cohesion: 0.13
Nodes (4): detect_saturation_regions(), ExperimentPointMetrics, SaturationFinding, test_saturation_detection_logic()

### Community 47 - "vercel.json"
Cohesion: 0.50
Nodes (3): builds, routes, version

### Community 49 - "_run_experiment_task"
Cohesion: 0.53
Nodes (4): _broadcast_job_event(), _run_experiment_task(), _log(), on_progress()

## Knowledge Gaps
- **171 isolated node(s):** `inferload`, `discoveredModels`, `cachedHistory`, `lastRenderedPoints`, `lastRenderedOptions` (+166 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 417 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `InferLoad — LLM Inference Load Testing & Capacity Planner` connect `InferLoad — LLM Inference Load Testing & Capacity Planner` to `RequestRecord`, `11. Validated Against Local Test Server`, `6. Running a Benchmark`, `README.md`, `13. Empirical Capacity Analysis & SLO Compliance (Phase 4)`, `7. Web UI — Local Interactive Benchmark Console`?**
  _High betweenness centrality (0.174) - this node is a cross-community bridge._
- **Why does `9. Architecture` connect `RequestRecord` to `InferLoad — LLM Inference Load Testing & Capacity Planner`?**
  _High betweenness centrality (0.162) - this node is a cross-community bridge._
- **Why does `RequestRecord` connect `RequestRecord` to `cli.py`, `BenchmarkResult`, `TargetConfig`, `json`?**
  _High betweenness centrality (0.117) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `TargetConfig` (e.g. with `InferenceClient` and `ExperimentConfig`) actually correct?**
  _`TargetConfig` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `BenchmarkRunner` (e.g. with `main()` and `run()`) actually correct?**
  _`BenchmarkRunner` has 25 INFERRED edges - model-reasoned connections that need verification._
- **Are the 21 inferred relationships involving `BenchmarkConfig` (e.g. with `ExperimentRunner` and `BenchmarkRunner`) actually correct?**
  _`BenchmarkConfig` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `RequestRecord` (e.g. with `2. Component Responsibilities` and `9. Architecture`) actually correct?**
  _`RequestRecord` has 9 INFERRED edges - model-reasoned connections that need verification._