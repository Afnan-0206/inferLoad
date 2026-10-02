# Graph Report - inferLoad  (2026-10-02)

## Corpus Check
- 51 files · ~44,258 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 3, .css 1)

## Summary
- 782 nodes · 1539 edges · 43 communities (35 shown, 8 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 232 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- RequestRecord
- cli.py
- TargetConfig
- test_web.py
- InferLoad Benchmark Methodology
- InferLoad Controlled Performance Experiments
- compare.py
- InferLoad Results Interpretation Guide
- environment.py
- run_local_benchmark.py
- BenchmarkResult
- rules/graphify.md
- workflows/graphify.md
- inferload
- Benchmarking Real Inference Servers (vLLM Target Guide)
- InferLoad — LLM Inference Load Testing & Capacity Planner
- statistics.py
- ExperimentConfig
- extract_telemetry_metrics
- app.js
- experiment.py
- InferLoad Real GPU & vLLM Validation Protocol
- 4. The 17-Step Operational Lifecycle
- test_cli.py
- runner.py
- InferLoad Benchmark Result: vLLM GPU Validation (Phase 5)
- test_config.py
- .run
- server_telemetry.py
- aggregate_benchmark_results
- 4. UI Capabilities Walkthrough
- .from_json_file
- README.md
- InferLoad Benchmark Reproducibility Guide
- SweepPointSpec
- web.py
- 2. Pre-Benchmark Environment Control
- reproducibility.md
- 11. Validated Against Local Test Server
- 6. Running a Benchmark
- 13. Empirical Capacity Analysis & SLO Compliance (Phase 4)
- 7. Web UI — Local Interactive Benchmark Console

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
- `3. Data Flow` --references--> `aggregate_benchmark_results()`  [INFERRED]
  docs/architecture.md → src/inferload/metrics.py

## Import Cycles
- None detected.

## Communities (43 total, 8 thin omitted)

### Community 0 - "RequestRecord"
Cohesion: 0.07
Nodes (5): 3. Data Flow, 9. Architecture, InferenceClient, RequestRecord, RequestSpec

### Community 1 - "cli.py"
Cohesion: 0.05
Nodes (37): 2. Component Responsibilities, analyze_capacity(), CapacityAnalysisResult, format_capacity_report(), load_slo_config(), PointCompliance, SLOConfig, capacity() (+29 more)

### Community 2 - "TargetConfig"
Cohesion: 0.06
Nodes (33): BenchmarkConfig, ExecutionConfig, TargetConfig, WorkloadConfig, BenchmarkRunner, WorkloadGenerator, make_chat_completion_json(), make_sse_stream_chunks() (+25 more)

### Community 3 - "test_web.py"
Cohesion: 0.13
Nodes (13): ExperimentJobState, JobStatus, WebBenchmarkRequest, client(), test_web_artifact_path_traversal_safety(), test_web_create_experiment_invalid_payload_rejected(), test_web_experiment_status_not_found(), test_web_health_endpoint() (+5 more)

### Community 4 - "InferLoad Benchmark Methodology"
Cohesion: 0.08
Nodes (26): 10. Why p95 and p99 Matter, 11. Why Tokens/Sec Alone is Insufficient, 12. Limitations of Client-Side Benchmarking, 1. What TTFT Actually Means in InferLoad, 2. Why First Streamed Chunk != Guaranteed Single Token, 3. What Can and Cannot Be Measured from an OpenAI-Compatible Endpoint, 4. Warmup and Connection Priming, 5. Cold Start vs. Steady State (+18 more)

### Community 5 - "InferLoad Controlled Performance Experiments"
Cohesion: 0.10
Nodes (19): 1. Closed-Loop Concurrency vs. Open-Loop Arrival Rate, 2. Parameter Sweeps and Repeated Trials, 3. Sample Size and Uncertainty Estimation, 4. Empirical Saturation Analysis, 5. Artifact Directory Structure, 6. Within-Run Request Statistics vs. Across-Run Repetition Statistics, 7. Deterministic Capacity Analysis & SLO Compliance, 8. Scientific Interpretation Checklist (+11 more)

### Community 6 - "compare.py"
Cohesion: 0.13
Nodes (10): BenchmarkComparison, _calc_diff_and_pct(), compare_benchmarks(), add_comparison(), compare_files(), MetricComparison, _build_dummy_result(), test_compare_benchmarks_deterministic_diffs() (+2 more)

### Community 7 - "InferLoad Results Interpretation Guide"
Cohesion: 0.11
Nodes (18): 1. Introduction: The Physics of Generative Inference, 2. What the Numbers Mean, 3. What the Numbers Do NOT Mean (Avoiding Overreach), 4. Client-Side vs. Server-Side Measurements, 5. Why Tail Latency Matters (The Tyranny of p95 and p99), 6. Why Throughput Flattens (The Knee of the Saturation Curve), 7. Small-N Uncertainty and Statistical Honesty, A. Time to First Token (TTFT) / First Usable Content Timing (+10 more)

### Community 8 - "environment.py"
Cohesion: 0.14
Nodes (6): capture_environment_metadata(), EnvironmentMetadata, _get_gpu_details(), _get_ram_total_gb(), get_health(), test_environment_metadata_safety()

### Community 9 - "run_local_benchmark.py"
Cohesion: 0.06
Nodes (5): main(), LocalMockServer, MockOpenAIHandler, MockServerStats, mock_server()

### Community 10 - "BenchmarkResult"
Cohesion: 0.20
Nodes (8): export_csv(), export_json(), export_results(), BenchmarkResult, _make_dummy_result(), test_export_all_results(), test_export_csv(), test_export_json()

### Community 15 - "Benchmarking Real Inference Servers (vLLM Target Guide)"
Cohesion: 0.08
Nodes (23): 1. Client-Side TTFT vs. Server Execution, 1. Why vLLM is the Primary Target, 2. Server Environment Requirements, 2. Server Queueing & Prometheus Telemetry Correlation, 3. Inter-Chunk Latency vs. Per-Token Latency, 3. Starting the vLLM Server, 4. Configuring InferLoad for vLLM, 4. Warmup Handling is Mandatory (+15 more)

### Community 16 - "InferLoad — LLM Inference Load Testing & Capacity Planner"
Cohesion: 0.14
Nodes (14): 10. Testing, 12. Controlled Performance Experiments (Phase 3), 14. Real GPU Validation & vLLM Telemetry Correlation (Phase 5 & 5.5), 15. Current Limitations, 16. Roadmap, 1. What InferLoad Is, 2. Why It Exists, 3. What It Measures (+6 more)

### Community 17 - "statistics.py"
Cohesion: 0.12
Nodes (5): generate_experiment_plots(), compute_sample_statistics(), get_student_t_critical(), SampleStatistics, test_sample_statistics_and_confidence_intervals()

### Community 18 - "ExperimentConfig"
Cohesion: 0.13
Nodes (10): ExperimentConfig, ExperimentMeta, ExperimentWorkload, SweepDefinition, validate_benchmark_quality(), expand_sweep_grid(), test_benchmark_quality_validation_rules(), test_experiment_end_to_end_mock_sweep() (+2 more)

### Community 19 - "extract_telemetry_metrics"
Cohesion: 0.20
Nodes (5): extract_telemetry_metrics(), parse_prometheus_text(), test_parse_prometheus_malformed_response(), test_parse_prometheus_text_known_and_histogram(), test_unknown_and_missing_metrics()

### Community 20 - "app.js"
Cohesion: 0.25
Nodes (14): collectFormData(), formatDate(), formatMetric(), initFormControls(), initHealth(), initHistoryDrawer(), loadHistoricalRun(), loadHistory() (+6 more)

### Community 21 - "experiment.py"
Cohesion: 0.17
Nodes (4): detect_saturation_regions(), ExperimentPointMetrics, SaturationFinding, test_saturation_detection_logic()

### Community 22 - "InferLoad Real GPU & vLLM Validation Protocol"
Cohesion: 0.07
Nodes (27): 1. Objectives & Validation Principles, 2. Linux & CUDA Prerequisites, 3. Hardware & Software Information to Record, 4. Starting and Verifying the vLLM Server, 5. Benchmark Calibration & Methodology, 6. What InferLoad Measures vs. What Requires Server-Side Telemetry, 7. Capacity Analysis Protocol (SLO Evaluation), 8. vLLM GPU Validation & Reproduction Checklist (+19 more)

### Community 23 - "4. The 17-Step Operational Lifecycle"
Cohesion: 0.07
Nodes (29): 10. Every Request Becomes a Raw Record, 11. Request Aggregation & Percentiles, 12. Repeated Experiments Measure Stability, 13. The Experiment Layer, 14. Saturation Analysis, 15. Capacity / SLO Analysis, 16. Optional Server Telemetry Correlation, 17. Structured Final Output Artifacts (+21 more)

### Community 26 - "InferLoad Benchmark Result: vLLM GPU Validation (Phase 5)"
Cohesion: 0.17
Nodes (11): 1. System Environment Audit & Hardware Assessment, 2. Configured Validation Workload Specification, 3. Cross-Environment Comparison: Local Ollama (CPU) vs. Prospective vLLM (GPU), 4. Server-Side Telemetry Correlation Plan, 5. Execution Instructions for GPU Host, 6. vLLM GPU Validation Checklist (22 Parameters), A. Target Configuration, B. Workload Matrix (+3 more)

### Community 27 - "test_config.py"
Cohesion: 0.17
Nodes (8): load_config(), test_load_config_file_not_found(), test_load_config_from_file(), test_target_config_already_has_chat_completions(), test_target_config_invalid_urls(), test_target_config_trailing_slash(), test_target_config_valid(), test_workload_config_validation()

### Community 28 - ".run"
Cohesion: 0.13
Nodes (5): ExportConfig, ExperimentRunner, ServerTelemetryCollector, test_telemetry_disabled_or_empty_url(), test_telemetry_unavailable_handling()

### Community 29 - "server_telemetry.py"
Cohesion: 0.14
Nodes (7): build_non_causal_correlation_notes(), ExperimentTelemetry, render_telemetry_correlation_markdown(), ServerTelemetrySnapshot, _build_mock_point_summary(), test_report_rendering_with_telemetry_and_non_causal_wording(), test_report_rendering_without_telemetry()

### Community 30 - "aggregate_benchmark_results"
Cohesion: 0.18
Nodes (9): aggregate_benchmark_results(), calculate_metric_stats(), calculate_percentile(), test_aggregate_benchmark_results_all_successful(), test_aggregate_benchmark_results_with_failures_and_warmup(), test_calculate_metric_stats(), test_metric_aliases_inter_chunk_and_content_timing(), test_percentile_empty_and_single() (+1 more)

### Community 31 - "4. UI Capabilities Walkthrough"
Cohesion: 0.18
Nodes (10): 1. Quick Start, 2. Architecture & Design Principles, 3. Web API Specification, 4. UI Capabilities Walkthrough, InferLoad Web UI — Local Interactive Benchmark Console, Results Presentation, SLO & Capacity Criteria, Start Web Server (+2 more)

### Community 33 - "README.md"
Cohesion: 0.25
Nodes (3): 1. ASCII Architecture Diagram, 4. Versioned Result Schema (`schema_version: "0.1"`), InferLoad Architecture

### Community 34 - "InferLoad Benchmark Reproducibility Guide"
Cohesion: 0.25
Nodes (8): 1. Overview & Core Philosophy, 3. Workload Calibration & Determinism, 4. Repetition & Statistical Integrity, 5. Step-by-Step Reproduction Checklist, A. Prompt Control & Prefill Length Homogeneity, B. Sampling Parameters & Generation Control, C. Warmup Execution, InferLoad Benchmark Reproducibility Guide

### Community 36 - "web.py"
Cohesion: 0.11
Nodes (6): ArrivalConfig, TelemetryConfig, build_experiment_config(), start_experiment(), validate_configuration(), _run_experiment_task()

### Community 37 - "2. Pre-Benchmark Environment Control"
Cohesion: 0.40
Nodes (5): 2. Pre-Benchmark Environment Control, A. Server & Host Hardware Control, B. Inference Serving Engine Configuration, C. Network & Proxy Topography, D. Client Host Integrity

### Community 38 - "reproducibility.md"
Cohesion: 0.50
Nodes (3): Step 1: Validate configuration, Step 2: Run benchmark or sweep experiment, Step 3: Run SLO capacity analysis (if applicable)

### Community 39 - "11. Validated Against Local Test Server"
Cohesion: 0.50
Nodes (4): 11. Validated Against Local Test Server, Key Verified Results, Running the Standalone End-to-End Benchmark, Verification Architecture

### Community 40 - "6. Running a Benchmark"
Cohesion: 0.50
Nodes (4): 6. Running a Benchmark, CLI Options, Execute Benchmark, Validate Configuration

### Community 41 - "13. Empirical Capacity Analysis & SLO Compliance (Phase 4)"
Cohesion: 0.67
Nodes (3): 13. Empirical Capacity Analysis & SLO Compliance (Phase 4), Deterministic Compliance Output, Run Capacity Analysis

### Community 42 - "7. Web UI — Local Interactive Benchmark Console"
Cohesion: 0.67
Nodes (3): 7. Web UI — Local Interactive Benchmark Console, Key Web UI Capabilities, Starting the Web UI

## Knowledge Gaps
- **157 isolated node(s):** `inferload`, `graphify`, `Workflow: graphify`, `1. What InferLoad Is`, `2. Why It Exists` (+152 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 393 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `InferLoad — LLM Inference Load Testing & Capacity Planner` connect `InferLoad — LLM Inference Load Testing & Capacity Planner` to `RequestRecord`, `README.md`, `11. Validated Against Local Test Server`, `6. Running a Benchmark`, `13. Empirical Capacity Analysis & SLO Compliance (Phase 4)`, `7. Web UI — Local Interactive Benchmark Console`?**
  _High betweenness centrality (0.191) - this node is a cross-community bridge._
- **Why does `9. Architecture` connect `RequestRecord` to `InferLoad — LLM Inference Load Testing & Capacity Planner`?**
  _High betweenness centrality (0.178) - this node is a cross-community bridge._
- **Why does `RequestRecord` connect `RequestRecord` to `cli.py`, `TargetConfig`, `BenchmarkResult`, `runner.py`, `aggregate_benchmark_results`?**
  _High betweenness centrality (0.131) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `TargetConfig` (e.g. with `InferenceClient` and `ExperimentConfig`) actually correct?**
  _`TargetConfig` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `BenchmarkRunner` (e.g. with `main()` and `run()`) actually correct?**
  _`BenchmarkRunner` has 25 INFERRED edges - model-reasoned connections that need verification._
- **Are the 21 inferred relationships involving `BenchmarkConfig` (e.g. with `ExperimentRunner` and `BenchmarkRunner`) actually correct?**
  _`BenchmarkConfig` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `RequestRecord` (e.g. with `2. Component Responsibilities` and `9. Architecture`) actually correct?**
  _`RequestRecord` has 9 INFERRED edges - model-reasoned connections that need verification._