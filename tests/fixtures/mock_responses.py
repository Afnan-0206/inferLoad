"""Mock HTTP responses and helper builders for testing."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator


def make_chat_completion_json(
    content: str = "Test response text",
    prompt_tokens: int = 15,
    completion_tokens: int = 8,
    model: str = "test-model",
) -> dict[str, Any]:
    """Generate a standard non-streaming OpenAI chat completion payload."""
    return {
        "id": "chatcmpl-mock-123",
        "object": "chat.completion",
        "created": 1700000000,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def make_sse_stream_chunks(
    tokens: list[str],
    prompt_tokens: int = 15,
    completion_tokens: int = 8,
    model: str = "test-model",
) -> list[str]:
    """Generate Server-Sent Event lines for an OpenAI streaming response."""
    lines: list[str] = []

    # First chunk often sets role
    first_chunk = {
        "id": "chatcmpl-stream-123",
        "object": "chat.completion.chunk",
        "created": 1700000000,
        "model": model,
        "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
    }
    lines.append(f"data: {json.dumps(first_chunk)}\n\n")

    # Content token chunks
    for token in tokens:
        chunk = {
            "id": "chatcmpl-stream-123",
            "object": "chat.completion.chunk",
            "created": 1700000000,
            "model": model,
            "choices": [{"index": 0, "delta": {"content": token}, "finish_reason": None}],
        }
        lines.append(f"data: {json.dumps(chunk)}\n\n")

    # Final chunk with finish reason and usage
    final_chunk = {
        "id": "chatcmpl-stream-123",
        "object": "chat.completion.chunk",
        "created": 1700000000,
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }
    lines.append(f"data: {json.dumps(final_chunk)}\n\n")
    lines.append("data: [DONE]\n\n")

    return lines
