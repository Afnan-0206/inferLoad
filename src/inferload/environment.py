"""System environment metadata collection for experiment reproducibility."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from typing import Any
from pydantic import BaseModel


class EnvironmentMetadata(BaseModel):
    """Snapshot of host system execution environment."""

    os_system: str
    os_release: str
    os_version: str
    python_version: str
    python_implementation: str
    cpu_architecture: str
    cpu_model: str
    cpu_cores: int | None
    ram_total_gb: float | None
    gpu_info: str
    gpu_name: str | None = None
    gpu_count: int | None = None
    cuda_version: str | None = None
    driver_version: str | None = None
    vllm_version: str | None = None
    server_version: str | None = None



def _get_ram_total_gb() -> float | None:
    """Safely obtain total system physical memory in gigabytes."""
    try:
        if sys.platform == "win32":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return round(stat.ullTotalPhys / (1024**3), 2)
        elif sys.platform.startswith("linux"):
            if os.path.exists("/proc/meminfo"):
                with open("/proc/meminfo", "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            parts = line.split()
                            kb = float(parts[1])
                            return round(kb / (1024**2), 2)
    except Exception:
        pass
    return None


def _get_gpu_details() -> tuple[str, str | None, int | None, str | None, str | None]:
    """Safely detect available GPU hardware, count, driver, and CUDA version without hard dependencies.

    Returns:
        (gpu_info_summary, gpu_name, gpu_count, cuda_version, driver_version)
    """
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            res = subprocess.run(
                [nvidia_smi, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
                count = len(lines)
                first_parts = [p.strip() for p in lines[0].split(",")]
                name = first_parts[0] if len(first_parts) > 0 else None
                driver = first_parts[2] if len(first_parts) > 2 else None

                # Check general nvidia-smi banner for CUDA version
                cuda_version = None
                try:
                    import re
                    banner_res = subprocess.run(
                        [nvidia_smi],
                        capture_output=True,
                        text=True,
                        timeout=2.0,
                        check=False,
                    )
                    if banner_res.returncode == 0:
                        m = re.search(r"CUDA Version:\s*([0-9]+\.[0-9]+)", banner_res.stdout)
                        if m:
                            cuda_version = m.group(1)
                except Exception:
                    pass

                summary = f"{count}x {', '.join(lines)}"
                return summary, name, count, cuda_version, driver
        except Exception:
            pass

    # If nvcc is available on PATH, check CUDA version as secondary check
    nvcc = shutil.which("nvcc")
    if nvcc:
        try:
            import re
            nvcc_res = subprocess.run(
                [nvcc, "--version"],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
            if nvcc_res.returncode == 0:
                m = re.search(r"release\s+([0-9]+\.[0-9]+)", nvcc_res.stdout)
                if m:
                    return "gpu: unavailable (nvcc detected)", None, None, m.group(1), None
        except Exception:
            pass

    return "gpu: unavailable", None, None, None, None


def capture_environment_metadata(
    server_version: str | None = None,
    vllm_version: str | None = None,
) -> EnvironmentMetadata:
    """Capture current system OS, Python, CPU, RAM, and GPU status."""
    gpu_summary, gpu_name, gpu_count, cuda_version, driver_version = _get_gpu_details()
    # If vllm_version wasn't passed directly but server_version is, align them
    eff_vllm_version = vllm_version or server_version
    return EnvironmentMetadata(
        os_system=platform.system(),
        os_release=platform.release(),
        os_version=platform.version(),
        python_version=platform.python_version(),
        python_implementation=platform.python_implementation(),
        cpu_architecture=platform.machine(),
        cpu_model=platform.processor() or platform.machine(),
        cpu_cores=os.cpu_count(),
        ram_total_gb=_get_ram_total_gb(),
        gpu_info=gpu_summary,
        gpu_name=gpu_name,
        gpu_count=gpu_count,
        cuda_version=cuda_version,
        driver_version=driver_version,
        vllm_version=eff_vllm_version,
        server_version=server_version,
    )

