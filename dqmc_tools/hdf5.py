"""Read-only HDF5 inspection and observable reading."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import h5py
import numpy as np

from dqmc_tools.errors import HDF5ReadError
from dqmc_tools.observables import load_observable_registry, resolve_observable
from dqmc_tools.paths import require_allowed_path


METADATA_KEYS = ("beta", "dt", "L", "Nx", "Ny", "U", "mu", "sign", "n_sample")
DEFAULT_ERROR_DATASET_SUFFIXES = (
    "_err",
    "_error",
    "_stderr",
    "_std_error",
    "_jackknife_err",
    "_jk_err",
)


def inspect_hdf5(
    path: str | Path,
    *,
    max_preview_items: int = 8,
    max_objects: int = 1000,
    allowed_roots: Iterable[str | Path] | str | Path | None = None,
) -> dict[str, Any]:
    """Inspect an HDF5 file read-only without loading large datasets."""

    resolved = require_allowed_path(path, allowed_roots)
    groups: list[dict[str, Any]] = []
    datasets: list[dict[str, Any]] = []
    truncated = False

    try:
        with h5py.File(resolved, "r") as handle:
            for name, item in _iter_hdf5_objects(handle):
                if len(groups) + len(datasets) >= max_objects:
                    truncated = True
                    break
                object_path = _h5_abs_path(name)
                if isinstance(item, h5py.Group):
                    groups.append({
                        "path": object_path,
                        "attrs": _attrs_to_dict(item.attrs),
                    })
                elif isinstance(item, h5py.Dataset):
                    datasets.append(_dataset_info(item, object_path, max_preview_items))
    except OSError as exc:
        raise HDF5ReadError(
            "HDF5 file could not be opened read-only.",
            details={"path": resolved, "reason": str(exc)},
        ) from exc

    return {
        "ok": True,
        "path": str(resolved),
        "groups": groups,
        "datasets": datasets,
        "truncated": truncated,
        "limits": {
            "max_preview_items": max_preview_items,
            "max_objects": max_objects,
        },
    }


def read_dataset(
    path: str | Path,
    dataset_path: str,
    *,
    max_items: int = 1024,
    allowed_roots: Iterable[str | Path] | str | Path | None = None,
) -> dict[str, Any]:
    """Read a dataset summary from an HDF5 file read-only."""

    resolved = require_allowed_path(path, allowed_roots)
    normalized_dataset_path = _normalize_h5_path(dataset_path)

    try:
        with h5py.File(resolved, "r") as handle:
            if normalized_dataset_path not in handle:
                raise HDF5ReadError(
                    "Dataset path was not found in the HDF5 file.",
                    details={
                        "path": resolved,
                        "dataset_path": normalized_dataset_path,
                    },
                )
            dataset = handle[normalized_dataset_path]
            if not isinstance(dataset, h5py.Dataset):
                raise HDF5ReadError(
                    "HDF5 path exists but is not a dataset.",
                    details={
                        "path": resolved,
                        "dataset_path": normalized_dataset_path,
                    },
                )

            return {
                "ok": True,
                "path": str(resolved),
                "dataset_path": normalized_dataset_path,
                "dataset": _dataset_summary(dataset, max_items=max_items),
            }
    except HDF5ReadError:
        raise
    except OSError as exc:
        raise HDF5ReadError(
            "HDF5 file could not be opened read-only.",
            details={"path": resolved, "reason": str(exc)},
        ) from exc


def read_observable(
    path: str | Path,
    observable_name: str,
    *,
    max_items: int = 1024,
    allowed_roots: Iterable[str | Path] | str | Path | None = None,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    """Read a registered observable from an HDF5 file."""

    observable = resolve_observable(observable_name, registry_path)
    dataset_path = str(observable.get("h5_path", ""))
    if not dataset_path:
        raise HDF5ReadError(
            "Resolved observable does not define an HDF5 path.",
            details={"observable_name": observable_name, "observable": observable},
        )

    dataset_result = read_dataset(
        path,
        dataset_path,
        max_items=max_items,
        allowed_roots=allowed_roots,
    )
    resolved = Path(dataset_result["path"])

    try:
        with h5py.File(resolved, "r") as handle:
            metadata = _extract_metadata(handle, dataset_path, max_items=max_items)
            error = _extract_error(
                handle,
                observable,
                dataset_path,
                registry_path=registry_path,
                max_items=max_items,
            )
    except OSError as exc:
        raise HDF5ReadError(
            "HDF5 file could not be opened read-only.",
            details={"path": resolved, "reason": str(exc)},
        ) from exc

    return {
        "ok": True,
        "path": dataset_result["path"],
        "observable": observable,
        "dataset_path": dataset_result["dataset_path"],
        "dataset": dataset_result["dataset"],
        "error": error,
        "uncertainty": error,
        "metadata": metadata,
    }


def _iter_hdf5_objects(handle: h5py.File):
    items: list[tuple[str, h5py.Group | h5py.Dataset]] = []
    handle.visititems(lambda name, item: items.append((name, item)))
    return sorted(items, key=lambda pair: pair[0])


def _dataset_info(dataset: h5py.Dataset, path: str, max_preview_items: int) -> dict[str, Any]:
    info = {
        "path": path,
        "shape": list(dataset.shape),
        "dtype": str(dataset.dtype),
        "attrs": _attrs_to_dict(dataset.attrs),
        "size": int(dataset.size),
        "preview": None,
        "preview_truncated": dataset.size > max_preview_items,
    }
    if dataset.size <= max_preview_items:
        info["preview"] = _preview_dataset(dataset)
    return info


def _dataset_summary(dataset: h5py.Dataset, *, max_items: int) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "shape": list(dataset.shape),
        "dtype": str(dataset.dtype),
        "attrs": _attrs_to_dict(dataset.attrs),
        "summary": {
            "size": int(dataset.size),
            "truncated": dataset.size > max_items,
            "preview": None,
        },
    }

    if dataset.size <= max_items:
        data = np.asarray(dataset[()])
        flat = data.reshape(-1) if data.shape else data.reshape(1)
        preview = [_json_safe(item) for item in flat.tolist()]
        summary["summary"]["preview"] = preview
        if dataset.size == 1:
            summary["summary"]["value"] = preview[0] if preview else None
        if np.issubdtype(data.dtype, np.number) and dataset.size > 0:
            summary["summary"]["min"] = _json_safe(np.nanmin(data))
            summary["summary"]["max"] = _json_safe(np.nanmax(data))
            summary["summary"]["mean"] = _json_safe(np.nanmean(data))

    return summary


def _extract_metadata(
    handle: h5py.File,
    dataset_path: str,
    *,
    max_items: int,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    measurement_group = _measurement_group_for(dataset_path)

    for key in METADATA_KEYS:
        candidates = _metadata_candidates(key, measurement_group)
        for candidate in candidates:
            if candidate in handle and isinstance(handle[candidate], h5py.Dataset):
                dataset = handle[candidate]
                value = _metadata_value(dataset, max_items=max_items)
                metadata[key] = value
                break

    return metadata


def _extract_error(
    handle: h5py.File,
    observable: dict[str, Any],
    dataset_path: str,
    *,
    registry_path: str | Path | None,
    max_items: int,
) -> dict[str, Any]:
    method = _error_method(observable, registry_path)
    candidates = _error_candidates(observable, dataset_path, registry_path)
    checked: list[str] = []

    for candidate in candidates:
        normalized = _normalize_h5_path(candidate)
        checked.append(normalized)
        if normalized in handle and isinstance(handle[normalized], h5py.Dataset):
            dataset = handle[normalized]
            return {
                "available": True,
                "method": method,
                "dataset_path": normalized,
                "dataset": _dataset_summary(dataset, max_items=max_items),
                "candidates_checked": checked,
            }

    return {
        "available": False,
        "method": method,
        "dataset_path": None,
        "dataset": None,
        "candidates_checked": checked,
        "reason": "no_error_dataset_found",
    }


def _error_method(
    observable: dict[str, Any],
    registry_path: str | Path | None,
) -> str:
    nested = observable.get("uncertainty")
    if isinstance(nested, dict) and nested.get("method"):
        return str(nested["method"])
    if observable.get("error_method"):
        return str(observable["error_method"])

    conventions = _uncertainty_conventions(registry_path)
    return str(conventions.get("default_error_method", "unknown"))


def _error_candidates(
    observable: dict[str, Any],
    dataset_path: str,
    registry_path: str | Path | None,
) -> list[str]:
    candidates: list[str] = []
    for key in (
        "error_h5_path",
        "error_dataset",
    ):
        value = observable.get(key)
        if value:
            candidates.append(str(value))

    for key in (
        "error_h5_paths",
        "error_h5_path_candidates",
        "error_dataset_candidates",
    ):
        candidates.extend(_as_str_list(observable.get(key)))

    nested = observable.get("uncertainty")
    if isinstance(nested, dict):
        for key in ("h5_path", "error_dataset"):
            if nested.get(key):
                candidates.append(str(nested[key]))
        for key in ("h5_paths", "h5_path_candidates", "error_dataset_candidates"):
            candidates.extend(_as_str_list(nested.get(key)))

    base = _normalize_h5_path(dataset_path)
    conventions = _uncertainty_conventions(registry_path)
    suffixes = _as_str_list(conventions.get("default_error_dataset_suffixes"))
    if not suffixes:
        suffixes = list(DEFAULT_ERROR_DATASET_SUFFIXES)
    candidates.extend(f"{base}{suffix}" for suffix in suffixes)

    return list(dict.fromkeys(_normalize_h5_path(item) for item in candidates if item))


def _uncertainty_conventions(registry_path: str | Path | None) -> dict[str, Any]:
    try:
        registry = load_observable_registry(registry_path)
    except Exception:
        return {}
    conventions = registry.get("uncertainty_conventions", {})
    return conventions if isinstance(conventions, dict) else {}


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _metadata_candidates(key: str, measurement_group: str | None) -> list[str]:
    candidates = []
    if key in {"sign", "n_sample"} and measurement_group:
        candidates.append(f"/{measurement_group}/{key}")
    candidates.extend([
        f"/metadata/{key}",
        f"/params/{key}",
    ])
    if key in {"sign", "n_sample"}:
        candidates.extend([
            "/meas_eqlt/" + key,
            "/meas_uneqlt/" + key,
        ])
    return list(dict.fromkeys(candidates))


def _metadata_value(dataset: h5py.Dataset, *, max_items: int) -> Any:
    result = _dataset_summary(dataset, max_items=max_items)
    summary = result["summary"]
    if "value" in summary:
        return summary["value"]
    return {
        "shape": result["shape"],
        "dtype": result["dtype"],
        "summary": summary,
    }


def _measurement_group_for(dataset_path: str) -> str | None:
    parts = _normalize_h5_path(dataset_path).strip("/").split("/")
    if parts and parts[0] in {"meas_eqlt", "meas_uneqlt"}:
        return parts[0]
    return None


def _preview_dataset(dataset: h5py.Dataset) -> Any:
    data = dataset[()]
    return _json_safe(data)


def _attrs_to_dict(attrs: h5py.AttributeManager) -> dict[str, Any]:
    return {str(key): _json_safe(value) for key, value in attrs.items()}


def _normalize_h5_path(path: str) -> str:
    stripped = str(path).strip()
    if not stripped:
        return ""
    return stripped if stripped.startswith("/") else f"/{stripped}"


def _h5_abs_path(name: str) -> str:
    return "/" + name.strip("/")


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, np.ndarray):
        as_list = value.tolist()
        if isinstance(as_list, list):
            return [_json_safe(item) for item in as_list]
        return _json_safe(as_list)
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return str(value)
