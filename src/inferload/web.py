"""InferLoad Web Server and REST API.

Provides local browser UI endpoints for configuring workloads, executing
benchmarks, tracking live trial progress, evaluating SLO capacity, and
inspecting artifacts.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from enum import Enum
import json
import logging
from pathlib import Path
import time
from typing import Any
import uuid

from fastapi import FastAPI, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import httpx
from pydantic import BaseModel, Field

from inferload import __version__
from inferload.capacity import SLOConfig, analyze_capacity, format_capacity_report
from inferload.config import ArrivalConfig, ExecutionConfig, TargetConfig, TelemetryConfig
from inferload.environment import capture_environment_metadata
from inferload.experiment import ExperimentResult, ExperimentRunner
from inferload.experiment_config import (
    ExperimentConfig,
    ExperimentMeta,
    ExperimentWorkload,
    SweepDefinition,
)

logger = logging.getLogger("inferload.web")


# Web schemas
class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class WebBenchmarkRequest(BaseModel):
    """Payload submitted from the browser to configure and launch an experiment."""

    name: str = Field(default="web-sweep")
    description: str = Field(default="InferLoad benchmark launched via browser UI")
    output_dir: str = Field(default="results")

    # Target
    base_url: str = Field(default="http://127.0.0.1:11434/v1")
    model: str = Field(default="qwen2.5:0.5b")
    timeout: float = Field(default=60.0)
    api_key: str | None = None

    # Workload
    prompts: list[str] = Field(
        default_factory=lambda: [
            "What is a database index?",
            "What is a hash table?",
        ]
    )
    max_tokens: int = Field(default=32)
    temperature: float = Field(default=0.0)
    seed: int | None = Field(default=42)
    stream: bool = Field(default=True)

    # Sweep
    concurrency: list[int] = Field(default_factory=lambda: [1, 2, 4])
    repetitions: int = Field(default=2)
    requests_per_point: int = Field(default=5)

    # Execution
    warmup_requests: int = Field(default=1)

    # Arrival mode
    arrival_mode: str = Field(default="closed")
    requests_per_second: float | None = None

    # SLO constraints
    slo: SLOConfig = Field(
        default_factory=lambda: SLOConfig(
            max_ttft_p95_ms=1000.0,
            max_total_latency_p95_ms=2500.0,
            max_error_rate_pct=1.0,
            min_throughput_req_per_sec=1.0,
        )
    )

    # Optional server telemetry
    telemetry_enabled: bool = False
    telemetry_url: str | None = None
    telemetry_timeout: float = 2.0


class ExperimentJobState(BaseModel):
    """State tracking for a background benchmark experiment."""

    job_id: str
    experiment_id: str | None = None
    status: JobStatus = JobStatus.PENDING
    progress_current: int = 0
    progress_total: int = 0
    current_trial: str = ""
    start_time: float = 0.0
    elapsed_seconds: float = 0.0
    error: str | None = None
    result: dict[str, Any] | None = None
    capacity: dict[str, Any] | None = None
    artifacts_dir: str | None = None
    plots: list[str] = Field(default_factory=list)


# In-memory job repository
_jobs: dict[str, ExperimentJobState] = {}
_jobs_lock = asyncio.Lock()


def build_experiment_config(req: WebBenchmarkRequest) -> tuple[ExperimentConfig, SLOConfig]:
    """Convert web request into canonical ExperimentConfig and SLOConfig instances."""
    exp_cfg = ExperimentConfig(
        experiment=ExperimentMeta(
            name=req.name.strip() or "web-sweep",
            description=req.description,
            output_dir=req.output_dir,
        ),
        target=TargetConfig(
            base_url=req.base_url.strip(),
            model=req.model.strip(),
            timeout=req.timeout,
            api_key=req.api_key,
        ),
        workload=ExperimentWorkload(
            prompts=req.prompts if req.prompts else ["Explain latency versus throughput."],
            max_tokens=req.max_tokens,
            temperature=req.temperature,
            seed=req.seed,
            stream=req.stream,
        ),
        sweep=SweepDefinition(
            concurrency=req.concurrency if req.concurrency else [1],
            repetitions=max(1, req.repetitions),
            requests_per_point=max(1, req.requests_per_point),
        ),
        execution=ExecutionConfig(
            warmup_requests=max(0, req.warmup_requests),
            streaming=req.stream,
        ),
        arrival=ArrivalConfig(
            mode=req.arrival_mode,
            requests_per_second=req.requests_per_second,
        ),
        telemetry=TelemetryConfig(
            enabled=req.telemetry_enabled,
            metrics_url=req.telemetry_url,
            timeout=req.telemetry_timeout,
        ),
    )
    return exp_cfg, req.slo


async def _run_experiment_task(
    job_id: str,
    exp_config: ExperimentConfig,
    slo_config: SLOConfig,
) -> None:
    """Execute the experiment runner in the background and update job state."""
    async with _jobs_lock:
        if job_id not in _jobs:
            return
        _jobs[job_id].status = JobStatus.RUNNING
        _jobs[job_id].start_time = time.time()

    runner = ExperimentRunner(exp_config)

    def on_progress(trial_id: str, current: int, total: int) -> None:
        if job_id in _jobs:
            _jobs[job_id].current_trial = trial_id
            _jobs[job_id].progress_current = current
            _jobs[job_id].progress_total = total
            _jobs[job_id].elapsed_seconds = round(time.time() - _jobs[job_id].start_time, 1)

    try:
        exp_result, exp_dir = await runner.run(progress_callback=on_progress)
        capacity_res = analyze_capacity(exp_result, slo_config)

        # Detect generated plots
        plots_dir = exp_dir / "plots"
        plot_names: list[str] = []
        if plots_dir.is_dir():
            for p in sorted(plots_dir.glob("*.png")):
                plot_names.append(p.name)

        async with _jobs_lock:
            job = _jobs[job_id]
            job.status = JobStatus.COMPLETED
            job.experiment_id = exp_result.experiment_id
            job.elapsed_seconds = round(time.time() - job.start_time, 1)
            job.artifacts_dir = str(exp_dir)
            job.result = exp_result.model_dump(mode="json")
            job.capacity = capacity_res.model_dump(mode="json")
            job.plots = plot_names
    except Exception as exc:
        logger.exception("Experiment job %s failed", job_id)
        async with _jobs_lock:
            job = _jobs[job_id]
            job.status = JobStatus.FAILED
            job.elapsed_seconds = round(time.time() - job.start_time, 1) if job.start_time > 0 else 0.0
            job.error = str(exc) or type(exc).__name__


def create_app() -> FastAPI:
    """Create and configure the FastAPI web application."""
    app = FastAPI(
        title="InferLoad Web Console",
        description="LLM Inference Load Testing & Capacity Laboratory Web Interface",
        version=__version__,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def get_health() -> dict[str, Any]:
        """Return system health, host environment, and local server availability."""
        env = capture_environment_metadata()

        # Check local Ollama endpoint
        ollama_status = {"available": False, "models": []}
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.get("http://127.0.0.1:11434/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                    ollama_status = {"available": True, "models": models}
        except Exception:
            pass

        return {
            "status": "ok",
            "inferload_version": __version__,
            "environment": env.model_dump(),
            "ollama": ollama_status,
        }

    @app.post("/api/validate")
    async def validate_configuration(req: WebBenchmarkRequest) -> dict[str, Any]:
        """Validate a benchmark configuration without executing it."""
        errors: list[str] = []

        if not req.base_url or not req.base_url.startswith(("http://", "https://")):
            errors.append("Target endpoint must be a valid HTTP or HTTPS URL (e.g. http://127.0.0.1:11434/v1).")

        if not req.model or not req.model.strip():
            errors.append("Model name is required.")

        if not req.concurrency:
            errors.append("At least one concurrency level must be specified (e.g. [1, 2, 4]).")
        else:
            for c in req.concurrency:
                if c < 1:
                    errors.append(f"Concurrency levels must be positive integers (got {c}).")

        if req.requests_per_point < 1:
            errors.append("Requests per point must be at least 1.")

        if req.repetitions < 1:
            errors.append("Repetitions must be at least 1.")

        if not req.prompts or all(not p.strip() for p in req.prompts):
            errors.append("At least one non-empty benchmark prompt is required.")

        if errors:
            return {"valid": False, "errors": errors}

        try:
            build_experiment_config(req)
            return {"valid": True, "errors": []}
        except Exception as exc:
            return {"valid": False, "errors": [str(exc)]}

    @app.post("/api/experiments", status_code=status.HTTP_202_ACCEPTED)
    async def start_experiment(
        req: WebBenchmarkRequest,
        background_tasks: BackgroundTasks,
    ) -> dict[str, Any]:
        """Validate config and start an experiment runner in the background."""
        val_res = await validate_configuration(req)
        if not val_res["valid"]:
            raise HTTPException(status_code=400, detail={"errors": val_res["errors"]})

        exp_config, slo_config = build_experiment_config(req)
        job_id = f"job-{uuid.uuid4().hex[:8]}"

        job_state = ExperimentJobState(
            job_id=job_id,
            status=JobStatus.PENDING,
            start_time=time.time(),
        )

        async with _jobs_lock:
            _jobs[job_id] = job_state

        background_tasks.add_task(_run_experiment_task, job_id, exp_config, slo_config)

        return {
            "job_id": job_id,
            "status": "pending",
            "message": "Benchmark experiment accepted and queued for execution.",
        }

    @app.get("/api/experiments/{job_id}")
    async def get_experiment_status(job_id: str) -> dict[str, Any]:
        """Return the current execution state, progress, or completed results for a job."""
        if job_id not in _jobs:
            raise HTTPException(status_code=404, detail=f"Experiment job '{job_id}' not found.")

        job = _jobs[job_id]
        if job.status == JobStatus.RUNNING:
            job.elapsed_seconds = round(time.time() - job.start_time, 1)

        return job.model_dump()

    @app.get("/api/experiments/{job_id}/report")
    async def get_experiment_report(job_id: str) -> dict[str, Any]:
        """Return the markdown text of the report.md generated for this job."""
        if job_id not in _jobs:
            raise HTTPException(status_code=404, detail=f"Experiment job '{job_id}' not found.")

        job = _jobs[job_id]
        if not job.artifacts_dir:
            raise HTTPException(status_code=400, detail="Experiment has not generated artifacts yet.")

        report_file = Path(job.artifacts_dir) / "report.md"
        if not report_file.is_file():
            raise HTTPException(status_code=404, detail="report.md not found in artifacts directory.")

        content = report_file.read_text(encoding="utf-8")
        return {"report_markdown": content}

    @app.get("/api/experiments/{job_id}/artifacts/{file_path:path}")
    async def get_experiment_artifact(job_id: str, file_path: str) -> FileResponse:
        """Safely serve an artifact file belonging to this experiment."""
        if job_id not in _jobs:
            raise HTTPException(status_code=404, detail=f"Experiment job '{job_id}' not found.")

        job = _jobs[job_id]
        if not job.artifacts_dir:
            raise HTTPException(status_code=400, detail="Experiment artifacts directory not available.")

        base_dir = Path(job.artifacts_dir).resolve()
        target = (base_dir / file_path).resolve()

        # Strict security constraint: prevent path traversal outside the experiment directory
        if not target.is_relative_to(base_dir):
            raise HTTPException(status_code=403, detail="Access denied: path traversal detected.")

        if not target.is_file():
            raise HTTPException(status_code=404, detail=f"Artifact file not found: {file_path}")

        media_type = "application/json" if target.suffix == ".json" else "text/markdown" if target.suffix == ".md" else "text/csv" if target.suffix == ".csv" else "image/png" if target.suffix == ".png" else "application/octet-stream"
        return FileResponse(target, media_type=media_type)

    @app.get("/api/history")
    async def list_experiment_history(results_dir: str = "results") -> list[dict[str, Any]]:
        """Scan the results directory for historical experiments and return summary descriptors."""
        p_res = Path(results_dir)
        if not p_res.is_dir():
            return []

        history: list[dict[str, Any]] = []
        for exp_dir in p_res.iterdir():
            if not exp_dir.is_dir() or not exp_dir.name.startswith("experiment-"):
                continue

            summary_file = exp_dir / "summary.json"
            if not summary_file.is_file():
                continue

            try:
                data = json.loads(summary_file.read_text(encoding="utf-8"))
                exp_res = ExperimentResult.model_validate(data)

                # Default reference SLO assessment
                ref_slo = SLOConfig(max_ttft_p95_ms=1000.0, max_total_latency_p95_ms=2500.0, max_error_rate_pct=1.0, min_throughput_req_per_sec=1.0)
                cap = analyze_capacity(exp_res, ref_slo)

                history.append({
                    "experiment_id": exp_res.experiment_id,
                    "name": exp_res.name,
                    "timestamp": exp_res.timestamp,
                    "model": exp_res.model,
                    "endpoint": exp_res.endpoint,
                    "concurrency_levels": exp_res.concurrency_levels,
                    "repetitions": exp_res.repetitions,
                    "requests_per_point": exp_res.requests_per_point,
                    "highest_compliant_concurrency": cap.highest_compliant_concurrency,
                    "dir_name": exp_dir.name,
                })
            except Exception:
                continue

        # Sort newest first
        history.sort(key=lambda x: x["timestamp"], reverse=True)
        return history

    @app.get("/api/history/{dir_name}")
    async def get_historical_experiment(dir_name: str, results_dir: str = "results") -> dict[str, Any]:
        """Load and return an existing historical experiment from results directory."""
        p_res = Path(results_dir).resolve()
        exp_dir = (p_res / dir_name).resolve()

        if not exp_dir.is_relative_to(p_res) or not exp_dir.is_dir():
            raise HTTPException(status_code=404, detail="Historical experiment directory not found.")

        summary_file = exp_dir / "summary.json"
        if not summary_file.is_file():
            raise HTTPException(status_code=404, detail="summary.json missing in historical experiment.")

        try:
            data = json.loads(summary_file.read_text(encoding="utf-8"))
            exp_res = ExperimentResult.model_validate(data)
            ref_slo = SLOConfig(max_ttft_p95_ms=1000.0, max_total_latency_p95_ms=2500.0, max_error_rate_pct=1.0, min_throughput_req_per_sec=1.0)
            cap = analyze_capacity(exp_res, ref_slo)

            plots_dir = exp_dir / "plots"
            plot_names = [p.name for p in sorted(plots_dir.glob("*.png"))] if plots_dir.is_dir() else []

            report_file = exp_dir / "report.md"
            report_md = report_file.read_text(encoding="utf-8") if report_file.is_file() else ""

            return {
                "experiment_id": exp_res.experiment_id,
                "artifacts_dir": str(exp_dir),
                "result": exp_res.model_dump(mode="json"),
                "capacity": cap.model_dump(mode="json"),
                "plots": plot_names,
                "report_markdown": report_md,
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to parse historical experiment: {exc}")

    # Mount results directory safely for historical artifact retrieval
    p_results = Path("results").resolve()
    p_results.mkdir(parents=True, exist_ok=True)
    app.mount("/results", StaticFiles(directory=str(p_results)), name="results")

    # Mount static assets
    static_dir = Path(__file__).parent / "web_static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/")
        async def serve_index() -> FileResponse:
            index_path = static_dir / "index.html"
            if index_path.is_file():
                return FileResponse(index_path, media_type="text/html")
            raise HTTPException(status_code=404, detail="index.html not found.")

    return app


app = create_app()
