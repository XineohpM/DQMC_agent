"""Reusable DQMC data and cluster tools.

The package is intentionally independent of any agent runtime. MCP and other
agent-facing adapters should import these functions, not own domain logic.
"""

from dqmc_tools.errors import (
    DQMCError,
    HDF5ReadError,
    AnalysisRegistryError,
    InvalidFilterError,
    ObservableAmbiguousError,
    ObservableNotFoundError,
    PathNotAllowedError,
    PathResolutionError,
    ToolUnavailableError,
    error_dict,
)
from dqmc_tools.hdf5 import inspect_hdf5, read_dataset, read_observable
from dqmc_tools.observables import (
    list_observables,
    load_observable_registry,
    resolve_observable,
)
from dqmc_tools.runs import list_runs, summarize_run
from dqmc_tools.slurm import query_slurm
from dqmc_tools.analyses import AnalysisDefinition, list_analyses, run_analysis

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "inspect_hdf5",
    "read_dataset",
    "read_observable",
    "load_observable_registry",
    "list_observables",
    "resolve_observable",
    "list_runs",
    "summarize_run",
    "query_slurm",
    "AnalysisDefinition",
    "list_analyses",
    "run_analysis",
    "DQMCError",
    "AnalysisRegistryError",
    "InvalidFilterError",
    "PathNotAllowedError",
    "PathResolutionError",
    "ObservableNotFoundError",
    "ObservableAmbiguousError",
    "HDF5ReadError",
    "ToolUnavailableError",
    "error_dict",
]
