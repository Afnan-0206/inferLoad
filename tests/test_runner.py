"""Tests for benchmark runner and client execution using mocked HTTP transport."""

import asyncio
import json
import pytest
import httpx

from inferload.config import BenchmarkConfig, ExecutionConfig, TargetConfig, WorkloadConfig
from inferload.runner import BenchmarkRunner
from tests.fixtures.mock_responses import make_chat_completion_json, make_sse_stream_chunks


@pytest.mark.asyncio
async def test_successful_non_streaming_request() -> None:
    expected_content = "Databases use indexes to quickly locate data."
    mock_payload = make_chat_completion_json(content=expected_content, prompt_tokens=10, completion_tokens=8)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        req_data = json.loads(request.content.decode("utf-8"))
        assert req_data["stream"] is False
        assert req_data["model"] == "mock-model"
        return httpx.Response(200, json=mock_payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        config = BenchmarkConfig(
            target=TargetConfig(base_url="http://localhost:8000/v1", model="mock-model"),
            workload=WorkloadConfig(
                requests=2,
                concurrency=1,
                stream=False,
                prompts=["Explain database indexing"],
            ),
        )
        runner = BenchmarkRunner(config, http_client=http_client)
        result = await runner.run()

    assert result.summary.total_requests == 2
    assert result.summary.success_count == 2
    assert result.summary.failure_count == 0
    assert result.summary.error_rate == 0.0

    for req in result.requests:
        assert req.status == "success"
        assert req.http_status == 200
        assert req.output_text == expected_content
        assert req.input_tokens == 10
        assert req.output_tokens == 8
        assert req.latency_to_first_token_ms is None  # Non-streaming cannot isolate TTFT
        assert req.total_latency_ms > 0


@pytest.mark.asyncio
async def test_successful_streaming_request() -> None:
    tokens = ["Hello", " ", "world", "!"]
    sse_lines = make_sse_stream_chunks(tokens, prompt_tokens=8, completion_tokens=4)
    sse_bytes = "".join(sse_lines).encode("utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        req_data = json.loads(request.content.decode("utf-8"))
        assert req_data["stream"] is True
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            content=sse_bytes,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        config = BenchmarkConfig(
            target=TargetConfig(base_url="http://localhost:8000/v1", model="mock-model"),
            workload=WorkloadConfig(
                requests=3,
                concurrency=2,
                stream=True,
                prompts=["Say hello world"],
            ),
        )
        runner = BenchmarkRunner(config, http_client=http_client)
        result = await runner.run()

    assert result.summary.total_requests == 3
    assert result.summary.success_count == 3
    assert result.summary.ttft_ms is not None
    assert result.summary.ttft_ms.count == 3

    for req in result.requests:
        assert req.status == "success"
        assert req.output_text == "Hello world!"
        assert req.chunk_count == 4
        assert req.latency_to_first_token_ms is not None
        assert req.latency_to_first_token_ms > 0
        assert req.input_tokens == 8
        assert req.output_tokens == 4


@pytest.mark.asyncio
async def test_concurrency_limits() -> None:
    max_active_observed = 0
    active_requests = 0
    lock = asyncio.Lock()

    async def async_handler(request: httpx.Request) -> httpx.Response:
        nonlocal max_active_observed, active_requests
        async with lock:
            active_requests += 1
            if active_requests > max_active_observed:
                max_active_observed = active_requests

        # Small sleep to simulate server processing time
        await asyncio.sleep(0.03)

        async with lock:
            active_requests -= 1

        mock_payload = make_chat_completion_json(content="concurrency test")
        return httpx.Response(200, json=mock_payload)

    # Use custom transport with async handler
    transport = httpx.MockTransport(async_handler)
    target_concurrency = 3
    async with httpx.AsyncClient(transport=transport) as http_client:
        config = BenchmarkConfig(
            target=TargetConfig(base_url="http://localhost:8000/v1", model="mock-model"),
            workload=WorkloadConfig(
                requests=12,
                concurrency=target_concurrency,
                stream=False,
                prompts=["Test prompt"],
            ),
        )
        runner = BenchmarkRunner(config, http_client=http_client)
        result = await runner.run()

    assert result.summary.total_requests == 12
    assert result.summary.success_count == 12
    # Verify concurrency never exceeded the target limit
    assert max_active_observed <= target_concurrency
    assert max_active_observed >= 2  # Ensured actual concurrency occurred


@pytest.mark.asyncio
async def test_timeout_handling() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Simulated read timeout from server")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        config = BenchmarkConfig(
            target=TargetConfig(base_url="http://localhost:8000/v1", model="mock-model", timeout=2.0),
            workload=WorkloadConfig(
                requests=2,
                concurrency=1,
                stream=True,
                prompts=["Prompt that will timeout"],
            ),
        )
        runner = BenchmarkRunner(config, http_client=http_client)
        result = await runner.run()

    assert result.summary.total_requests == 2
    assert result.summary.success_count == 0
    assert result.summary.failure_count == 2
    assert result.summary.error_rate == 1.0
    assert "ReadTimeout" in result.summary.error_breakdown

    for req in result.requests:
        assert req.status == "timeout"
        assert req.error_type == "ReadTimeout"
        assert "Simulated read timeout" in (req.error_message or "")


@pytest.mark.asyncio
async def test_http_error_handling() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b'{"error": "Internal Server Error"}')

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        config = BenchmarkConfig(
            target=TargetConfig(base_url="http://localhost:8000/v1", model="mock-model"),
            workload=WorkloadConfig(
                requests=3,
                concurrency=1,
                stream=True,
                prompts=["Prompt causing 500"],
            ),
        )
        runner = BenchmarkRunner(config, http_client=http_client)
        result = await runner.run()

    assert result.summary.total_requests == 3
    assert result.summary.success_count == 0
    assert result.summary.failure_count == 3
    assert result.summary.error_breakdown == {"HTTP_500": 3}

    for req in result.requests:
        assert req.status == "error"
        assert req.http_status == 500
        assert req.error_type == "HTTP_500"
        assert "Internal Server Error" in (req.error_message or "")


@pytest.mark.asyncio
async def test_malformed_streaming_chunk() -> None:
    # First chunk is valid SSE, second chunk has invalid JSON
    sse_text = (
        'data: {"id": "1", "choices": [{"delta": {"content": "First token"}}]}\n\n'
        'data: {INVALID_JSON_CORRUPTED_STREAM\n\n'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            content=sse_text.encode("utf-8"),
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        config = BenchmarkConfig(
            target=TargetConfig(base_url="http://localhost:8000/v1", model="mock-model"),
            workload=WorkloadConfig(
                requests=1,
                concurrency=1,
                stream=True,
                prompts=["Prompt with broken chunk"],
            ),
        )
        runner = BenchmarkRunner(config, http_client=http_client)
        result = await runner.run()

    assert result.summary.total_requests == 1
    assert result.summary.success_count == 0
    assert result.summary.failure_count == 1
    assert result.requests[0].status == "error"
    assert result.requests[0].error_type == "MalformedStreamChunk"
    assert "Malformed SSE JSON" in (result.requests[0].error_message or "")


@pytest.mark.asyncio
async def test_failed_request_accounting_and_warmup_isolation() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1

        # 2 warmup requests -> both succeed
        # request 1 -> 200 success
        # request 2 -> 429 rate limit
        # request 3 -> 200 success
        if call_count <= 2:
            return httpx.Response(200, json=make_chat_completion_json("warmup resp"))
        elif call_count == 3:
            return httpx.Response(200, json=make_chat_completion_json("success 1"))
        elif call_count == 4:
            return httpx.Response(429, content=b'{"error": "rate limit exceeded"}')
        else:
            return httpx.Response(200, json=make_chat_completion_json("success 2"))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        config = BenchmarkConfig(
            target=TargetConfig(base_url="http://localhost:8000/v1", model="mock-model"),
            workload=WorkloadConfig(
                requests=3,
                concurrency=1,
                stream=False,
                prompts=["P1", "P2", "P3"],
            ),
            execution=ExecutionConfig(warmup_requests=2),
        )
        runner = BenchmarkRunner(config, http_client=http_client)
        result = await runner.run()

    # Total HTTP calls = 2 warmup + 3 benchmark = 5
    assert call_count == 5

    # Summary only contains 3 benchmark requests!
    assert result.summary.total_requests == 3
    assert result.summary.success_count == 2
    assert result.summary.failure_count == 1
    assert pytest.approx(result.summary.error_rate, 0.01) == 0.333
    assert result.summary.error_breakdown == {"HTTP_429": 1}

    # None of the 3 requests was silently dropped
    assert len(result.requests) == 3
    assert [r.status for r in result.requests] == ["success", "error", "success"]


@pytest.mark.asyncio
async def test_benchmark_result_reproducibility_metadata() -> None:
    """Audit test: Verify all required reproducibility metadata fields are captured and backward compatible."""
    from inferload.models import BenchmarkResult

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=make_chat_completion_json("metadata test"))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        config = BenchmarkConfig(
            target=TargetConfig(base_url="http://localhost:8000/v1", model="test-meta-model"),
            workload=WorkloadConfig(
                requests=2,
                concurrency=1,
                stream=False,
                prompts=["Prompt"],
                max_tokens=64,
                temperature=0.0,
                seed=42,
            ),
            execution=ExecutionConfig(warmup_requests=1),
        )
        runner = BenchmarkRunner(config, http_client=http_client)
        result = await runner.run()

    # Verify all reproducibility fields
    assert result.model == "test-meta-model"
    assert result.endpoint == "http://localhost:8000/v1/chat/completions"
    assert result.timestamp is not None
    assert result.inferload_version == "0.1.0"
    assert result.concurrency == 1
    assert result.request_count == 2
    assert result.warmup_requests == 1
    assert result.repetitions == 1
    assert result.max_tokens == 64
    assert result.temperature == 0.0
    assert result.seed == 42
    assert result.streaming is False

    # Environment metadata
    assert result.environment is not None
    assert result.environment.os_system != ""
    assert result.environment.python_version != ""
    assert result.environment.cpu_architecture != ""
    assert hasattr(result.environment, "gpu_name")
    assert hasattr(result.environment, "gpu_count")
    assert hasattr(result.environment, "cuda_version")
    assert hasattr(result.environment, "driver_version")

    # Backwards compatibility: deserialize raw legacy dict missing 'environment' and new fields
    dump = result.model_dump(mode="json")
    del dump["environment"]
    del dump["seed"]
    legacy_result = BenchmarkResult.model_validate(dump)
    assert legacy_result.run_id == result.run_id
    assert legacy_result.environment is None


@pytest.mark.asyncio
async def test_open_loop_scheduler_time_driven() -> None:
    """Audit test: Verify open-loop scheduler launches requests at scheduled time intervals."""
    from inferload.config import ArrivalConfig

    call_times: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        call_times.append(asyncio.get_running_loop().time())
        return httpx.Response(200, json=make_chat_completion_json("open loop"))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        config = BenchmarkConfig(
            target=TargetConfig(base_url="http://localhost:8000/v1", model="test-model"),
            workload=WorkloadConfig(
                requests=3,
                concurrency=1,
                stream=False,
                prompts=["P1", "P2", "P3"],
            ),
            arrival=ArrivalConfig(mode="rate", requests_per_second=20.0),  # interval = 0.05s
        )
        runner = BenchmarkRunner(config, http_client=http_client)
        result = await runner.run()

    assert result.summary.total_requests == 3
    assert len(call_times) == 3
    # Verify intervals between consecutive requests are roughly ~0.05s
    delta1 = call_times[1] - call_times[0]
    delta2 = call_times[2] - call_times[1]
    assert 0.03 <= delta1 <= 0.15
    assert 0.03 <= delta2 <= 0.15


@pytest.mark.asyncio
async def test_runner_defensive_error_handling_uncaught_client_exception() -> None:
    """Audit test: Verify no failed request is dropped even if an unexpected exception occurs."""
    from unittest.mock import patch

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=make_chat_completion_json("ok"))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        config = BenchmarkConfig(
            target=TargetConfig(base_url="http://localhost:8000/v1", model="test-model"),
            workload=WorkloadConfig(
                requests=2,
                concurrency=1,
                stream=False,
                prompts=["P1", "P2"],
            ),
        )
        runner = BenchmarkRunner(config, http_client=http_client)

        # Force execute_request to raise an unexpected OSError
        with patch("inferload.client.InferenceClient.execute_request", side_effect=OSError("Socket failure")):
            result = await runner.run()

    assert result.summary.total_requests == 2
    assert result.summary.success_count == 0
    assert result.summary.failure_count == 2
    assert result.summary.error_rate == 1.0
    assert "OSError" in result.summary.error_breakdown
    assert len(result.requests) == 2
    assert result.requests[0].status == "error"
    assert "Socket failure" in (result.requests[0].error_message or "")
