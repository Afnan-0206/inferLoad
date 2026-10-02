"""Benchmark orchestration and asynchronous concurrent runner."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import time
from typing import Callable
import uuid

import httpx

from inferload import __version__
from inferload.client import InferenceClient
from inferload.config import BenchmarkConfig
from inferload.environment import capture_environment_metadata
from inferload.metrics import aggregate_benchmark_results
from inferload.models import BenchmarkResult, RequestRecord, RequestSpec
from inferload.workload import WorkloadGenerator


class BenchmarkRunner:
    """Orchestrates warmup, controlled concurrency execution, and result aggregation."""

    def __init__(
        self,
        config: BenchmarkConfig,
        http_client: httpx.AsyncClient | None = None,
        run_id: str | None = None,
    ) -> None:
        self.config = config
        self._external_client = http_client
        self._custom_run_id = run_id
        self.workload_generator = WorkloadGenerator(config)

    async def run(
        self,
        progress_callback: Callable[[RequestRecord, int, int], None] | None = None,
    ) -> BenchmarkResult:
        """Execute the configured benchmark run and return structured results."""
        client_to_use = self._external_client
        owns_client = False

        if client_to_use is None:
            if self.config.arrival.mode == "rate":
                # In open-loop mode, allow unbounded concurrent connections so the time-driven
                # scheduler is never artificially throttled by client-side socket pool exhaustion.
                limits = httpx.Limits(
                    max_connections=None,
                    max_keepalive_connections=100,
                )
            else:
                concurrency = self.config.workload.concurrency
                limits = httpx.Limits(
                    max_connections=max(concurrency * 2, 10),
                    max_keepalive_connections=concurrency,
                )
            client_to_use = httpx.AsyncClient(
                limits=limits,
                timeout=self.config.target.timeout,
            )
            owns_client = True

        try:
            inference_client = InferenceClient(self.config.target, client=client_to_use)

            # 1. Warmup Phase (if configured)
            warmup_specs = self.workload_generator.generate_warmup_requests()
            if warmup_specs:
                await self._execute_specs_bounded(
                    warmup_specs,
                    inference_client,
                    client_to_use,
                    concurrency=min(self.config.workload.concurrency, len(warmup_specs)),
                )

            # 2. Benchmark Phase
            benchmark_specs = self.workload_generator.generate_benchmark_requests()
            num_requests = len(benchmark_specs)
            effective_concurrency = min(self.config.workload.concurrency, max(1, num_requests))

            t_start_perf = time.perf_counter()
            if self.config.arrival.mode == "rate":
                rate = self.config.arrival.requests_per_second or 1.0
                records = await self._execute_specs_open_loop(
                    benchmark_specs,
                    inference_client,
                    client_to_use,
                    rate=rate,
                    progress_callback=progress_callback,
                )
            else:
                records = await self._execute_specs_bounded(
                    benchmark_specs,
                    inference_client,
                    client_to_use,
                    concurrency=effective_concurrency,
                    progress_callback=progress_callback,
                )
            t_end_perf = time.perf_counter()
            total_duration_s = max(0.0001, t_end_perf - t_start_perf)

            # Sort records deterministically by request index
            records.sort(key=lambda r: r.index)

            # 3. Aggregate metrics
            summary = aggregate_benchmark_results(records, total_duration_s=total_duration_s)

            run_id = self._custom_run_id or f"run-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
            environment = capture_environment_metadata()
            result = BenchmarkResult(
                schema_version="0.1",
                run_id=run_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                inferload_version=__version__,
                endpoint=self.config.target.chat_completions_url,
                model=self.config.target.model,
                concurrency=self.config.workload.concurrency,
                request_count=self.config.workload.requests,
                warmup_count=self.config.execution.warmup_requests,
                warmup_requests=self.config.execution.warmup_requests,
                repetitions=1,
                max_tokens=self.config.workload.max_tokens,
                temperature=self.config.workload.temperature,
                seed=self.config.workload.seed,
                streaming=self.config.workload.stream,
                environment=environment,
                target=self.config.target.model_dump(),
                workload=self.config.workload.model_dump(),
                execution=self.config.execution.model_dump(),
                arrival=self.config.arrival.model_dump(),
                summary=summary,
                requests=records,
            )
            return result

        finally:
            if owns_client and client_to_use is not None:
                await client_to_use.aclose()

    async def _execute_specs_bounded(
        self,
        specs: list[RequestSpec],
        inference_client: InferenceClient,
        http_client: httpx.AsyncClient,
        concurrency: int,
        progress_callback: Callable[[RequestRecord, int, int], None] | None = None,
    ) -> list[RequestRecord]:
        """Execute request specs with strict bounded concurrency using an asyncio.Queue worker pool."""
        queue: asyncio.Queue[RequestSpec] = asyncio.Queue()
        for spec in specs:
            queue.put_nowait(spec)

        records: list[RequestRecord] = []
        lock = asyncio.Lock()
        total_count = len(specs)
        completed_count = 0

        async def worker() -> None:
            nonlocal completed_count
            while True:
                try:
                    spec = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                try:
                    record = await inference_client.execute_request(spec, client=http_client)
                except Exception as exc:
                    now = time.time()
                    record = RequestRecord(
                        request_id=spec.request_id,
                        index=spec.index,
                        is_warmup=spec.is_warmup,
                        prompt=spec.prompt,
                        start_time=now,
                        end_time=now,
                        duration_ms=0.0,
                        status="error",
                        input_text_length=len(spec.prompt),
                        streaming=spec.stream,
                        error_type=type(exc).__name__,
                        error_message=str(exc) or "Unhandled exception during request execution",
                    )

                async with lock:
                    records.append(record)
                    completed_count += 1
                    current_completed = completed_count

                if progress_callback:
                    progress_callback(record, current_completed, total_count)

                queue.task_done()

                if self.config.execution.delay_between_requests_ms > 0:
                    await asyncio.sleep(self.config.execution.delay_between_requests_ms / 1000.0)

        workers = [asyncio.create_task(worker()) for _ in range(concurrency)]
        await asyncio.gather(*workers)
        return records

    async def _execute_specs_open_loop(
        self,
        specs: list[RequestSpec],
        inference_client: InferenceClient,
        http_client: httpx.AsyncClient,
        rate: float,
        progress_callback: Callable[[RequestRecord, int, int], None] | None = None,
    ) -> list[RequestRecord]:
        """Dispatch requests according to an open-loop constant arrival rate process.

        Requests are scheduled to start at fixed intervals (1/rate) regardless of whether
        prior requests have completed.
        """
        interval = 1.0 / rate
        total_count = len(specs)
        records: list[RequestRecord] = []
        lock = asyncio.Lock()
        completed_count = 0

        async def run_single(spec: RequestSpec) -> None:
            nonlocal completed_count
            try:
                record = await inference_client.execute_request(spec, client=http_client)
            except Exception as exc:
                now = time.time()
                record = RequestRecord(
                    request_id=spec.request_id,
                    index=spec.index,
                    is_warmup=spec.is_warmup,
                    prompt=spec.prompt,
                    start_time=now,
                    end_time=now,
                    duration_ms=0.0,
                    status="error",
                    input_text_length=len(spec.prompt),
                    streaming=spec.stream,
                    error_type=type(exc).__name__,
                    error_message=str(exc) or "Unhandled exception during open-loop execution",
                )
            async with lock:
                records.append(record)
                completed_count += 1
                curr = completed_count
            if progress_callback:
                progress_callback(record, curr, total_count)

        tasks: list[asyncio.Task] = []
        t0 = time.perf_counter()
        for i, spec in enumerate(specs):
            target_start = t0 + (i * interval)
            now = time.perf_counter()
            delay = target_start - now
            if delay > 0:
                await asyncio.sleep(delay)
            task = asyncio.create_task(run_single(spec))
            tasks.append(task)

        await asyncio.gather(*tasks)
        return records

