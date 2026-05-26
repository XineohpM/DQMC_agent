"""Safe wrappers around dqmc-dev util.py HDF5 helpers."""

from __future__ import annotations

import importlib.util
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Literal

import numpy as np

from dqmc_tools.config import get_dqmc_dev_root
from dqmc_tools.errors import HDF5ReadError, InvalidArgumentError, RegistryError
from dqmc_tools.paths import require_allowed_path
from dqmc_tools.registry import resolve_registry_entry


ReadMode = Literal["file", "firstfile", "directory"]


def inspect_hdf5(
    path: str | Path,
    dataset_keys: Iterable[str],
    *,
    mode: ReadMode = "file",
    max_items: int = 1024,
    allowed_roots: Iterable[str | Path] | str | Path | None = None,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    """Inspect explicitly requested datasets through dqmc-dev util.py wrappers."""

    keys = [_resolve_dataset_key(item, registry_path=registry_path) for item in dataset_keys]
    if not keys:
        raise InvalidArgumentError(
            "inspect_hdf5 requires at least one explicit dataset key or registry name.",
            details={"dataset_keys": list(dataset_keys)},
        )

    resolved = require_allowed_path(path, allowed_roots)
    datasets = []
    errors = []
    for key in keys:
        try:
            datasets.append(read_dataset(resolved, key, mode=mode, max_items=max_items, allowed_roots=[resolved]))
        except Exception as exc:  # keep per-key failures factual
            errors.append({
                "dataset_key": key,
                "error_type": exc.__class__.__name__,
                "message": str(exc),
            })

    return {
        "ok": True,
        "path": str(resolved),
        "mode": mode,
        "util_function": _util_function_name(mode),
        "datasets": datasets,
        "errors": errors,
        "limits": {"max_items": max_items},
    }


def read_dataset(
    path: str | Path,
    dataset_key: str,
    *,
    mode: ReadMode = "file",
    max_items: int = 1024,
    allowed_roots: Iterable[str | Path] | str | Path | None = None,
) -> dict[str, Any]:
    """Read one explicit dataset key through dqmc-dev util.py."""

    resolved = require_allowed_path(path, allowed_roots)
    key = _require_dataset_key(dataset_key)
    data = _read_keys(resolved, [key], mode=mode)[0]
    return {
        "ok": True,
        "path": str(resolved),
        "mode": mode,
        "util_function": _util_function_name(mode),
        "dataset_key": key,
        "dataset": _array_summary(data, max_items=max_items),
    }


def read_registered_quantity(
    path: str | Path,
    name: str,
    *,
    mode: ReadMode = "file",
    max_items: int = 1024,
    allowed_roots: Iterable[str | Path] | str | Path | None = None,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    """Resolve a registry entry and read its dataset facts without error estimation."""

    entry = resolve_registry_entry(name, registry_path=registry_path)
    resolved = require_allowed_path(path, allowed_roots)
    attempts = _candidate_dataset_keys(entry)
    last_error: Exception | None = None
    for key in attempts:
        try:
            data = _read_keys(resolved, [key], mode=mode)[0]
            return {
                "ok": True,
                "path": str(resolved),
                "mode": mode,
                "util_function": _util_function_name(mode),
                "registry_entry": entry,
                "dataset_key": key,
                "candidate_dataset_keys": attempts,
                "dataset": _array_summary(data, max_items=max_items),
                "error": None,
                "error_note": "Single-file/direct reads do not estimate observable errors.",
            }
        except Exception as exc:
            last_error = exc

    raise HDF5ReadError(
        "Registered quantity could not be read from any candidate dataset key.",
        details={
            "name": name,
            "path": resolved,
            "candidate_dataset_keys": attempts,
            "last_error": str(last_error) if last_error else None,
        },
    )


def estimate_registered_observable(
    directory: str | Path,
    observable_name: str,
    *,
    estimator: Literal["jackknife", "jackknife_noniid"] = "jackknife",
    dataset_keys_override: dict[str, str] | None = None,
    max_items: int = 1024,
    allowed_roots: Iterable[str | Path] | str | Path | None = None,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    """Estimate mean/error for a registered observable across a group of HDF5 files."""

    entry = resolve_registry_entry(
        observable_name,
        entry_type="observable",
        registry_path=registry_path,
    )
    resolved = require_allowed_path(directory, allowed_roots)
    if not resolved.is_dir():
        raise HDF5ReadError(
            "Jackknife estimation requires a directory of HDF5 files.",
            details={"path": resolved},
        )

    keys = _estimation_keys(entry, dataset_keys_override)
    util = _dqmc_util()
    directory_arg = _directory_arg(resolved)

    try:
        if estimator == "jackknife":
            sign, values = util.load(directory_arg, keys["sign"], keys["value"])
            estimate = util.jackknife(sign, values)
        elif estimator == "jackknife_noniid":
            n_sample, sign, values = util.load(
                directory_arg,
                keys["n_sample"],
                keys["sign"],
                keys["value"],
            )
            estimate = util.jackknife_noniid(n_sample, sign, values)
        else:
            raise InvalidArgumentError(
                "Unsupported estimator.",
                details={"estimator": estimator, "supported": ["jackknife", "jackknife_noniid"]},
            )
    except InvalidArgumentError:
        raise
    except Exception as exc:
        raise HDF5ReadError(
            "Registered observable could not be estimated with jackknife.",
            details={
                "directory": resolved,
                "observable_name": observable_name,
                "dataset_keys": keys,
                "estimator": estimator,
                "reason": str(exc),
            },
        ) from exc

    file_count = len(sorted(resolved.glob("*.h5")))
    return {
        "ok": True,
        "directory": str(resolved),
        "registry_entry": entry,
        "dataset_keys": keys,
        "estimator": estimator,
        "util_function": estimator,
        "hdf5_file_count": file_count,
        "estimate": {
            "mean": _json_safe(np.asarray(estimate[0])),
            "error": _json_safe(np.asarray(estimate[1])),
            "shape": list(np.asarray(estimate[0]).shape),
        },
        "raw_estimate": _array_summary(np.asarray(estimate), max_items=max_items),
    }


def _read_keys(path: Path, keys: list[str], *, mode: ReadMode) -> tuple[Any, ...]:
    util = _dqmc_util()
    try:
        if mode == "file":
            return util.load_file(str(path), *keys)
        if mode == "firstfile":
            return util.load_firstfile(_directory_arg(path), *keys)
        if mode == "directory":
            result = util.load(_directory_arg(path), *keys)
            if result is None:
                raise HDF5ReadError(
                    "No HDF5 files matched directory read.",
                    details={"path": path, "keys": keys},
                )
            return result
    except HDF5ReadError:
        raise
    except Exception as exc:
        raise HDF5ReadError(
            "Dataset could not be read through dqmc-dev util.py.",
            details={"path": path, "dataset_keys": keys, "mode": mode, "reason": str(exc)},
        ) from exc
    raise InvalidArgumentError(
        "Unsupported read mode.",
        details={"mode": mode, "supported": ["file", "firstfile", "directory"]},
    )


@lru_cache(maxsize=1)
def _dqmc_util():
    util_path = get_dqmc_dev_root() / "util" / "util.py"
    if not util_path.exists():
        raise HDF5ReadError(
            "dqmc-dev util.py was not found.",
            details={"path": util_path},
        )
    spec = importlib.util.spec_from_file_location("_dqmc_dev_util", util_path)
    if spec is None or spec.loader is None:
        raise HDF5ReadError(
            "dqmc-dev util.py could not be loaded.",
            details={"path": util_path},
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_dataset_key(value: str, *, registry_path: str | Path | None) -> str:
    raw = _require_dataset_key(value)
    if "/" in raw:
        return raw.strip("/")
    try:
        return str(resolve_registry_entry(raw, registry_path=registry_path)["dataset_key"]).strip("/")
    except RegistryError:
        return raw


def _candidate_dataset_keys(entry: dict[str, Any]) -> list[str]:
    dataset_key = str(entry.get("dataset_key", "")).strip("/")
    candidates = [dataset_key] if dataset_key else []
    if entry.get("entry_type") == "parameter" and dataset_key and "/" not in dataset_key:
        candidates.extend([f"metadata/{dataset_key}", f"params/{dataset_key}"])
    return list(dict.fromkeys(item for item in candidates if item))


def _estimation_keys(entry: dict[str, Any], override: dict[str, str] | None) -> dict[str, str]:
    if override:
        value = override.get("value")
        sign = override.get("sign")
        n_sample = override.get("n_sample")
        if not value or not sign:
            raise InvalidArgumentError(
                "dataset_keys_override must include at least value and sign.",
                details={"dataset_keys_override": override},
            )
        return {
            "value": _require_dataset_key(value),
            "sign": _require_dataset_key(sign),
            "n_sample": _require_dataset_key(n_sample or _default_peer_key(value, "n_sample")),
        }

    value = _require_dataset_key(str(entry.get("dataset_key", "")))
    sign = _default_peer_key(value, "sign")
    n_sample = _default_peer_key(value, "n_sample")
    return {"value": value, "sign": sign, "n_sample": n_sample}


def _default_peer_key(dataset_key: str, peer: str) -> str:
    parts = _require_dataset_key(dataset_key).split("/")
    if len(parts) <= 1:
        return peer
    return "/".join([*parts[:-1], peer])


def _require_dataset_key(dataset_key: str) -> str:
    key = str(dataset_key).strip().strip("/")
    if not key:
        raise InvalidArgumentError(
            "Dataset key must be a non-empty string.",
            details={"dataset_key": dataset_key},
        )
    return key


def _directory_arg(path: Path) -> str:
    text = str(path)
    return text if text.endswith("/") else f"{text}/"


def _util_function_name(mode: ReadMode) -> str:
    return {
        "file": "load_file",
        "firstfile": "load_firstfile",
        "directory": "load",
    }.get(mode, str(mode))


def _array_summary(value: Any, *, max_items: int) -> dict[str, Any]:
    data = np.asarray(value)
    flat = data.reshape(-1) if data.shape else data.reshape(1)
    summary: dict[str, Any] = {
        "shape": list(data.shape),
        "dtype": str(data.dtype),
        "size": int(data.size),
        "truncated": data.size > max_items,
        "preview": None,
    }
    if data.size <= max_items:
        summary["preview"] = [_json_safe(item) for item in flat.tolist()]
        if data.size == 1:
            summary["value"] = summary["preview"][0]
        summary.update(_numeric_summary(data))
    return summary


def _numeric_summary(data: np.ndarray) -> dict[str, Any]:
    if data.size == 0 or not np.issubdtype(data.dtype, np.number):
        return {}
    if np.issubdtype(data.dtype, np.complexfloating):
        abs_data = np.abs(data)
        return {
            "mean_real": _json_safe(np.nanmean(data.real)),
            "mean_imag": _json_safe(np.nanmean(data.imag)),
            "abs_min": _json_safe(np.nanmin(abs_data)),
            "abs_max": _json_safe(np.nanmax(abs_data)),
            "abs_mean": _json_safe(np.nanmean(abs_data)),
        }
    return {
        "min": _json_safe(np.nanmin(data)),
        "max": _json_safe(np.nanmax(data)),
        "mean": _json_safe(np.nanmean(data)),
    }


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, complex):
        return {"real": value.real, "imag": value.imag}
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, np.ndarray):
        as_list = value.tolist()
        return _json_safe(as_list)
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return str(value)
