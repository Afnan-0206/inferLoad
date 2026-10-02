#!/usr/bin/env python3
"""Run a standalone end-to-end benchmark against a local mock OpenAI server.

Usage:
    python scripts/run_local_benchmark.py
    python scripts/run_local_benchmark.py --config examples/integration.yaml --requests 10 --concurrency 2
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

# Ensure src and root are in sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "src"))
sys.path.insert(0, str(root_dir))

from inferload.config import load_config
from inferload.exporters import export_results
from inferload.runner import BenchmarkRunner
from inferload.cli import _print_benchmark_summary
from tests.integration.mock_server import LocalMockServer, MockServerConfig


def main() -> int:
    parser = argparse.ArgumentParser(description="InferLoad Local Mock End-to-End Benchmark")
    parser.add_argument("--config", default="examples/integration.yaml", help="Path to config YAML")
    parser.add_argument("--port", type=int, default=8000, help="Port for mock server (0 for ephemeral)")
    parser.add_argument("--requests", type=int, default=None, help="Override requests count")
    parser.add_argument("--concurrency", type=int, default=None, help="Override concurrency")
    parser.add_argument("--ttft-delay-ms", type=float, default=100.0, help="Injected TTFT delay in ms")
    parser.add_argument("--chunk-delay-ms", type=float, default=20.0, help="Injected chunk delay in ms")
    parser.add_argument("--chunk-count", type=int, default=5, help="Number of chunks per request")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_file():
        print(f"Error: Config file not found at {config_path}", file=sys.stderr)
        return 1

    cfg = load_config(config_path)
    if args.requests is not None:
        cfg.workload.requests = args.requests
    if args.concurrency is not None:
        cfg.workload.concurrency = args.concurrency

    # Start local mock server
    server_cfg = MockServerConfig(
        default_ttft_delay_ms=args.ttft_delay_ms,
        default_chunk_delay_ms=args.chunk_delay_ms,
        default_chunk_count=args.chunk_count,
    )
    mock_server = LocalMockServer(host="127.0.0.1", port=args.port, config=server_cfg)

    print(f"Starting local mock OpenAI endpoint on 127.0.0.1:{args.port}...")
    base_url = mock_server.start()
    cfg.target.base_url = base_url

    print(f"Server listening at {base_url}/chat/completions")
    print(f"Injected server behavior: TTFT delay={args.ttft_delay_ms}ms, chunk delay={args.chunk_delay_ms}ms, chunks={args.chunk_count}")
    print(f"Running benchmark: {cfg.workload.requests} requests @ concurrency {cfg.workload.concurrency} (stream={cfg.workload.stream})...\n")

    try:
        runner = BenchmarkRunner(cfg)
        result = asyncio.run(runner.run())

        exported = export_results(
            result=result,
            output_dir=cfg.export.output_dir,
            prefix=cfg.export.prefix,
            formats=cfg.export.formats,
        )

        _print_benchmark_summary(result, exported)

        # Server-side validation
        stats = mock_server.stats.to_dict()
        print("\nServer-Side Validation:")
        print(f"  Total requests processed by server: {stats['total_requests']}")
        print(f"  Max observed concurrent requests:   {stats['max_concurrency']} (Target limit: {cfg.workload.concurrency})")

        if stats["max_concurrency"] > cfg.workload.concurrency:
            print(f"  [FAIL] Server observed concurrency {stats['max_concurrency']} exceeded target {cfg.workload.concurrency}!", file=sys.stderr)
            return 1
        else:
            print(f"  [PASS] Concurrency was strictly bounded (<= {cfg.workload.concurrency}).")

        return 0

    finally:
        mock_server.stop()
        print("Mock server stopped.")


if __name__ == "__main__":
    sys.exit(main())
