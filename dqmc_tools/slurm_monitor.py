"""Agent-layer helpers for comparing SLURM status snapshots."""

from __future__ import annotations

from typing import Any


def diff_slurm_snapshots(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Compare two query_slurm payloads without polling or background state."""

    previous_jobs = {_job_id(job): job for job in previous.get("jobs", []) if _job_id(job)}
    current_jobs = {_job_id(job): job for job in current.get("jobs", []) if _job_id(job)}

    added = [_job_summary(current_jobs[job_id]) for job_id in sorted(set(current_jobs) - set(previous_jobs))]
    removed = [_job_summary(previous_jobs[job_id]) for job_id in sorted(set(previous_jobs) - set(current_jobs))]
    state_changed = []
    unchanged_count = 0
    for job_id in sorted(set(previous_jobs) & set(current_jobs)):
        previous_state = _job_state(previous_jobs[job_id])
        current_state = _job_state(current_jobs[job_id])
        if previous_state != current_state:
            state_changed.append({
                "job_id": job_id,
                "job_name": _job_name(current_jobs[job_id]) or _job_name(previous_jobs[job_id]),
                "previous_state": previous_state,
                "current_state": current_state,
                "previous": previous_jobs[job_id],
                "current": current_jobs[job_id],
            })
        else:
            unchanged_count += 1

    return {
        "ok": True,
        "added": added,
        "removed": removed,
        "state_changed": state_changed,
        "unchanged_count": unchanged_count,
    }


def format_slurm_snapshot_diff(diff: dict[str, Any]) -> str:
    """Format a snapshot diff for an agent/user response."""

    added = diff.get("added") or []
    removed = diff.get("removed") or []
    changed = diff.get("state_changed") or []
    if not added and not removed and not changed:
        return "No SLURM job status changes."

    lines = []
    if added:
        lines.append(f"Added {len(added)} job(s): {_format_job_summaries(added)}.")
    if removed:
        lines.append(f"Removed {len(removed)} job(s): {_format_job_summaries(removed)}.")
    if changed:
        lines.append(f"State changed for {len(changed)} job(s): {_format_state_changes(changed)}.")
    return "\n".join(lines)


def _job_summary(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": _job_id(job),
        "job_name": _job_name(job),
        "state": _job_state(job),
        "raw": job,
    }


def _format_job_summaries(jobs: list[dict[str, Any]]) -> str:
    return "; ".join(
        " ".join(item for item in [_text(job.get("job_id")), _text(job.get("job_name")), _text(job.get("state"))] if item)
        for job in jobs
    )


def _format_state_changes(changes: list[dict[str, Any]]) -> str:
    return "; ".join(
        " ".join(
            item
            for item in [
                _text(change.get("job_id")),
                _text(change.get("job_name")),
                f"{_text(change.get('previous_state'))} -> {_text(change.get('current_state'))}",
            ]
            if item
        )
        for change in changes
    )


def _job_id(job: dict[str, Any]) -> str:
    return _text(job.get("job_id") or job.get("id"))


def _job_name(job: dict[str, Any]) -> str:
    return _text(job.get("name") or job.get("job_name"))


def _job_state(job: dict[str, Any]) -> str:
    return _text(job.get("job_state") or job.get("state") or job.get("state_description")).upper() or "UNKNOWN"


def _text(value: Any) -> str:
    scalar = _scalar(value)
    if scalar is None:
        return ""
    return str(scalar).strip()


def _scalar(value: Any) -> Any:
    if isinstance(value, list):
        for item in value:
            scalar = _scalar(item)
            if scalar not in (None, ""):
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
