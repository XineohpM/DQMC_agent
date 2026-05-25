"""Thin MCP adapter for `dqmc_tools`.

All domain logic lives in `dqmc_tools`. This module only registers MCP tools,
forwards arguments, and converts typed exceptions to JSON-safe error results.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from dqmc_tools.errors import error_dict
from dqmc_tools.hdf5 import inspect_hdf5 as dqmc_inspect_hdf5
from dqmc_tools.hdf5 import read_observable as dqmc_read_observable
from dqmc_tools.observables import resolve_observable as dqmc_resolve_observable
from dqmc_tools.runs import list_runs as dqmc_list_runs
from dqmc_tools.runs import summarize_run as dqmc_summarize_run
from dqmc_tools.slurm import query_slurm as dqmc_query_slurm


SERVER_INSTRUCTIONS = (
    "DQMC hands tools expose controlled filesystem, HDF5, observable-registry, "
    "run-summary, and read-only SLURM operations. Tools return factual data and "
    "bounded summaries; upstream agents are responsible for interpretation."
)


def build_server() -> FastMCP:
    """Build the DQMC MCP server."""

    server = FastMCP("dqmc-hands", instructions=SERVER_INSTRUCTIONS)

    @server.tool(
        name="list_runs",
        description=(
            "List candidate DQMC run directories under an allowed root. Use this "
            "when you need to discover runs before choosing files to inspect. Do "
            "not use this to inspect HDF5 contents; use inspect_hdf5 or "
            "summarize_run after a candidate run is selected. Parameters: root is "
            "a directory path; filters may include name_contains, modified_after, "
            "modified_before, and has_hdf5; allowed_roots is optional and otherwise "
            "comes from DQMC_ALLOWED_ROOTS. Example: {'root': '/scratch/phoenix', "
            "'filters': {'name_contains': 'U-10', 'has_hdf5': true}, "
            "'allowed_roots': ['/scratch/phoenix']}. Returns a bounded list of "
            "run summaries with path, name, mtime, and file counts. Raw-data path "
            "access fails closed when no allowed root is configured."
        ),
    )
    def list_runs(
        root: str,
        filters: dict[str, Any] | None = None,
        max_runs: int = 200,
        allowed_roots: list[str] | None = None,
    ) -> Any:
        try:
            return dqmc_list_runs(
                root,
                filters=filters,
                max_runs=max_runs,
                allowed_roots=allowed_roots,
            )
        except Exception as exc:
            return error_dict(exc)

    @server.tool(
        name="inspect_hdf5",
        description=(
            "Inspect an HDF5 file read-only without loading large arrays. Use this "
            "when the available groups/datasets or shapes are unknown. Do not use "
            "this to read a registered observable value; use read_observable when "
            "you already know the desired observable. Parameters: path is the HDF5 "
            "file path; max_preview_items bounds scalar/small-array previews; "
            "allowed_roots is optional and otherwise comes from DQMC_ALLOWED_ROOTS. "
            "Example: {'path': '/scratch/phoenix/run/data.h5', "
            "'allowed_roots': ['/scratch/phoenix']}. Returns groups, datasets, "
            "shape, dtype, attrs, bounded previews, and truncation limits. The "
            "file is opened read-only."
        ),
    )
    def inspect_hdf5(
        path: str,
        max_preview_items: int = 8,
        max_objects: int = 1000,
        allowed_roots: list[str] | None = None,
    ) -> dict[str, Any]:
        try:
            return dqmc_inspect_hdf5(
                path,
                max_preview_items=max_preview_items,
                max_objects=max_objects,
                allowed_roots=allowed_roots,
            )
        except Exception as exc:
            return error_dict(exc)

    @server.tool(
        name="resolve_observable",
        description=(
            "Resolve a DQMC observable name to registry metadata and its HDF5 "
            "path. Use this before reading an observable when the canonical "
            "repo_id or storage path needs confirmation. Do not use this to read "
            "data from an HDF5 file; use read_observable for values. Parameters: "
            "name may be a repo id such as EqLt.density, an HDF5 path such as "
            "/meas_eqlt/density, or an unambiguous tail such as density; "
            "registry_path optionally overrides observables.yaml. Returns "
            "repo_id, h5_path, kind, time_kind, spin, measured_as, and related "
            "registry fields. Ambiguous shorthand returns a structured error with "
            "candidate repo ids."
        ),
    )
    def resolve_observable(
        name: str,
        registry_path: str | None = None,
    ) -> dict[str, Any]:
        try:
            return dqmc_resolve_observable(name, registry_path=registry_path)
        except Exception as exc:
            return error_dict(exc)

    @server.tool(
        name="read_observable",
        description=(
            "Read a registered DQMC observable from an HDF5 file read-only. Use "
            "this when you know the file path and need factual values/metadata for "
            "an observable such as EqLt.density or Uneqlt.gt0. Do not use this to "
            "inspect the whole file structure; call inspect_hdf5 first when "
            "datasets are unknown. Parameters: path is the HDF5 file; "
            "observable_name is a registry id, HDF5 path, or unambiguous tail; "
            "max_items bounds returned values; allowed_roots is optional and "
            "otherwise comes from DQMC_ALLOWED_ROOTS; registry_path optionally "
            "overrides observables.yaml. Returns registry metadata, "
            "dataset shape/dtype, numeric summaries, bounded previews, explicit "
            "error/uncertainty facts from registered or conventional error "
            "datasets, and metadata such as beta, dt, L, U, mu, sign, and "
            "n_sample when present. It does not label sign quality, error-bar "
            "overlap, or scientific reliability."
        ),
    )
    def read_observable(
        path: str,
        observable_name: str,
        max_items: int = 1024,
        allowed_roots: list[str] | None = None,
        registry_path: str | None = None,
    ) -> dict[str, Any]:
        try:
            return dqmc_read_observable(
                path,
                observable_name,
                max_items=max_items,
                allowed_roots=allowed_roots,
                registry_path=registry_path,
            )
        except Exception as exc:
            return error_dict(exc)

    @server.tool(
        name="summarize_run",
        description=(
            "Summarize a DQMC run directory using bounded read-only inspection. "
            "Use this after selecting a run to see discovered HDF5 files, basic "
            "metadata, and which registered observables are present or missing. "
            "Do not use this for current queue state; use query_slurm. Parameters: "
            "path is the run directory; max_files bounds inspected HDF5 files; "
            "allowed_roots is optional and otherwise comes from DQMC_ALLOWED_ROOTS. "
            "Returns per-file dataset/group counts, available/missing registered "
            "observables, metadata facts, and truncation flags."
        ),
    )
    def summarize_run(
        path: str,
        max_files: int = 20,
        allowed_roots: list[str] | None = None,
    ) -> dict[str, Any]:
        try:
            return dqmc_summarize_run(
                path,
                max_files=max_files,
                allowed_roots=allowed_roots,
            )
        except Exception as exc:
            return error_dict(exc)

    @server.tool(
        name="query_slurm",
        description=(
            "Query read-only SLURM job status with local squeue. Use this for "
            "current or recent queue/status questions. Do not use this to submit, "
            "cancel, or modify jobs; no mutating SLURM operation is exposed. "
            "Parameters: filters may include user, job_id, state, and partition. "
            "Example: {'filters': {'user': 'phoenix', 'state': 'RUNNING'}}. "
            "Returns parsed job rows, command arguments used, and whether JSON or "
            "fallback squeue output was used. If SLURM is unavailable, returns a "
            "structured tool_unavailable error."
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
