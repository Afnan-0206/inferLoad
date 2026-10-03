# Graph Report - inferLoad  (2026-10-03)

## Corpus Check
- 53 files · ~50,493 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 6 file(s) not represented in the graph (top: (none) 5, .css 1)

## Summary
- 833 nodes · 1649 edges · 50 communities (36 shown, 14 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 237 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `77e15530`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- RequestRecord
- capacity.py
- BenchmarkRunner
- test_web.py
- InferLoad Benchmark Methodology
- InferLoad Controlled Performance Experiments
- BenchmarkComparison
- InferLoad Results Interpretation Guide
- cli.py
- mock_server.py
- BenchmarkResult
- rules/graphify.md
- workflows/graphify.md
- inferload
- Benchmarking Real Inference Servers (vLLM Target Guide)
- InferLoad — LLM Inference Load Testing & Capacity Planner
- environment.py
- ExperimentConfig
- extract_telemetry_metrics
- app.js
- ExperimentPointMetrics
- InferLoad Real GPU & vLLM Validation Protocol
- 4. The 17-Step Operational Lifecycle
- .run
- InferLoad Benchmark Result: vLLM GPU Validation (Phase 5)
- TargetConfig
- config.py
- test_compare.py
- ServerTelemetryCollector
- 4. UI Capabilities Walkthrough
- .from_json_file
- load_experiment_config
- BenchmarkConfig
- MockServerConfig
- metrics.py
- RequestSpec
- 2. Component Responsibilities
- test_capacity.py
- test_cli.py
- create_app
- web.py
- ExperimentTelemetry
- SampleStatistics
- vercel.json
- compute_sample_statistics
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
- `2. Component Responsibilities` --references--> `compare()`  [INFERRED]
  docs/architecture.md → src/inferload/cli.py
- `2. Component Responsibilities` --references--> `experiment()`  [INFERRED]
  docs/architecture.md → src/inferload/cli.py
- `2. Component Responsibilities` --references--> `capacity()`  [INFERRED]
  docs/architecture.md → src/inferload/cli.py

## Import Cycles
- None detected.

## Communities (50 total, 14 thin omitted)

### Community 1 - "capacity.py"
Cohesion: 0.13
Nodes (7): CapacityAnalysisResult, format_capacity_report(), load_slo_config(), PointCompliance, capacity(), ExperimentResult, PointSummary

### Community 2 - "BenchmarkRunner"
Cohesion: 0.12
Nodes (20): WorkloadConfig, BenchmarkRunner, make_chat_completion_json(), make_sse_stream_chunks(), test_benchmark_result_reproducibility_metadata(), handler(), test_concurrency_limits(), async_handler() (+12 more)

### Community 3 - "test_web.py"
Cohesion: 0.16
Nodes (14): ExperimentJobState, JobStatus, client(), test_web_artifact_path_traversal_safety(), test_web_create_experiment_invalid_payload_rejected(), test_web_experiment_status_not_found(), test_web_health_endpoint(), test_web_historical_report_resolution() (+6 more)

### Community 4 - "InferLoad Benchmark Methodology"
Cohesion: 0.04
Nodes (42): 10. Why p95 and p99 Matter, 11. Why Tokens/Sec Alone is Insufficient, 12. Limitations of Client-Side Benchmarking, 1. What TTFT Actually Means in InferLoad, 2. Why First Streamed Chunk != Guaranteed Single Token, 3. What Can and Cannot Be Measured from an OpenAI-Compatible Endpoint, 4. Warmup and Connection Priming, 5. Cold Start vs. Steady State (+34 more)

### Community 5 - "InferLoad Controlled Performance Experiments"
Cohesion: 0.10
Nodes (19): 1. Closed-Loop Concurrency vs. Open-Loop Arrival Rate, 2. Parameter Sweeps and Repeated Trials, 3. Sample Size and Uncertainty Estimation, 4. Empirical Saturation Analysis, 5. Artifact Directory Structure, 6. Within-Run Request Statistics vs. Across-Run Repetition Statistics, 7. Deterministic Capacity Analysis & SLO Compliance, 8. Scientific Interpretation Checklist (+11 more)

### Community 6 - "BenchmarkComparison"
Cohesion: 0.18
Nodes (5): BenchmarkComparison, _calc_diff_and_pct(), add_comparison(), format_comparison_table(), MetricComparison

### Community 7 - "InferLoad Results Interpretation Guide"
Cohesion: 0.11
Nodes (18): 1. Introduction: The Physics of Generative Inference, 2. What the Numbers Mean, 3. What the Numbers Do NOT Mean (Avoiding Overreach), 4. Client-Side vs. Server-Side Measurements, 5. Why Tail Latency Matters (The Tyranny of p95 and p99), 6. Why Throughput Flattens (The Knee of the Saturation Curve), 7. Small-N Uncertainty and Statistical Honesty, A. Time to First Token (TTFT) / First Usable Content Timing (+10 more)

### Community 8 - "cli.py"
Cohesion: 0.14
Nodes (7): main(), _format_metric_val(), _print_benchmark_summary(), run(), load_config(), test_load_config_file_not_found(), test_load_config_from_file()

### Community 9 - "mock_server.py"
Cohesion: 0.06
Nodes (4): LocalMockServer, MockOpenAIHandler, MockServerStats, mock_server()

### Community 10 - "BenchmarkResult"
Cohesion: 0.20
Nodes (8): export_csv(), export_json(), export_results(), BenchmarkResult, _make_dummy_result(), test_export_all_results(), test_export_csv(), test_export_json()

### Community 15 - "Benchmarking Real Inference Servers (vLLM Target Guide)"
Cohesion: 0.08
Nodes (23): 1. Client-Side TTFT vs. Server Execution, 1. Why vLLM is the Primary Target, 2. Server Environment Requirements, 2. Server Queueing & Prometheus Telemetry Correlation, 3. Inter-Chunk Latency vs. Per-Token Latency, 3. Starting the vLLM Server, 4. Configuring InferLoad for vLLM, 4. Warmup Handling is Mandatory (+15 more)

### Community 16 - "InferLoad — LLM Inference Load Testing & Capacity Planner"
Cohesion: 0.07
Nodes (28): 10. Testing, 11. Validated Against Local Test Server, 12. Controlled Performance Experiments (Phase 3), 13. Empirical Capacity Analysis & SLO Compliance (Phase 4), 14. Real GPU Validation & vLLM Telemetry Correlation (Phase 5 & 5.5), 15. Current Limitations, 16. Roadmap, 1. What InferLoad Is (+20 more)

### Community 17 - "environment.py"
Cohesion: 0.15
Nodes (6): capture_environment_metadata(), EnvironmentMetadata, _get_gpu_details(), _get_ram_total_gb(), get_health(), test_environment_metadata_safety()

### Community 18 - "ExperimentConfig"
Cohesion: 0.09
Nodes (12): ExperimentConfig, ExperimentMeta, ExperimentWorkload, SweepDefinition, validate_benchmark_quality(), expand_sweep_grid(), SweepPointSpec, build_experiment_config() (+4 more)

### Community 19 - "extract_telemetry_metrics"
Cohesion: 0.16
Nodes (6): extract_telemetry_metrics(), parse_prometheus_text(), ServerTelemetrySnapshot, test_parse_prometheus_malformed_response(), test_parse_prometheus_text_known_and_histogram(), test_unknown_and_missing_metrics()

### Community 20 - "app.js"
Cohesion: 0.08
Nodes (50): appendLog(), attachPromptDelete(), buildPayload(), cachedHistory, discoveredModels, downloadJsonFile(), drawInteractiveChart(), extractNormalizedPoints() (+42 more)

### Community 21 - "ExperimentPointMetrics"
Cohesion: 0.32
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

### Community 27 - "TargetConfig"
Cohesion: 0.16
Nodes (6): TargetConfig, test_target_config_already_has_chat_completions(), test_target_config_invalid_urls(), test_target_config_trailing_slash(), test_target_config_valid(), test_workload_config_validation()

### Community 28 - "config.py"
Cohesion: 0.21
Nodes (3): ExecutionConfig, ExportConfig, TelemetryConfig

### Community 29 - "test_compare.py"
Cohesion: 0.24
Nodes (6): compare_benchmarks(), compare_files(), _build_dummy_result(), test_compare_benchmarks_deterministic_diffs(), test_compare_files_and_cli(), test_compare_with_zero_and_none_values()

### Community 30 - "ServerTelemetryCollector"
Cohesion: 0.25
Nodes (3): ServerTelemetryCollector, test_telemetry_disabled_or_empty_url(), test_telemetry_unavailable_handling()

### Community 31 - "4. UI Capabilities Walkthrough"
Cohesion: 0.18
Nodes (10): 1. Quick Start, 2. Architecture & Design Principles, 3. Web API Specification, 4. UI Capabilities Walkthrough, InferLoad Web UI — Local Interactive Benchmark Console, Results Presentation, SLO & Capacity Criteria, Start Web Server (+2 more)

### Community 33 - "load_experiment_config"
Cohesion: 0.13
Nodes (8): compare(), experiment(), report(), validate(), version(), web(), load_experiment_config(), test_load_vllm_gpu_baseline_config()

### Community 34 - "BenchmarkConfig"
Cohesion: 0.20
Nodes (5): BenchmarkConfig, WorkloadGenerator, test_open_loop_constant_rate_scheduling(), test_workload_round_robin_deterministic(), test_workload_seeded_reproducibility()

### Community 35 - "MockServerConfig"
Cohesion: 0.18
Nodes (6): MockServerConfig, test_concurrency_bounded_verification(), test_malformed_chunk_live_stream(), test_non_streaming_timing_correctness(), test_timing_correctness_streaming(), test_warmup_exclusion_and_fault_injection()

### Community 36 - "metrics.py"
Cohesion: 0.18
Nodes (9): aggregate_benchmark_results(), calculate_metric_stats(), calculate_percentile(), test_aggregate_benchmark_results_all_successful(), test_aggregate_benchmark_results_with_failures_and_warmup(), test_calculate_metric_stats(), test_metric_aliases_inter_chunk_and_content_timing(), test_percentile_empty_and_single() (+1 more)

### Community 37 - "RequestSpec"
Cohesion: 0.31
Nodes (3): 3. Data Flow, InferenceClient, RequestSpec

### Community 38 - "2. Component Responsibilities"
Cohesion: 0.22
Nodes (6): 1. ASCII Architecture Diagram, 2. Component Responsibilities, 4. Versioned Result Schema (`schema_version: "0.1"`), InferLoad Architecture, BenchmarkSummary, MetricStats

### Community 40 - "test_capacity.py"
Cohesion: 0.30
Nodes (14): analyze_capacity(), SLOConfig, _dummy_stat(), _make_dummy_experiment(), _make_dummy_point(), test_all_slos_satisfied(), test_cli_capacity_command(), test_error_rate_violation() (+6 more)

### Community 42 - "create_app"
Cohesion: 0.13
Nodes (9): create_app(), get_experiment_artifact(), get_experiment_report(), get_historical_experiment(), list_experiment_history(), mock_chat_completions(), start_experiment(), validate_configuration() (+1 more)

### Community 45 - "ExperimentTelemetry"
Cohesion: 0.19
Nodes (6): build_non_causal_correlation_notes(), ExperimentTelemetry, render_telemetry_correlation_markdown(), _build_mock_point_summary(), test_report_rendering_with_telemetry_and_non_causal_wording(), test_report_rendering_without_telemetry()

### Community 48 - "compute_sample_statistics"
Cohesion: 0.50
Nodes (3): compute_sample_statistics(), get_student_t_critical(), test_sample_statistics_and_confidence_intervals()

### Community 49 - "_run_experiment_task"
Cohesion: 0.67
Nodes (3): _run_experiment_task(), _log(), on_progress()

## Knowledge Gaps
- **162 isolated node(s):** `inferload`, `discoveredModels`, `cachedHistory`, `lastRenderedPoints`, `lastRenderedOptions` (+157 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 402 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `InferLoad — LLM Inference Load Testing & Capacity Planner` connect `InferLoad — LLM Inference Load Testing & Capacity Planner` to `RequestRecord`, `InferLoad Benchmark Methodology`?**
  _High betweenness centrality (0.171) - this node is a cross-community bridge._
- **Why does `9. Architecture` connect `RequestRecord` to `InferLoad — LLM Inference Load Testing & Capacity Planner`, `RequestSpec`?**
  _High betweenness centrality (0.160) - this node is a cross-community bridge._
- **Why does `RequestRecord` connect `RequestRecord` to `BenchmarkRunner`, `metrics.py`, `RequestSpec`, `2. Component Responsibilities`, `._execute_specs_bounded`, `BenchmarkResult`, `experiment.py`?**
  _High betweenness centrality (0.118) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `TargetConfig` (e.g. with `InferenceClient` and `ExperimentConfig`) actually correct?**
  _`TargetConfig` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `BenchmarkRunner` (e.g. with `main()` and `run()`) actually correct?**
  _`BenchmarkRunner` has 25 INFERRED edges - model-reasoned connections that need verification._
- **Are the 21 inferred relationships involving `BenchmarkConfig` (e.g. with `ExperimentRunner` and `BenchmarkRunner`) actually correct?**
  _`BenchmarkConfig` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `RequestRecord` (e.g. with `2. Component Responsibilities` and `9. Architecture`) actually correct?**
  _`RequestRecord` has 9 INFERRED edges - model-reasoned connections that need verification._