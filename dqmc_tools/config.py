"""Environment-backed configuration helpers for DQMC tools."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


ALLOWED_ROOTS_ENV = "DQMC_ALLOWED_ROOTS"
OUTPUT_ROOT_ENV = "DQMC_OUTPUT_ROOT"
OBSERVABLE_REGISTRY_ENV = "DQMC_OBSERVABLE_REGISTRY"


def get_allowed_roots(value: str | Path | Iterable[str | Path] | None = None) -> list[Path]:
    """Return configured raw-data roots.

    If `value` is omitted, roots are read from `DQMC_ALLOWED_ROOTS` and split
    with `os.pathsep`, which is `;` on Windows and `:` on Unix-like systems.
    """

    raw_value = os.environ.get(ALLOWED_ROOTS_ENV, "") if value is None else value
    if isinstance(raw_value, (str, Path)):
        if isinstance(raw_value, Path):
            return [raw_value.expanduser()]
        items = [item for item in raw_value.split(os.pathsep) if item.strip()]
    else:
        items = list(raw_value)
    return [Path(item).expanduser() for item in items]


def get_output_root(value: str | Path | None = None) -> Path | None:
    """Return the generated-output root from an explicit value or environment."""

    raw_value = os.environ.get(OUTPUT_ROOT_ENV, "") if value is None else value
    if raw_value is None or str(raw_value).strip() == "":
        return None
    return Path(raw_value).expanduser()


def get_observable_registry_path(value: str | Path | None = None) -> Path | None:
    """Return an optional observable-registry override path."""

    raw_value = os.environ.get(OBSERVABLE_REGISTRY_ENV, "") if value is None else value
    if raw_value is None or str(raw_value).strip() == "":
        return None
    return Path(raw_value).expanduser()
