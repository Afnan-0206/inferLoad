"""End-to-end integration tests using a real local HTTP server on loopback."""

import pytest

from inferload.config import BenchmarkConfig, ExecutionConfig, TargetConfig, WorkloadConfig
from inferload.runner import BenchmarkRunner
from tests.integration.mock_server import LocalMockServer, MockServerConfig


@pytest.fixture
def mock_server():
    """Start and automatically shut down a local mock OpenAI server."""
    server = LocalMockServer(host="127.0.0.1", port=0)
    base_url = server.start()
    yield server, base_url
    server.stop()


@pytest.mark.asyncio
async def test_timing_correctness_streaming(mock_server) -> None:
    """Verify that measured TTFT, total latency, and inter-token latency match injected server delays."""
    server, base_url = mock_server

    # Injected timing parameters:
    # TTFT delay: 100 ms
    # 5 chunks with 20 ms delay between chunks
    # Expected TTFT: ~100 ms (plus small socket/HTTP overhead, ~100-160 ms)
    # Expected total duration: 100 ms + (4 * 20 ms) = ~180 ms (~180-260 ms)
    # Expected inter-token latency: ~20 ms (~18-35 ms)
    server.config = MockServerConfig(
        default_ttft_delay_ms=100.0,
        default_chunk_delay_ms=20.0,
        default_chunk_count=5,
    )

    config = BenchmarkConfig(
        target=TargetConfig(base_url=base_url, model="mock-model", timeout=10.0),
        workload=WorkloadConfig(
            requests=6,
            concurrency=2,
            stream=True,
            prompts=["Explain quantum computing"],
        ),
        execution=ExecutionConfig(warmup_requests=0),
    )

    runner = BenchmarkRunner(config)
    result = await runner.run()

    summary = result.summary
    assert summary.total_requests == 6
    assert summary.success_count == 6
    assert summary.failure_count == 0
    assert summary.ttft_ms is not None
    assert summary.inter_token_latency_ms is not None

    # Check TTFT (injected 100 ms -> allowable range: 90 ms to 220 ms on local loopback)
    assert 90.0 <= summary.ttft_ms.p50 <= 220.0, f"Observed TTFT p50: {summary.ttft_ms.p50} ms"

    # Check Total Latency (injected 180 ms -> allowable range: 170 ms to 350 ms on local loopback)
    assert 170.0 <= summary.total_latency_ms.p50 <= 350.0, f"Observed Total Latency p50: {summary.total_latency_ms.p50} ms"

    # Check Inter-Token Latency (injected 20 ms -> allowable range: 15 ms to 45 ms)
    assert 15.0 <= summary.inter_token_latency_ms.p50 <= 45.0, (
        f"Observed ITL p50: {summary.inter_token_latency_ms.p50} ms"
    )

    # Token counting check (5 completion tokens * 6 requests = 30 tokens)
    assert summary.aggregate_output_tokens == 30
    assert summary.aggregate_input_tokens == 12 * 6


@pytest.mark.asyncio
async def test_concurrency_bounded_verification(mock_server) -> None:
    """Verify that InferLoad strictly respects the configured concurrency limit under live HTTP load."""
    server, base_url = mock_server

    server.config = MockServerConfig(
        default_ttft_delay_ms=60.0,
        default_chunk_delay_ms=15.0,
        default_chunk_count=4,
    )
    server.stats.reset()

    target_concurrency = 3
    num_requests = 12

    config = BenchmarkConfig(
        target=TargetConfig(base_url=base_url, model="mock-model", timeout=10.0),
        workload=WorkloadConfig(
            requests=num_requests,
            concurrency=target_concurrency,
            stream=True,
            prompts=["Test prompt for concurrency bounds"],
        ),
        execution=ExecutionConfig(warmup_requests=0),
    )

    runner = BenchmarkRunner(config)
    result = await runner.run()

    server_stats = server.stats.to_dict()

    # The server's observed max concurrency MUST NEVER exceed the configured concurrency
    assert server_stats["max_concurrency"] <= target_concurrency, (
        f"Server observed {server_stats['max_concurrency']} concurrent requests, "
        f"exceeding target limit of {target_concurrency}"
    )

    # Concurrency must be greater than 1 (ensuring true concurrency was exercised)
    assert server_stats["max_concurrency"] >= 2, (
        f"Expected concurrent execution >= 2, but observed {server_stats['max_concurrency']}"
    )

    assert server_stats["total_requests"] == num_requests
    assert result.summary.total_requests == num_requests
    assert result.summary.success_count == num_requests


@pytest.mark.asyncio
async def test_warmup_exclusion_and_fault_injection(mock_server) -> None:
    """Verify that warmup requests are excluded from stats and injected errors (429, 500) are captured."""
    server, base_url = mock_server
    server.config = MockServerConfig(
        default_ttft_delay_ms=20.0,
        default_chunk_delay_ms=5.0,
        default_chunk_count=2,
    )
    server.stats.reset()

    # 4 distinct prompts: 2 normal successes, 1 429 error, 1 500 error
    prompts = [
        "Normal request 1",
        "inject:429 Rate limited request",
        "Normal request 2",
        "inject:500 Server error request",
    ]

    config = BenchmarkConfig(
        target=TargetConfig(base_url=base_url, model="mock-model", timeout=10.0),
        workload=WorkloadConfig(
            requests=4,
            concurrency=1,
            stream=True,
            prompts=prompts,
            seed=None,  # Round robin
        ),
        execution=ExecutionConfig(warmup_requests=2),
    )

    runner = BenchmarkRunner(config)
    result = await runner.run()

    # Total HTTP calls to server = 2 warmup + 4 benchmark = 6
    server_stats = server.stats.to_dict()
    assert server_stats["total_requests"] == 6

    # Summary must contain exactly 4 benchmark requests
    summary = result.summary
    assert summary.total_requests == 4
    assert summary.success_count == 2
    assert summary.failure_count == 2
    assert summary.error_rate == 0.5
    assert summary.error_breakdown == {"HTTP_429": 1, "HTTP_500": 1}

    # Ensure no request was silently lost
    assert len(result.requests) == 4
    assert [r.status for r in result.requests] == ["success", "error", "success", "error"]


@pytest.mark.asyncio
async def test_malformed_chunk_live_stream(mock_server) -> None:
    """Verify that a corrupted SSE stream is cleanly caught as MalformedStreamChunk."""
    server, base_url = mock_server

    config = BenchmarkConfig(
        target=TargetConfig(base_url=base_url, model="mock-model", timeout=5.0),
        workload=WorkloadConfig(
            requests=1,
            concurrency=1,
            stream=True,
            prompts=["inject:malformed Trigger broken SSE"],
        ),
    )

    runner = BenchmarkRunner(config)
    result = await runner.run()

    assert result.summary.total_requests == 1
    assert result.summary.failure_count == 1
    req = result.requests[0]
    assert req.status == "error"
    assert req.error_type == "MalformedStreamChunk"
    assert "Malformed SSE JSON" in (req.error_message or "")


@pytest.mark.asyncio
async def test_non_streaming_timing_correctness(mock_server) -> None:
    """Verify non-streaming request timing and absence of false TTFT."""
    server, base_url = mock_server
    server.config = MockServerConfig(
        default_ttft_delay_ms=100.0,
        default_chunk_delay_ms=20.0,
        default_chunk_count=3,
    )

    # Injected non-streaming duration: 100 ms + 2 * 20 ms = 140 ms
    config = BenchmarkConfig(
        target=TargetConfig(base_url=base_url, model="mock-model", timeout=5.0),
        workload=WorkloadConfig(
            requests=3,
            concurrency=1,
            stream=False,
            prompts=["Non-streaming prompt"],
        ),
    )

    runner = BenchmarkRunner(config)
    result = await runner.run()

    summary = result.summary
    assert summary.total_requests == 3
    assert summary.success_count == 3
    assert summary.ttft_ms is None  # Must NOT claim TTFT for non-streaming!

    # Total latency should be around 140 ms (130 - 250 ms)
    assert 130.0 <= summary.total_latency_ms.p50 <= 250.0
