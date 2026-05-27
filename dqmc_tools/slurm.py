"""Read-only SLURM status queries."""

from __future__ import annotations

import json
import getpass
import shutil
import subprocess
from collections import Counter, defaultdict
from typing import Any

from dqmc_tools.errors import InvalidArgumentError, ToolUnavailableError


SUPPORTED_FILTERS = {"me", "user", "job_id", "state", "partition"}
HISTORY_SUPPORTED_FILTERS = {"me", "user", "job_id", "state", "start", "end", "partition", "max_rows"}
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
SACCT_COLUMNS = (
    "JobID",
    "JobName",
    "User",
    "State",
    "ExitCode",
    "Elapsed",
    "Timelimit",
    "Submit",
    "Start",
    "End",
    "Partition",
    "NodeList",
    "WorkDir",
)
SACCT_FIELD_NAMES = (
    "job_id",
    "job_name",
    "user",
    "state",
    "exit_code",
    "elapsed",
    "time_limit",
    "submit",
    "start",
    "end",
    "partition",
    "node_list",
    "work_dir",
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
            jobs = payload.get("jobs") or []
            return {
                "ok": True,
                "source": "squeue_json",
                "command": json_command,
                "commands_attempted": attempted,
                "jobs": jobs,
                **_grouped_job_summary(jobs),
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

    fallback_jobs = _parse_fallback_rows(fallback_result.stdout)
    return {
        "ok": True,
        "source": "squeue_fallback",
        "command": fallback_command,
        "commands_attempted": attempted,
        "jobs": fallback_jobs,
        **_grouped_job_summary(fallback_jobs),
    }


def query_slurm_history(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Query historical SLURM job status with read-only sacct."""

    parsed_filters = _validate_history_filters(filters or {})
    max_rows = parsed_filters.pop("max_rows", None)
    sacct_path = shutil.which("sacct")
    if not sacct_path:
        raise ToolUnavailableError(
            "SLURM command `sacct` is not available.",
            details={"command": "sacct"},
        )

    command = _build_sacct_command(sacct_path, parsed_filters)
    result = _run_command(command)
    if result.returncode != 0:
        raise ToolUnavailableError(
            "SLURM `sacct` query failed.",
            details={"command": command, "stderr": result.stderr},
        )

    jobs, warnings = _parse_sacct_rows(result.stdout)
    if max_rows is not None and len(jobs) > max_rows:
        jobs = jobs[:max_rows]
        warnings.append(f"Result truncated to max_rows={max_rows}.")

    return {
        "ok": True,
        "source": "sacct_parsable2",
        "command": command,
        "jobs": jobs,
        "summary": _history_summary(jobs),
        "warnings": warnings,
    }


def _validate_filters(filters: dict[str, Any]) -> dict[str, Any]:
    unknown = sorted(set(filters) - SUPPORTED_FILTERS)
    if unknown:
        raise InvalidArgumentError(
            "Unsupported SLURM filters were provided.",
            details={"unsupported_filters": unknown, "supported_filters": sorted(SUPPORTED_FILTERS)},
        )
    parsed: dict[str, Any] = {}
    for key, value in filters.items():
        if value is None or str(value).strip() == "":
            continue
        if key == "me":
            if _truthy_filter(value):
                parsed[key] = True
            continue
        parsed[key] = str(value).strip()
    return parsed


def _validate_history_filters(filters: dict[str, Any]) -> dict[str, Any]:
    unknown = sorted(set(filters) - HISTORY_SUPPORTED_FILTERS)
    if unknown:
        raise InvalidArgumentError(
            "Unsupported SLURM history filters were provided.",
            details={"unsupported_filters": unknown, "supported_filters": sorted(HISTORY_SUPPORTED_FILTERS)},
        )

    parsed: dict[str, Any] = {}
    for key, value in filters.items():
        if value is None or str(value).strip() == "":
            continue
        if key == "me":
            if _truthy_filter(value):
                parsed[key] = True
            continue
        if key == "max_rows":
            parsed[key] = _positive_int_filter(key, value)
            continue
        parsed[key] = str(value).strip()
    return parsed


def _build_squeue_command(squeue_path: str, filters: dict[str, Any], *, json_output: bool) -> list[str]:
    args = [squeue_path]
    if json_output:
        args.append("--json")
    else:
        args.extend(["--noheader", "--format=%i|%j|%u|%T|%M|%l|%P|%R"])

    if filters.get("me"):
        args.append("--me")
    if "user" in filters:
        args.extend(["--user", filters["user"]])
    if "job_id" in filters:
        args.extend(["--jobs", filters["job_id"]])
    if "state" in filters:
        args.extend(["--states", filters["state"]])
    if "partition" in filters:
        args.extend(["--partition", filters["partition"]])
    return args


def _build_sacct_command(sacct_path: str, filters: dict[str, Any]) -> list[str]:
    args = [
        sacct_path,
        "--parsable2",
        "--noheader",
        f"--format={','.join(SACCT_COLUMNS)}",
    ]
    if filters.get("me"):
        args.extend(["--user", getpass.getuser()])
    if "user" in filters:
        args.extend(["--user", filters["user"]])
    if "job_id" in filters:
        args.extend(["--jobs", filters["job_id"]])
    if "state" in filters:
        args.extend(["--state", filters["state"]])
    if "start" in filters:
        args.extend(["--starttime", filters["start"]])
    if "end" in filters:
        args.extend(["--endtime", filters["end"]])
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


def _parse_sacct_rows(stdout: str) -> tuple[list[dict[str, str]], list[str]]:
    rows = []
    short_row_count = 0
    for line in stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("|", maxsplit=len(SACCT_COLUMNS) - 1)
        if len(parts) < len(SACCT_COLUMNS):
            short_row_count += 1
        parts = parts + [""] * (len(SACCT_COLUMNS) - len(parts))
        row = dict(zip(SACCT_FIELD_NAMES, [_slurm_text(part) for part in parts]))
        row["state"] = row["state"].upper()
        rows.append(row)

    warnings = []
    if short_row_count:
        warnings.append(f"{short_row_count} sacct row(s) had fewer fields than expected.")
    return rows, warnings


def _truthy_filter(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise InvalidArgumentError(
        "SLURM `me` filter must be a boolean value.",
        details={"me": value},
    )


def _positive_int_filter(key: str, value: Any) -> int:
    try:
        parsed = int(str(value).strip())
    except ValueError as exc:
        raise InvalidArgumentError(
            f"SLURM `{key}` filter must be a positive integer.",
            details={key: value},
        ) from exc
    if parsed <= 0:
        raise InvalidArgumentError(
            f"SLURM `{key}` filter must be a positive integer.",
            details={key: value},
        )
    return parsed


def _grouped_job_summary(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    facts = [_job_facts(job) for job in jobs]
    state_counts = _counts(fact["state"] for fact in facts)
    category_counts = _counts(fact["category"] for fact in facts)
    by_job_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fact in facts:
        by_job_name[fact["job_name"]].append(fact)

    groups = []
    array_job_total = 0
    for job_name in sorted(by_job_name):
        group_facts = sorted(by_job_name[job_name], key=_job_sort_key)
        by_array: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for fact in group_facts:
            by_array[fact["array_job_id"]].append(fact)

        array_groups = []
        for array_job_id in sorted(by_array, key=_natural_sort_key):
            array_facts = sorted(by_array[array_job_id], key=_job_sort_key)
            array_groups.append({
                "array_job_id": array_job_id,
                "total_jobs": len(array_facts),
                "state_counts": _counts(fact["state"] for fact in array_facts),
                "category_counts": _counts(fact["category"] for fact in array_facts),
                "array_task_ids": sorted(
                    {fact["array_task_id"] for fact in array_facts if fact["array_task_id"] is not None},
                    key=_natural_sort_key,
                ),
                "jobs": [fact["raw"] for fact in array_facts],
            })

        array_job_total += len(array_groups)
        groups.append({
            "job_name": job_name,
            "total_jobs": len(group_facts),
            "state_counts": _counts(fact["state"] for fact in group_facts),
            "category_counts": _counts(fact["category"] for fact in group_facts),
            "array_job_count": len(array_groups),
            "array_jobs": array_groups,
        })

    return {
        "summary": {
            "total_jobs": len(jobs),
            "state_counts": state_counts,
            "category_counts": category_counts,
            "job_name_count": len(groups),
            "array_job_count": array_job_total,
        },
        "groups": {"by_job_name": groups},
    }


def _history_summary(jobs: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "total_jobs": len(jobs),
        "state_counts": _counts(job["state"] for job in jobs),
        "exit_code_counts": _counts(job["exit_code"] for job in jobs),
    }


def _job_facts(job: dict[str, Any]) -> dict[str, Any]:
    job_id = _slurm_text(job.get("job_id") or job.get("id") or "")
    state = _job_state(job)
    return {
        "raw": job,
        "job_id": job_id,
        "job_name": _slurm_text(job.get("name") or job.get("job_name") or "(unnamed)"),
        "state": state,
        "category": _state_category(state, _job_reason(job)),
        "array_job_id": _array_job_id(job, job_id),
        "array_task_id": _array_task_id(job, job_id),
    }


def _job_state(job: dict[str, Any]) -> str:
    value = job.get("job_state") or job.get("state") or job.get("state_description") or "UNKNOWN"
    return _slurm_text(value).upper() or "UNKNOWN"


def _job_reason(job: dict[str, Any]) -> str:
    value = job.get("state_reason") or job.get("reason") or job.get("nodes") or ""
    return _slurm_text(value)


def _array_job_id(job: dict[str, Any], job_id: str) -> str:
    value = _slurm_scalar(job.get("array_job_id"))
    if _has_slurm_value(value):
        return str(value).strip()
    if "_" in job_id:
        return job_id.split("_", maxsplit=1)[0]
    return job_id or "unknown"


def _array_task_id(job: dict[str, Any], job_id: str) -> str | None:
    value = _slurm_scalar(job.get("array_task_id"))
    if _has_slurm_value(value):
        return str(value).strip()
    if "_" in job_id:
        return job_id.split("_", maxsplit=1)[1]
    return None


def _slurm_text(value: Any) -> str:
    scalar = _slurm_scalar(value)
    if scalar is None:
        return ""
    return str(scalar).strip()


def _slurm_scalar(value: Any) -> Any:
    if isinstance(value, list):
        for item in value:
            scalar = _slurm_scalar(item)
            if _has_slurm_value(scalar):
                return scalar
        return None
    if isinstance(value, dict):
        if value.get("set") is False:
            return None
        if value.get("infinite") is True:
            return "INFINITE"
        if "number" in value:
            return value["number"]
        if "name" in value:
            return value["name"]
        if "id" in value:
            return _slurm_scalar(value["id"])
        return None
    return value


def _has_slurm_value(value: Any) -> bool:
    if value is None:
        return False
    return str(value).strip() not in {"", "N/A", "NONE"}


def _state_category(state: str, reason: str) -> str:
    normalized_state = state.strip().upper()
    normalized_reason = reason.strip().upper().replace(" ", "")
    if normalized_state in {"RUNNING", "R", "COMPLETING", "CG", "CONFIGURING", "CF", "RESIZING", "RS"}:
        return "running"
    if normalized_state in {"PENDING", "PD"}:
        if normalized_reason in {
            "DEPENDENCY",
            "DEPENDENCYNEVER",
            "JOBHELDADMIN",
            "JOBHELDUSER",
            "PARTITIONDOWN",
            "REQNODENOTAVAIL",
        }:
            return "held_blocked"
        return "pending"
    if normalized_state in {
        "BOOT_FAIL",
        "BF",
        "FAILED",
        "F",
        "NODE_FAIL",
        "NF",
        "OUT_OF_MEMORY",
        "OOM",
        "PREEMPTED",
        "PR",
        "SPECIAL_EXIT",
        "SE",
        "STOPPED",
        "ST",
        "SUSPENDED",
        "S",
        "TIMEOUT",
        "TO",
    }:
        return "held_blocked"
    return "other"


def _counts(values) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _job_sort_key(fact: dict[str, Any]) -> tuple[Any, ...]:
    return (
        _natural_sort_key(fact["array_job_id"]),
        _natural_sort_key(fact["array_task_id"] or ""),
        _natural_sort_key(fact["job_id"]),
    )


def _natural_sort_key(value: Any) -> tuple[int, Any]:
    text = str(value)
    if text.isdigit():
        return (0, int(text))
    return (1, text)
