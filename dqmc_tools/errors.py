"""Typed errors and JSON-safe error conversion for DQMC hands tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any


JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


class DQMCError(Exception):
    """Base class for expected tool failures."""

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
    """Raised when a path is outside configured roots."""

    code = "path_not_allowed"


class PathResolutionError(DQMCError):
    """Raised when a path cannot be resolved."""

    code = "path_resolution_error"


class RegistryError(DQMCError):
    """Raised for registry loading or resolution failures."""

    code = "registry_error"


class RegistryNotFoundError(RegistryError):
    """Raised when a registry entry cannot be resolved."""

    code = "registry_not_found"


class RegistryAmbiguousError(RegistryError):
    """Raised when a registry query matches multiple entries."""

    code = "registry_ambiguous"


class HDF5ReadError(DQMCError):
    """Raised when a dataset cannot be read through dqmc-dev util.py."""

    code = "hdf5_read_error"


class InvalidArgumentError(DQMCError):
    """Raised when a tool argument or filter is unsupported."""

    code = "invalid_argument"


class ScriptRegistryError(DQMCError):
    """Raised for script registry and runner failures."""

    code = "script_registry_error"


class ScriptPreflightError(DQMCError):
    """Raised when required script inputs are missing or malformed."""

    code = "script_preflight_error"


class ScriptApprovalRequiredError(DQMCError):
    """Raised when a script execution lacks explicit user approval."""

    code = "user_approval_required"


class ToolUnavailableError(DQMCError):
    """Raised when an external read-only command is unavailable."""

    code = "tool_unavailable"


def error_dict(exc: Exception) -> dict[str, JsonValue]:
    """Convert expected and unexpected exceptions into JSON-safe dicts."""

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
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)
