"""Read-only SLURM status queries."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from dqmc_tools.errors import InvalidArgumentError, ToolUnavailableError


SUPPORTED_FILTERS = {"user", "job_id", "state", "partition"}
FALLBACK_COLUMNS = (
    "job_id",
    "name",
    "user",
    "state",
    "time_used",
    "time_limit",
    "partition",
    "nodes",
)


def query_slurm(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Query SLURM job status with read-only squeue."""

    parsed_filters = _validate_filters(filters or {})
    squeue_path = shutil.which("squeue")
    if not squeue_path:
        raise ToolUnavailableError(
            "SLURM command `squeue` is not available.",
            details={"command": "squeue"},
        )

    json_command = _build_squeue_command(squeue_path, parsed_filters, json_output=True)
    attempted = [json_command]
    json_result = _run_command(json_command)
    if json_result.returncode == 0:
        try:
            payload = json.loads(json_result.stdout or "{}")
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            return {
                "ok": True,
                "source": "squeue_json",
                "command": json_command,
                "commands_attempted": attempted,
                "jobs": payload.get("jobs", []),
                "raw": payload,
            }

    fallback_command = _build_squeue_command(squeue_path, parsed_filters, json_output=False)
    attempted.append(fallback_command)
    fallback_result = _run_command(fallback_command)
    if fallback_result.returncode != 0:
        raise ToolUnavailableError(
            "SLURM `squeue` query failed.",
            details={
                "commands_attempted": attempted,
                "json_stderr": json_result.stderr,
                "fallback_stderr": fallback_result.stderr,
            },
        )

    return {
        "ok": True,
        "source": "squeue_fallback",
        "command": fallback_command,
        "commands_attempted": attempted,
        "jobs": _parse_fallback_rows(fallback_result.stdout),
    }


def _validate_filters(filters: dict[str, Any]) -> dict[str, str]:
    unknown = sorted(set(filters) - SUPPORTED_FILTERS)
    if unknown:
        raise InvalidArgumentError(
            "Unsupported SLURM filters were provided.",
            details={"unsupported_filters": unknown, "supported_filters": sorted(SUPPORTED_FILTERS)},
        )
    parsed: dict[str, str] = {}
    for key, value in filters.items():
        if value is None or str(value).strip() == "":
            continue
        parsed[key] = str(value).strip()
    return parsed


def _build_squeue_command(squeue_path: str, filters: dict[str, str], *, json_output: bool) -> list[str]:
    args = [squeue_path]
    if json_output:
        args.append("--json")
    else:
        args.extend(["--noheader", "--format=%i|%j|%u|%T|%M|%l|%P|%R"])

    if "user" in filters:
        args.extend(["--user", filters["user"]])
    if "job_id" in filters:
        args.extend(["--jobs", filters["job_id"]])
    if "state" in filters:
        args.extend(["--states", filters["state"]])
    if "partition" in filters:
        args.extend(["--partition", filters["partition"]])
    return args


def _run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, capture_output=True, text=True, check=False, timeout=30)
    except OSError as exc:
        raise ToolUnavailableError(
            "SLURM command could not be executed.",
            details={"command": args, "reason": str(exc)},
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ToolUnavailableError(
            "SLURM command timed out.",
            details={"command": args, "timeout_seconds": exc.timeout},
        ) from exc


def _parse_fallback_rows(stdout: str) -> list[dict[str, str]]:
    rows = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("|", maxsplit=len(FALLBACK_COLUMNS) - 1)
        parts = parts + [""] * (len(FALLBACK_COLUMNS) - len(parts))
        rows.append(dict(zip(FALLBACK_COLUMNS, [part.strip() for part in parts])))
    return rows
