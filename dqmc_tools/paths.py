"""Path normalization and safety checks for DQMC tools."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from dqmc_tools.config import get_allowed_roots, get_output_root
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
    """Resolve `path` and require it to be inside an allowed raw-data root."""

    candidate = resolve_existing_path(path)
    roots = _resolve_allowed_roots(allowed_roots)

    if not roots:
        raise PathNotAllowedError(
            "No allowed roots are configured for raw-data access.",
            details={
                "path": candidate,
                "env_var": "DQMC_ALLOWED_ROOTS",
            },
        )

    if any(_is_relative_to(candidate, root) for root in roots):
        return candidate

    raise PathNotAllowedError(
        "Path is outside configured allowed roots.",
        details={
            "path": candidate,
            "allowed_roots": roots,
        },
    )


def require_output_path(
    path: str | Path,
    output_root: str | Path | None = None,
) -> Path:
    """Resolve a generated-output path under the configured output root."""

    root = get_output_root(output_root)
    if root is None:
        raise PathNotAllowedError(
            "No output root is configured for generated files.",
            details={"path": path, "env_var": "DQMC_OUTPUT_ROOT"},
        )

    root_resolved = root.expanduser().resolve(strict=False)
    raw_candidate = Path(path).expanduser()
    candidate = raw_candidate if raw_candidate.is_absolute() else root_resolved / raw_candidate
    candidate_resolved = candidate.resolve(strict=False)

    if _is_relative_to(candidate_resolved, root_resolved):
        return candidate_resolved

    raise PathNotAllowedError(
        "Output path is outside the configured output root.",
        details={
            "path": candidate_resolved,
            "output_root": root_resolved,
        },
    )


def _resolve_allowed_roots(
    allowed_roots: Iterable[str | Path] | str | Path | None,
) -> list[Path]:
    roots = get_allowed_roots(allowed_roots)
    resolved_roots: list[Path] = []
    for root in roots:
        try:
            resolved_roots.append(Path(root).expanduser().resolve(strict=True))
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
    return resolved_roots


def _is_relative_to(path: Path, root: Path) -> bool:
    return path == root or root in path.parents
