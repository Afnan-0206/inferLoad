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
import hmac
import os
from pathlib import Path
import time
from typing import Any, AsyncGenerator
import uuid

from fastapi import (
    FastAPI,
    HTTPException,
    BackgroundTasks,
    Request,
    WebSocket,
    WebSocketDisconnect,
    Depends,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, Response
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
    logs: list[str] = Field(default_factory=list)


# In-memory job repository & event subscriber channels
_jobs: dict[str, ExperimentJobState] = {}
_jobs_lock = asyncio.Lock()

_job_subscribers: dict[str, set[asyncio.Queue]] = {}
_job_subscribers_lock = asyncio.Lock()


async def _register_subscriber(job_id: str) -> asyncio.Queue:
    """Register an asynchronous queue to receive live real-time benchmark events."""
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    async with _job_subscribers_lock:
        if job_id not in _job_subscribers:
            _job_subscribers[job_id] = set()
        _job_subscribers[job_id].add(q)
    return q


async def _unregister_subscriber(job_id: str, q: asyncio.Queue) -> None:
    """Safely unregister an event subscriber queue."""
    async with _job_subscribers_lock:
        if job_id in _job_subscribers:
            _job_subscribers[job_id].discard(q)
            if not _job_subscribers[job_id]:
                del _job_subscribers[job_id]


async def _broadcast_job_event(job_id: str, event_data: dict[str, Any]) -> None:
    """Broadcast an event payload to all active WebSocket and SSE subscribers for a job."""
    async with _job_subscribers_lock:
        subscribers = list(_job_subscribers.get(job_id, set()))
    for q in subscribers:
        try:
            q.put_nowait(event_data)
        except asyncio.QueueFull:
            pass
        except Exception:
            pass


# Authentication & RBAC helpers
def get_auth_token_from_request(request: Request) -> str | None:
    """Extract Bearer token or custom header from incoming HTTP request."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    custom_header = request.headers.get("X-InferLoad-Token")
    if custom_header:
        return custom_header.strip()
    return None


def require_auth(request: Request) -> dict[str, Any]:
    """Dependency that enforces API token authorization if INFERLOAD_AUTH_TOKEN is configured."""
    configured_token = os.environ.get("INFERLOAD_AUTH_TOKEN", "").strip()
    if not configured_token:
        return {"auth_required": False, "authenticated": True, "role": "admin"}

    provided = get_auth_token_from_request(request)
    if not provided or not hmac.compare_digest(provided, configured_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Valid InferLoad API Bearer token required. Provide Authorization: Bearer <token>.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"auth_required": True, "authenticated": True, "role": "admin"}


def _resolve_artifacts_dir(job_id: str) -> Path | None:
    """Resolve artifacts directory for either an active in-memory job or a historical run."""
    if job_id in _jobs and _jobs[job_id].artifacts_dir:
        p = Path(_jobs[job_id].artifacts_dir).resolve()
        if p.is_dir():
            return p

    dir_name = job_id[len("historical-"):] if job_id.startswith("historical-") else job_id
    results_base = Path("results").resolve()
    cand = (results_base / dir_name).resolve()
    if cand.is_relative_to(results_base) and cand.is_dir():
        return cand
    return None


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
    """Execute the experiment runner in the background and stream progress in real time."""
    def _log(msg: str) -> None:
        t_str = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{t_str}] {msg}"
        if job_id in _jobs:
            _jobs[job_id].logs.append(formatted)
        try:
            asyncio.create_task(_broadcast_job_event(job_id, {"type": "log", "message": formatted}))
        except Exception:
            pass

    try:
        async with _jobs_lock:
            if job_id not in _jobs:
                return
            _jobs[job_id].status = JobStatus.RUNNING
            _jobs[job_id].start_time = time.time()
            _log(f"Benchmark job started. Target: {exp_config.target.base_url} (Model: {exp_config.target.model})")
            _log(f"Concurrency sweep: {exp_config.sweep.concurrency}, Repetitions: {exp_config.sweep.repetitions}, Requests/point: {exp_config.sweep.requests_per_point}")

        await _broadcast_job_event(job_id, {
            "type": "status",
            "status": "running",
            "start_time": _jobs[job_id].start_time,
            "target": exp_config.target.base_url,
            "model": exp_config.target.model,
        })

        runner = ExperimentRunner(exp_config)

        def on_progress(trial_id: str, current: int, total: int) -> None:
            if job_id in _jobs:
                now_elapsed = round(time.time() - _jobs[job_id].start_time, 1)
                _jobs[job_id].current_trial = trial_id
                _jobs[job_id].progress_current = current
                _jobs[job_id].progress_total = total
                _jobs[job_id].elapsed_seconds = now_elapsed
                _log(f"Running trial [{current}/{total}]: {trial_id}")
                try:
                    asyncio.create_task(_broadcast_job_event(job_id, {
                        "type": "progress",
                        "trial_id": trial_id,
                        "current": current,
                        "total": total,
                        "elapsed_seconds": now_elapsed,
                    }))
                except Exception:
                    pass

        exp_result, exp_dir = await runner.run(progress_callback=on_progress)
        _log("Trials complete. Evaluating SLO capacity compliance constraints...")
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
            comp = capacity_res.highest_compliant_concurrency
            _log(f"Experiment completed. Highest compliant concurrency: {comp if comp is not None else 'None'}")

        await _broadcast_job_event(job_id, {
            "type": "completed",
            "job": _jobs[job_id].model_dump(),
        })
    except Exception as exc:
        logger.exception("Experiment job %s failed", job_id)
        _log(f"Experiment failed: {exc}")
        async with _jobs_lock:
            job = _jobs[job_id]
            job.status = JobStatus.FAILED
            job.elapsed_seconds = round(time.time() - job.start_time, 1) if job.start_time > 0 else 0.0
            job.error = str(exc) or type(exc).__name__

        await _broadcast_job_event(job_id, {
            "type": "failed",
            "error": str(exc),
            "elapsed_seconds": _jobs[job_id].elapsed_seconds,
        })


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

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        ico_path = static_dir / "favicon.ico"
        if ico_path.is_file():
            return FileResponse(ico_path, media_type="image/x-icon")
        svg_path = static_dir / "favicon.svg"
        if svg_path.is_file():
            return FileResponse(svg_path, media_type="image/svg+xml")
        return Response(status_code=204)

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

    async def _do_validate_configuration(req: WebBenchmarkRequest) -> dict[str, Any]:
        """Internal helper to validate benchmark configuration and endpoint reachability."""
        errors: list[str] = []

        if not req.base_url or not (req.base_url.startswith(("http://", "https://", "/"))):
            errors.append("Target endpoint must be a valid HTTP/HTTPS URL or local path (e.g. http://127.0.0.1:11434/v1 or /mock/v1).")

        # Resolve relative URLs like /mock/v1 to local server address if relative
        effective_base_url = req.base_url
        if effective_base_url.startswith("/"):
            effective_base_url = f"http://127.0.0.1:8000{effective_base_url}"

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
            return {"valid": False, "errors": errors, "endpoint_reachable": False, "endpoint_detail": "Configuration validation failed"}

        # Live reachability check
        endpoint_reachable = False
        endpoint_detail = "Unknown"
        try:
            t0 = time.perf_counter()
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.get(effective_base_url.rstrip("/") + "/models")
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
                endpoint_reachable = resp.status_code in [200, 401, 403, 404]
                endpoint_detail = f"Reachable - HTTP {resp.status_code} ({elapsed_ms}ms)"
        except Exception:
            try:
                t0 = time.perf_counter()
                async with httpx.AsyncClient(timeout=1.5) as client:
                    resp = await client.get(effective_base_url)
                    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
                    endpoint_reachable = True
                    endpoint_detail = f"Reachable - HTTP {resp.status_code} ({elapsed_ms}ms)"
            except Exception as e:
                endpoint_detail = f"Unreachable ({type(e).__name__})"

        try:
            req_copy = req.model_copy()
            if req_copy.base_url.startswith("/"):
                req_copy.base_url = effective_base_url
            build_experiment_config(req_copy)
            return {
                "valid": True,
                "errors": [],
                "endpoint_reachable": endpoint_reachable,
                "endpoint_detail": endpoint_detail,
            }
        except Exception as exc:
            return {
                "valid": False,
                "errors": [str(exc)],
                "endpoint_reachable": endpoint_reachable,
                "endpoint_detail": endpoint_detail,
            }

    @app.get("/api/auth/status")
    async def get_auth_status(request: Request) -> dict[str, Any]:
        """Return RBAC status and indicate whether an API token is required or verified."""
        configured_token = os.environ.get("INFERLOAD_AUTH_TOKEN", "").strip()
        if not configured_token:
            return {
                "auth_required": False,
                "authenticated": True,
                "mode": "permissive",
                "message": "Open / Single-tenant mode (no server token configured).",
            }
        provided = get_auth_token_from_request(request)
        is_valid = bool(provided and hmac.compare_digest(provided, configured_token))
        return {
            "auth_required": True,
            "authenticated": is_valid,
            "mode": "token",
            "message": "Admin access verified via API token." if is_valid else "Token required for benchmark mutation endpoints.",
        }

    @app.post("/api/validate")
    async def validate_configuration(
        req: WebBenchmarkRequest,
        _auth: dict[str, Any] = Depends(require_auth),
    ) -> dict[str, Any]:
        """Validate a benchmark configuration and check endpoint reachability."""
        return await _do_validate_configuration(req)

    @app.post("/api/telemetry/test")
    async def test_telemetry_endpoint(
        request: Request,
        _auth: dict[str, Any] = Depends(require_auth),
    ) -> dict[str, Any]:
        """Test reachability and scrapability of a Prometheus telemetry endpoint."""
        body = await request.json()
        metrics_url = body.get("metrics_url", "").strip()
        if not metrics_url or not metrics_url.startswith(("http://", "https://")):
            return {"valid": False, "error": "Invalid metrics URL provided. Must start with http:// or https://"}

        try:
            t0 = time.perf_counter()
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(metrics_url)
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
                if resp.status_code != 200:
                    return {
                        "valid": False,
                        "status_code": resp.status_code,
                        "error": f"Endpoint returned HTTP {resp.status_code} ({elapsed_ms}ms)",
                    }
                from inferload.server_telemetry import parse_prometheus_text, extract_telemetry_metrics
                parsed = parse_prometheus_text(resp.text)
                snapshot = extract_telemetry_metrics(parsed)
                return {
                    "valid": True,
                    "status_code": 200,
                    "latency_ms": elapsed_ms,
                    "parsed_metrics_count": len(parsed),
                    "snapshot": snapshot.model_dump(),
                }
        except Exception as exc:
            return {"valid": False, "error": f"Failed to connect: {exc}"}

    @app.post("/api/experiments", status_code=status.HTTP_202_ACCEPTED)
    async def start_experiment(
        req: WebBenchmarkRequest,
        background_tasks: BackgroundTasks,
        _auth: dict[str, Any] = Depends(require_auth),
    ) -> dict[str, Any]:
        """Validate config and start an experiment runner in the background."""
        val_res = await _do_validate_configuration(req)
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

    @app.websocket("/ws/experiments/{job_id}")
    async def experiment_websocket(websocket: WebSocket, job_id: str) -> None:
        """Real-time bi-directional WebSocket connection for instant trial and log streaming."""
        await websocket.accept()
        if job_id not in _jobs:
            await websocket.send_json({"type": "error", "message": f"Experiment job '{job_id}' not found."})
            await websocket.close()
            return

        job = _jobs[job_id]
        # Emit initial current state snapshot
        await websocket.send_json({
            "type": "initial_state",
            "job": job.model_dump(),
        })

        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            await websocket.close()
            return

        queue = await _register_subscriber(job_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    await websocket.send_json(event)
                    if event.get("type") in ("completed", "failed"):
                        break
                except asyncio.TimeoutError:
                    # Keep-alive heartbeat
                    await websocket.send_json({"type": "ping", "timestamp": time.time()})
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.debug("WebSocket client disconnected for %s: %s", job_id, exc)
        finally:
            await _unregister_subscriber(job_id, queue)
            try:
                await websocket.close()
            except Exception:
                pass

    @app.get("/api/experiments/{job_id}/stream")
    async def experiment_sse_stream(job_id: str) -> StreamingResponse:
        """Server-Sent Events (SSE) streaming fallback for real-time benchmark updates."""
        if job_id not in _jobs:
            raise HTTPException(status_code=404, detail=f"Experiment job '{job_id}' not found.")

        async def event_generator() -> AsyncGenerator[str, None]:
            job = _jobs[job_id]
            yield f"data: {json.dumps({'type': 'initial_state', 'job': job.model_dump()})}\n\n"
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                return

            queue = await _register_subscriber(job_id)
            try:
                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=15.0)
                        yield f"data: {json.dumps(event)}\n\n"
                        if event.get("type") in ("completed", "failed"):
                            break
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
            finally:
                await _unregister_subscriber(job_id, queue)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @app.get("/api/experiments/{job_id}")
    async def get_experiment_status(job_id: str) -> dict[str, Any]:
        """Return the current execution state, progress, or completed results for a job."""
        if job_id not in _jobs:
            raise HTTPException(status_code=404, detail=f"Experiment job '{job_id}' not found.")

        job = _jobs[job_id]
        if job.status == JobStatus.RUNNING:
            job.elapsed_seconds = round(time.time() - job.start_time, 1)

        return job.model_dump()

    @app.get("/api/experiments/{job_id}/logs")
    async def get_experiment_logs(job_id: str) -> dict[str, Any]:
        """Return real-time execution logs for an active or completed experiment."""
        if job_id not in _jobs:
            raise HTTPException(status_code=404, detail=f"Experiment job '{job_id}' not found.")
        job = _jobs[job_id]
        return {
            "job_id": job.job_id,
            "status": job.status,
            "logs": job.logs,
            "progress_current": job.progress_current,
            "progress_total": job.progress_total,
            "current_trial": job.current_trial,
            "elapsed_seconds": round(time.time() - job.start_time, 1) if job.status == JobStatus.RUNNING else job.elapsed_seconds,
        }

    @app.get("/api/experiments/{job_id}/report")
    async def get_experiment_report(job_id: str) -> dict[str, Any]:
        """Return the markdown text of the report.md generated for an active or historical job."""
        artifacts_dir = _resolve_artifacts_dir(job_id)
        if not artifacts_dir:
            raise HTTPException(status_code=404, detail=f"Experiment '{job_id}' not found.")

        report_file = artifacts_dir / "report.md"
        if not report_file.is_file():
            raise HTTPException(status_code=404, detail="report.md not found in artifacts directory.")

        content = report_file.read_text(encoding="utf-8")
        return {"report_markdown": content}

    @app.get("/api/experiments/{job_id}/artifacts/{file_path:path}")
    async def get_experiment_artifact(job_id: str, file_path: str) -> FileResponse:
        """Safely serve an artifact file belonging to an active or historical experiment."""
        base_dir = _resolve_artifacts_dir(job_id)
        if not base_dir:
            raise HTTPException(status_code=404, detail=f"Experiment '{job_id}' not found.")

        target = (base_dir / file_path).resolve()

        # Check aliases and plots subdirectory if file not found directly
        if not (target.is_file() and target.is_relative_to(base_dir)):
            alias_map = {
                "plot_ttft.png": "plots/concurrency_vs_ttft_p95.png",
                "plot_latency.png": "plots/concurrency_vs_total_latency_p95.png",
                "plot_throughput.png": "plots/concurrency_vs_throughput.png",
                "plot_errors.png": "plots/concurrency_vs_error_rate.png",
                "concurrency_vs_ttft_p95.png": "plots/concurrency_vs_ttft_p95.png",
                "concurrency_vs_total_latency_p95.png": "plots/concurrency_vs_total_latency_p95.png",
                "concurrency_vs_throughput.png": "plots/concurrency_vs_throughput.png",
                "concurrency_vs_error_rate.png": "plots/concurrency_vs_error_rate.png",
            }
            cand_rel = alias_map.get(file_path) or f"plots/{file_path}"
            cand_target = (base_dir / cand_rel).resolve()
            if cand_target.is_file() and cand_target.is_relative_to(base_dir):
                target = cand_target

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

    # Built-in lightweight mock OpenAI-compatible inference endpoint for cloud demos
    @app.get("/mock/v1/models")
    async def mock_models() -> dict[str, Any]:
        """Return simulated models list."""
        return {
            "object": "list",
            "data": [
                {"id": "mock-llama3-8b", "object": "model", "owned_by": "inferload-mock"},
                {"id": "mock-qwen2.5-7b", "object": "model", "owned_by": "inferload-mock"},
            ],
        }

    @app.post("/mock/v1/chat/completions")
    async def mock_chat_completions(request: Request) -> Any:
        """Simulate realistic streaming or non-streaming LLM responses."""
        body = await request.json()
        is_stream = body.get("stream", False)
        max_tokens = min(body.get("max_tokens", 32), 128)
        model = body.get("model", "mock-llama3-8b")
        req_id = f"chatcmpl-mock-{uuid.uuid4().hex[:6]}"

        if not is_stream:
            await asyncio.sleep(0.08)  # TTFT delay
            return {
                "id": req_id,
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": "InferLoad simulated inference completion."},
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 12, "completion_tokens": max_tokens, "total_tokens": 12 + max_tokens},
            }

        async def generate_mock_stream() -> AsyncGenerator[str, None]:
            await asyncio.sleep(0.06)  # TTFT delay (~60ms)
            words = ["InferLoad", " verifies", " LLM", " server", " latency", " and", " throughput", " under", " concurrent", " load", "."]
            for i in range(min(max_tokens, len(words))):
                token = (" " if i > 0 else "") + words[i % len(words)]
                chunk = {
                    "id": req_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{"index": 0, "delta": {"content": token}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(chunk)}\n\n"
                await asyncio.sleep(0.015)  # Inter-token latency (~65 tok/s)

            final_chunk = {
                "id": req_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            yield f"data: {json.dumps(final_chunk)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(generate_mock_stream(), media_type="text/event-stream")

    # Mount results directory safely for historical artifact retrieval
    p_results = Path("results").resolve()
    try:
        p_results.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    if p_results.is_dir():
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
