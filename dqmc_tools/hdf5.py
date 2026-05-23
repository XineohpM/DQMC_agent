"""Read-only HDF5 inspection and observable reading."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import h5py
import numpy as np

from dqmc_tools.errors import HDF5ReadError
from dqmc_tools.paths import require_allowed_path


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


def _preview_dataset(dataset: h5py.Dataset) -> Any:
    data = dataset[()]
    return _json_safe(data)


def _attrs_to_dict(attrs: h5py.AttributeManager) -> dict[str, Any]:
    return {str(key): _json_safe(value) for key, value in attrs.items()}


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
