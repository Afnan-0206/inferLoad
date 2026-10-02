"""Tests for deterministic and reproducible workload generation."""

from inferload.config import BenchmarkConfig, ExecutionConfig, TargetConfig, WorkloadConfig
from inferload.workload import WorkloadGenerator


def test_workload_round_robin_deterministic() -> None:
    config = BenchmarkConfig(
        target=TargetConfig(base_url="http://localhost:8000/v1", model="test-model"),
        workload=WorkloadConfig(
            requests=5,
            concurrency=2,
            stream=True,
            prompts=["prompt A", "prompt B", "prompt C"],
            seed=None,
        ),
        execution=ExecutionConfig(warmup_requests=2),
    )

    gen = WorkloadGenerator(config)
    warmups = gen.generate_warmup_requests()
    assert len(warmups) == 2
    assert warmups[0].is_warmup is True
    assert warmups[0].prompt == "prompt A"
    assert warmups[1].prompt == "prompt B"

    bench = gen.generate_benchmark_requests()
    assert len(bench) == 5
    assert [b.prompt for b in bench] == [
        "prompt A",
        "prompt B",
        "prompt C",
        "prompt A",
        "prompt B",
    ]
    for i, b in enumerate(bench):
        assert b.index == i
        assert b.is_warmup is False
        assert b.stream is True


def test_workload_seeded_reproducibility() -> None:
    config1 = BenchmarkConfig(
        target=TargetConfig(base_url="http://localhost:8000/v1", model="test-model"),
        workload=WorkloadConfig(
            requests=20,
            concurrency=4,
            prompts=["P1", "P2", "P3", "P4", "P5"],
            seed=12345,
        ),
    )
    config2 = BenchmarkConfig(
        target=TargetConfig(base_url="http://localhost:8000/v1", model="test-model"),
        workload=WorkloadConfig(
            requests=20,
            concurrency=4,
            prompts=["P1", "P2", "P3", "P4", "P5"],
            seed=12345,
        ),
    )

    gen1 = WorkloadGenerator(config1)
    gen2 = WorkloadGenerator(config2)

    reqs1 = gen1.generate_benchmark_requests()
    reqs2 = gen2.generate_benchmark_requests()

    prompts1 = [r.prompt for r in reqs1]
    prompts2 = [r.prompt for r in reqs2]

    assert prompts1 == prompts2
