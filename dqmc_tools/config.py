"""Environment-backed configuration for DQMC hands tools."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from dqmc_tools.errors import ConfigurationError


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ALLOWED_ROOTS_ENV = "DQMC_ALLOWED_ROOTS"
OUTPUT_ROOT_ENV = "DQMC_OUTPUT_ROOT"
REGISTRY_PATH_ENV = "DQMC_REGISTRY_PATH"
SCRIPT_TIMEOUT_ENV = "DQMC_SCRIPT_TIMEOUT_SECONDS"
DQMC_DEV_ROOT_ENV = "DQMC_DEV_ROOT"

DEFAULT_SCRIPT_TIMEOUT_SECONDS = 300


def get_allowed_roots(value: str | Path | Iterable[str | Path] | None = None) -> list[Path]:
    """Return raw-data roots from an explicit value or DQMC_ALLOWED_ROOTS."""

    raw_value = os.environ.get(ALLOWED_ROOTS_ENV, "") if value is None else value
    if isinstance(raw_value, Path):
        items: Iterable[str | Path] = [raw_value]
    elif isinstance(raw_value, str):
        items = [item for item in raw_value.split(os.pathsep) if item.strip()]
    else:
        items = raw_value
    return [Path(item).expanduser() for item in items]


def get_output_root(value: str | Path | None = None) -> Path:
    """Return generated-output root, defaulting to the project outputs/ dir."""

    raw_value = os.environ.get(OUTPUT_ROOT_ENV, "") if value is None else value
    if raw_value is None or str(raw_value).strip() == "":
        return PROJECT_ROOT / "outputs"
    return Path(raw_value).expanduser()


def get_registry_path(value: str | Path | None = None) -> Path:
    """Return the observable registry path."""

    raw_value = os.environ.get(REGISTRY_PATH_ENV, "") if value is None else value
    if raw_value is None or str(raw_value).strip() == "":
        return PROJECT_ROOT / "registry.yaml"
    return Path(raw_value).expanduser()


def get_dqmc_dev_root(value: str | Path | None = None) -> Path:
    """Return the required dqmc-dev root from DQMC_DEV_ROOT."""

    raw_value = os.environ.get(DQMC_DEV_ROOT_ENV, "") if value is None else value
    if raw_value is None or str(raw_value).strip() == "":
        raise ConfigurationError(
            f"`{DQMC_DEV_ROOT_ENV}` must be set to the dqmc-dev checkout path.",
            details={"env_var": DQMC_DEV_ROOT_ENV},
        )
    root = Path(raw_value).expanduser()
    try:
        return root.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ConfigurationError(
            f"`{DQMC_DEV_ROOT_ENV}` points to a path that does not exist.",
            details={"env_var": DQMC_DEV_ROOT_ENV, "path": root},
        ) from exc
    except OSError as exc:
        raise ConfigurationError(
            f"`{DQMC_DEV_ROOT_ENV}` could not be resolved.",
            details={
                "env_var": DQMC_DEV_ROOT_ENV,
                "path": root,
                "reason": str(exc),
            },
        ) from exc


def get_script_timeout(value: int | str | None = None) -> int:
    """Return the default script timeout in seconds."""

    raw_value = os.environ.get(SCRIPT_TIMEOUT_ENV, "") if value is None else value
    if raw_value is None or str(raw_value).strip() == "":
        return DEFAULT_SCRIPT_TIMEOUT_SECONDS
    return int(raw_value)
