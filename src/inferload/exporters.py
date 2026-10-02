"""Result exporters for InferLoad benchmarks (JSON and CSV)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Sequence

from inferload.models import BenchmarkResult


def export_json(result: BenchmarkResult, file_path: str | Path) -> Path:
    """Export benchmark result as a structured JSON file."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        # Use Pydantic's model_dump with mode="json" to serialize dates/floats cleanly
        json.dump(result.model_dump(mode="json"), f, indent=2)

    return path


def export_csv(result: BenchmarkResult, file_path: str | Path) -> Path:
    """Export per-request details from a benchmark result as a CSV file."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    headers = [
        "request_id",
        "index",
        "is_warmup",
        "status",
        "http_status",
        "ttft_ms",
        "total_latency_ms",
        "inter_token_latency_ms",
        "output_tokens_per_second",
        "input_tokens",
        "output_tokens",
        "input_text_length",
        "output_text_length",
        "chunk_count",
        "error_type",
        "error_message",
        "start_time",
        "end_time",
        "prompt",
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for req in result.requests:
            writer.writerow([
                req.request_id,
                req.index,
                req.is_warmup,
                req.status,
                req.http_status or "",
                f"{req.ttft_ms:.3f}" if req.ttft_ms is not None else "",
                f"{req.total_latency_ms:.3f}",
                f"{req.inter_token_latency_ms:.3f}" if req.inter_token_latency_ms is not None else "",
                f"{req.output_tokens_per_second:.3f}" if req.output_tokens_per_second is not None else "",
                req.input_tokens if req.input_tokens is not None else "",
                req.output_tokens if req.output_tokens is not None else "",
                req.input_text_length,
                req.output_text_length,
                req.chunk_count,
                req.error_type or "",
                req.error_message or "",
                f"{req.start_time:.6f}",
                f"{req.end_time:.6f}",
                req.prompt.replace("\n", " "),
            ])

    return path


def export_results(
    result: BenchmarkResult,
    output_dir: str | Path,
    prefix: str = "run",
    formats: Sequence[str] = ("json", "csv"),
) -> dict[str, Path]:
    """Export benchmark result to specified directory in requested formats."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    run_tag = result.run_id
    exported: dict[str, Path] = {}

    for fmt in formats:
        fmt_clean = fmt.lower().strip()
        if fmt_clean == "json":
            json_file = out_dir / f"{prefix}-{run_tag}.json"
            export_json(result, json_file)
            exported["json"] = json_file
        elif fmt_clean == "csv":
            csv_file = out_dir / f"{prefix}-{run_tag}.csv"
            export_csv(result, csv_file)
            exported["csv"] = csv_file

    return exported
