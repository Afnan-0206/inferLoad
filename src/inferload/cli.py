"""Command-line interface for InferLoad using Typer."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from inferload import __version__
from inferload.config import load_config
from inferload.exporters import export_results
from inferload.models import BenchmarkResult
from inferload.runner import BenchmarkRunner

app = typer.Typer(
    name="inferload",
    help="InferLoad — LLM Inference Load Testing & Capacity Planner",
    add_completion=False,
)
console = Console()


def _format_metric_val(val: float | None, unit: str = "ms") -> str:
    if val is None:
        return "N/A"
    return f"{val:.2f} {unit}"


def _print_benchmark_summary(result: BenchmarkResult, exported_files: dict[str, Path]) -> None:
    summary = result.summary
    target_url = result.target.get("base_url", "unknown")
    model = result.target.get("model", "unknown")
    concurrency = result.workload.get("concurrency", 1)

    console.print("\n[bold]InferLoad Benchmark[/bold]")
    console.print("-------------------")
    console.print(f"Target: {target_url}")
    console.print(f"Model: {model}\n")

    console.print(f"Requests: {summary.total_requests}")
    console.print(f"Concurrency: {concurrency}")
    console.print(f"Success: {summary.success_count}")
    console.print(f"Errors: {summary.failure_count}\n")

    console.print("[bold]TTFT[/bold]")
    if summary.ttft_ms:
        console.print(f"p50: {_format_metric_val(summary.ttft_ms.p50)}")
        console.print(f"p95: {_format_metric_val(summary.ttft_ms.p95)}")
        console.print(f"p99: {_format_metric_val(summary.ttft_ms.p99)}\n")
    else:
        console.print("p50: N/A (non-streaming or no tokens)")
        console.print("p95: N/A")
        console.print("p99: N/A\n")

    console.print("[bold]Total Latency[/bold]")
    console.print(f"p50: {_format_metric_val(summary.total_latency_ms.p50)}")
    console.print(f"p95: {_format_metric_val(summary.total_latency_ms.p95)}")
    console.print(f"p99: {_format_metric_val(summary.total_latency_ms.p99)}\n")

    console.print("[bold]Throughput[/bold]")
    console.print(f"Requests/s: {summary.requests_per_second:.2f}")
    if summary.aggregate_tokens_per_second is not None:
        console.print(f"Output tok/s: {summary.aggregate_tokens_per_second:.2f}\n")
    else:
        console.print("Output tok/s: N/A (usage metrics not returned by target)\n")

    if exported_files:
        console.print("[bold]Export:[/bold]")
        for path in exported_files.values():
            console.print(str(path))


@app.command()
def run(
    config_file: Path = typer.Argument(..., help="Path to the YAML workload configuration file"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Override output directory"),
    requests: Optional[int] = typer.Option(None, "--requests", "-n", help="Override request count"),
    concurrency: Optional[int] = typer.Option(None, "--concurrency", "-c", help="Override concurrency"),
    run_id: Optional[str] = typer.Option(None, "--run-id", help="Explicit benchmark run identifier"),
) -> None:
    """Run an LLM inference benchmark from a YAML configuration file."""
    try:
        cfg = load_config(config_file)
    except Exception as exc:
        console.print(f"[bold red]Configuration Error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    if output_dir is not None:
        cfg.export.output_dir = str(output_dir)
    if requests is not None:
        cfg.workload.requests = requests
    if concurrency is not None:
        cfg.workload.concurrency = concurrency

    console.print(f"[green]Loaded config from {config_file}[/green]")
    console.print(
        f"Executing benchmark: {cfg.workload.requests} requests at concurrency {cfg.workload.concurrency} "
        f"against {cfg.target.chat_completions_url} (stream={cfg.workload.stream})..."
    )

    runner = BenchmarkRunner(cfg, run_id=run_id)
    try:
        result = asyncio.run(runner.run())
    except Exception as exc:
        console.print(f"[bold red]Benchmark Execution Error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # Export results
    exported = export_results(
        result=result,
        output_dir=cfg.export.output_dir,
        prefix=cfg.export.prefix,
        formats=cfg.export.formats,
    )

    _print_benchmark_summary(result, exported)


@app.command()
def compare(
    baseline_file: Path = typer.Argument(..., help="Path to baseline benchmark JSON file"),
    candidate_file: Path = typer.Argument(..., help="Path to candidate benchmark JSON file"),
    json_output: bool = typer.Option(False, "--json", help="Output comparison result as raw JSON"),
) -> None:
    """Compare two benchmark runs (baseline vs candidate) to evaluate regressions and throughput deltas."""
    from inferload.compare import compare_files, format_comparison_table
    import json

    try:
        comparison = compare_files(baseline_file, candidate_file)
    except Exception as exc:
        console.print(f"[bold red]Comparison Error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    if json_output:
        console.print(json.dumps(comparison.model_dump(mode="json"), indent=2))
    else:
        table_str = format_comparison_table(comparison)
        console.print(f"\n{table_str}\n")


@app.command()
def experiment(
    config_file: Path = typer.Argument(..., help="Path to experiment YAML configuration file"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Override output directory"),
) -> None:
    """Run a controlled multi-point parameter sweep experiment with repetitions and statistical analysis."""
    from inferload.experiment_config import load_experiment_config
    from inferload.experiment import ExperimentRunner

    try:
        cfg = load_experiment_config(config_file)
    except Exception as exc:
        console.print(f"[bold red]Experiment Config Error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    if output_dir is not None:
        cfg.experiment.output_dir = str(output_dir)

    console.print(f"\n[bold green]Starting Experiment: {cfg.experiment.name}[/bold green]")
    console.print(f"Target: {cfg.target.base_url} (model: {cfg.target.model})")
    console.print(
        f"Sweep concurrency: {cfg.sweep.concurrency}, Repetitions: {cfg.sweep.repetitions}, "
        f"Requests per point: {cfg.sweep.requests_per_point}\n"
    )

    runner = ExperimentRunner(cfg)

    def on_progress(trial_id: str, current: int, total: int) -> None:
        console.print(f"  [{current}/{total}] Running trial: {trial_id}...")

    try:
        result, out_dir = asyncio.run(runner.run(progress_callback=on_progress))
    except Exception as exc:
        console.print(f"[bold red]Experiment Execution Error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    console.print(f"\n[bold green]Experiment Completed Successfully![/bold green]")
    console.print(f"Output Directory: [bold]{out_dir}[/bold]")
    console.print(f"  Summary JSON: {out_dir / 'summary.json'}")
    console.print(f"  Points CSV:   {out_dir / 'points.csv'}")
    console.print(f"  Report MD:    {out_dir / 'report.md'}")
    console.print(f"  Static Plots: {out_dir / 'plots'}\n")

    console.print(f"{'Concurrency':<12} {'Trials':<8} {'TTFT p50 (mean)':<18} {'Latency p95 (mean)':<20} {'Throughput (mean)':<18}")
    console.print("-" * 76)
    for p in result.points:
        ttft_str = f"{p.ttft_p50.mean:.1f} ms" if p.ttft_p50.mean is not None else "N/A"
        lat_str = f"{p.latency_p95.mean:.1f} ms" if p.latency_p95.mean is not None else "N/A"
        thru_str = f"{p.throughput.mean:.2f} req/s" if p.throughput.mean is not None else "N/A"
        console.print(f"{p.concurrency:<12} {p.repetitions:<8} {ttft_str:<18} {lat_str:<20} {thru_str:<18}")

    if result.quality_warnings:
        console.print("\n[bold yellow]Quality & Calibration Advisories:[/bold yellow]")
        for qw in result.quality_warnings:
            console.print(f"  ! {qw}")

    if result.saturation_findings:
        console.print("\n[bold yellow]Saturation Findings:[/bold yellow]")
        for sf in result.saturation_findings:
            console.print(f"  - {sf.summary_message}")


@app.command()
def capacity(
    experiment_dir: Path = typer.Argument(..., help="Path to experiment results directory or summary.json"),
    slo: Path = typer.Option(..., "--slo", "-s", help="Path to YAML file defining target SLO constraints"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Optional path to save capacity analysis report"),
) -> None:
    """Analyze empirical capacity and SLO compliance over tested benchmark sweep points."""
    from inferload.capacity import load_slo_config, analyze_capacity, format_capacity_report
    from inferload.experiment import ExperimentResult

    exp_path = Path(experiment_dir)
    summary_file = exp_path / "summary.json" if exp_path.is_dir() else exp_path
    if not summary_file.is_file():
        console.print(f"[bold red]Experiment summary not found:[/bold red] {summary_file}")
        raise typer.Exit(code=1)

    try:
        slo_cfg = load_slo_config(slo)
    except Exception as exc:
        console.print(f"[bold red]SLO Configuration Error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    try:
        content = summary_file.read_text(encoding="utf-8")
        exp_result = ExperimentResult.model_validate_json(content)
        analysis = analyze_capacity(exp_result, slo_cfg)
    except Exception as exc:
        console.print(f"[bold red]Capacity Analysis Error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    report_text = format_capacity_report(analysis)
    console.print(report_text)

    if output is not None:
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(report_text, encoding="utf-8")
            console.print(f"\n[green]Saved capacity analysis to {output}[/green]")
        except Exception as exc:
            console.print(f"[bold red]Failed to save capacity report:[/bold red] {exc}")


@app.command()
def report(
    experiment_dir: Path = typer.Argument(..., help="Path to experiment results directory or report.md"),
) -> None:
    """Display the markdown report and analysis for a completed experiment directory."""
    exp_path = Path(experiment_dir)
    report_file = exp_path / "report.md" if exp_path.is_dir() else exp_path
    if not report_file.is_file():
        console.print(f"[bold red]Report file not found:[/bold red] {report_file}")
        raise typer.Exit(code=1)

    from rich.markdown import Markdown
    content = report_file.read_text(encoding="utf-8")
    console.print(Markdown(content))


@app.command()
def validate(
    config_file: Path = typer.Argument(..., help="Path to YAML configuration file to validate"),
) -> None:
    """Validate a YAML configuration file against the InferLoad schema."""
    try:
        # Check if it's an experiment or standard benchmark config
        import yaml
        with open(config_file, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        if isinstance(raw, dict) and "experiment" in raw and "sweep" in raw:
            from inferload.experiment_config import load_experiment_config
            exp_cfg = load_experiment_config(config_file)
            console.print(f"[bold green]Experiment configuration is valid![/bold green] ({config_file})")
            console.print(f"  Experiment: {exp_cfg.experiment.name}")
            console.print(f"  Target: {exp_cfg.target.base_url} (model: {exp_cfg.target.model})")
            console.print(f"  Sweep Concurrency: {exp_cfg.sweep.concurrency}")
            console.print(f"  Repetitions: {exp_cfg.sweep.repetitions}, Requests/point: {exp_cfg.sweep.requests_per_point}")
            return

        if isinstance(raw, dict) and "slo" in raw:
            from inferload.capacity import load_slo_config
            slo_cfg = load_slo_config(config_file)
            console.print(f"[bold green]SLO configuration is valid![/bold green] ({config_file})")
            if slo_cfg.max_ttft_p95_ms is not None:
                console.print(f"  TTFT p95 max: {slo_cfg.max_ttft_p95_ms} ms")
            if slo_cfg.max_total_latency_p95_ms is not None:
                console.print(f"  Total Latency p95 max: {slo_cfg.max_total_latency_p95_ms} ms")
            if slo_cfg.max_error_rate_pct is not None:
                console.print(f"  Error rate max: {slo_cfg.max_error_rate_pct}%")
            if slo_cfg.min_throughput_req_per_sec is not None:
                console.print(f"  Min throughput: {slo_cfg.min_throughput_req_per_sec} req/s")
            return


        cfg = load_config(config_file)
        console.print(f"[bold green]Configuration is valid![/bold green] ({config_file})")
        console.print(f"  Target: {cfg.target.base_url} (model: {cfg.target.model})")
        console.print(f"  Requests: {cfg.workload.requests}, Concurrency: {cfg.workload.concurrency}")
        console.print(f"  Streaming: {cfg.workload.stream}, Warmup: {cfg.execution.warmup_requests}")
        console.print(f"  Prompts: {len(cfg.workload.prompts)} defined")
    except Exception as exc:
        console.print(f"[bold red]Validation failed:[/bold red] {exc}")
        raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Display InferLoad version."""
    console.print(f"InferLoad version: {__version__}")


@app.command()
def web(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Bind host address"),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port number"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development"),
) -> None:
    """Start the local InferLoad Web UI and REST API server."""
    import uvicorn
    from inferload.web import app as fastapi_app

    console.print("\n[bold green]InferLoad Web UI[/bold green]")
    console.print("----------------")
    console.print(f"Running at: [bold cyan]http://{host}:{port}[/bold cyan]\n")
    console.print("[dim]Press Ctrl+C to terminate the web server.[/dim]\n")

    uvicorn.run(fastapi_app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    app()


