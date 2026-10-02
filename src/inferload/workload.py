"""Workload generation: creates reproducible sequences of request specifications."""

from __future__ import annotations

import random
from typing import Sequence
import uuid

from inferload.config import BenchmarkConfig
from inferload.models import RequestSpec


class WorkloadGenerator:
    """Generates request specifications for warmup and benchmark phases."""

    def __init__(self, config: BenchmarkConfig) -> None:
        self.config = config
        self._seed = config.workload.seed
        self._rng = random.Random(self._seed) if self._seed is not None else None

    def _select_prompt(self, index: int, prompts: Sequence[str]) -> str:
        """Select a prompt either via seeded random sampling or deterministic round-robin."""
        if self._rng is not None:
            return self._rng.choice(prompts)
        return prompts[index % len(prompts)]

    def generate_warmup_requests(self) -> list[RequestSpec]:
        """Generate unmeasured warmup request specifications."""
        warmup_count = self.config.execution.warmup_requests
        if warmup_count <= 0:
            return []

        specs: list[RequestSpec] = []
        prompts = self.config.workload.prompts
        for i in range(warmup_count):
            spec = RequestSpec(
                request_id=f"warmup-{i+1}-{uuid.uuid4().hex[:8]}",
                index=i,
                is_warmup=True,
                prompt=self._select_prompt(i, prompts),
                max_tokens=self.config.workload.max_tokens,
                temperature=self.config.workload.temperature,
                stream=self.config.workload.stream,
                extra_params=self.config.workload.extra_params,
            )
            specs.append(spec)
        return specs

    def generate_benchmark_requests(self) -> list[RequestSpec]:
        """Generate measured benchmark request specifications."""
        count = self.config.workload.requests
        prompts = self.config.workload.prompts
        specs: list[RequestSpec] = []

        for i in range(count):
            spec = RequestSpec(
                request_id=f"req-{i+1}-{uuid.uuid4().hex[:8]}",
                index=i,
                is_warmup=False,
                prompt=self._select_prompt(i, prompts),
                max_tokens=self.config.workload.max_tokens,
                temperature=self.config.workload.temperature,
                stream=self.config.workload.stream,
                extra_params=self.config.workload.extra_params,
            )
            specs.append(spec)
        return specs
