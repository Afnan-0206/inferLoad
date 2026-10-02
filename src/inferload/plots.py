"""Static plot generation using matplotlib for benchmark experiment sweeps."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence
import matplotlib

# Set non-interactive Agg backend before importing pyplot to ensure headless safety
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from inferload.statistics import SampleStatistics


def generate_experiment_plots(
    summary_data: list[dict],
    output_dir: Path | str,
) -> list[Path]:
    """Generate reproducible PNG plots for an experiment and return list of saved file paths."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []

    # Filter points by concurrency sweep if available
    concurrency_points = [p for p in summary_data if "concurrency" in p]
    if len(concurrency_points) >= 2:
        # Sort by concurrency
        concurrency_points.sort(key=lambda p: p["concurrency"])

        # 1. Concurrency vs TTFT p95
        p1 = out / "concurrency_vs_ttft_p95.png"
        fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
        x = [p["concurrency"] for p in concurrency_points]
        y = [p.get("ttft_p95_mean") or p.get("ttft_p95") or 0.0 for p in concurrency_points]
        y_err = [p.get("ttft_p95_std") for p in concurrency_points]
        has_err = any(e is not None and e > 0 for e in y_err)

        if has_err:
            err_vals = [e or 0.0 for e in y_err]
            ax.errorbar(x, y, yerr=err_vals, fmt="-o", capsize=4, color="#1f77b4", label="TTFT p95 (mean ± std)")
        else:
            ax.plot(x, y, "-o", color="#1f77b4", label="TTFT p95")

        ax.set_title("Concurrency vs. Time to First Token (p95)", fontsize=11, fontweight="bold")
        ax.set_xlabel("Concurrency (Workers)", fontsize=10)
        ax.set_ylabel("TTFT p95 (ms)", fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.6)
        ax.legend(loc="best")
        fig.tight_layout()
        fig.savefig(p1)
        plt.close(fig)
        generated.append(p1)

        # 2. Concurrency vs Throughput
        p2 = out / "concurrency_vs_throughput.png"
        fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
        y_thru = [p.get("throughput_mean") or p.get("throughput_rps") or 0.0 for p in concurrency_points]
        y_thru_err = [p.get("throughput_std") for p in concurrency_points]
        has_thru_err = any(e is not None and e > 0 for e in y_thru_err)

        if has_thru_err:
            err_vals = [e or 0.0 for e in y_thru_err]
            ax.errorbar(x, y_thru, yerr=err_vals, fmt="-s", capsize=4, color="#2ca02c", label="Throughput (mean ± std)")
        else:
            ax.plot(x, y_thru, "-s", color="#2ca02c", label="Throughput")

        ax.set_title("Concurrency vs. Request Throughput", fontsize=11, fontweight="bold")
        ax.set_xlabel("Concurrency (Workers)", fontsize=10)
        ax.set_ylabel("Throughput (Requests/sec)", fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.6)
        ax.legend(loc="best")
        fig.tight_layout()
        fig.savefig(p2)
        plt.close(fig)
        generated.append(p2)

        # 3. Concurrency vs Error Rate
        p3 = out / "concurrency_vs_error_rate.png"
        fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
        y_err_rate = [(p.get("error_rate_mean") or p.get("error_rate", 0.0)) * 100.0 for p in concurrency_points]
        ax.plot(x, y_err_rate, "-^", color="#d62728", label="Error Rate (%)")
        ax.set_title("Concurrency vs. Error Rate", fontsize=11, fontweight="bold")
        ax.set_xlabel("Concurrency (Workers)", fontsize=10)
        ax.set_ylabel("Error Rate (%)", fontsize=10)
        ax.set_ylim(bottom=-1.0, top=max(10.0, max(y_err_rate) * 1.2 if y_err_rate else 10.0))
        ax.grid(True, linestyle="--", alpha=0.6)
        ax.legend(loc="best")
        fig.tight_layout()
        fig.savefig(p3)
        plt.close(fig)
        generated.append(p3)

        # 4. Concurrency vs Total Latency p95
        p4 = out / "concurrency_vs_total_latency_p95.png"
        fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
        y_tot_lat = [p.get("latency_p95_mean") or p.get("latency_p95") or 0.0 for p in concurrency_points]
        y_tot_err = [p.get("latency_p95_std") for p in concurrency_points]
        has_tot_err = any(e is not None and e > 0 for e in y_tot_err)

        if has_tot_err:
            err_vals = [e or 0.0 for e in y_tot_err]
            ax.errorbar(x, y_tot_lat, yerr=err_vals, fmt="-d", capsize=4, color="#9467bd", label="Total Latency p95 (mean ± std)")
        else:
            ax.plot(x, y_tot_lat, "-d", color="#9467bd", label="Total Latency p95")

        ax.set_title("Concurrency vs. Total Response Latency (p95)", fontsize=11, fontweight="bold")
        ax.set_xlabel("Concurrency (Workers)", fontsize=10)
        ax.set_ylabel("Total Latency p95 (ms)", fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.6)
        ax.legend(loc="best")
        fig.tight_layout()
        fig.savefig(p4)
        plt.close(fig)
        generated.append(p4)

    # 4. Prompt Profile vs TTFT (if prompt profile sweep exists)
    profile_points = [p for p in summary_data if "prompt_profile" in p and p["prompt_profile"]]
    unique_profiles = sorted(set(p["prompt_profile"] for p in profile_points))
    if len(unique_profiles) >= 2:
        p4 = out / "prompt_profile_vs_ttft.png"
        fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
        profile_ttfts = []
        for prof in unique_profiles:
            matching = [p for p in profile_points if p["prompt_profile"] == prof]
            vals = [m.get("ttft_p50_mean") or m.get("ttft_p50") or 0.0 for m in matching]
            profile_ttfts.append(sum(vals) / len(vals) if vals else 0.0)

        ax.bar(unique_profiles, profile_ttfts, color="#9467bd", alpha=0.85, edgecolor="black")
        ax.set_title("Prompt Profile vs. TTFT (p50)", fontsize=11, fontweight="bold")
        ax.set_xlabel("Prompt Profile", fontsize=10)
        ax.set_ylabel("TTFT p50 (ms)", fontsize=10)
        ax.grid(axis="y", linestyle="--", alpha=0.6)
        fig.tight_layout()
        fig.savefig(p4)
        plt.close(fig)
        generated.append(p4)

    # 5. Output tokens vs Total Latency (if max_tokens sweep exists)
    token_points = [p for p in summary_data if "max_tokens" in p]
    unique_tokens = sorted(set(p["max_tokens"] for p in token_points))
    if len(unique_tokens) >= 2:
        p5 = out / "output_tokens_vs_total_latency.png"
        fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
        token_points.sort(key=lambda p: p["max_tokens"])
        x_tok = [p["max_tokens"] for p in token_points]
        y_lat = [p.get("latency_p50_mean") or p.get("latency_p50") or 0.0 for p in token_points]
        ax.plot(x_tok, y_lat, "-d", color="#8c564b", label="Total Latency p50 (ms)")
        ax.set_title("Generation Length vs. Total Latency", fontsize=11, fontweight="bold")
        ax.set_xlabel("Max Tokens", fontsize=10)
        ax.set_ylabel("Total Latency p50 (ms)", fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.6)
        ax.legend(loc="best")
        fig.tight_layout()
        fig.savefig(p5)
        plt.close(fig)
        generated.append(p5)

    return generated
