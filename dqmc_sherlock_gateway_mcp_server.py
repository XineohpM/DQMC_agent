"""Thin MCP adapter for short-lived Sherlock remote gateway calls."""

from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from dqmc_tools import remote_gateway
from dqmc_tools.errors import InvalidArgumentError, error_dict


SERVER_INSTRUCTIONS = (
    "Sherlock gateway tools run locally and call Sherlock through short-lived "
    "SSH invocations of dqmc_tools.remote_call. They do not start a remote "
    "Codex, do not keep a long-lived MCP server on Sherlock, and do not submit "
    "or cancel SLURM jobs. The default profile is status-only and redacts "
    "Sherlock path fields from returned data."
)
PROFILE_ENV = "DQMC_SHERLOCK_GATEWAY_PROFILE"
STATUS_ONLY_PROFILE = "status-only"
DATA_READING_PROFILE = "data-reading"
PROFILE_ALIASES = {
    "status": STATUS_ONLY_PROFILE,
    STATUS_ONLY_PROFILE: STATUS_ONLY_PROFILE,
    DATA_READING_PROFILE: DATA_READING_PROFILE,
}


def build_server(profile: str | None = None) -> FastMCP:
    """Build the Sherlock remote gateway MCP server."""

    profile = _normalize_profile(profile or os.environ.get(PROFILE_ENV, STATUS_ONLY_PROFILE))
    server = FastMCP("dqmc-sherlock-gateway", instructions=SERVER_INSTRUCTIONS)

    @server.tool(
        name="sherlock_query_slurm",
        description=(
            "Query Sherlock current SLURM status through a short-lived SSH "
            "remote_call. This is read-only and never submits, cancels, or "
            "mutates jobs. Parameters: optional filters with me, user, job_id, "
            "state, or partition. Sherlock path fields are redacted. The "
            "response includes a top-level formatted_summary; for user-facing "
            "status replies, output formatted_summary verbatim instead of "
            "rewriting the table or running shell commands."
        ),
    )
    def sherlock_query_slurm(filters: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            return remote_gateway.call_sherlock_tool("query_slurm", {"filters": filters})
        except Exception as exc:
            return error_dict(exc)

    @server.tool(
        name="sherlock_query_slurm_history",
        description=(
            "Query Sherlock historical SLURM status through a short-lived SSH "
            "remote_call to sacct. This is read-only and never submits, cancels, "
            "or mutates jobs. Parameters: optional filters with me, user, job_id, "
            "state, start, end, partition, or max_rows. Sherlock path fields are "
            "redacted."
        ),
    )
    def sherlock_query_slurm_history(filters: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            return remote_gateway.call_sherlock_tool("query_slurm_history", {"filters": filters})
        except Exception as exc:
            return error_dict(exc)

    @server.tool(
        name="sherlock_get_slurm_job_detail",
        description=(
            "Get Sherlock SLURM job detail through a short-lived SSH remote_call. "
            "It checks current queue first, then historical sacct when enabled. "
            "This is read-only. Parameters: job_id, include_history. Sherlock path "
            "fields are redacted. The response includes a top-level formatted_detail; "
            "for user-facing job detail replies, output formatted_detail verbatim "
            "instead of running direct SSH, custom squeue, awk, or shell commands."
        ),
    )
    def sherlock_get_slurm_job_detail(job_id: str, include_history: bool = True) -> dict[str, Any]:
        try:
            return remote_gateway.call_sherlock_tool(
                "get_slurm_job_detail",
                {"job_id": job_id, "include_history": include_history},
            )
        except Exception as exc:
            return error_dict(exc)

    if profile == DATA_READING_PROFILE:

        @server.tool(
            name="sherlock_summarize_run",
            description=(
                "Summarize one explicit Sherlock run directory through a short-lived "
                "SSH remote_call. This does not discover runs or scan large Sherlock "
                "directories. Defaults are bounded to keep output small. Parameters: "
                "path; optional max_files, max_registry_entries, max_log_chars, "
                "allowed_roots, registry_path."
            ),
        )
        def sherlock_summarize_run(
            path: str,
            max_files: int = 5,
            max_registry_entries: int = 50,
            max_log_chars: int = 1000,
            allowed_roots: list[str] | None = None,
            registry_path: str | None = None,
        ) -> dict[str, Any]:
            try:
                return remote_gateway.call_sherlock_tool(
                    "summarize_run",
                    {
                        "path": path,
                        "max_files": max_files,
                        "max_registry_entries": max_registry_entries,
                        "max_log_chars": max_log_chars,
                        "allowed_roots": allowed_roots,
                        "registry_path": registry_path,
                    },
                    include_remote_env=True,
                    redact_paths=False,
                )
            except Exception as exc:
                return error_dict(exc)

    return server


def _normalize_profile(profile: str) -> str:
    normalized = str(profile).strip().lower()
    if normalized in PROFILE_ALIASES:
        return PROFILE_ALIASES[normalized]
    raise InvalidArgumentError(
        "Unsupported Sherlock gateway profile.",
        details={"profile": profile, "allowed_profiles": sorted(PROFILE_ALIASES)},
    )


mcp = build_server()


if __name__ == "__main__":
    mcp.run()
