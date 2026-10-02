"""Lightweight local mock OpenAI-compatible HTTP server for integration testing.

Supports:
- POST /v1/chat/completions (and /chat/completions)
- Streaming Server-Sent Events (SSE) with configurable delays
- Configurable initial TTFT delay and inter-chunk delays
- Active concurrency tracking and maximum concurrency recording
- Fault injection: 429 rate limit, 500 server error, timeout, malformed SSE chunks
- Diagnostic stats endpoint: GET /stats
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class MockServerStats:
    """Thread-safe statistics and concurrency tracker for the mock server."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.active_requests: int = 0
        self.max_concurrency: int = 0
        self.total_requests: int = 0
        self.streaming_requests: int = 0
        self.non_streaming_requests: int = 0

    def on_request_start(self, is_streaming: bool) -> None:
        with self.lock:
            self.active_requests += 1
            if self.active_requests > self.max_concurrency:
                self.max_concurrency = self.active_requests
            self.total_requests += 1
            if is_streaming:
                self.streaming_requests += 1
            else:
                self.non_streaming_requests += 1

    def on_request_end(self) -> None:
        with self.lock:
            self.active_requests = max(0, self.active_requests - 1)

    def reset(self) -> None:
        with self.lock:
            self.active_requests = 0
            self.max_concurrency = 0
            self.total_requests = 0
            self.streaming_requests = 0
            self.non_streaming_requests = 0

    def to_dict(self) -> dict[str, Any]:
        with self.lock:
            return {
                "active_requests": self.active_requests,
                "max_concurrency": self.max_concurrency,
                "total_requests": self.total_requests,
                "streaming_requests": self.streaming_requests,
                "non_streaming_requests": self.non_streaming_requests,
            }


class MockServerConfig:
    """Default configuration for simulated delays and chunk counts."""

    def __init__(
        self,
        default_ttft_delay_ms: float = 100.0,
        default_chunk_delay_ms: float = 20.0,
        default_chunk_count: int = 5,
        default_tokens_per_chunk: list[str] | None = None,
    ) -> None:
        self.default_ttft_delay_ms = default_ttft_delay_ms
        self.default_chunk_delay_ms = default_chunk_delay_ms
        self.default_chunk_count = default_chunk_count
        self.tokens = default_tokens_per_chunk or ["The", " quick", " brown", " fox", " jumps"]


class MockOpenAIHandler(BaseHTTPRequestHandler):
    """HTTP request handler simulating OpenAI /v1/chat/completions."""

    protocol_version = "HTTP/1.1"

    # Injected by server factory
    stats: MockServerStats
    config: MockServerConfig

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy standard HTTP access logs during testing
        pass

    def do_GET(self) -> None:
        """Diagnostic endpoints."""
        if self.path in ("/stats", "/v1/stats"):
            data = json.dumps(self.stats.to_dict()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if self.path in ("/health", "/v1/health"):
            data = b'{"status": "ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        """Handle /chat/completions request."""
        clean_path = self.path.split("?")[0].rstrip("/")
        if clean_path not in ("/chat/completions", "/v1/chat/completions"):
            self.send_error(404, f"Endpoint {self.path} not supported")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception:
            payload = {}

        stream = bool(payload.get("stream", True))
        self.stats.on_request_start(is_streaming=stream)

        try:
            # Check for error injection triggers from headers or body
            inject_error = (
                self.headers.get("X-Inject-Error")
                or payload.get("inject_error")
                or self._detect_error_in_prompt(payload)
            )

            if inject_error == "429":
                self._send_error_json(429, "rate_limit_error", "Rate limit exceeded (injected 429)")
                return
            elif inject_error == "500":
                self._send_error_json(500, "server_error", "Internal server error (injected 500)")
                return
            elif inject_error == "timeout":
                # Sleep longer than the typical client timeout
                time.sleep(2.5)
                self._send_error_json(504, "gateway_timeout", "Gateway timeout (injected timeout)")
                return
            # Extract delay configurations (per-request overrides or server defaults)
            ttft_delay_ms = float(
                self.headers.get("X-Inject-TTFT-Ms")
                or payload.get("inject_ttft_ms")
                or self.config.default_ttft_delay_ms
            )
            chunk_delay_ms = float(
                self.headers.get("X-Inject-Chunk-Delay-Ms")
                or payload.get("inject_chunk_delay_ms")
                or self.config.default_chunk_delay_ms
            )
            chunk_count = int(
                self.headers.get("X-Inject-Chunk-Count")
                or payload.get("inject_chunk_count")
                or self.config.default_chunk_count
            )
            malformed_stream = (inject_error == "malformed")

            if stream:
                self._handle_streaming(
                    ttft_delay_ms=ttft_delay_ms,
                    chunk_delay_ms=chunk_delay_ms,
                    chunk_count=chunk_count,
                    model=payload.get("model", "mock-model"),
                    malformed=malformed_stream,
                )
            else:
                self._handle_non_streaming(
                    ttft_delay_ms=ttft_delay_ms,
                    chunk_delay_ms=chunk_delay_ms,
                    chunk_count=chunk_count,
                    model=payload.get("model", "mock-model"),
                )
        finally:
            self.stats.on_request_end()

    def _detect_error_in_prompt(self, payload: dict[str, Any]) -> str | None:
        messages = payload.get("messages", [])
        if messages and isinstance(messages, list):
            content = str(messages[-1].get("content", ""))
            if "inject:429" in content:
                return "429"
            if "inject:500" in content:
                return "500"
            if "inject:timeout" in content:
                return "timeout"
            if "inject:malformed" in content:
                return "malformed"
        return None

    def _send_error_json(self, status: int, err_type: str, message: str) -> None:
        data = json.dumps({
            "error": {
                "message": message,
                "type": err_type,
                "code": status,
            }
        }).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_streaming(
        self,
        ttft_delay_ms: float,
        chunk_delay_ms: float,
        chunk_count: int,
        model: str,
        malformed: bool = False,
    ) -> None:
        """Stream SSE chunks with precise artificial delays."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        tokens = self.config.tokens
        num_tokens = len(tokens)

        # 1. Wait for TTFT delay before the first content chunk
        if ttft_delay_ms > 0:
            time.sleep(ttft_delay_ms / 1000.0)

        # Emit first role chunk
        role_chunk = {
            "id": "chatcmpl-mock",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        }
        self.wfile.write(f"data: {json.dumps(role_chunk)}\n\n".encode("utf-8"))
        self.wfile.flush()

        # Emit content token chunks with inter-chunk delays
        for i in range(chunk_count):
            if malformed and i == 1:
                # Inject corrupted JSON
                self.wfile.write(b"data: {corrupted_json_stream_chunk_error\n\n")
                self.wfile.flush()
                return

            token_text = tokens[i % num_tokens]
            chunk = {
                "id": "chatcmpl-mock",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{"index": 0, "delta": {"content": token_text}, "finish_reason": None}],
            }
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode("utf-8"))
            self.wfile.flush()

            if i < chunk_count - 1 and chunk_delay_ms > 0:
                time.sleep(chunk_delay_ms / 1000.0)

        # Final chunk with finish reason and usage metrics
        final_chunk = {
            "id": "chatcmpl-mock",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": chunk_count,
                "total_tokens": 12 + chunk_count,
            },
        }
        self.wfile.write(f"data: {json.dumps(final_chunk)}\n\n".encode("utf-8"))
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _handle_non_streaming(
        self,
        ttft_delay_ms: float,
        chunk_delay_ms: float,
        chunk_count: int,
        model: str,
    ) -> None:
        """Handle non-streaming request by simulating total generation delay."""
        total_delay_s = (ttft_delay_ms + max(0, chunk_count - 1) * chunk_delay_ms) / 1000.0
        if total_delay_s > 0:
            time.sleep(total_delay_s)

        tokens = self.config.tokens
        text = "".join(tokens[i % len(tokens)] for i in range(chunk_count))

        payload = {
            "id": "chatcmpl-mock-nonstream",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": text,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": chunk_count,
                "total_tokens": 12 + chunk_count,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class LocalMockServer:
    """Wrapper to start and stop the local mock server in a background thread."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        config: MockServerConfig | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.config = config or MockServerConfig()
        self.stats = MockServerStats()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> str:
        """Start the server on host and ephemeral or requested port. Returns base_url."""
        handler_cls = type(
            "ConfiguredMockHandler",
            (MockOpenAIHandler,),
            {"stats": self.stats, "config": self.config},
        )
        self._server = ThreadingHTTPServer((self.host, self.port), handler_cls)
        # In case port 0 was passed, get allocated port
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return f"http://{self.host}:{self.port}/v1"

    def stop(self) -> None:
        """Stop and shutdown the HTTP server."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/v1"
