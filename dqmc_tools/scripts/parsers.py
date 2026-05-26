"""Output parsers for whitelisted script manifests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


def parse_outputs(
    parser_id: str | None,
    output_files: list[dict[str, Any]],
    *,
    stdout: str = "",
    max_preview_rows: int = 5,
) -> tuple[dict[str, Any], list[str]]:
    """Parse generated outputs without failing the script result."""

    if parser_id is None:
        return {}, []

    try:
        if parser_id == "tsv":
            return {"tsv": [_parse_tsv(Path(item["path"]), max_preview_rows) for item in output_files if item["path"].endswith(".tsv")]}, []
        if parser_id == "npy_manifest":
            return {"arrays": [_parse_array(Path(item["path"])) for item in output_files if Path(item["path"]).suffix in {".npy", ".npz"}]}, []
        if parser_id == "image_manifest":
            return {"images": [_parse_image(Path(item["path"])) for item in output_files if Path(item["path"]).suffix.lower() in {".png", ".pdf", ".jpg", ".jpeg"}]}, []
        if parser_id == "stdout_key_value":
            return {"stdout_key_values": _parse_stdout_key_values(stdout)}, []
        return {}, [f"unknown_parser:{parser_id}"]
    except Exception as exc:
        return {}, [f"parser_failed:{parser_id}:{exc}"]


def _parse_tsv(path: Path, max_preview_rows: int) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return {"path": str(path), "columns": [], "row_count": 0, "preview": []}
    columns = lines[0].split("\t")
    rows = [line.split("\t") for line in lines[1:]]
    preview = [dict(zip(columns, row + [""] * (len(columns) - len(row)))) for row in rows[:max_preview_rows]]
    return {
        "path": str(path),
        "columns": columns,
        "row_count": len(rows),
        "preview": preview,
    }


def _parse_array(path: Path) -> dict[str, Any]:
    if path.suffix == ".npz":
        with np.load(path, allow_pickle=False) as payload:
            arrays = {
                key: {"shape": list(payload[key].shape), "dtype": str(payload[key].dtype)}
                for key in payload.files
            }
        return {"path": str(path), "format": "npz", "arrays": arrays}
    array = np.load(path, allow_pickle=False, mmap_mode="r")
    return {
        "path": str(path),
        "format": "npy",
        "shape": list(array.shape),
        "dtype": str(array.dtype),
    }


def _parse_image(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "format": path.suffix.lower().lstrip("."),
        "size_bytes": path.stat().st_size,
        "mtime": path.stat().st_mtime,
    }


def _parse_stdout_key_values(stdout: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        key = key.strip()
        if key:
            out[key] = value.strip()
    return out
