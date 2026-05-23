"""Reusable DQMC data and cluster tools.

The package is intentionally independent of any agent runtime. MCP and other
agent-facing adapters should import these functions, not own domain logic.
"""

from dqmc_tools.errors import (
    DQMCError,
    HDF5ReadError,
    InvalidFilterError,
    ObservableAmbiguousError,
    ObservableNotFoundError,
    PathNotAllowedError,
    PathResolutionError,
    ToolUnavailableError,
    error_dict,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "DQMCError",
    "InvalidFilterError",
    "PathNotAllowedError",
    "PathResolutionError",
    "ObservableNotFoundError",
    "ObservableAmbiguousError",
    "HDF5ReadError",
    "ToolUnavailableError",
    "error_dict",
]
