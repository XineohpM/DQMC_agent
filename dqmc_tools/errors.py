"""Typed exceptions and JSON-safe error conversion for DQMC tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any


JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


class DQMCError(Exception):
    """Base class for expected DQMC tool failures."""

    code = "dqmc_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "ok": False,
            "error_type": self.code,
            "message": self.message,
            "details": _json_safe(self.details),
        }


class PathNotAllowedError(DQMCError):
    """Raised when a path is outside configured allowed roots."""

    code = "path_not_allowed"


class PathResolutionError(DQMCError):
    """Raised when a filesystem path cannot be resolved as required."""

    code = "path_resolution_error"


class InvalidFilterError(DQMCError):
    """Raised when a tool receives unsupported or malformed filters."""

    code = "invalid_filter"


class AnalysisRegistryError(DQMCError):
    """Raised when an analysis registry entry is missing or invalid."""

    code = "analysis_registry_error"


class ObservableNotFoundError(DQMCError):
    """Raised when an observable id or dataset cannot be found."""

    code = "observable_not_found"


class ObservableAmbiguousError(DQMCError):
    """Raised when an observable shorthand maps to multiple candidates."""

    code = "observable_ambiguous"


class HDF5ReadError(DQMCError):
    """Raised when an HDF5 file cannot be inspected or read as requested."""

    code = "hdf5_read_error"


class ToolUnavailableError(DQMCError):
    """Raised when an external read-only tool such as SLURM is unavailable."""

    code = "tool_unavailable"


def error_dict(exc: Exception) -> dict[str, JsonValue]:
    """Convert an exception into the JSON-safe error shape used by adapters."""

    if isinstance(exc, DQMCError):
        return exc.to_dict()

    return {
        "ok": False,
        "error_type": exc.__class__.__name__,
        "message": str(exc),
        "details": {},
    }


def _json_safe(value: Any) -> JsonValue:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return str(value)
