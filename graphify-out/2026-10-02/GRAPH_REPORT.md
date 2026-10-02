# Graph Report - inferLoad  (2026-10-02)

## Corpus Check
- 51 files · ~45,397 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 3, .css 1)

## Summary
- 790 nodes · 1556 edges · 36 communities (27 shown, 9 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 233 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- runner.py
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
- config.py
- InferLoad Benchmark Result: vLLM GPU Validation (Phase 5)
- test_config.py
- .run
- server_telemetry.py
- test_server_telemetry.py
- 4. UI Capabilities Walkthrough
- .from_json_file
- load_experiment_config
- SweepPointSpec
- web.py

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

## Communities (36 total, 9 thin omitted)

### Community 0 - "runner.py"
Cohesion: 0.05
Nodes (21): 1. ASCII Architecture Diagram, 2. Component Responsibilities, 3. Data Flow, 4. Versioned Result Schema (`schema_version: "0.1"`), InferLoad Architecture, 9. Architecture, InferenceClient, aggregate_benchmark_results() (+13 more)

### Community 1 - "cli.py"
Cohesion: 0.07
Nodes (29): analyze_capacity(), CapacityAnalysisResult, format_capacity_report(), load_slo_config(), PointCompliance, SLOConfig, capacity(), compare() (+21 more)

### Community 2 - "TargetConfig"
Cohesion: 0.05
Nodes (33): main(), BenchmarkConfig, TargetConfig, WorkloadConfig, BenchmarkRunner, WorkloadGenerator, make_chat_completion_json(), make_sse_stream_chunks() (+25 more)

### Community 3 - "test_web.py"
Cohesion: 0.13
Nodes (13): ExperimentJobState, JobStatus, WebBenchmarkRequest, client(), test_web_artifact_path_traversal_safety(), test_web_create_experiment_invalid_payload_rejected(), test_web_experiment_status_not_found(), test_web_health_endpoint() (+5 more)

### Community 4 - "InferLoad Benchmark Methodology"
Cohesion: 0.08
Nodes (26): 10. Why p95 and p99 Matter, 11. Why Tokens/Sec Alone is Insufficient, 12. Limitations of Client-Side Benchmarking, 1. What TTFT Actually Means in InferLoad, 2. Why First Streamed Chunk != Guaranteed Single Token, 3. What Can and Cannot Be Measured from an OpenAI-Compatible Endpoint, 4. Warmup and Connection Priming, 5. Cold Start vs. Steady State (+18 more)

### Community 5 - "InferLoad Controlled Performance Experiments"
Cohesion: 0.05
Nodes (35): 1. Closed-Loop Concurrency vs. Open-Loop Arrival Rate, 2. Parameter Sweeps and Repeated Trials, 3. Sample Size and Uncertainty Estimation, 4. Empirical Saturation Analysis, 5. Artifact Directory Structure, 6. Within-Run Request Statistics vs. Across-Run Repetition Statistics, 7. Deterministic Capacity Analysis & SLO Compliance, 8. Scientific Interpretation Checklist (+27 more)

### Community 6 - "compare.py"
Cohesion: 0.11
Nodes (10): BenchmarkComparison, _calc_diff_and_pct(), compare_benchmarks(), add_comparison(), compare_files(), format_comparison_table(), MetricComparison, test_compare_benchmarks_deterministic_diffs() (+2 more)

### Community 7 - "InferLoad Results Interpretation Guide"
Cohesion: 0.11
Nodes (18): 1. Introduction: The Physics of Generative Inference, 2. What the Numbers Mean, 3. What the Numbers Do NOT Mean (Avoiding Overreach), 4. Client-Side vs. Server-Side Measurements, 5. Why Tail Latency Matters (The Tyranny of p95 and p99), 6. Why Throughput Flattens (The Knee of the Saturation Curve), 7. Small-N Uncertainty and Statistical Honesty, A. Time to First Token (TTFT) / First Usable Content Timing (+10 more)

### Community 8 - "environment.py"
Cohesion: 0.08
Nodes (11): capture_environment_metadata(), EnvironmentMetadata, _get_gpu_details(), _get_ram_total_gb(), create_app(), get_health(), get_historical_experiment(), list_experiment_history() (+3 more)

### Community 9 - "run_local_benchmark.py"
Cohesion: 0.06
Nodes (4): LocalMockServer, MockOpenAIHandler, MockServerStats, mock_server()

### Community 10 - "BenchmarkResult"
Cohesion: 0.24
Nodes (8): export_csv(), export_json(), export_results(), BenchmarkResult, _make_dummy_result(), test_export_all_results(), test_export_csv(), test_export_json()

### Community 15 - "Benchmarking Real Inference Servers (vLLM Target Guide)"
Cohesion: 0.08
Nodes (23): 1. Client-Side TTFT vs. Server Execution, 1. Why vLLM is the Primary Target, 2. Server Environment Requirements, 2. Server Queueing & Prometheus Telemetry Correlation, 3. Inter-Chunk Latency vs. Per-Token Latency, 3. Starting the vLLM Server, 4. Configuring InferLoad for vLLM, 4. Warmup Handling is Mandatory (+15 more)

### Community 16 - "InferLoad — LLM Inference Load Testing & Capacity Planner"
Cohesion: 0.07
Nodes (28): 10. Testing, 11. Validated Against Local Test Server, 12. Controlled Performance Experiments (Phase 3), 13. Empirical Capacity Analysis & SLO Compliance (Phase 4), 14. Real GPU Validation & vLLM Telemetry Correlation (Phase 5 & 5.5), 15. Current Limitations, 16. Roadmap, 1. What InferLoad Is (+20 more)

### Community 17 - "statistics.py"
Cohesion: 0.15
Nodes (4): compute_sample_statistics(), get_student_t_critical(), SampleStatistics, test_sample_statistics_and_confidence_intervals()

### Community 18 - "ExperimentConfig"
Cohesion: 0.16
Nodes (9): ExperimentConfig, ExperimentMeta, ExperimentWorkload, SweepDefinition, validate_benchmark_quality(), expand_sweep_grid(), test_benchmark_quality_validation_rules(), test_experiment_end_to_end_mock_sweep() (+1 more)

### Community 19 - "extract_telemetry_metrics"
Cohesion: 0.16
Nodes (6): extract_telemetry_metrics(), parse_prometheus_text(), ServerTelemetrySnapshot, test_parse_prometheus_malformed_response(), test_parse_prometheus_text_known_and_histogram(), test_unknown_and_missing_metrics()

### Community 20 - "app.js"
Cohesion: 0.17
Nodes (21): buildModelDropdown(), collectFormData(), discoveredModels, fmt(), formatDate(), initFormControls(), initHealth(), loadHistoricalRun() (+13 more)

### Community 21 - "experiment.py"
Cohesion: 0.19
Nodes (5): detect_saturation_regions(), ExperimentPointMetrics, SaturationFinding, generate_experiment_plots(), test_saturation_detection_logic()

### Community 22 - "InferLoad Real GPU & vLLM Validation Protocol"
Cohesion: 0.07
Nodes (27): 1. Objectives & Validation Principles, 2. Linux & CUDA Prerequisites, 3. Hardware & Software Information to Record, 4. Starting and Verifying the vLLM Server, 5. Benchmark Calibration & Methodology, 6. What InferLoad Measures vs. What Requires Server-Side Telemetry, 7. Capacity Analysis Protocol (SLO Evaluation), 8. vLLM GPU Validation & Reproduction Checklist (+19 more)

### Community 23 - "4. The 17-Step Operational Lifecycle"
Cohesion: 0.07
Nodes (29): 10. Every Request Becomes a Raw Record, 11. Request Aggregation & Percentiles, 12. Repeated Experiments Measure Stability, 13. The Experiment Layer, 14. Saturation Analysis, 15. Capacity / SLO Analysis, 16. Optional Server Telemetry Correlation, 17. Structured Final Output Artifacts (+21 more)

### Community 24 - "config.py"
Cohesion: 0.16
Nodes (5): ArrivalConfig, ExecutionConfig, ExportConfig, TelemetryConfig, build_experiment_config()

### Community 26 - "InferLoad Benchmark Result: vLLM GPU Validation (Phase 5)"
Cohesion: 0.17
Nodes (11): 1. System Environment Audit & Hardware Assessment, 2. Configured Validation Workload Specification, 3. Cross-Environment Comparison: Local Ollama (CPU) vs. Prospective vLLM (GPU), 4. Server-Side Telemetry Correlation Plan, 5. Execution Instructions for GPU Host, 6. vLLM GPU Validation Checklist (22 Parameters), A. Target Configuration, B. Workload Matrix (+3 more)

### Community 27 - "test_config.py"
Cohesion: 0.15
Nodes (9): load_config(), test_load_config_file_not_found(), test_load_config_from_file(), test_load_vllm_gpu_baseline_config(), test_target_config_already_has_chat_completions(), test_target_config_invalid_urls(), test_target_config_trailing_slash(), test_target_config_valid() (+1 more)

### Community 28 - ".run"
Cohesion: 0.14
Nodes (5): ExperimentResult, ExperimentRunner, PointSummary, ExperimentTelemetry, ServerTelemetryCollector

### Community 29 - "server_telemetry.py"
Cohesion: 0.18
Nodes (3): build_non_causal_correlation_notes(), render_telemetry_correlation_markdown(), test_report_rendering_with_telemetry_and_non_causal_wording()

### Community 30 - "test_server_telemetry.py"
Cohesion: 0.16
Nodes (5): _build_mock_point_summary(), test_optional_telemetry_configuration_and_backward_compatibility(), test_report_rendering_without_telemetry(), test_telemetry_disabled_or_empty_url(), test_telemetry_unavailable_handling()

### Community 31 - "4. UI Capabilities Walkthrough"
Cohesion: 0.18
Nodes (10): 1. Quick Start, 2. Architecture & Design Principles, 3. Web API Specification, 4. UI Capabilities Walkthrough, InferLoad Web UI — Local Interactive Benchmark Console, Results Presentation, SLO & Capacity Criteria, Start Web Server (+2 more)

## Knowledge Gaps
- **159 isolated node(s):** `inferload`, `discoveredModels`, `style`, `graphify`, `Workflow: graphify` (+154 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 396 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `InferLoad — LLM Inference Load Testing & Capacity Planner` connect `InferLoad — LLM Inference Load Testing & Capacity Planner` to `runner.py`, `InferLoad Controlled Performance Experiments`?**
  _High betweenness centrality (0.187) - this node is a cross-community bridge._
- **Why does `9. Architecture` connect `runner.py` to `InferLoad — LLM Inference Load Testing & Capacity Planner`?**
  _High betweenness centrality (0.174) - this node is a cross-community bridge._
- **Why does `RequestRecord` connect `runner.py` to `models.py`, `TargetConfig`, `BenchmarkResult`?**
  _High betweenness centrality (0.129) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `TargetConfig` (e.g. with `InferenceClient` and `ExperimentConfig`) actually correct?**
  _`TargetConfig` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `BenchmarkRunner` (e.g. with `main()` and `run()`) actually correct?**
  _`BenchmarkRunner` has 25 INFERRED edges - model-reasoned connections that need verification._
- **Are the 21 inferred relationships involving `BenchmarkConfig` (e.g. with `ExperimentRunner` and `BenchmarkRunner`) actually correct?**
  _`BenchmarkConfig` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `RequestRecord` (e.g. with `2. Component Responsibilities` and `9. Architecture`) actually correct?**
  _`RequestRecord` has 9 INFERRED edges - model-reasoned connections that need verification._