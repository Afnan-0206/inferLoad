"""Experiment orchestration, sweep expansion, statistical aggregation, and reporting."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable
import uuid

from pydantic import BaseModel, Field
import httpx

from inferload import __version__
from inferload.analysis import ExperimentPointMetrics, SaturationFinding, detect_saturation_regions
from inferload.config import ArrivalConfig, BenchmarkConfig, ExecutionConfig, ExportConfig, TargetConfig, WorkloadConfig
from inferload.environment import EnvironmentMetadata, capture_environment_metadata
from inferload.experiment_config import ExperimentConfig, validate_benchmark_quality
from inferload.models import BenchmarkResult
from inferload.plots import generate_experiment_plots
from inferload.runner import BenchmarkRunner
from inferload.server_telemetry import (
    ExperimentTelemetry,
    ServerTelemetryCollector,
    build_non_causal_correlation_notes,
    render_telemetry_correlation_markdown,
)
from inferload.statistics import SampleStatistics, compute_sample_statistics



class SweepPointSpec:
    """A single concrete benchmark trial in the sweep grid."""

    def __init__(
        self,
        concurrency: int,
        max_tokens: int,
        prompt_profile: str | None,
        prompts: list[str],
        arrival_rate: float | None,
        repetition: int,
        requests_count: int,
    ) -> None:
        self.concurrency = concurrency
        self.max_tokens = max_tokens
        self.prompt_profile = prompt_profile
        self.prompts = prompts
        self.arrival_rate = arrival_rate
        self.repetition = repetition
        self.requests_count = requests_count

    @property
    def point_key(self) -> str:
        prof = f"-{self.prompt_profile}" if self.prompt_profile else ""
        rate = f"-r{self.arrival_rate}" if self.arrival_rate else ""
        return f"c{self.concurrency}-m{self.max_tokens}{prof}{rate}"

    @property
    def run_id(self) -> str:
        return f"{self.point_key}-rep{self.repetition}"


class PointSummary(BaseModel):
    """Aggregated statistics across repetitions for a distinct parameter point."""

    concurrency: int
    max_tokens: int
    prompt_profile: str | None = None
    arrival_rate: float | None = None
    repetitions: int
    requests_per_point: int

    ttft_p50: SampleStatistics
    ttft_p95: SampleStatistics
    ttft_p99: SampleStatistics

    latency_p50: SampleStatistics
    latency_p95: SampleStatistics
    latency_p99: SampleStatistics

    throughput: SampleStatistics
    tokens_per_second: SampleStatistics
    error_rate: SampleStatistics


class ExperimentResult(BaseModel):
    """Complete, versioned output artifact of an experiment."""

    schema_version: str = "0.2"
    experiment_id: str
    name: str
    description: str
    timestamp: str
    inferload_version: str

    # Explicit top-level metadata fields required by Phase 4
    model: str = ""
    endpoint: str = ""
    concurrency_levels: list[int] = Field(default_factory=list)
    requests_per_point: int = 0
    repetitions: int = 1
    warmup_requests: int = 0
    arrival_mode: str = "closed"
    prompt_profile: str | None = None
    max_tokens: int = 128
    temperature: float = 0.0
    seed: int | None = None
    streaming: bool = True

    target: dict[str, Any]
    environment: EnvironmentMetadata
    sweep_config: dict[str, Any]
    workload_config: dict[str, Any] = Field(default_factory=dict)
    execution_config: dict[str, Any] = Field(default_factory=dict)
    arrival_config: dict[str, Any] = Field(default_factory=dict)
    quality_warnings: list[str] = Field(default_factory=list)
    points: list[PointSummary]
    saturation_findings: list[SaturationFinding]
    raw_run_ids: list[str]
    telemetry: ExperimentTelemetry = Field(default_factory=ExperimentTelemetry)



def expand_sweep_grid(config: ExperimentConfig) -> list[SweepPointSpec]:
    """Expand experiment configuration into deterministic sweep point executions."""
    sweep = config.sweep
    workload = config.workload

    concurrencies = sweep.concurrency
    max_tokens_list = sweep.max_tokens or [workload.max_tokens]

    # Resolve prompt sets
    profile_tuples: list[tuple[str | None, list[str]]] = []
    if sweep.prompt_profiles:
        for prof in sweep.prompt_profiles:
            if prof in workload.prompt_profiles:
                profile_tuples.append((prof, workload.prompt_profiles[prof]))
            else:
                raise ValueError(f"Prompt profile '{prof}' not found in workload.prompt_profiles")
    elif workload.prompt_profiles and not workload.prompts:
        for prof_name, p_list in workload.prompt_profiles.items():
            profile_tuples.append((prof_name, p_list))
    else:
        profile_tuples.append((None, workload.prompts))

    arrival_rates = sweep.arrival_rates or ([config.arrival.requests_per_second] if config.arrival.mode == "rate" else [None])

    grid: list[SweepPointSpec] = []
    for c in concurrencies:
        for m in max_tokens_list:
            for prof_name, prompts in profile_tuples:
                for rate in arrival_rates:
                    for rep in range(1, sweep.repetitions + 1):
                        spec = SweepPointSpec(
                            concurrency=c,
                            max_tokens=m,
                            prompt_profile=prof_name,
                            prompts=prompts,
                            arrival_rate=rate,
                            repetition=rep,
                            requests_count=sweep.requests_per_point,
                        )
                        grid.append(spec)

    return grid


class ExperimentRunner:
    """Executes multi-point parameter sweeps, computes repetitions statistics, and exports artifacts."""

    def __init__(
        self,
        config: ExperimentConfig,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self._external_client = http_client

    async def run(
        self,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> tuple[ExperimentResult, Path]:
        """Execute the full experiment sweep and save structured artifacts."""
        quality_warnings = validate_benchmark_quality(self.config)
        grid = expand_sweep_grid(self.config)
        total_trials = len(grid)

        now_utc = datetime.now(timezone.utc)
        exp_id = f"experiment-{self.config.experiment.name}-{now_utc.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        exp_dir = Path(self.config.experiment.output_dir) / exp_id
        raw_dir = exp_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        # Optional server telemetry collector
        telemetry_collector = ServerTelemetryCollector(
            metrics_url=self.config.telemetry.metrics_url,
            enabled=self.config.telemetry.enabled,
            server_version=self.config.telemetry.server_version,
            http_client=self._external_client,
        )
        snap_before = await telemetry_collector.capture_snapshot()
        snap_during = None
        mid_trial_idx = max(1, total_trials // 2)

        environment = capture_environment_metadata(
            server_version=self.config.telemetry.server_version,
            vllm_version=self.config.telemetry.server_version,
        )
        raw_results: dict[str, list[BenchmarkResult]] = {}
        all_run_ids: list[str] = []

        for idx, trial in enumerate(grid, 1):
            if progress_callback:
                progress_callback(trial.run_id, idx, total_trials)

            if idx == mid_trial_idx and self.config.telemetry.enabled:
                snap_during = await telemetry_collector.capture_snapshot()

            # Build individual BenchmarkConfig for this trial
            point_arrival = ArrivalConfig(
                mode="rate" if trial.arrival_rate else "closed",
                requests_per_second=trial.arrival_rate,
            )
            bench_cfg = BenchmarkConfig(
                target=self.config.target,
                workload=WorkloadConfig(
                    requests=trial.requests_count,
                    concurrency=trial.concurrency,
                    stream=self.config.workload.stream,
                    prompts=trial.prompts,
                    max_tokens=trial.max_tokens,
                    temperature=self.config.workload.temperature,
                    seed=self.config.workload.seed,
                    extra_params=self.config.workload.extra_params,
                ),
                execution=self.config.execution,
                export=ExportConfig(output_dir=str(raw_dir), formats=["json"]),
                arrival=point_arrival,
            )

            runner = BenchmarkRunner(
                bench_cfg,
                http_client=self._external_client,
                run_id=trial.run_id,
            )
            res = await runner.run()

            # Save individual raw JSON
            raw_file = raw_dir / f"{trial.run_id}.json"
            with open(raw_file, "w", encoding="utf-8") as f:
                json.dump(res.model_dump(mode="json"), f, indent=2)

            all_run_ids.append(trial.run_id)
            if trial.point_key not in raw_results:
                raw_results[trial.point_key] = []
            raw_results[trial.point_key].append(res)

        # 2. Compute repetition statistics per point
        point_summaries: list[PointSummary] = []
        plot_rows: list[dict[str, Any]] = []

        for point_key, runs in raw_results.items():
            first_run = runs[0]
            concurrency = first_run.concurrency
            max_tokens = first_run.workload.get("max_tokens", self.config.workload.max_tokens)
            arrival_rate = first_run.arrival.get("requests_per_second")

            # Extract metrics across repetitions
            ttft_p50s = [r.summary.ttft_ms.p50 for r in runs if r.summary.ttft_ms and r.summary.ttft_ms.p50 is not None]
            ttft_p95s = [r.summary.ttft_ms.p95 for r in runs if r.summary.ttft_ms and r.summary.ttft_ms.p95 is not None]
            ttft_p99s = [r.summary.ttft_ms.p99 for r in runs if r.summary.ttft_ms and r.summary.ttft_ms.p99 is not None]

            lat_p50s = [r.summary.total_latency_ms.p50 for r in runs if r.summary.total_latency_ms.p50 is not None]
            lat_p95s = [r.summary.total_latency_ms.p95 for r in runs if r.summary.total_latency_ms.p95 is not None]
            lat_p99s = [r.summary.total_latency_ms.p99 for r in runs if r.summary.total_latency_ms.p99 is not None]

            thrus = [r.summary.requests_per_second for r in runs]
            tok_rates = [r.summary.aggregate_tokens_per_second for r in runs if r.summary.aggregate_tokens_per_second is not None]
            err_rates = [r.summary.error_rate for r in runs]

            stat_ttft_p50 = compute_sample_statistics(ttft_p50s)
            stat_ttft_p95 = compute_sample_statistics(ttft_p95s)
            stat_ttft_p99 = compute_sample_statistics(ttft_p99s)

            stat_lat_p50 = compute_sample_statistics(lat_p50s)
            stat_lat_p95 = compute_sample_statistics(lat_p95s)
            stat_lat_p99 = compute_sample_statistics(lat_p99s)

            stat_thru = compute_sample_statistics(thrus)
            stat_tok_rate = compute_sample_statistics(tok_rates)
            stat_err = compute_sample_statistics(err_rates)

            ps = PointSummary(
                concurrency=concurrency,
                max_tokens=max_tokens,
                prompt_profile=None,
                arrival_rate=arrival_rate,
                repetitions=len(runs),
                requests_per_point=first_run.request_count,
                ttft_p50=stat_ttft_p50,
                ttft_p95=stat_ttft_p95,
                ttft_p99=stat_ttft_p99,
                latency_p50=stat_lat_p50,
                latency_p95=stat_lat_p95,
                latency_p99=stat_lat_p99,
                throughput=stat_thru,
                tokens_per_second=stat_tok_rate,
                error_rate=stat_err,
            )
            point_summaries.append(ps)

            plot_rows.append({
                "concurrency": concurrency,
                "max_tokens": max_tokens,
                "ttft_p50_mean": stat_ttft_p50.mean,
                "ttft_p95_mean": stat_ttft_p95.mean,
                "ttft_p95_std": stat_ttft_p95.std_dev,
                "latency_p50_mean": stat_lat_p50.mean,
                "latency_p95_mean": stat_lat_p95.mean,
                "latency_p95_std": stat_lat_p95.std_dev,
                "throughput_mean": stat_thru.mean,
                "throughput_std": stat_thru.std_dev,
                "error_rate_mean": stat_err.mean or 0.0,
            })

        # 3. Saturation analysis
        saturation_inputs = [
            ExperimentPointMetrics(
                load_parameter=float(ps.concurrency if not ps.arrival_rate else ps.arrival_rate),
                throughput_rps=ps.throughput.mean or 0.0,
                latency_p95_ms=ps.latency_p95.mean or 0.0,
                error_rate=ps.error_rate.mean or 0.0,
            )
            for ps in point_summaries
        ]
        param_label = "arrival rate" if self.config.arrival.mode == "rate" else "concurrency"
        saturation_findings = detect_saturation_regions(saturation_inputs, parameter_name=param_label)

        # Telemetry snapshot after sweep and correlation notes
        snap_after = await telemetry_collector.capture_snapshot()
        corr_notes = build_non_causal_correlation_notes(
            point_summaries,
            snap_before,
            snap_during,
            snap_after,
        )
        exp_telemetry = ExperimentTelemetry(
            enabled=self.config.telemetry.enabled,
            available=(
                (snap_before is not None and snap_before.available)
                or (snap_during is not None and snap_during.available)
                or (snap_after is not None and snap_after.available)
            ),
            endpoint_url=self.config.telemetry.metrics_url,
            server_version=self.config.telemetry.server_version,
            error_message=snap_before.error_message if (snap_before and not snap_before.available) else None,
            telemetry_before=snap_before,
            telemetry_during=snap_during,
            telemetry_after=snap_after,
            correlation_notes=corr_notes,
        )

        exp_result = ExperimentResult(
            schema_version="0.2",
            experiment_id=exp_id,
            name=self.config.experiment.name,
            description=self.config.experiment.description,
            timestamp=now_utc.isoformat(),
            inferload_version=__version__,
            model=self.config.target.model,
            endpoint=str(self.config.target.base_url),
            concurrency_levels=self.config.sweep.concurrency,
            requests_per_point=self.config.sweep.requests_per_point,
            repetitions=self.config.sweep.repetitions,
            warmup_requests=self.config.execution.warmup_requests,
            arrival_mode=self.config.arrival.mode,
            prompt_profile=None,
            max_tokens=self.config.workload.max_tokens,
            temperature=self.config.workload.temperature,
            seed=self.config.workload.seed,
            streaming=self.config.workload.stream,
            target=self.config.target.model_dump(),
            environment=environment,
            sweep_config=self.config.sweep.model_dump(),
            workload_config=self.config.workload.model_dump(),
            execution_config=self.config.execution.model_dump(),
            arrival_config=self.config.arrival.model_dump(),
            quality_warnings=quality_warnings,
            points=point_summaries,
            saturation_findings=saturation_findings,
            raw_run_ids=all_run_ids,
            telemetry=exp_telemetry,
        )


        # 4. Save summary.json
        summary_file = exp_dir / "summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(exp_result.model_dump(mode="json"), f, indent=2)

        # 5. Save points.csv
        points_csv = exp_dir / "points.csv"
        self._write_points_csv(points_csv, raw_results)

        # 6. Generate static plots
        plots_dir = exp_dir / "plots"
        generate_experiment_plots(plot_rows, plots_dir)

        # 7. Generate report.md
        report_file = exp_dir / "report.md"
        report_md = self._render_report_markdown(exp_result)
        report_file.write_text(report_md, encoding="utf-8")

        return exp_result, exp_dir

    def _write_points_csv(
        self,
        path: Path,
        raw_results: dict[str, list[BenchmarkResult]],
    ) -> None:
        headers = [
            "run_id",
            "concurrency",
            "max_tokens",
            "arrival_mode",
            "arrival_rate",
            "requests",
            "success_count",
            "failure_count",
            "error_rate",
            "ttft_p50_ms",
            "ttft_p95_ms",
            "ttft_p99_ms",
            "latency_p50_ms",
            "latency_p95_ms",
            "latency_p99_ms",
            "throughput_rps",
            "tokens_per_second",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for runs in raw_results.values():
                for r in runs:
                    writer.writerow([
                        r.run_id,
                        r.concurrency,
                        r.workload.get("max_tokens", ""),
                        r.arrival.get("mode", "closed"),
                        r.arrival.get("requests_per_second", ""),
                        r.summary.total_requests,
                        r.summary.success_count,
                        r.summary.failure_count,
                        f"{r.summary.error_rate:.4f}",
                        f"{r.summary.ttft_ms.p50:.2f}" if r.summary.ttft_ms and r.summary.ttft_ms.p50 else "",
                        f"{r.summary.ttft_ms.p95:.2f}" if r.summary.ttft_ms and r.summary.ttft_ms.p95 else "",
                        f"{r.summary.ttft_ms.p99:.2f}" if r.summary.ttft_ms and r.summary.ttft_ms.p99 else "",
                        f"{r.summary.total_latency_ms.p50:.2f}",
                        f"{r.summary.total_latency_ms.p95:.2f}",
                        f"{r.summary.total_latency_ms.p99:.2f}",
                        f"{r.summary.requests_per_second:.2f}",
                        f"{r.summary.aggregate_tokens_per_second:.2f}" if r.summary.aggregate_tokens_per_second else "",
                    ])

    def _render_report_markdown(self, res: ExperimentResult) -> str:
        lines: list[str] = [
            f"# InferLoad Experiment Report: {res.name}",
            "",
            f"**Experiment ID:** `{res.experiment_id}`  ",
            f"**Timestamp:** `{res.timestamp}`  ",
            f"**InferLoad Version:** `v{res.inferload_version}`  ",
            f"**Target Endpoint:** `{res.endpoint or res.target.get('base_url')}`  ",
            f"**Target Model:** `{res.model or res.target.get('model')}`  ",
            "",
        ]

        if res.description:
            lines.extend([f"**Description:** {res.description}", ""])

        # 1. Environment
        env = res.environment
        lines.extend([
            "## 1. System Execution Environment",
            "",
            "| Component | Detected Specification |",
            "| :--- | :--- |",
            f"| **OS** | {env.os_system} {env.os_release} (build {env.os_version}) |",
            f"| **Python** | {env.python_implementation} {env.python_version} |",
            f"| **CPU Architecture** | {env.cpu_architecture} ({env.cpu_cores or 'unknown'} cores) |",
            f"| **CPU Model** | {env.cpu_model} |",
            f"| **System RAM** | {env.ram_total_gb or 'unavailable'} GB |",
            f"| **GPU Hardware** | {env.gpu_info} |",
            f"| **GPU Model** | {env.gpu_name or 'unavailable'} |",
            f"| **GPU Count** | {env.gpu_count or 'unavailable'} |",
            f"| **CUDA Version** | {env.cuda_version or 'unavailable'} |",
            f"| **Driver Version** | {env.driver_version or 'unavailable'} |",
            f"| **Server / vLLM Version** | {env.server_version or env.vllm_version or 'unspecified'} |",
            "",

        ])

        # 2. Workload definition
        lines.extend([
            "## 2. Workload Definition",
            "",
            "| Parameter | Value |",
            "| :--- | :--- |",
            f"| **Target Model** | `{res.model or res.target.get('model')}` |",
            f"| **Base URL** | `{res.endpoint or res.target.get('base_url')}` |",
            f"| **Streaming** | `{res.streaming}` |",
            f"| **Max Tokens** | {res.max_tokens} |",
            f"| **Temperature** | {res.temperature} |",
            f"| **Arrival Mode** | `{res.arrival_mode}` |",
            "",
        ])

        # 3. Benchmark methodology
        lines.extend([
            "## 3. Benchmark Methodology",
            "",
            "- **Load Mode:** " + ("Open-Loop (Constant Arrival Rate)" if res.arrival_mode == "rate" else "Closed-Loop (Bounded Concurrency Workers)"),
            f"- **Warmup Isolation:** {res.warmup_requests} warmup requests executed and excluded before metric collection per trial.",
            f"- **Workload Volume:** {res.requests_per_point} measured requests per repetition point.",
            f"- **Repetitions:** {res.repetitions} independent benchmark trials per parameter point to measure repeatability.",
            "- **Trial Isolation:** Each trial is executed as an independent run, saved under `raw/`, and aggregated without pooling raw requests.",
            "",
        ])
        if res.quality_warnings:
            lines.extend([
                "> [!NOTE]",
                "> **Benchmark Quality & Calibration Advisories:**",
            ])
            for qw in res.quality_warnings:
                lines.append(f"> - {qw}")
            lines.append("")

        # 4. Per-point results
        lines.extend([
            "## 4. Per-Point Results / Sweep Results Summary",
            "",
            "| Concurrency | Trials | Reqs/Trial | TTFT p50 (mean) | TTFT p95 (mean) | Latency p95 (mean) | Throughput (mean) | Error Rate |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ])
        for p in res.points:
            ttft_p50_str = f"{p.ttft_p50.mean:.1f} ms" if p.ttft_p50.mean is not None else "N/A"
            ttft_p95_str = f"{p.ttft_p95.mean:.1f} ms" if p.ttft_p95.mean is not None else "N/A"
            lat_p95_str = f"{p.latency_p95.mean:.1f} ms" if p.latency_p95.mean is not None else "N/A"
            thru_str = f"{p.throughput.mean:.2f} req/s" if p.throughput.mean is not None else "N/A"
            err_str = f"{(p.error_rate.mean or 0.0)*100.0:.1f}%"
            lines.append(
                f"| {p.concurrency} | {p.repetitions} | {p.requests_per_point} | {ttft_p50_str} | {ttft_p95_str} | {lat_p95_str} | {thru_str} | {err_str} |"
            )
        lines.append("")

        # 5. Repetition statistics
        lines.extend([
            "## 5. Statistical Repetitions & Uncertainty Analysis",
            "",
            "Statistical summary across independent repetitions ($N$ trials) for each tested parameter point:",
            "",
            "| Concurrency | Metric | Trials ($N$) | Mean | Std Dev | Min | Max | CV (%) |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ])
        for p in res.points:
            c = p.concurrency
            for m_name, stat in [("TTFT p95", p.ttft_p95), ("Latency p95", p.latency_p95), ("Throughput", p.throughput)]:
                if stat.mean is not None:
                    sd_str = f"{stat.std_dev:.2f}" if stat.std_dev is not None else "N/A"
                    min_str = f"{stat.minimum:.2f}" if stat.minimum is not None else "N/A"
                    max_str = f"{stat.maximum:.2f}" if stat.maximum is not None else "N/A"
                    cv_str = f"{stat.coefficient_of_variation_pct:.1f}%" if stat.coefficient_of_variation_pct is not None else "N/A"
                    lines.append(f"| {c} | {m_name} | {stat.sample_size} | {stat.mean:.2f} | {sd_str} | {min_str} | {max_str} | {cv_str} |")
        lines.append("")

        # 6. Confidence intervals
        lines.extend([
            "## 6. Uncertainty & Confidence Intervals (Student's t, 95%)",
            "",
            "Confidence intervals are computed using the Student's t-distribution with $N - 1$ degrees of freedom to account for small sample sizes ($N < 30$):",
            "",
            "| Concurrency | Metric | Sample Size ($N$) | Mean | Std Dev | 95% Confidence Interval | Margin of Error |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ])
        for p in res.points:
            c = p.concurrency
            for m_name, stat in [("TTFT p95", p.ttft_p95), ("Latency p95", p.latency_p95), ("Throughput", p.throughput)]:
                if stat.mean is not None:
                    sd_str = f"{stat.std_dev:.2f}" if stat.std_dev is not None else "N/A"
                    if stat.ci_95_lower is not None and stat.ci_95_upper is not None:
                        ci_str = f"[{stat.ci_95_lower:.2f}, {stat.ci_95_upper:.2f}]"
                        moe = (stat.ci_95_upper - stat.ci_95_lower) / 2.0
                        moe_str = f"±{moe:.2f}"
                    else:
                        ci_str = "N/A"
                        moe_str = "N/A"
                    lines.append(f"| {c} | {m_name} | {stat.sample_size} | {stat.mean:.2f} | {sd_str} | {ci_str} | {moe_str} |")
        lines.append("")

        # 7. Throughput vs concurrency
        lines.extend([
            "## 7. Throughput vs. Concurrency",
            "",
            "| Concurrency | Throughput (mean) | Throughput Std Dev | Throughput Scaling Ratio |",
            "| :--- | :--- | :--- | :--- |",
        ])
        base_thru = res.points[0].throughput.mean if res.points and res.points[0].throughput.mean else 1.0
        for p in res.points:
            thru_mean = p.throughput.mean or 0.0
            thru_std = f"±{p.throughput.std_dev:.2f}" if p.throughput.std_dev else "N/A"
            ratio = f"{thru_mean / base_thru:.2f}x" if base_thru > 0 else "N/A"
            lines.append(f"| {p.concurrency} | {thru_mean:.2f} req/s | {thru_std} | {ratio} |")
        lines.append("")

        # 8. TTFT vs concurrency
        lines.extend([
            "## 8. Time to First Token (TTFT) vs. Concurrency",
            "",
            "| Concurrency | TTFT p50 (mean) | TTFT p95 (mean) | TTFT p99 (mean) | TTFT p95 Growth Ratio |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ])
        base_ttft95 = res.points[0].ttft_p95.mean if res.points and res.points[0].ttft_p95.mean else 1.0
        for p in res.points:
            t50 = f"{p.ttft_p50.mean:.1f} ms" if p.ttft_p50.mean is not None else "N/A"
            t95 = f"{p.ttft_p95.mean:.1f} ms" if p.ttft_p95.mean is not None else "N/A"
            t99 = f"{p.ttft_p99.mean:.1f} ms" if p.ttft_p99.mean is not None else "N/A"
            growth = f"{p.ttft_p95.mean / base_ttft95:.2f}x" if p.ttft_p95.mean and base_ttft95 > 0 else "N/A"
            lines.append(f"| {p.concurrency} | {t50} | {t95} | {t99} | {growth} |")
        lines.append("")

        # 9. Error rate vs concurrency
        lines.extend([
            "## 9. Error Rate vs. Concurrency",
            "",
            "| Concurrency | Total Requests | Error Rate (%) | Status |",
            "| :--- | :--- | :--- | :--- |",
        ])
        for p in res.points:
            err_pct = (p.error_rate.mean or 0.0) * 100.0
            tot_reqs = p.repetitions * p.requests_per_point
            status = "Clean (0 errors)" if err_pct == 0.0 else f"Failures detected ({err_pct:.2f}%)"
            lines.append(f"| {p.concurrency} | {tot_reqs} | {err_pct:.2f}% | {status} |")
        lines.append("")

        # 10. SLO compliance
        lines.extend([
            "## 10. SLO Compliance & Capacity Assessment",
            "",
            "Reference SLO baseline (TTFT p95 <= 1000.0 ms, Error Rate <= 1.0%, Throughput >= 1.0 req/s):",
            "",
            "| Concurrency | Throughput | TTFT p95 | Error Rate | Reference Status |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ])
        compliant_concurrencies: list[int] = []
        for p in res.points:
            t_ok = (p.ttft_p95.mean is not None and p.ttft_p95.mean <= 1000.0)
            e_ok = ((p.error_rate.mean or 0.0) * 100.0 <= 1.0)
            tp_ok = (p.throughput.mean is not None and p.throughput.mean >= 1.0)
            is_ok = t_ok and e_ok and tp_ok
            if is_ok:
                compliant_concurrencies.append(p.concurrency)
            status_badge = "COMPLIANT" if is_ok else "VIOLATION"
            lines.append(
                f"| {p.concurrency} | {p.throughput.mean:.2f} req/s | {p.ttft_p95.mean:.1f} ms | {(p.error_rate.mean or 0.0)*100.0:.1f}% | `{status_badge}` |"
            )
        highest_c = str(max(compliant_concurrencies)) if compliant_concurrencies else "None (No tested point compliant)"
        lines.extend([
            "",
            f"**Highest Observed Compliant Tested Concurrency (Reference):** `{highest_c}`",
            "",
            "> [!NOTE]",
            "> *Capacity is limited to tested configurations and does not extrapolate beyond observed measurements. "
            "> Run `inferload capacity <experiment-dir> --slo <slo.yaml>` for customized SLO analysis.*",
            "",
        ])

        # 11. Observed saturation-like behavior
        lines.extend([
            "## 11. Observed Saturation-like Behavior",
            "",
        ])
        if res.saturation_findings:
            for sf in res.saturation_findings:
                lines.extend([
                    f"> [!WARNING]",
                    f"> **{sf.summary_message}**",
                    f"> *Cautionary note:* {sf.cautionary_note}",
                    "",
                ])
        else:
            lines.extend([
                "No inflection regions meeting saturation criteria were observed under the tested parameter range.",
                "",
            ])

        # 12. Server Telemetry Correlation
        lines.extend(render_telemetry_correlation_markdown(res.telemetry, res.points))

        # 13. Limitations
        lines.extend([
            "## 13. Benchmark Interpretation and Statistical Limitations",
            "",
            "1. **Sample Size Limitations:** Repetitions ($N < 30$) incur wide Student's t margins of error. Small sample estimates should not be treated as absolute population limits.",
            "2. **Within-Run vs. Across-Run Separation:** Within-run request statistics measure latency distributions under a single trial. Across-run repetition statistics measure system repeatability and stability. These samples are preserved separately to avoid pooling correlated requests.",
            "3. **Telemetry Boundary Limitations:** Point-in-time server telemetry snapshots capture boundary system states (before, during, after). They do not trace individual per-request queue or compute latencies. Causal assertions require validated server tracing.",
            "4. **Closed-Loop vs. Open-Loop Dynamics:** In closed-loop mode, workers wait for previous requests to complete before dispatching new ones. Latency increases will automatically suppress arrival rate, preventing queue explosion.",
            "5. **No Predictive Extrapolation:** Observed capacity represents the highest compliant tested point only. Extrapolating beyond tested concurrency is not supported.",
            "",
            "## 14. Generated Visualizations",
            "",
            "- [Concurrency vs TTFT p95](plots/concurrency_vs_ttft_p95.png)",
            "- [Concurrency vs Throughput](plots/concurrency_vs_throughput.png)",
            "- [Concurrency vs Error Rate](plots/concurrency_vs_error_rate.png)",
            "- [Concurrency vs Total Latency p95](plots/concurrency_vs_total_latency_p95.png)",
            "",
        ])

        return "\n".join(lines)


