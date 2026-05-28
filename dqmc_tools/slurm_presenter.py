"""Human-readable summaries for SLURM status payloads."""

from __future__ import annotations

from typing import Any


DEFAULT_MAX_GROUPS = 0
DEFAULT_MAX_EXAMPLES_PER_ARRAY = 3


def format_slurm_status_summary(
    payload: dict[str, Any],
    *,
    max_groups: int = DEFAULT_MAX_GROUPS,
    max_examples_per_array: int = DEFAULT_MAX_EXAMPLES_PER_ARRAY,
) -> str:
    """Format a query_slurm payload as a compact table summary."""

    if payload.get("ok") is False:
        message = _text(payload.get("message")) or "unknown error"
        return f"SLURM status query failed: {message}"

    summary = payload.get("summary") or {}
    total_jobs = int(summary.get("total_jobs") or 0)
    if total_jobs == 0:
        return "No current SLURM jobs."

    rows = _table_rows((payload.get("groups") or {}).get("by_job_name") or [])
    if max_groups:
        rows = rows[:max_groups]
    table_lines = _format_table(rows)
    category_counts = summary.get("category_counts") or {}
    return "\n".join(
        [
            "```",
            *table_lines,
            "```",
            f"Total jobs: {total_jobs}",
            f"Pending: {_pending_count(category_counts, summary.get('state_counts') or {})}",
            f"Running: {_running_count(category_counts, summary.get('state_counts') or {})}",
        ]
    )


def _table_rows(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for group in groups:
        job_name = _text(group.get("job_name")) or "(unnamed)"
        array_jobs = group.get("array_jobs") or []
        if not array_jobs:
            rows.append(
                {
                    "job_name": job_name,
                    "array_job_id": _fallback_job_id(group),
                    "total": int(group.get("total_jobs") or 0),
                    "pending": _pending_count(group.get("category_counts") or {}, group.get("state_counts") or {}),
                    "running": _running_count(group.get("category_counts") or {}, group.get("state_counts") or {}),
                }
            )
            continue
        for array_group in array_jobs:
            rows.append(
                {
                    "job_name": job_name,
                    "array_job_id": _array_group_id(array_group),
                    "total": int(array_group.get("total_jobs") or 0),
                    "pending": _pending_count(
                        array_group.get("category_counts") or {},
                        array_group.get("state_counts") or {},
                    ),
                    "running": _running_count(
                        array_group.get("category_counts") or {},
                        array_group.get("state_counts") or {},
                    ),
                }
            )
    return rows


def _format_table(rows: list[dict[str, Any]]) -> list[str]:
    headers = {
        "job_name": "Job Name",
        "array_job_id": "Array Job ID",
        "total": "Total",
        "pending": "Pending",
        "running": "Running",
    }
    widths = {
        key: max(len(headers[key]), *(len(str(row[key])) for row in rows))
        for key in headers
    }
    lines = [
        (
            f"{headers['job_name']:<{widths['job_name']}}  "
            f"{headers['array_job_id']:<{widths['array_job_id']}}  "
            f"{headers['total']:<{widths['total']}}  "
            f"{headers['pending']:<{widths['pending']}}  "
            f"{headers['running']:<{widths['running']}}"
        ),
        *[
            (
                f"{row['job_name']:<{widths['job_name']}}  "
                f"{row['array_job_id']:<{widths['array_job_id']}}  "
                f"{row['total']:<{widths['total']}}  "
                f"{row['pending']:<{widths['pending']}}  "
                f"{row['running']:<{widths['running']}}"
            )
            for row in rows
        ],
    ]
    return [line.rstrip() for line in lines]


def _array_group_id(array_group: dict[str, Any]) -> str:
    array_job_id = _text(array_group.get("array_job_id"))
    if array_job_id:
        return array_job_id
    return _fallback_job_id(array_group)


def _fallback_job_id(group: dict[str, Any]) -> str:
    for job in group.get("jobs") or []:
        job_id = _text(job.get("job_id") or job.get("id"))
        if job_id:
            return job_id
    return "unknown"


def _pending_count(category_counts: dict[str, Any], state_counts: dict[str, Any]) -> int:
    if "pending" in category_counts:
        return int(category_counts.get("pending") or 0)
    return int(state_counts.get("PENDING") or state_counts.get("PD") or 0)


def _running_count(category_counts: dict[str, Any], state_counts: dict[str, Any]) -> int:
    if "running" in category_counts:
        return int(category_counts.get("running") or 0)
    return sum(
        int(state_counts.get(state) or 0)
        for state in ("RUNNING", "R", "COMPLETING", "CG", "CONFIGURING", "CF", "RESIZING", "RS")
    )


def _text(value: Any) -> str:
    scalar = _scalar(value)
    if scalar is None:
        return ""
    return str(scalar).strip()


def _scalar(value: Any) -> Any:
    if isinstance(value, list):
        for item in value:
            scalar = _scalar(item)
            if _has_value(scalar):
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
            return _scalar(value["id"])
        return None
    return value


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    return str(value).strip() not in {"", "N/A", "NONE"}
