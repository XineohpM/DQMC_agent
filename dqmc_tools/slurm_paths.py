"""Path candidate inference for SLURM job details."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from dqmc_tools.config import get_allowed_roots
from dqmc_tools.errors import PathNotAllowedError


CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


def infer_slurm_path_candidates(
    job_detail: dict[str, Any] | list[dict[str, Any]],
    *,
    allowed_roots: Iterable[str | Path] | str | Path | None = None,
    user_path: str | Path | None = None,
) -> dict[str, Any]:
    """Infer bounded run/output path candidates from SLURM job detail facts."""

    roots = _resolve_allowed_roots(allowed_roots)
    raw_candidates = []
    for detail_candidate in _detail_candidates(job_detail):
        source_job_id = _text(detail_candidate.get("job_id"))
        source = _text(detail_candidate.get("source"))
        work_dir = _text(detail_candidate.get("work_dir"))
        if work_dir:
            raw_candidates.append(_path_candidate(
                work_dir,
                confidence="high",
                evidence="sacct.WorkDir" if source == "sacct" else "squeue.WorkDir",
                source_job_id=source_job_id,
                roots=roots,
            ))

        stdout_parent = _absolute_parent(_text(detail_candidate.get("stdout_path")))
        if stdout_parent is not None:
            raw_candidates.append(_path_candidate(
                stdout_parent,
                confidence="medium",
                evidence="stdout_path_parent",
                source_job_id=source_job_id,
                roots=roots,
            ))

        stderr_parent = _absolute_parent(_text(detail_candidate.get("stderr_path")))
        if stderr_parent is not None:
            raw_candidates.append(_path_candidate(
                stderr_parent,
                confidence="medium",
                evidence="stderr_path_parent",
                source_job_id=source_job_id,
                roots=roots,
            ))

    if user_path is not None and str(user_path).strip() != "":
        raw_candidates.append(_path_candidate(
            user_path,
            confidence="high",
            evidence="user_provided_path",
            source_job_id="",
            roots=roots,
        ))

    path_candidates = _dedupe_candidates(raw_candidates)
    warnings = []
    if path_candidates and not roots:
        warnings.append("No allowed_roots configured; path candidates are not marked accessible.")

    return {"ok": True, "path_candidates": path_candidates, "warnings": warnings}


def _detail_candidates(job_detail: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(job_detail, list):
        return [item for item in job_detail if isinstance(item, dict)]
    candidates = job_detail.get("candidates")
    if isinstance(candidates, list):
        return [item for item in candidates if isinstance(item, dict)]
    return [job_detail]


def _path_candidate(
    path: str | Path,
    *,
    confidence: str,
    evidence: str,
    source_job_id: str,
    roots: list[Path],
) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve(strict=False)
    within_allowed_roots = bool(roots) and any(_is_relative_to(resolved, root) for root in roots)
    accessible = within_allowed_roots and resolved.exists()
    rejection_reason = _rejection_reason(
        roots=roots,
        within_allowed_roots=within_allowed_roots,
        accessible=accessible,
    )
    return {
        "path": str(resolved),
        "confidence": confidence,
        "evidence": evidence,
        "accessible": accessible,
        "within_allowed_roots": within_allowed_roots,
        "rejection_reason": rejection_reason,
        "source_job_id": source_job_id,
    }


def _rejection_reason(*, roots: list[Path], within_allowed_roots: bool, accessible: bool) -> str:
    if not roots:
        return "no_allowed_roots"
    if not within_allowed_roots:
        return "outside_allowed_roots"
    if not accessible:
        return "path_missing"
    return ""


def _absolute_parent(path: str) -> Path | None:
    if not path:
        return None
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        return None
    return candidate.parent


def _dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        existing = deduped.get(candidate["path"])
        if existing is None or CONFIDENCE_RANK[candidate["confidence"]] > CONFIDENCE_RANK[existing["confidence"]]:
            deduped[candidate["path"]] = candidate
    return list(deduped.values())


def _resolve_allowed_roots(allowed_roots: Iterable[str | Path] | str | Path | None) -> list[Path]:
    roots = []
    for root in get_allowed_roots(allowed_roots):
        try:
            roots.append(Path(root).expanduser().resolve(strict=True))
        except FileNotFoundError as exc:
            raise PathNotAllowedError(
                "Configured allowed root does not exist.",
                details={"allowed_root": root},
            ) from exc
        except OSError as exc:
            raise PathNotAllowedError(
                "Configured allowed root could not be resolved.",
                details={"allowed_root": root, "reason": str(exc)},
            ) from exc
    return roots


def _is_relative_to(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
