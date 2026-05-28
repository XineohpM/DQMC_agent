"""Controlled artifact synchronization helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from dqmc_tools.errors import (
    InvalidArgumentError,
    PathNotAllowedError,
    ScriptApprovalRequiredError,
    ScriptRegistryError,
    ToolUnavailableError,
)
from dqmc_tools.paths import require_output_path


DEFAULT_SYNC_TIMEOUT_SECONDS = 300
UNSAFE_REMOTE_CHARS = {"\x00", "\n", "\r", ";", "&", "|", "`", "$", "<", ">"}


def sync_sherlock_artifacts(
    *,
    remote_host: str,
    remote_path: str,
    remote_allowed_hosts: Iterable[str] | None,
    remote_allowed_roots: Iterable[str],
    local_subdir: str | Path | None = None,
    output_root: str | Path | None = None,
    dry_run: bool = True,
    user_confirmation: dict[str, Any] | None = None,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    """Synchronize one allowed Sherlock artifact path into the local output root."""

    host = _validate_remote_host(remote_host, remote_allowed_hosts)
    source_path = _validate_remote_path(remote_path)
    allowed_roots = [_validate_remote_path(root) for root in remote_allowed_roots]
    if not allowed_roots:
        raise PathNotAllowedError(
            "No remote allowed roots are configured.",
            details={"remote_path": source_path},
        )
    if not any(_remote_is_relative_to(source_path, root) for root in allowed_roots):
        raise PathNotAllowedError(
            "Remote path is outside configured allowed roots.",
            details={"remote_path": source_path, "remote_allowed_roots": allowed_roots},
        )

    destination = require_output_path(local_subdir or _default_local_subdir(host, source_path), output_root)
    if not dry_run:
        _require_sync_approval(user_confirmation)

    rsync_path = shutil.which("rsync")
    if not rsync_path:
        raise ToolUnavailableError(
            "Command `rsync` is not available.",
            details={"command": "rsync"},
        )

    command = _build_rsync_command(
        rsync_path,
        remote_host=host,
        remote_path=source_path,
        destination=destination,
        dry_run=dry_run,
        include_patterns=include_patterns or [],
        exclude_patterns=exclude_patterns or [],
    )
    if not dry_run:
        destination.mkdir(parents=True, exist_ok=True)

    completed = _run_rsync(command, timeout_seconds=timeout_seconds or DEFAULT_SYNC_TIMEOUT_SECONDS)
    if completed.returncode != 0:
        raise ScriptRegistryError(
            "Artifact synchronization failed.",
            details={
                "command": command,
                "returncode": completed.returncode,
                "stdout_tail": _tail(completed.stdout),
                "stderr_tail": _tail(completed.stderr),
            },
        )

    return {
        "ok": True,
        "dry_run": dry_run,
        "command": command,
        "remote": {"host": host, "path": source_path},
        "destination": str(destination),
        "user_confirmation": dict(user_confirmation or {}),
        "manifest": _parse_rsync_manifest(completed.stdout),
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
        "warnings": [],
    }


def _validate_remote_host(remote_host: str, allowed_hosts: Iterable[str] | None) -> str:
    host = str(remote_host).strip()
    allowed = {str(item).strip() for item in (allowed_hosts or []) if str(item).strip()}
    if not host:
        raise InvalidArgumentError(
            "Remote host must be a non-empty allowlisted value.",
            details={"remote_host": remote_host},
        )
    if not allowed or host not in allowed:
        raise InvalidArgumentError(
            "Remote host is outside the allowed host list.",
            details={"remote_host": host, "remote_allowed_hosts": sorted(allowed)},
        )
    return host


def _validate_remote_path(value: str) -> str:
    raw = str(value).strip()
    if not raw:
        raise InvalidArgumentError(
            "Remote path must be a non-empty absolute POSIX path.",
            details={"remote_path": value},
        )
    if any(char in raw for char in UNSAFE_REMOTE_CHARS):
        raise InvalidArgumentError(
            "Remote path contains unsupported characters.",
            details={"remote_path": value},
        )
    path = PurePosixPath(raw)
    if not path.is_absolute() or ".." in path.parts:
        raise InvalidArgumentError(
            "Remote path must be an absolute POSIX path without parent traversal.",
            details={"remote_path": value},
        )
    return str(path)


def _remote_is_relative_to(path: str, root: str) -> bool:
    candidate = PurePosixPath(path)
    allowed_root = PurePosixPath(root)
    return candidate == allowed_root or allowed_root in candidate.parents


def _default_local_subdir(remote_host: str, remote_path: str) -> Path:
    return Path(remote_host) / remote_path.strip("/")


def _require_sync_approval(user_confirmation: dict[str, Any] | None) -> None:
    confirmation = user_confirmation or {}
    if confirmation.get("approved") is True and str(confirmation.get("text") or "").strip():
        return
    raise ScriptApprovalRequiredError(
        "Artifact synchronization requires explicit user approval.",
        details={"operation": "sync_sherlock_artifacts"},
    )


def _build_rsync_command(
    rsync_path: str,
    *,
    remote_host: str,
    remote_path: str,
    destination: Path,
    dry_run: bool,
    include_patterns: list[str],
    exclude_patterns: list[str],
) -> list[str]:
    command = [
        rsync_path,
        "--archive",
        "--itemize-changes",
        "--human-readable",
        "--protect-args",
    ]
    if dry_run:
        command.append("--dry-run")
    for pattern in include_patterns:
        command.extend(["--include", _validate_rsync_pattern(pattern)])
    for pattern in exclude_patterns:
        command.extend(["--exclude", _validate_rsync_pattern(pattern)])
    command.extend([f"{remote_host}:{remote_path.rstrip('/')}/", str(destination)])
    return command


def _validate_rsync_pattern(pattern: str) -> str:
    raw = str(pattern).strip()
    if not raw or raw.startswith("/") or ".." in PurePosixPath(raw).parts:
        raise InvalidArgumentError(
            "Sync include/exclude patterns must be non-empty relative patterns.",
            details={"pattern": pattern},
        )
    if any(char in raw for char in UNSAFE_REMOTE_CHARS):
        raise InvalidArgumentError(
            "Sync include/exclude pattern contains unsupported characters.",
            details={"pattern": pattern},
        )
    return raw


def _run_rsync(command: list[str], *, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except OSError as exc:
        raise ToolUnavailableError(
            "Command `rsync` could not be executed.",
            details={"command": command, "reason": str(exc)},
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ToolUnavailableError(
            "Command `rsync` timed out.",
            details={"command": command, "timeout_seconds": exc.timeout},
        ) from exc


def _parse_rsync_manifest(stdout: str) -> dict[str, Any]:
    manifest = {"created": [], "updated": [], "deleted": [], "skipped": [], "unknown": []}
    for line in stdout.splitlines():
        if not line.strip():
            continue
        itemize, path = _split_itemize_line(line)
        if not itemize or not path:
            continue
        change = _manifest_change(itemize)
        item = {"path": path, "change": change, "itemize": itemize}
        manifest[change].append(item)
    total_items = sum(len(manifest[key]) for key in ("created", "updated", "deleted", "skipped", "unknown"))
    return {**manifest, "total_items": total_items}


def _split_itemize_line(line: str) -> tuple[str, str]:
    parts = line.split(maxsplit=1)
    if len(parts) != 2:
        return line.strip(), ""
    return parts[0].strip(), parts[1].strip()


def _manifest_change(itemize: str) -> str:
    if itemize.startswith(">") and "+" in itemize:
        return "created"
    if itemize.startswith(">"):
        return "updated"
    if itemize.startswith("."):
        return "skipped"
    return "unknown"


def _tail(value: str, max_chars: int = 4000) -> str:
    return value[-max_chars:]
