"""Thin MCP adapter for the DQMC hands implementation."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from dqmc_tools.errors import error_dict
from dqmc_tools.hdf5 import estimate_registered_observable as dqmc_estimate_registered_observable
from dqmc_tools.hdf5 import inspect_hdf5 as dqmc_inspect_hdf5
from dqmc_tools.hdf5 import read_dataset as dqmc_read_dataset
from dqmc_tools.hdf5 import read_registered_quantity as dqmc_read_registered_quantity
from dqmc_tools.registry import resolve_registry_entry as dqmc_resolve_registry_entry
from dqmc_tools.runs import summarize_run as dqmc_summarize_run
from dqmc_tools.scripts.runner import describe_script_adapter as dqmc_describe_script_adapter
from dqmc_tools.scripts.runner import list_script_adapters as dqmc_list_script_adapters
from dqmc_tools.scripts.runner import run_script_adapter as dqmc_run_script_adapter
from dqmc_tools.slurm import query_slurm as dqmc_query_slurm


SERVER_INSTRUCTIONS = (
    "DQMC hands tools expose controlled wrappers around the fixed dqmc-dev "
    "checkout, registry.yaml, explicit HDF5 dataset reads, user-provided run "
    "summaries, whitelisted scripts, and read-only SLURM status. No list_runs "
    "tool is exposed; users must provide directories explicitly."
)


def build_server() -> FastMCP:
    """Build the DQMC MCP server."""

    server = FastMCP("dqmc-hands", instructions=SERVER_INSTRUCTIONS)

    @server.tool(
        name="summarize_run",
        description=(
            "Summarize one user-provided DQMC run directory. This does not "
            "discover candidate runs. It reports HDF5 files, selected metadata, "
            "and registry availability using registry fields id, aliases, and "
            "code.generation.variable. Parameters: path; optional max_files, "
            "max_registry_entries, max_log_chars, allowed_roots, registry_path."
        ),
    )
    def summarize_run(
        path: str,
        max_files: int = 20,
        max_registry_entries: int = 100,
        max_log_chars: int = 4000,
        allowed_roots: list[str] | None = None,
        registry_path: str | None = None,
    ) -> dict[str, Any]:
        try:
            return dqmc_summarize_run(
                path,
                max_files=max_files,
                max_registry_entries=max_registry_entries,
                max_log_chars=max_log_chars,
                allowed_roots=allowed_roots,
                registry_path=registry_path,
            )
        except Exception as exc:
            return error_dict(exc)

    @server.tool(
        name="inspect_hdf5",
        description=(
            "Inspect explicitly requested datasets through dqmc-dev/util/util.py "
            "wrappers only. This is not HDF5 tree discovery and it adds no extra "
            "HDF5 parsing logic. dataset_keys must contain concrete dataset keys "
            "or registry names resolved through id, aliases, or "
            "code.generation.variable. Parameters: path, dataset_keys; optional "
            "mode file/firstfile/directory, max_items, allowed_roots, registry_path."
        ),
    )
    def inspect_hdf5(
        path: str,
        dataset_keys: list[str],
        mode: str = "file",
        max_items: int = 1024,
        allowed_roots: list[str] | None = None,
        registry_path: str | None = None,
    ) -> dict[str, Any]:
        try:
            return dqmc_inspect_hdf5(
                path,
                dataset_keys,
                mode=mode,  # type: ignore[arg-type]
                max_items=max_items,
                allowed_roots=allowed_roots,
                registry_path=registry_path,
            )
        except Exception as exc:
            return error_dict(exc)

    @server.tool(
        name="read_dataset",
        description=(
            "Read one explicit dataset key through dqmc-dev/util/util.py "
            "load_file, load_firstfile, or load. Use this for direct factual "
            "dataset summaries only. Parameters: path, dataset_key; optional mode, "
            "max_items, allowed_roots."
        ),
    )
    def read_dataset(
        path: str,
        dataset_key: str,
        mode: str = "file",
        max_items: int = 1024,
        allowed_roots: list[str] | None = None,
    ) -> dict[str, Any]:
        try:
            return dqmc_read_dataset(
                path,
                dataset_key,
                mode=mode,  # type: ignore[arg-type]
                max_items=max_items,
                allowed_roots=allowed_roots,
            )
        except Exception as exc:
            return error_dict(exc)

    @server.tool(
        name="resolve_registry_entry",
        description=(
            "Resolve a registry.yaml entry by id, alias, code.generation.variable, "
            "or dataset tail. Registry entries use the real schema fields id, "
            "aliases, and code.generation.variable; runtime results also include "
            "entry_type and dataset_key for downstream use. Parameters: name; "
            "optional entry_type observable/parameter and registry_path."
        ),
    )
    def resolve_registry_entry(
        name: str,
        entry_type: str | None = None,
        registry_path: str | None = None,
    ) -> dict[str, Any]:
        try:
            return dqmc_resolve_registry_entry(
                name,
                entry_type=entry_type,
                registry_path=registry_path,
            )
        except Exception as exc:
            return error_dict(exc)

    @server.tool(
        name="read_registered_quantity",
        description=(
            "Resolve a registry entry and read the matching dataset through "
            "dqmc-dev/util/util.py. This is a single-file or direct directory read "
            "and does not estimate observable errors. Parameters: path, name; "
            "optional mode, max_items, allowed_roots, registry_path."
        ),
    )
    def read_registered_quantity(
        path: str,
        name: str,
        mode: str = "file",
        max_items: int = 1024,
        allowed_roots: list[str] | None = None,
        registry_path: str | None = None,
    ) -> dict[str, Any]:
        try:
            return dqmc_read_registered_quantity(
                path,
                name,
                mode=mode,  # type: ignore[arg-type]
                max_items=max_items,
                allowed_roots=allowed_roots,
                registry_path=registry_path,
            )
        except Exception as exc:
            return error_dict(exc)

    @server.tool(
        name="estimate_registered_observable",
        description=(
            "Estimate a registered observable over a directory of HDF5 files using "
            "dqmc-dev/util/util.py jackknife or jackknife_noniid. Use this for "
            "mean/error estimates across a group of files; single-file reads do "
            "not provide these errors. Parameters: directory, observable_name; "
            "optional estimator, dataset_keys_override, max_items, allowed_roots, "
            "registry_path."
        ),
    )
    def estimate_registered_observable(
        directory: str,
        observable_name: str,
        estimator: str = "jackknife",
        dataset_keys_override: dict[str, str] | None = None,
        max_items: int = 1024,
        allowed_roots: list[str] | None = None,
        registry_path: str | None = None,
    ) -> dict[str, Any]:
        try:
            return dqmc_estimate_registered_observable(
                directory,
                observable_name,
                estimator=estimator,  # type: ignore[arg-type]
                dataset_keys_override=dataset_keys_override,
                max_items=max_items,
                allowed_roots=allowed_roots,
                registry_path=registry_path,
            )
        except Exception as exc:
            return error_dict(exc)

    @server.tool(
        name="list_script_adapters",
        description=(
            "List whitelisted dqmc-dev script adapters. The fixed dqmc-dev root is "
            "/Users/phoenixm/Desktop/dqmc-dev. Some adapters require derived "
            "input files produced by earlier scripts; use describe_script_adapter "
            "or dry-run run_script_adapter to inspect preflight requirements."
        ),
    )
    def list_script_adapters() -> list[dict[str, Any]] | dict[str, Any]:
        try:
            return dqmc_list_script_adapters()
        except Exception as exc:
            return error_dict(exc)

    @server.tool(
        name="describe_script_adapter",
        description=(
            "Describe one whitelisted dqmc-dev script adapter, including schema, "
            "required input files, output patterns, parser, and approval policy. "
            "Use this before running secondary scripts that consume derived data."
        ),
    )
    def describe_script_adapter(script_id: str) -> dict[str, Any]:
        try:
            return dqmc_describe_script_adapter(script_id)
        except Exception as exc:
            return error_dict(exc)

    @server.tool(
        name="run_script_adapter",
        description=(
            "Dry-run or execute a whitelisted dqmc-dev script adapter with "
            "preflight checks. Actual execution, including input generation and "
            "workflow-mutating scripts, requires explicit user_confirmation with "
            "approved=true and non-empty text. Use dry_run=true first to inspect "
            "command, cwd, required inputs, and output root. The default output "
            "root is this project's outputs/ directory."
        ),
    )
    def run_script_adapter(
        script_id: str,
        params: dict[str, Any] | None = None,
        cwd: str | None = None,
        allowed_roots: list[str] | None = None,
        output_root: str | None = None,
        timeout_seconds: int | None = None,
        dry_run: bool = False,
        user_confirmation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            return dqmc_run_script_adapter(
                script_id,
                params=params,
                cwd=cwd,
                allowed_roots=allowed_roots,
                output_root=output_root,
                timeout_seconds=timeout_seconds,
                dry_run=dry_run,
                user_confirmation=user_confirmation,
            )
        except Exception as exc:
            return error_dict(exc)

    @server.tool(
        name="query_slurm",
        description=(
            "Query read-only SLURM job status with local squeue. This never "
            "submits, cancels, or mutates jobs. Parameters: optional filters with "
            "user, job_id, state, or partition."
        ),
    )
    def query_slurm(filters: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            return dqmc_query_slurm(filters=filters)
        except Exception as exc:
            return error_dict(exc)

    return server


mcp = build_server()


if __name__ == "__main__":
    mcp.run()
