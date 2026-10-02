# Graph Report - inferLoad  (2026-10-02)

## Corpus Check
- 51 files · ~47,079 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 3, .css 1)

## Summary
- 811 nodes · 1610 edges · 42 communities (31 shown, 11 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 237 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `21b2d7b3`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- RequestRecord
- test_capacity.py
- TargetConfig
- test_web.py
- InferLoad Benchmark Methodology
- InferLoad Controlled Performance Experiments
- BenchmarkResult
- InferLoad Results Interpretation Guide
- test_experiment.py
- MockOpenAIHandler
- pathlib
- rules/graphify.md
- workflows/graphify.md
- inferload
- Benchmarking Real Inference Servers (vLLM Target Guide)
- InferLoad — LLM Inference Load Testing & Capacity Planner
- statistics.py
- web.py
- extract_telemetry_metrics
- app.js
- experiment.py
- InferLoad Real GPU & vLLM Validation Protocol
- 4. The 17-Step Operational Lifecycle
- config.py
- InferLoad Benchmark Result: vLLM GPU Validation (Phase 5)
- test_config.py
- PointSummary
- server_telemetry.py
- test_server_telemetry.py
- 4. UI Capabilities Walkthrough
- .from_json_file
- cli.py
- BenchmarkRunner
- WorkloadConfig
- metrics.py
- RequestSpec
- 2. Component Responsibilities
- plots.py
- test_cli.py

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
- `2. Component Responsibilities` --references--> `compare()`  [INFERRED]
  docs/architecture.md → src/inferload/cli.py
- `2. Component Responsibilities` --references--> `experiment()`  [INFERRED]
  docs/architecture.md → src/inferload/cli.py
- `2. Component Responsibilities` --references--> `capacity()`  [INFERRED]
  docs/architecture.md → src/inferload/cli.py

## Import Cycles
- None detected.

## Communities (42 total, 11 thin omitted)

### Community 1 - "test_capacity.py"
Cohesion: 0.06
Nodes (31): analyze_capacity(), CapacityAnalysisResult, format_capacity_report(), load_slo_config(), PointCompliance, SLOConfig, capacity(), capture_environment_metadata() (+23 more)

### Community 2 - "TargetConfig"
Cohesion: 0.11
Nodes (19): TargetConfig, make_chat_completion_json(), make_sse_stream_chunks(), test_benchmark_result_reproducibility_metadata(), handler(), test_concurrency_limits(), async_handler(), test_failed_request_accounting_and_warmup_isolation() (+11 more)

### Community 3 - "test_web.py"
Cohesion: 0.16
Nodes (14): ExperimentJobState, JobStatus, client(), test_web_artifact_path_traversal_safety(), test_web_create_experiment_invalid_payload_rejected(), test_web_experiment_status_not_found(), test_web_health_endpoint(), test_web_historical_report_resolution() (+6 more)

### Community 4 - "InferLoad Benchmark Methodology"
Cohesion: 0.08
Nodes (26): 10. Why p95 and p99 Matter, 11. Why Tokens/Sec Alone is Insufficient, 12. Limitations of Client-Side Benchmarking, 1. What TTFT Actually Means in InferLoad, 2. Why First Streamed Chunk != Guaranteed Single Token, 3. What Can and Cannot Be Measured from an OpenAI-Compatible Endpoint, 4. Warmup and Connection Priming, 5. Cold Start vs. Steady State (+18 more)

### Community 5 - "InferLoad Controlled Performance Experiments"
Cohesion: 0.10
Nodes (19): 1. Closed-Loop Concurrency vs. Open-Loop Arrival Rate, 2. Parameter Sweeps and Repeated Trials, 3. Sample Size and Uncertainty Estimation, 4. Empirical Saturation Analysis, 5. Artifact Directory Structure, 6. Within-Run Request Statistics vs. Across-Run Repetition Statistics, 7. Deterministic Capacity Analysis & SLO Compliance, 8. Scientific Interpretation Checklist (+11 more)

### Community 6 - "BenchmarkResult"
Cohesion: 0.12
Nodes (12): BenchmarkComparison, _calc_diff_and_pct(), compare_benchmarks(), add_comparison(), compare_files(), format_comparison_table(), MetricComparison, BenchmarkResult (+4 more)

### Community 7 - "InferLoad Results Interpretation Guide"
Cohesion: 0.11
Nodes (18): 1. Introduction: The Physics of Generative Inference, 2. What the Numbers Mean, 3. What the Numbers Do NOT Mean (Avoiding Overreach), 4. Client-Side vs. Server-Side Measurements, 5. Why Tail Latency Matters (The Tyranny of p95 and p99), 6. Why Throughput Flattens (The Knee of the Saturation Curve), 7. Small-N Uncertainty and Statistical Honesty, A. Time to First Token (TTFT) / First Usable Content Timing (+10 more)

### Community 8 - "test_experiment.py"
Cohesion: 0.10
Nodes (3): LocalMockServer, mock_server(), test_environment_metadata_safety()

### Community 10 - "pathlib"
Cohesion: 0.17
Nodes (6): export_csv(), export_json(), _make_dummy_result(), test_export_all_results(), test_export_csv(), test_export_json()

### Community 15 - "Benchmarking Real Inference Servers (vLLM Target Guide)"
Cohesion: 0.08
Nodes (23): 1. Client-Side TTFT vs. Server Execution, 1. Why vLLM is the Primary Target, 2. Server Environment Requirements, 2. Server Queueing & Prometheus Telemetry Correlation, 3. Inter-Chunk Latency vs. Per-Token Latency, 3. Starting the vLLM Server, 4. Configuring InferLoad for vLLM, 4. Warmup Handling is Mandatory (+15 more)

### Community 16 - "InferLoad — LLM Inference Load Testing & Capacity Planner"
Cohesion: 0.04
Nodes (44): 1. Overview & Core Philosophy, 2. Pre-Benchmark Environment Control, 3. Workload Calibration & Determinism, 4. Repetition & Statistical Integrity, 5. Step-by-Step Reproduction Checklist, A. Prompt Control & Prefill Length Homogeneity, A. Server & Host Hardware Control, B. Inference Serving Engine Configuration (+36 more)

### Community 17 - "statistics.py"
Cohesion: 0.21
Nodes (4): compute_sample_statistics(), get_student_t_critical(), SampleStatistics, test_sample_statistics_and_confidence_intervals()

### Community 18 - "web.py"
Cohesion: 0.06
Nodes (19): TelemetryConfig, ExperimentConfig, ExperimentMeta, ExperimentWorkload, load_experiment_config(), SweepDefinition, validate_benchmark_quality(), expand_sweep_grid() (+11 more)

### Community 19 - "extract_telemetry_metrics"
Cohesion: 0.20
Nodes (5): extract_telemetry_metrics(), parse_prometheus_text(), test_parse_prometheus_malformed_response(), test_parse_prometheus_text_known_and_histogram(), test_unknown_and_missing_metrics()

### Community 20 - "app.js"
Cohesion: 0.12
Nodes (35): buildModelDropdown(), buildSettingsOllamaInventory(), cachedHistory, collectFormData(), discoveredModels, displayDedicatedReport(), filterFullHistoryTable(), fmt() (+27 more)

### Community 21 - "experiment.py"
Cohesion: 0.26
Nodes (4): detect_saturation_regions(), ExperimentPointMetrics, SaturationFinding, test_saturation_detection_logic()

### Community 22 - "InferLoad Real GPU & vLLM Validation Protocol"
Cohesion: 0.07
Nodes (27): 1. Objectives & Validation Principles, 2. Linux & CUDA Prerequisites, 3. Hardware & Software Information to Record, 4. Starting and Verifying the vLLM Server, 5. Benchmark Calibration & Methodology, 6. What InferLoad Measures vs. What Requires Server-Side Telemetry, 7. Capacity Analysis Protocol (SLO Evaluation), 8. vLLM GPU Validation & Reproduction Checklist (+19 more)

### Community 23 - "4. The 17-Step Operational Lifecycle"
Cohesion: 0.07
Nodes (29): 10. Every Request Becomes a Raw Record, 11. Request Aggregation & Percentiles, 12. Repeated Experiments Measure Stability, 13. The Experiment Layer, 14. Saturation Analysis, 15. Capacity / SLO Analysis, 16. Optional Server Telemetry Correlation, 17. Structured Final Output Artifacts (+21 more)

### Community 24 - "config.py"
Cohesion: 0.12
Nodes (4): ArrivalConfig, ExecutionConfig, ExportConfig, ExperimentRunner

### Community 26 - "InferLoad Benchmark Result: vLLM GPU Validation (Phase 5)"
Cohesion: 0.17
Nodes (11): 1. System Environment Audit & Hardware Assessment, 2. Configured Validation Workload Specification, 3. Cross-Environment Comparison: Local Ollama (CPU) vs. Prospective vLLM (GPU), 4. Server-Side Telemetry Correlation Plan, 5. Execution Instructions for GPU Host, 6. vLLM GPU Validation Checklist (22 Parameters), A. Target Configuration, B. Workload Matrix (+3 more)

### Community 27 - "test_config.py"
Cohesion: 0.14
Nodes (9): load_config(), test_load_config_file_not_found(), test_load_config_from_file(), test_load_vllm_gpu_baseline_config(), test_target_config_already_has_chat_completions(), test_target_config_invalid_urls(), test_target_config_trailing_slash(), test_target_config_valid() (+1 more)

### Community 28 - "PointSummary"
Cohesion: 0.29
Nodes (3): PointSummary, _build_mock_point_summary(), test_report_rendering_without_telemetry()

### Community 29 - "server_telemetry.py"
Cohesion: 0.17
Nodes (5): build_non_causal_correlation_notes(), ExperimentTelemetry, render_telemetry_correlation_markdown(), ServerTelemetrySnapshot, test_report_rendering_with_telemetry_and_non_causal_wording()

### Community 30 - "test_server_telemetry.py"
Cohesion: 0.16
Nodes (4): ServerTelemetryCollector, test_optional_telemetry_configuration_and_backward_compatibility(), test_telemetry_disabled_or_empty_url(), test_telemetry_unavailable_handling()

### Community 31 - "4. UI Capabilities Walkthrough"
Cohesion: 0.18
Nodes (10): 1. Quick Start, 2. Architecture & Design Principles, 3. Web API Specification, 4. UI Capabilities Walkthrough, InferLoad Web UI — Local Interactive Benchmark Console, Results Presentation, SLO & Capacity Criteria, Start Web Server (+2 more)

### Community 33 - "cli.py"
Cohesion: 0.12
Nodes (11): main(), compare(), experiment(), _format_metric_val(), _print_benchmark_summary(), report(), run(), validate() (+3 more)

### Community 34 - "BenchmarkRunner"
Cohesion: 0.14
Nodes (6): BenchmarkConfig, BenchmarkRunner, WorkloadGenerator, test_open_loop_constant_rate_scheduling(), test_workload_round_robin_deterministic(), test_workload_seeded_reproducibility()

### Community 35 - "WorkloadConfig"
Cohesion: 0.19
Nodes (7): WorkloadConfig, MockServerConfig, test_concurrency_bounded_verification(), test_malformed_chunk_live_stream(), test_non_streaming_timing_correctness(), test_timing_correctness_streaming(), test_warmup_exclusion_and_fault_injection()

### Community 36 - "metrics.py"
Cohesion: 0.18
Nodes (9): aggregate_benchmark_results(), calculate_metric_stats(), calculate_percentile(), test_aggregate_benchmark_results_all_successful(), test_aggregate_benchmark_results_with_failures_and_warmup(), test_calculate_metric_stats(), test_metric_aliases_inter_chunk_and_content_timing(), test_percentile_empty_and_single() (+1 more)

### Community 37 - "RequestSpec"
Cohesion: 0.31
Nodes (3): 3. Data Flow, InferenceClient, RequestSpec

### Community 38 - "2. Component Responsibilities"
Cohesion: 0.22
Nodes (6): 1. ASCII Architecture Diagram, 2. Component Responsibilities, 4. Versioned Result Schema (`schema_version: "0.1"`), InferLoad Architecture, BenchmarkSummary, MetricStats

## Knowledge Gaps
- **159 isolated node(s):** `inferload`, `discoveredModels`, `cachedHistory`, `graphify`, `Workflow: graphify` (+154 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 396 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `InferLoad — LLM Inference Load Testing & Capacity Planner` connect `InferLoad — LLM Inference Load Testing & Capacity Planner` to `RequestRecord`?**
  _High betweenness centrality (0.180) - this node is a cross-community bridge._
- **Why does `9. Architecture` connect `RequestRecord` to `InferLoad — LLM Inference Load Testing & Capacity Planner`, `RequestSpec`?**
  _High betweenness centrality (0.167) - this node is a cross-community bridge._
- **Why does `RequestRecord` connect `RequestRecord` to `BenchmarkRunner`, `metrics.py`, `RequestSpec`, `2. Component Responsibilities`, `._execute_specs_bounded`, `pathlib`, `runner.py`?**
  _High betweenness centrality (0.124) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `TargetConfig` (e.g. with `InferenceClient` and `ExperimentConfig`) actually correct?**
  _`TargetConfig` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `BenchmarkRunner` (e.g. with `main()` and `run()`) actually correct?**
  _`BenchmarkRunner` has 25 INFERRED edges - model-reasoned connections that need verification._
- **Are the 21 inferred relationships involving `BenchmarkConfig` (e.g. with `ExperimentRunner` and `BenchmarkRunner`) actually correct?**
  _`BenchmarkConfig` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `RequestRecord` (e.g. with `2. Component Responsibilities` and `9. Architecture`) actually correct?**
  _`RequestRecord` has 9 INFERRED edges - model-reasoned connections that need verification._