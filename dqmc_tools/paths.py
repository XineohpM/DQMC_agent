"""Path normalization and safety checks."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from dqmc_tools.config import ALLOWED_ROOTS_ENV, get_allowed_roots, get_output_root
from dqmc_tools.errors import PathNotAllowedError, PathResolutionError


def resolve_existing_path(path: str | Path) -> Path:
    """Resolve an existing path or raise a structured path error."""

    try:
        return Path(path).expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise PathResolutionError(
            "Path does not exist.",
            details={"path": path},
        ) from exc
    except OSError as exc:
        raise PathResolutionError(
            "Path could not be resolved.",
            details={"path": path, "reason": str(exc)},
        ) from exc


def require_allowed_path(
    path: str | Path,
    allowed_roots: Iterable[str | Path] | str | Path | None = None,
) -> Path:
    """Resolve `path` and require it to be under an allowed raw-data root."""

    candidate = resolve_existing_path(path)
    roots = _resolve_roots(get_allowed_roots(allowed_roots))
    if not roots:
        raise PathNotAllowedError(
            "No allowed roots are configured for raw-data access.",
            details={"path": candidate, "env_var": ALLOWED_ROOTS_ENV},
        )
    if any(_is_relative_to(candidate, root) for root in roots):
        return candidate
    raise PathNotAllowedError(
        "Path is outside configured allowed roots.",
        details={"path": candidate, "allowed_roots": roots},
    )


def require_output_path(path: str | Path, output_root: str | Path | None = None) -> Path:
    """Resolve a generated-output path under the configured output root."""

    root = get_output_root(output_root).expanduser().resolve(strict=False)
    raw_candidate = Path(path).expanduser()
    candidate = raw_candidate if raw_candidate.is_absolute() else root / raw_candidate
    resolved = candidate.resolve(strict=False)
    if _is_relative_to(resolved, root):
        return resolved
    raise PathNotAllowedError(
        "Output path is outside the configured output root.",
        details={"path": resolved, "output_root": root},
    )


def require_workflow_path(
    path: str | Path,
    *,
    output_root: str | Path | None = None,
    allowed_roots: Iterable[str | Path] | str | Path | None = None,
    must_exist: bool = False,
) -> Path:
    """Resolve a workflow-mutating path under output root or allowed roots."""

    raw = Path(path).expanduser()
    candidate = raw.resolve(strict=must_exist)
    output_root_path = get_output_root(output_root).expanduser().resolve(strict=False)
    roots = _resolve_roots(get_allowed_roots(allowed_roots))
    if _is_relative_to(candidate, output_root_path) or any(
        _is_relative_to(candidate, root) for root in roots
    ):
        return candidate
    raise PathNotAllowedError(
        "Workflow path is outside output root and allowed roots.",
        details={
            "path": candidate,
            "output_root": output_root_path,
            "allowed_roots": roots,
        },
    )


def _resolve_roots(roots: Iterable[str | Path]) -> list[Path]:
    resolved: list[Path] = []
    for root in roots:
        try:
            resolved.append(Path(root).expanduser().resolve(strict=True))
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
    return resolved


def _is_relative_to(path: Path, root: Path) -> bool:
    return path == root or root in path.parents
