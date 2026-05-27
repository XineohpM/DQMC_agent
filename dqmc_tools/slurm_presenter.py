"""Human-readable summaries for SLURM status payloads."""

from __future__ import annotations

from typing import Any


CATEGORY_ORDER = ("running", "pending", "held_blocked", "other")
DEFAULT_MAX_GROUPS = 6
DEFAULT_MAX_EXAMPLES_PER_ARRAY = 3


def format_slurm_status_summary(
    payload: dict[str, Any],
    *,
    max_groups: int = DEFAULT_MAX_GROUPS,
    max_examples_per_array: int = DEFAULT_MAX_EXAMPLES_PER_ARRAY,
) -> str:
    """Format a query_slurm payload as a compact user-facing summary."""

    if payload.get("ok") is False:
        message = _text(payload.get("message")) or "unknown error"
        return f"SLURM 状态查询失败：{message}"

    summary = payload.get("summary") or {}
    total_jobs = int(summary.get("total_jobs") or 0)
    if total_jobs == 0:
        return "当前没有任务。"

    lines = [
        f"当前共有 {total_jobs} 个任务：{_format_category_counts(summary.get('category_counts') or {})}。"
    ]

    groups = (payload.get("groups") or {}).get("by_job_name") or []
    for group in groups[:max_groups]:
        lines.append(_format_job_name_group(group, max_examples_per_array=max_examples_per_array))

    remaining = len(groups) - max_groups
    if remaining > 0:
        lines.append(f"另有 {remaining} 个 job name 分组未展开。")

    return "\n".join(lines)


def _format_category_counts(counts: dict[str, Any]) -> str:
    return ", ".join(f"{name}={int(counts.get(name) or 0)}" for name in CATEGORY_ORDER)


def _format_job_name_group(group: dict[str, Any], *, max_examples_per_array: int) -> str:
    name = _text(group.get("job_name")) or "(unnamed)"
    total = int(group.get("total_jobs") or 0)
    state_counts = _format_counts(group.get("state_counts") or {})
    array_jobs = group.get("array_jobs") or []
    array_parts = [_format_array_group(array_group) for array_group in array_jobs]
    line = f"{name}: {total} 个任务"
    if state_counts:
        line += f"，{state_counts}"
    if array_parts:
        line += f"；{'; '.join(array_parts)}"
    line += "。"

    examples = _job_examples(array_jobs, max_examples_per_array=max_examples_per_array)
    if examples:
        line += f"\n  示例：{'; '.join(examples)}"
    return line


def _format_array_group(array_group: dict[str, Any]) -> str:
    array_id = _text(array_group.get("array_job_id")) or "unknown"
    total = int(array_group.get("total_jobs") or 0)
    part = f"array {array_id}: {total} 个任务"
    task_span = _format_task_span(array_group.get("array_task_ids") or [])
    if task_span:
        part += f"，tasks {task_span}"
    return part


def _format_counts(counts: dict[str, Any]) -> str:
    return ", ".join(f"{key}={int(counts[key])}" for key in sorted(counts))


def _format_task_span(task_ids: list[Any]) -> str:
    values = [_text(value) for value in task_ids if _text(value) != ""]
    if not values:
        return ""
    numeric_values = [int(value) for value in values if value.isdigit()]
    if len(numeric_values) == len(values):
        numeric_values.sort()
        if numeric_values == list(range(numeric_values[0], numeric_values[-1] + 1)):
            return f"{numeric_values[0]}-{numeric_values[-1]}"
    return ",".join(values)


def _job_examples(array_jobs: list[dict[str, Any]], *, max_examples_per_array: int) -> list[str]:
    examples: list[str] = []
    for array_group in array_jobs:
        for job in (array_group.get("jobs") or [])[:max_examples_per_array]:
            examples.append(_format_job_example(job))
    return [example for example in examples if example]


def _format_job_example(job: dict[str, Any]) -> str:
    job_id = _text(job.get("job_id") or job.get("id"))
    state = _text(job.get("job_state") or job.get("state") or job.get("state_description")).upper()
    reason = _text(job.get("state_reason") or job.get("reason") or job.get("nodes"))
    parts = [job_id, state, reason]
    return " ".join(part for part in parts if part)


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
