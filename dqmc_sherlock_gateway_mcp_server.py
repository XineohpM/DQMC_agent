"""Thin MCP adapter for short-lived Sherlock remote gateway calls."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from dqmc_tools import remote_gateway
from dqmc_tools.errors import error_dict


SERVER_INSTRUCTIONS = (
    "Sherlock gateway tools run locally and call Sherlock through short-lived "
    "SSH invocations of dqmc_tools.remote_call. They do not start a remote "
    "Codex, do not keep a long-lived MCP server on Sherlock, and do not submit "
    "or cancel SLURM jobs."
)


def build_server() -> FastMCP:
    """Build the Sherlock remote gateway MCP server."""

    server = FastMCP("dqmc-sherlock-gateway", instructions=SERVER_INSTRUCTIONS)

    @server.tool(
        name="sherlock_query_slurm",
        description=(
            "Query Sherlock current SLURM status through a short-lived SSH "
            "remote_call. This is read-only and never submits, cancels, or "
            "mutates jobs. Parameters: optional filters with me, user, job_id, "
            "state, or partition."
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
            "state, start, end, partition, or max_rows."
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
            "This is read-only. Parameters: job_id, include_history."
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
            )
        except Exception as exc:
            return error_dict(exc)

    return server


mcp = build_server()


if __name__ == "__main__":
    mcp.run()
