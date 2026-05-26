"""Summaries for explicitly provided DQMC run directories."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from dqmc_tools.hdf5 import read_dataset, read_registered_quantity
from dqmc_tools.paths import require_allowed_path
from dqmc_tools.registry import list_registry_entries


HDF5_SUFFIXES = {".h5", ".hdf5"}
METADATA_KEYS = (
    "metadata/beta",
    "metadata/U",
    "metadata/mu",
    "metadata/Nx",
    "metadata/Ny",
    "params/dt",
    "params/L",
    "params/n_sweep",
    "params/n_sweep_warm",
    "params/n_sweep_meas",
    "params/period_eqlt",
    "params/period_uneqlt",
    "meas_eqlt/sign",
    "meas_eqlt/n_sample",
)


def summarize_run(
    path: str | Path,
    *,
    max_files: int = 20,
    max_registry_entries: int = 100,
    max_log_chars: int = 4000,
    allowed_roots: Iterable[str | Path] | str | Path | None = None,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    """Summarize a user-provided run directory without discovering runs."""

    run_path = require_allowed_path(path, allowed_roots)
    if not run_path.is_dir():
        raise NotADirectoryError(f"Run path must be a directory: {run_path}")

    hdf5_files = _hdf5_files(run_path)
    metadata = _metadata_facts(run_path, allowed_roots=[run_path])
    available, missing = _registry_availability(
        run_path,
        max_entries=max_registry_entries,
        allowed_roots=[run_path],
        registry_path=registry_path,
    )

    reported_files = hdf5_files[:max_files]
    return {
        "ok": True,
        "path": str(run_path),
        "name": run_path.name,
        "hdf5_file_count": len(hdf5_files),
        "reported_hdf5_file_count": len(reported_files),
        "hdf5_files_truncated": len(hdf5_files) > len(reported_files),
        "hdf5_files": [
            {
                "path": str(item),
                "relative_path": str(item.relative_to(run_path)),
                "size_bytes": item.stat().st_size,
                "log": _sibling_log_facts(item, max_chars=max_log_chars),
            }
            for item in reported_files
        ],
        "metadata": metadata,
        "available_registry_entries": available,
        "missing_registry_entries": missing,
        "limits": {
            "max_files": max_files,
            "max_registry_entries": max_registry_entries,
            "max_log_chars": max_log_chars,
        },
    }


def _hdf5_files(path: Path) -> list[Path]:
    return sorted(
        item for item in path.iterdir()
        if item.is_file() and item.suffix.lower() in HDF5_SUFFIXES
    )


def _metadata_facts(path: Path, *, allowed_roots: list[Path]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in METADATA_KEYS:
        try:
            result = read_dataset(path, key, mode="firstfile", max_items=16, allowed_roots=allowed_roots)
        except Exception:
            continue
        summary = result["dataset"]
        out[key] = summary.get("value", summary)
    return out


def _registry_availability(
    path: Path,
    *,
    max_entries: int,
    allowed_roots: list[Path],
    registry_path: str | Path | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    available = []
    missing = []
    entries = list_registry_entries(registry_path=registry_path)[:max_entries]
    for entry in entries:
        item = {
            "entry_type": entry.get("entry_type"),
            "id": entry.get("id"),
            "dataset_key": entry.get("dataset_key"),
        }
        try:
            result = read_registered_quantity(
                path,
                str(entry.get("id", "")),
                mode="firstfile",
                max_items=0,
                allowed_roots=allowed_roots,
                registry_path=registry_path,
            )
            item["resolved_dataset_key"] = result["dataset_key"]
            item["shape"] = result["dataset"]["shape"]
            item["dtype"] = result["dataset"]["dtype"]
            available.append(item)
        except Exception as exc:
            item["reason"] = str(exc)
            missing.append(item)
    return available, missing


def _sibling_log_facts(hdf5_file: Path, *, max_chars: int) -> dict[str, Any]:
    log_path = Path(str(hdf5_file) + ".log")
    if not log_path.exists():
        return {"exists": False, "path": str(log_path)}
    text = log_path.read_text(encoding="utf-8", errors="replace")
    tail = text[-max_chars:]
    sweep_matches = list(re.finditer(r"(\d+)\s*/\s*(\d+)\s+sweeps completed", text))
    last_sweep = None
    if sweep_matches:
        last = sweep_matches[-1]
        last_sweep = {"completed": int(last.group(1)), "total": int(last.group(2))}
    return {
        "exists": True,
        "path": str(log_path),
        "size_bytes": log_path.stat().st_size,
        "tail": tail,
        "has_saving_data_marker": "saving data to disk" in text,
        "has_save_success_marker": "sim_data_save() succeeded" in text,
        "last_sweep": last_sweep,
    }
