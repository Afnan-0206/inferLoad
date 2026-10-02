"""Tests for configuration parsing and validation."""

from pathlib import Path
import pytest
from pydantic import ValidationError

from inferload.config import BenchmarkConfig, TargetConfig, WorkloadConfig, load_config


def test_target_config_valid() -> None:
    target = TargetConfig(
        base_url="https://api.openai.com/v1",
        api_key="secret-key",
        model="gpt-4o-mini",
    )
    assert target.base_url == "https://api.openai.com/v1"
    assert target.chat_completions_url == "https://api.openai.com/v1/chat/completions"
    assert target.api_key == "secret-key"


def test_target_config_trailing_slash() -> None:
    target = TargetConfig(
        base_url="http://localhost:8000/v1/",
        model="local-llm",
    )
    assert target.base_url == "http://localhost:8000/v1"
    assert target.chat_completions_url == "http://localhost:8000/v1/chat/completions"


def test_target_config_already_has_chat_completions() -> None:
    target = TargetConfig(
        base_url="http://localhost:8000/v1/chat/completions",
        model="local-llm",
    )
    assert target.chat_completions_url == "http://localhost:8000/v1/chat/completions"


def test_target_config_invalid_urls() -> None:
    # Missing scheme
    with pytest.raises(ValidationError) as exc:
        TargetConfig(base_url="localhost:8000/v1", model="test")
    assert "Invalid URL scheme" in str(exc.value)

    # Unsupported scheme (ftp)
    with pytest.raises(ValidationError) as exc:
        TargetConfig(base_url="ftp://localhost:8000/v1", model="test")
    assert "Invalid URL scheme" in str(exc.value)

    # Missing netloc
    with pytest.raises(ValidationError) as exc:
        TargetConfig(base_url="http://", model="test")
    assert "valid host" in str(exc.value)


def test_workload_config_validation() -> None:
    # Concurrency must be > 0
    with pytest.raises(ValidationError):
        WorkloadConfig(requests=10, concurrency=0, prompts=["hello"])

    with pytest.raises(ValidationError):
        WorkloadConfig(requests=10, concurrency=-1, prompts=["hello"])

    # Requests must be > 0
    with pytest.raises(ValidationError):
        WorkloadConfig(requests=0, concurrency=2, prompts=["hello"])

    # Prompts must not be empty
    with pytest.raises(ValidationError):
        WorkloadConfig(requests=10, concurrency=2, prompts=[])

    with pytest.raises(ValidationError):
        WorkloadConfig(requests=10, concurrency=2, prompts=["   "])


def test_load_config_from_file(tmp_path: Path) -> None:
    yaml_content = """
target:
  base_url: "http://127.0.0.1:8000/v1"
  model: "qwen-7b"
  timeout: 30.0

workload:
  requests: 15
  concurrency: 3
  stream: true
  prompts:
    - "Test prompt 1"
    - "Test prompt 2"
  max_tokens: 64
  temperature: 0.7
  seed: 42
  extra_params:
    top_p: 0.95

execution:
  warmup_requests: 3
  delay_between_requests_ms: 10.0

export:
  output_dir: "custom_results"
  formats:
    - "json"
    - "csv"
"""
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text(yaml_content, encoding="utf-8")

    cfg = load_config(config_file)
    assert cfg.target.base_url == "http://127.0.0.1:8000/v1"
    assert cfg.target.model == "qwen-7b"
    assert cfg.target.timeout == 30.0
    assert cfg.workload.requests == 15
    assert cfg.workload.concurrency == 3
    assert cfg.workload.stream is True
    assert len(cfg.workload.prompts) == 2
    assert cfg.workload.extra_params["top_p"] == 0.95
    assert cfg.execution.warmup_requests == 3
    assert cfg.export.output_dir == "custom_results"
    assert cfg.export.formats == ["json", "csv"]


def test_load_config_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        load_config("non_existent_file_path_12345.yaml")


def test_load_vllm_gpu_baseline_config() -> None:
    from inferload.experiment_config import load_experiment_config
    cfg = load_experiment_config("examples/vllm_gpu_baseline.yaml")
    assert cfg.experiment.name == "vllm-gpu-baseline"
    assert cfg.sweep.concurrency == [1, 2, 4, 8]
    assert cfg.sweep.max_tokens == [64, 128]
    assert cfg.sweep.repetitions == 3
    assert cfg.sweep.requests_per_point == 30
    assert cfg.execution.warmup_requests == 10
    assert cfg.workload.stream is True
    assert cfg.workload.temperature == 0.0
    assert cfg.workload.seed == 42
    assert "short" in cfg.workload.prompt_profiles
    assert "medium" in cfg.workload.prompt_profiles
    assert "long" in cfg.workload.prompt_profiles

