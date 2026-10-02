"""HTTP client execution for OpenAI-compatible chat completion endpoints."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from inferload.config import TargetConfig
from inferload.models import RequestRecord, RequestSpec


class InferenceClient:
    """Handles execution of individual inference requests against an OpenAI-compatible endpoint."""

    def __init__(
        self,
        target: TargetConfig,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.target = target
        self._external_client = client
        self.endpoint_url = target.chat_completions_url

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.target.api_key:
            headers["Authorization"] = f"Bearer {self.target.api_key}"
        headers.update(self.target.headers)
        return headers

    def _build_payload(self, spec: RequestSpec) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.target.model,
            "messages": [{"role": "user", "content": spec.prompt}],
            "stream": spec.stream,
        }
        if spec.max_tokens is not None:
            payload["max_tokens"] = spec.max_tokens
        if spec.temperature is not None:
            payload["temperature"] = spec.temperature

        # If streaming, optionally request stream_options for usage tokens if supported
        if spec.stream:
            payload["stream_options"] = {"include_usage": True}

        # Merge any user-specified extra parameters
        payload.update(spec.extra_params)
        return payload

    async def execute_request(
        self,
        spec: RequestSpec,
        client: httpx.AsyncClient | None = None,
    ) -> RequestRecord:
        """Execute a single benchmark request and capture precise timing metrics."""
        http_client = client or self._external_client
        if http_client is None:
            raise RuntimeError("No httpx.AsyncClient provided to execute_request")

        if spec.stream:
            return await self._execute_streaming(spec, http_client)
        else:
            return await self._execute_non_streaming(spec, http_client)

    async def _execute_streaming(
        self,
        spec: RequestSpec,
        client: httpx.AsyncClient,
    ) -> RequestRecord:
        wall_start = time.time()
        perf_start = time.perf_counter()

        perf_first_byte: float | None = None
        perf_first_token: float | None = None
        last_chunk_perf: float | None = None

        chunk_delays_ms: list[float] = []
        chunk_count = 0
        output_chunks: list[str] = []
        input_tokens: int | None = None
        output_tokens: int | None = None

        headers = self._build_headers()
        headers["Accept"] = "text/event-stream"
        payload = self._build_payload(spec)

        try:
            async with client.stream(
                "POST",
                self.endpoint_url,
                json=payload,
                headers=headers,
                timeout=self.target.timeout,
            ) as response:
                perf_first_byte = time.perf_counter()

                if response.status_code >= 400:
                    body = await response.aread()
                    error_text = body.decode("utf-8", errors="replace")
                    perf_end = time.perf_counter()
                    wall_end = time.time()
                    return RequestRecord(
                        request_id=spec.request_id,
                        index=spec.index,
                        is_warmup=spec.is_warmup,
                        prompt=spec.prompt,
                        start_time=wall_start,
                        end_time=wall_end,
                        latency_to_first_byte_ms=(perf_first_byte - perf_start) * 1000.0,
                        latency_to_first_token_ms=None,
                        duration_ms=(perf_end - perf_start) * 1000.0,
                        status="error",
                        http_status=response.status_code,
                        input_text_length=len(spec.prompt),
                        output_text="",
                        output_text_length=0,
                        input_tokens=None,
                        output_tokens=None,
                        streaming=True,
                        chunk_count=0,
                        chunk_delays_ms=[],
                        error_type=f"HTTP_{response.status_code}",
                        error_message=f"HTTP {response.status_code}: {error_text}",
                    )

                async for line in response.aiter_lines():
                    t_line = time.perf_counter()
                    if not line:
                        continue

                    # Server-Sent Events standard format: 'data: ...'
                    line = line.strip()
                    if line.startswith(":"):
                        # SSE keep-alive comment
                        continue

                    if not line.startswith("data:"):
                        continue

                    data_str = line[len("data:") :].strip()
                    if data_str == "[DONE]":
                        break

                    try:
                        chunk_data = json.loads(data_str)
                    except Exception as json_err:
                        perf_end = time.perf_counter()
                        wall_end = time.time()
                        return RequestRecord(
                            request_id=spec.request_id,
                            index=spec.index,
                            is_warmup=spec.is_warmup,
                            prompt=spec.prompt,
                            start_time=wall_start,
                            end_time=wall_end,
                            latency_to_first_byte_ms=(perf_first_byte - perf_start) * 1000.0 if perf_first_byte else None,
                            latency_to_first_token_ms=(perf_first_token - perf_start) * 1000.0 if perf_first_token else None,
                            duration_ms=(perf_end - perf_start) * 1000.0,
                            status="error",
                            http_status=response.status_code,
                            input_text_length=len(spec.prompt),
                            output_text="".join(output_chunks),
                            output_text_length=len("".join(output_chunks)),
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            streaming=True,
                            chunk_count=chunk_count,
                            chunk_delays_ms=chunk_delays_ms,
                            error_type="MalformedStreamChunk",
                            error_message=f"Malformed SSE JSON: {str(json_err)} (raw: '{line[:100]}')",
                        )

                    # Extract usage metadata if provided in chunk
                    if "usage" in chunk_data and chunk_data["usage"]:
                        usage = chunk_data["usage"]
                        input_tokens = usage.get("prompt_tokens", input_tokens)
                        output_tokens = usage.get("completion_tokens", output_tokens)

                    # Extract delta content
                    choices = chunk_data.get("choices", [])
                    token_text = ""
                    if choices:
                        delta = choices[0].get("delta", {})
                        token_text = delta.get("content") or choices[0].get("text") or ""

                    if token_text:
                        chunk_count += 1
                        output_chunks.append(token_text)
                        if perf_first_token is None:
                            perf_first_token = t_line
                            last_chunk_perf = t_line
                        else:
                            delay = (t_line - (last_chunk_perf or t_line)) * 1000.0
                            chunk_delays_ms.append(delay)
                            last_chunk_perf = t_line

            perf_end = time.perf_counter()
            wall_end = time.time()
            full_output = "".join(output_chunks)

            # If the endpoint did not provide usage tokens, we leave output_tokens as None
            # to avoid inventing token counts without the exact tokenizer.

            return RequestRecord(
                request_id=spec.request_id,
                index=spec.index,
                is_warmup=spec.is_warmup,
                prompt=spec.prompt,
                start_time=wall_start,
                end_time=wall_end,
                latency_to_first_byte_ms=(perf_first_byte - perf_start) * 1000.0 if perf_first_byte else None,
                latency_to_first_token_ms=(perf_first_token - perf_start) * 1000.0 if perf_first_token else None,
                duration_ms=(perf_end - perf_start) * 1000.0,
                status="success",
                http_status=200,
                input_text_length=len(spec.prompt),
                output_text=full_output,
                output_text_length=len(full_output),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                streaming=True,
                chunk_count=chunk_count,
                chunk_delays_ms=chunk_delays_ms,
                error_type=None,
                error_message=None,
            )

        except httpx.TimeoutException as exc:
            perf_end = time.perf_counter()
            wall_end = time.time()
            return RequestRecord(
                request_id=spec.request_id,
                index=spec.index,
                is_warmup=spec.is_warmup,
                prompt=spec.prompt,
                start_time=wall_start,
                end_time=wall_end,
                latency_to_first_byte_ms=(perf_first_byte - perf_start) * 1000.0 if perf_first_byte else None,
                latency_to_first_token_ms=(perf_first_token - perf_start) * 1000.0 if perf_first_token else None,
                duration_ms=(perf_end - perf_start) * 1000.0,
                status="timeout",
                http_status=None,
                input_text_length=len(spec.prompt),
                output_text="".join(output_chunks),
                output_text_length=len("".join(output_chunks)),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                streaming=True,
                chunk_count=chunk_count,
                chunk_delays_ms=chunk_delays_ms,
                error_type=type(exc).__name__,
                error_message=str(exc) or "Request timed out",
            )
        except Exception as exc:
            perf_end = time.perf_counter()
            wall_end = time.time()
            return RequestRecord(
                request_id=spec.request_id,
                index=spec.index,
                is_warmup=spec.is_warmup,
                prompt=spec.prompt,
                start_time=wall_start,
                end_time=wall_end,
                latency_to_first_byte_ms=(perf_first_byte - perf_start) * 1000.0 if perf_first_byte else None,
                latency_to_first_token_ms=(perf_first_token - perf_start) * 1000.0 if perf_first_token else None,
                duration_ms=(perf_end - perf_start) * 1000.0,
                status="error",
                http_status=None,
                input_text_length=len(spec.prompt),
                output_text="".join(output_chunks),
                output_text_length=len("".join(output_chunks)),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                streaming=True,
                chunk_count=chunk_count,
                chunk_delays_ms=chunk_delays_ms,
                error_type=type(exc).__name__,
                error_message=str(exc) or "Unexpected client error",
            )

    async def _execute_non_streaming(
        self,
        spec: RequestSpec,
        client: httpx.AsyncClient,
    ) -> RequestRecord:
        wall_start = time.time()
        perf_start = time.perf_counter()

        headers = self._build_headers()
        payload = self._build_payload(spec)

        try:
            response = await client.post(
                self.endpoint_url,
                json=payload,
                headers=headers,
                timeout=self.target.timeout,
            )
            perf_end = time.perf_counter()
            wall_end = time.time()
            total_duration_ms = (perf_end - perf_start) * 1000.0

            if response.status_code >= 400:
                return RequestRecord(
                    request_id=spec.request_id,
                    index=spec.index,
                    is_warmup=spec.is_warmup,
                    prompt=spec.prompt,
                    start_time=wall_start,
                    end_time=wall_end,
                    latency_to_first_byte_ms=total_duration_ms,
                    latency_to_first_token_ms=None,
                    duration_ms=total_duration_ms,
                    status="error",
                    http_status=response.status_code,
                    input_text_length=len(spec.prompt),
                    output_text="",
                    output_text_length=0,
                    input_tokens=None,
                    output_tokens=None,
                    streaming=False,
                    chunk_count=0,
                    chunk_delays_ms=[],
                    error_type=f"HTTP_{response.status_code}",
                    error_message=f"HTTP {response.status_code}: {response.text}",
                )

            data = response.json()
            output_text = ""
            choices = data.get("choices", [])
            if choices:
                msg = choices[0].get("message", {})
                output_text = msg.get("content") or choices[0].get("text") or ""

            input_tokens = None
            output_tokens = None
            if "usage" in data and data["usage"]:
                input_tokens = data["usage"].get("prompt_tokens")
                output_tokens = data["usage"].get("completion_tokens")

            return RequestRecord(
                request_id=spec.request_id,
                index=spec.index,
                is_warmup=spec.is_warmup,
                prompt=spec.prompt,
                start_time=wall_start,
                end_time=wall_end,
                latency_to_first_byte_ms=total_duration_ms,
                # In non-streaming mode, first token cannot be isolated from total generation time
                latency_to_first_token_ms=None,
                duration_ms=total_duration_ms,
                status="success",
                http_status=response.status_code,
                input_text_length=len(spec.prompt),
                output_text=output_text,
                output_text_length=len(output_text),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                streaming=False,
                chunk_count=1 if output_text else 0,
                chunk_delays_ms=[],
                error_type=None,
                error_message=None,
            )

        except httpx.TimeoutException as exc:
            perf_end = time.perf_counter()
            wall_end = time.time()
            return RequestRecord(
                request_id=spec.request_id,
                index=spec.index,
                is_warmup=spec.is_warmup,
                prompt=spec.prompt,
                start_time=wall_start,
                end_time=wall_end,
                latency_to_first_byte_ms=None,
                latency_to_first_token_ms=None,
                duration_ms=(perf_end - perf_start) * 1000.0,
                status="timeout",
                http_status=None,
                input_text_length=len(spec.prompt),
                output_text="",
                output_text_length=0,
                input_tokens=None,
                output_tokens=None,
                streaming=False,
                chunk_count=0,
                chunk_delays_ms=[],
                error_type=type(exc).__name__,
                error_message=str(exc) or "Request timed out",
            )
        except Exception as exc:
            perf_end = time.perf_counter()
            wall_end = time.time()
            return RequestRecord(
                request_id=spec.request_id,
                index=spec.index,
                is_warmup=spec.is_warmup,
                prompt=spec.prompt,
                start_time=wall_start,
                end_time=wall_end,
                latency_to_first_byte_ms=None,
                latency_to_first_token_ms=None,
                duration_ms=(perf_end - perf_start) * 1000.0,
                status="error",
                http_status=None,
                input_text_length=len(spec.prompt),
                output_text="",
                output_text_length=0,
                input_tokens=None,
                output_tokens=None,
                streaming=False,
                chunk_count=0,
                chunk_delays_ms=[],
                error_type=type(exc).__name__,
                error_message=str(exc) or "Unexpected client error",
            )
