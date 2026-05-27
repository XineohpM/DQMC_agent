"""Reusable DQMC hands tools.

The package is intentionally independent of any agent runtime. MCP and other
adapters should import these functions rather than own domain logic.
"""

from dqmc_tools.config import (
    ALLOWED_ROOTS_ENV,
    DQMC_DEV_ROOT_ENV,
    OUTPUT_ROOT_ENV,
    REGISTRY_PATH_ENV,
    get_allowed_roots,
    get_dqmc_dev_root,
    get_output_root,
    get_registry_path,
    get_script_timeout,
)
from dqmc_tools.errors import (
    ConfigurationError,
    DQMCError,
    HDF5ReadError,
    InvalidArgumentError,
    PathNotAllowedError,
    PathResolutionError,
    RegistryAmbiguousError,
    RegistryError,
    RegistryNotFoundError,
    ScriptApprovalRequiredError,
    ScriptPreflightError,
    ScriptRegistryError,
    ToolUnavailableError,
    error_dict,
)
from dqmc_tools.hdf5 import (
    estimate_registered_observable,
    inspect_hdf5,
    read_dataset,
    read_observable,
    read_registered_quantity,
)
from dqmc_tools.paths import (
    require_allowed_path,
    require_output_path,
    require_workflow_path,
    resolve_existing_path,
)
from dqmc_tools.registry import (
    list_observables,
    list_registry_entries,
    load_registry,
    resolve_observable,
    resolve_registry_entry,
)
from dqmc_tools.runs import summarize_run
from dqmc_tools.scripts import (
    InputRequirement,
    ScriptDefinition,
    audit_script_adapters,
    describe_script_adapter,
    list_script_adapters,
    run_script_adapter,
)
from dqmc_tools.slurm import query_slurm, query_slurm_history
from dqmc_tools.slurm_presenter import format_slurm_status_summary

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "ALLOWED_ROOTS_ENV",
    "DQMC_DEV_ROOT_ENV",
    "OUTPUT_ROOT_ENV",
    "REGISTRY_PATH_ENV",
    "get_allowed_roots",
    "get_dqmc_dev_root",
    "get_output_root",
    "get_registry_path",
    "get_script_timeout",
    "resolve_existing_path",
    "require_allowed_path",
    "require_output_path",
    "require_workflow_path",
    "load_registry",
    "list_registry_entries",
    "resolve_registry_entry",
    "list_observables",
    "resolve_observable",
    "summarize_run",
    "inspect_hdf5",
    "read_dataset",
    "read_observable",
    "read_registered_quantity",
    "estimate_registered_observable",
    "InputRequirement",
    "ScriptDefinition",
    "audit_script_adapters",
    "list_script_adapters",
    "describe_script_adapter",
    "run_script_adapter",
    "query_slurm",
    "query_slurm_history",
    "format_slurm_status_summary",
    "ConfigurationError",
    "DQMCError",
    "HDF5ReadError",
    "InvalidArgumentError",
    "PathNotAllowedError",
    "PathResolutionError",
    "RegistryAmbiguousError",
    "RegistryError",
    "RegistryNotFoundError",
    "ScriptApprovalRequiredError",
    "ScriptPreflightError",
    "ScriptRegistryError",
    "ToolUnavailableError",
    "error_dict",
]
