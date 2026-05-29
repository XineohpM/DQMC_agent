"""Human-readable summaries for SLURM status payloads."""

from __future__ import annotations

from collections import Counter
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


def format_slurm_job_detail(
    payload: dict[str, Any],
    *,
    max_sample_jobs: int = 5,
    max_step_rows: int = 8,
) -> str:
    """Format a get_slurm_job_detail payload as a compact English summary."""

    if payload.get("ok") is False:
        message = _text(payload.get("message")) or "unknown error"
        return f"SLURM job detail query failed: {message}"

    job_id = _text(payload.get("job_id")) or "unknown"
    candidates = [item for item in (payload.get("candidates") or []) if isinstance(item, dict)]
    if not candidates:
        return f"No SLURM job detail found for job {job_id}."

    if len(candidates) == 1:
        return _format_single_job_detail(job_id, candidates[0])
    if _is_step_group(job_id, candidates):
        return _format_step_group_detail(job_id, candidates, max_step_rows=max_step_rows)
    return _format_multi_candidate_detail(job_id, candidates, max_sample_jobs=max_sample_jobs)


def _format_single_job_detail(job_id: str, candidate: dict[str, Any]) -> str:
    rows = [
        ("Job ID", _candidate_text(candidate, "job_id")),
        ("Job Name", _candidate_text(candidate, "job_name")),
        ("Source", _candidate_text(candidate, "source")),
        ("State", _candidate_text(candidate, "state")),
        ("Category", _candidate_text(candidate, "category")),
        ("Partition", _candidate_text(candidate, "partition")),
        ("Elapsed", _candidate_text(candidate, "elapsed")),
        ("Time Limit", _candidate_text(candidate, "time_limit")),
        ("Node/Reason", _candidate_text(candidate, "node_or_reason")),
        ("Exit Code", _candidate_text(candidate, "exit_code")),
        ("Submit", _candidate_text(candidate, "submit")),
        ("Start", _candidate_text(candidate, "start")),
        ("End", _candidate_text(candidate, "end")),
    ]
    table = _format_key_value_table([(key, value) for key, value in rows if value])
    return "\n".join([f"SLURM job detail for {job_id}", "```", *table, "```"])


def _format_multi_candidate_detail(
    job_id: str,
    candidates: list[dict[str, Any]],
    *,
    max_sample_jobs: int,
) -> str:
    lines = [
        f"SLURM job detail for {job_id}",
        f"Job name: {_common_job_name(candidates)}",
        f"Source: {_source_summary(candidates)}",
        f"Matches: {len(candidates)}",
        f"State counts: {_count_summary(_candidate_text(candidate, 'state') for candidate in candidates)}",
        f"Category counts: {_count_summary(_candidate_text(candidate, 'category') for candidate in candidates)}",
        f"Sample jobs: {_sample_jobs(candidates, max_sample_jobs=max_sample_jobs)}",
    ]
    return "\n".join(lines)


def _format_step_group_detail(
    job_id: str,
    candidates: list[dict[str, Any]],
    *,
    max_step_rows: int,
) -> str:
    shown_rows = candidates[:max_step_rows]
    table = _format_step_table(shown_rows)
    lines = [
        f"SLURM job detail for {job_id}",
        f"Job name: {_common_job_name(candidates)}",
        f"Source: {_source_summary(candidates)}",
        f"Matches: {len(candidates)}",
        "Step group: task-level sacct rows; no unique step row was guessed.",
        f"State counts: {_count_summary(_candidate_text(candidate, 'state') for candidate in candidates)}",
        f"Exit code counts: {_count_summary(_candidate_text(candidate, 'exit_code') for candidate in candidates)}",
        "Rows:",
        "```",
        *table,
        "```",
    ]
    if len(candidates) > len(shown_rows):
        lines.append(f"Additional rows omitted: {len(candidates) - len(shown_rows)}")
    return "\n".join(lines)


def _format_key_value_table(rows: list[tuple[str, str]]) -> list[str]:
    field_width = max(12, *(len(key) for key, _value in rows))
    lines = [f"{'Field':<{field_width}}  Value"]
    lines.extend(f"{key:<{field_width}}  {value}".rstrip() for key, value in rows)
    return lines


def _format_step_table(candidates: list[dict[str, Any]]) -> list[str]:
    rows = [
        {
            "job_id": _candidate_text(candidate, "job_id"),
            "state": _candidate_text(candidate, "state"),
            "exit_code": _candidate_text(candidate, "exit_code"),
            "elapsed": _candidate_text(candidate, "elapsed"),
            "node_or_reason": _candidate_text(candidate, "node_or_reason"),
        }
        for candidate in candidates
    ]
    headers = {
        "job_id": "Job ID",
        "state": "State",
        "exit_code": "Exit Code",
        "elapsed": "Elapsed",
        "node_or_reason": "Node/Reason",
    }
    widths = {
        key: max(len(headers[key]), *(len(row[key]) for row in rows))
        for key in headers
    }
    widths["job_id"] = max(21, widths["job_id"])
    lines = [
        (
            f"{headers['job_id']:<{widths['job_id']}}  "
            f"{headers['state']:<{widths['state']}}  "
            f"{headers['exit_code']:<{widths['exit_code']}}  "
            f"{headers['elapsed']:<{widths['elapsed']}}  "
            f"{headers['node_or_reason']:<{widths['node_or_reason']}}"
        ).rstrip()
    ]
    lines.extend(
        (
            f"{row['job_id']:<{widths['job_id']}}  "
            f"{row['state']:<{widths['state']}}  "
            f"{row['exit_code']:<{widths['exit_code']}}  "
            f"{row['elapsed']:<{widths['elapsed']}}  "
            f"{row['node_or_reason']:<{widths['node_or_reason']}}"
        ).rstrip()
        for row in rows
    )
    return lines


def _is_step_group(job_id: str, candidates: list[dict[str, Any]]) -> bool:
    candidate_ids = [_candidate_text(candidate, "job_id") for candidate in candidates]
    if not job_id or len(candidates) <= 1:
        return False
    return any("." in candidate_id for candidate_id in candidate_ids) and all(
        candidate_id == job_id or candidate_id.startswith(f"{job_id}.")
        for candidate_id in candidate_ids
        if candidate_id
    )


def _common_job_name(candidates: list[dict[str, Any]]) -> str:
    for candidate in candidates:
        job_name = _candidate_text(candidate, "job_name")
        if job_name and job_name.lower() not in {"batch", "extern", "0"}:
            return job_name
    return "unknown"


def _source_summary(candidates: list[dict[str, Any]]) -> str:
    sources = [_candidate_text(candidate, "source") for candidate in candidates]
    counts = _counts(source for source in sources if source)
    if not counts:
        return "unknown"
    if len(counts) == 1:
        return next(iter(counts))
    return _count_summary(counts.elements())


def _count_summary(values) -> str:
    counts = _counts(value for value in values if value)
    if not counts:
        return "none"
    return ", ".join(f"{key}={counts[key]}" for key in sorted(counts))


def _sample_jobs(candidates: list[dict[str, Any]], *, max_sample_jobs: int) -> str:
    job_ids = [_candidate_text(candidate, "job_id") for candidate in candidates]
    job_ids = [job_id for job_id in job_ids if job_id]
    if not job_ids:
        return "none"
    shown = job_ids[:max_sample_jobs]
    sample = ", ".join(shown)
    omitted = len(job_ids) - len(shown)
    if omitted > 0:
        sample = f"{sample}, ... (+{omitted} more)"
    return sample


def _candidate_text(candidate: dict[str, Any], key: str) -> str:
    value = _text(candidate.get(key))
    if value:
        return value
    raw = candidate.get("raw")
    if isinstance(raw, dict):
        return _text(raw.get(key))
    return ""


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


def _counts(values) -> Counter[str]:
    return Counter(value for value in values if value)
