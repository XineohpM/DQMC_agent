"""Run directory discovery and factual summaries."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from dqmc_tools.errors import InvalidFilterError, PathResolutionError
from dqmc_tools.hdf5 import inspect_hdf5
from dqmc_tools.observables import list_observables
from dqmc_tools.paths import require_allowed_path


HDF5_SUFFIXES = {".h5", ".hdf5"}
LOG_SUFFIXES = {".log", ".out", ".err"}
JOB_SUFFIXES = {".slurm", ".sbatch", ".sh"}
SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    "node_modules",
    "build",
    "dist",
    "dqmc_tools.egg-info",
}
SUPPORTED_FILTERS = {"name_contains", "modified_after", "modified_before", "has_hdf5"}


def list_runs(
    root: str | Path,
    filters: dict[str, Any] | None = None,
    *,
    max_runs: int = 200,
    allowed_roots: Iterable[str | Path] | str | Path | None = None,
) -> list[dict[str, Any]]:
    """List candidate DQMC run directories under an allowed root."""

    root_path = require_allowed_path(root, allowed_roots)
    if not root_path.is_dir():
        raise PathResolutionError(
            "Run-listing root must be a directory.",
            details={"path": root_path},
        )

    parsed_filters = _validate_filters(filters or {})
    runs: list[dict[str, Any]] = []

    for directory in _iter_directories(root_path):
        summary = _directory_summary(directory)
        if not _is_run_candidate(summary):
            continue
        if not _matches_filters(summary, parsed_filters):
            continue
        runs.append(summary)
        if len(runs) >= max_runs:
            break

    runs.sort(key=lambda item: (-item["mtime"], item["path"]))
    return runs


def summarize_run(
    path: str | Path,
    *,
    max_files: int = 20,
    allowed_roots: Iterable[str | Path] | str | Path | None = None,
) -> dict[str, Any]:
    """Return a compact factual summary of a DQMC run directory."""

    run_path = require_allowed_path(path, allowed_roots)
    if not run_path.is_dir():
        raise PathResolutionError(
            "Run path must be a directory.",
            details={"path": run_path},
        )

    hdf5_files = _find_hdf5_files(run_path, max_files=max_files)
    observables = list_observables()
    observable_paths = {
        str(item.get("h5_path", "")): str(item.get("repo_id", ""))
        for item in observables
        if item.get("h5_path") and item.get("repo_id")
    }

    files = []
    for hdf5_path in hdf5_files:
        inspection = inspect_hdf5(hdf5_path, allowed_roots=[run_path])
        dataset_paths = {item["path"] for item in inspection["datasets"]}
        available = [
            {"repo_id": repo_id, "h5_path": h5_path}
            for h5_path, repo_id in sorted(observable_paths.items())
            if h5_path in dataset_paths
        ]
        missing = [
            {"repo_id": repo_id, "h5_path": h5_path}
            for h5_path, repo_id in sorted(observable_paths.items())
            if h5_path not in dataset_paths
        ]
        files.append({
            "path": str(hdf5_path),
            "relative_path": str(hdf5_path.relative_to(run_path)),
            "datasets": len(inspection["datasets"]),
            "groups": len(inspection["groups"]),
            "available_observables": available,
            "missing_observables": missing,
            "metadata": _metadata_from_inspection(inspection),
            "inspection_truncated": inspection["truncated"],
        })

    return {
        "ok": True,
        "path": str(run_path),
        "name": run_path.name,
        "mtime": run_path.stat().st_mtime,
        "mtime_iso": _mtime_iso(run_path),
        "hdf5_file_count": _count_hdf5_files(run_path),
        "reported_hdf5_file_count": len(files),
        "hdf5_files_truncated": _count_hdf5_files(run_path) > len(files),
        "hdf5_files": files,
        "limits": {"max_files": max_files},
    }


def _iter_directories(root: Path):
    yield root
    for current_root, dirs, _files in os.walk(root):
        dirs[:] = [item for item in dirs if item not in SKIP_DIRS]
        for dirname in sorted(dirs):
            yield Path(current_root) / dirname


def _directory_summary(directory: Path) -> dict[str, Any]:
    files = [item for item in directory.iterdir() if item.is_file()]
    hdf5_count = sum(1 for item in files if item.suffix.lower() in HDF5_SUFFIXES)
    log_count = sum(1 for item in files if item.suffix.lower() in LOG_SUFFIXES)
    job_count = sum(1 for item in files if item.suffix.lower() in JOB_SUFFIXES)
    stat = directory.stat()
    return {
        "path": str(directory),
        "name": directory.name,
        "mtime": stat.st_mtime,
        "mtime_iso": _mtime_iso(directory),
        "hdf5_file_count": hdf5_count,
        "log_file_count": log_count,
        "job_file_count": job_count,
    }


def _is_run_candidate(summary: dict[str, Any]) -> bool:
    return (
        summary["hdf5_file_count"] > 0
        or summary["log_file_count"] > 0
        or summary["job_file_count"] > 0
    )


def _validate_filters(filters: dict[str, Any]) -> dict[str, Any]:
    unknown = sorted(set(filters) - SUPPORTED_FILTERS)
    if unknown:
        raise InvalidFilterError(
            "Unsupported run filters were provided.",
            details={"unsupported_filters": unknown, "supported_filters": sorted(SUPPORTED_FILTERS)},
        )

    parsed = dict(filters)
    for key in ("modified_after", "modified_before"):
        if key in parsed and parsed[key] is not None:
            parsed[key] = _parse_time_filter(parsed[key], key)
    if "has_hdf5" in parsed and not isinstance(parsed["has_hdf5"], bool):
        raise InvalidFilterError(
            "`has_hdf5` filter must be a boolean.",
            details={"filter": "has_hdf5", "value": parsed["has_hdf5"]},
        )
    return parsed


def _matches_filters(summary: dict[str, Any], filters: dict[str, Any]) -> bool:
    name_contains = filters.get("name_contains")
    if name_contains and str(name_contains).lower() not in summary["name"].lower():
        return False
    if "has_hdf5" in filters:
        has_hdf5 = summary["hdf5_file_count"] > 0
        if has_hdf5 != filters["has_hdf5"]:
            return False
    if "modified_after" in filters and summary["mtime"] < filters["modified_after"]:
        return False
    if "modified_before" in filters and summary["mtime"] > filters["modified_before"]:
        return False
    return True


def _parse_time_filter(value: Any, filter_name: str) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).timestamp()
        except ValueError as exc:
            raise InvalidFilterError(
                "Time filter must be a Unix timestamp or ISO datetime string.",
                details={"filter": filter_name, "value": value},
            ) from exc
    raise InvalidFilterError(
        "Time filter must be a Unix timestamp or ISO datetime string.",
        details={"filter": filter_name, "value": value},
    )


def _find_hdf5_files(root: Path, *, max_files: int) -> list[Path]:
    files = []
    for current_root, dirs, filenames in os.walk(root):
        dirs[:] = [item for item in dirs if item not in SKIP_DIRS]
        for filename in sorted(filenames):
            candidate = Path(current_root) / filename
            if candidate.suffix.lower() in HDF5_SUFFIXES:
                files.append(candidate.resolve())
                if len(files) >= max_files:
                    return files
    return files


def _count_hdf5_files(root: Path) -> int:
    count = 0
    for current_root, dirs, filenames in os.walk(root):
        dirs[:] = [item for item in dirs if item not in SKIP_DIRS]
        count += sum(1 for name in filenames if Path(name).suffix.lower() in HDF5_SUFFIXES)
    return count


def _metadata_from_inspection(inspection: dict[str, Any]) -> dict[str, Any]:
    datasets = {item["path"]: item for item in inspection["datasets"]}
    out: dict[str, Any] = {}
    for family in ("metadata", "params", "meas_eqlt", "meas_uneqlt"):
        for key in ("beta", "dt", "L", "Nx", "Ny", "U", "mu", "sign", "n_sample"):
            path = f"/{family}/{key}"
            if key not in out and path in datasets:
                preview = datasets[path].get("preview")
                if isinstance(preview, list) and len(preview) == 1:
                    out[key] = preview[0]
                elif preview is not None:
                    out[key] = preview
    return out


def _mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
