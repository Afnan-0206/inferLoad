"""Tests for CLI interface using Typer CliRunner."""

from pathlib import Path
from typer.testing import CliRunner

from inferload.cli import app

runner = CliRunner()


def test_cli_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "InferLoad version: 0.1.0" in result.stdout


def test_cli_validate_success(tmp_path: Path) -> None:
    config_file = tmp_path / "valid.yaml"
    config_file.write_text(
        """
target:
  base_url: "http://localhost:8000/v1"
  model: "test-model"
workload:
  requests: 10
  concurrency: 2
  prompts: ["Hello"]
""",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["validate", str(config_file)])
    assert result.exit_code == 0
    assert "Configuration is valid!" in result.stdout


def test_cli_validate_failure(tmp_path: Path) -> None:
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text(
        """
target:
  base_url: "invalid_url_no_scheme"
  model: "test"
workload:
  requests: -5
  concurrency: 0
  prompts: []
""",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["validate", str(bad_config)])
    assert result.exit_code == 1
    assert "Validation failed" in result.stdout
