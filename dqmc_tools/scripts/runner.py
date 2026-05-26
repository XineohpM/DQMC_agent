"""Whitelisted script runner with preflight and explicit approval checks."""

from __future__ import annotations

import glob
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

from dqmc_tools.config import get_output_root, get_script_timeout
from dqmc_tools.errors import (
    InvalidArgumentError,
    ScriptApprovalRequiredError,
    ScriptPreflightError,
    ScriptRegistryError,
)
from dqmc_tools.paths import require_allowed_path, require_output_path
from dqmc_tools.scripts.definitions import InputRequirement, ScriptDefinition
from dqmc_tools.scripts.parsers import parse_outputs


DEFAULT_REGISTRY: tuple[ScriptDefinition, ...] = ()


def list_script_adapters(
    registry: Iterable[ScriptDefinition] | None = None,
) -> list[dict[str, Any]]:
    """List whitelisted scripts without exposing callables."""

    return [_definition_summary(item) for item in _registry_map(registry).values()]


def describe_script_adapter(
    script_id: str,
    *,
    registry: Iterable[ScriptDefinition] | None = None,
) -> dict[str, Any]:
    """Describe one whitelisted script adapter."""

    definition = _get_definition(script_id, registry)
    return _definition_summary(definition, include_schema=True)


def run_script_adapter(
    script_id: str,
    params: Mapping[str, Any] | None = None,
    *,
    cwd: str | Path | None = None,
    allowed_roots: Iterable[str | Path] | str | Path | None = None,
    output_root: str | Path | None = None,
    timeout_seconds: int | None = None,
    dry_run: bool = False,
    user_confirmation: Mapping[str, Any] | None = None,
    registry: Iterable[ScriptDefinition] | None = None,
) -> dict[str, Any]:
    """Run, or dry-run, a whitelisted script adapter."""

    definition = _get_definition(script_id, registry)
    parsed_params = _validate_params(definition, dict(params or {}))
    resolved_cwd = _resolve_cwd(cwd, allowed_roots=allowed_roots)
    resolved_output_root = get_output_root(output_root).resolve(strict=False)
    parsed_params = _resolve_path_params(
        definition,
        parsed_params,
        allowed_roots=allowed_roots,
        output_root=resolved_output_root,
    )
    preflight = _preflight_inputs(
        definition,
        parsed_params,
        cwd=resolved_cwd,
        allowed_roots=allowed_roots,
    )
    command = _build_command(definition, parsed_params)

    base_result = {
        "ok": True,
        "script_id": definition.script_id,
        "command": command,
        "cwd": str(resolved_cwd),
        "dry_run": dry_run,
        "preflight": preflight,
        "output_root": str(resolved_output_root),
        "user_confirmation": dict(user_confirmation or {}),
    }
    if dry_run:
        return {
            **base_result,
            "returncode": None,
            "stdout_tail": "",
            "stderr_tail": "",
            "output_files": [],
            "parsed_outputs": {},
            "warnings": [],
        }

    _require_approval(definition, user_confirmation)

    started = time.time()
    try:
        completed = subprocess.run(
            command,
            cwd=str(resolved_cwd),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds or definition.default_timeout_seconds or get_script_timeout(),
            env=_subprocess_env(output_root=resolved_output_root),
        )
    except subprocess.TimeoutExpired as exc:
        raise ScriptRegistryError(
            "Whitelisted script timed out.",
            details={
                "script_id": definition.script_id,
                "command": command,
                "timeout_seconds": exc.timeout,
            },
        ) from exc
    ended = time.time()

    output_files, manifest_warnings = _output_manifest(
        definition,
        parsed_params,
        cwd=resolved_cwd,
        output_root=resolved_output_root,
    )
    parsed_outputs, parse_warnings = parse_outputs(
        definition.parser_id,
        output_files,
        stdout=completed.stdout,
    )

    return {
        **base_result,
        "started_at": started,
        "ended_at": ended,
        "duration_seconds": ended - started,
        "returncode": completed.returncode,
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
        "output_files": output_files,
        "parsed_outputs": parsed_outputs,
        "warnings": manifest_warnings + parse_warnings,
    }


def default_argv_builder(definition: ScriptDefinition, params: Mapping[str, Any]) -> list[str]:
    """Build argv from a simple mapping of param names to CLI flags."""

    path = str(definition.path)
    if definition.path.suffix == ".py":
        command = [sys.executable, path]
    elif definition.path.suffix == ".sh":
        command = ["bash", path]
    else:
        command = [path]
    properties = definition.args_schema.get("properties", {})
    positional = []
    for name, value in params.items():
        if value is None:
            continue
        spec = properties.get(name, {})
        if spec.get("raw_args"):
            if isinstance(value, (list, tuple)):
                command.extend(str(item) for item in value)
            else:
                command.append(str(value))
            continue
        if spec.get("positional"):
            positional.append((int(spec.get("position", 0)), value))
            continue
        flag = spec.get("flag", f"--{name.replace('_', '-')}")
        if isinstance(value, bool):
            if spec.get("action") == "store_false":
                if value is False:
                    command.append(flag)
            elif value:
                command.append(flag)
            elif spec.get("false_flag"):
                command.append(spec["false_flag"])
            continue
        if isinstance(value, (list, tuple)):
            command.append(flag)
            command.extend(str(item) for item in value)
            continue
        command.extend([flag, str(value)])
    for _position, value in sorted(positional, key=lambda item: item[0]):
        if isinstance(value, (list, tuple)):
            command.extend(str(item) for item in value)
        else:
            command.append(str(value))
    return command


def _registry_map(
    registry: Iterable[ScriptDefinition] | None,
) -> dict[str, ScriptDefinition]:
    if registry is None:
        from dqmc_tools.scripts.builtin_catalog import DEFAULT_SCRIPT_CATALOG

        entries = DEFAULT_SCRIPT_CATALOG
    else:
        entries = tuple(registry)
    out: dict[str, ScriptDefinition] = {}
    for item in entries:
        _validate_definition(item)
        if item.script_id in out:
            raise ScriptRegistryError(
                "Duplicate script id in registry.",
                details={"script_id": item.script_id},
            )
        out[item.script_id] = item
    return out


def _get_definition(
    script_id: str,
    registry: Iterable[ScriptDefinition] | None,
) -> ScriptDefinition:
    entries = _registry_map(registry)
    if script_id not in entries:
        raise ScriptRegistryError(
            "Script is not registered in the whitelist.",
            details={"script_id": script_id, "registered": sorted(entries)},
        )
    return entries[script_id]


def _validate_definition(definition: ScriptDefinition) -> None:
    if not isinstance(definition, ScriptDefinition):
        raise ScriptRegistryError(
            "Script registry entries must be ScriptDefinition instances.",
            details={"type": type(definition).__name__},
        )
    if not definition.script_id or "/" in definition.script_id or "\\" in definition.script_id:
        raise ScriptRegistryError(
            "Script id must be a non-path registry key.",
            details={"script_id": definition.script_id},
        )
    if not definition.path.exists():
        raise ScriptRegistryError(
            "Whitelisted script path does not exist.",
            details={"script_id": definition.script_id, "path": definition.path},
        )


def _validate_params(definition: ScriptDefinition, params: dict[str, Any]) -> dict[str, Any]:
    properties = definition.args_schema.get("properties", {})
    required = set(definition.args_schema.get("required", []))
    unknown = sorted(set(params) - set(properties))
    missing = sorted(item for item in required if item not in params or params[item] is None or params[item] == "")
    if unknown or missing:
        raise InvalidArgumentError(
            "Script parameters failed schema validation.",
            details={"unknown": unknown, "missing": missing, "script_id": definition.script_id},
        )
    return params


def _resolve_path_params(
    definition: ScriptDefinition,
    params: dict[str, Any],
    *,
    allowed_roots: Iterable[str | Path] | str | Path | None,
    output_root: Path,
) -> dict[str, Any]:
    properties = definition.args_schema.get("properties", {})
    resolved = dict(params)
    for name, spec in properties.items():
        if name not in resolved or resolved[name] is None or resolved[name] == "":
            continue
        role = spec.get("path_role")
        if role == "output":
            resolved[name] = str(require_output_path(resolved[name], output_root))
    return resolved


def _resolve_cwd(
    cwd: str | Path | None,
    *,
    allowed_roots: Iterable[str | Path] | str | Path | None,
) -> Path:
    if cwd is None:
        return require_allowed_path(Path.cwd(), [Path.cwd()])
    return require_allowed_path(cwd, allowed_roots)


def _preflight_inputs(
    definition: ScriptDefinition,
    params: Mapping[str, Any],
    *,
    cwd: Path,
    allowed_roots: Iterable[str | Path] | str | Path | None,
) -> list[dict[str, Any]]:
    out = []
    failures = []
    for requirement in definition.required_inputs:
        result = _check_input(requirement, params, cwd=cwd, allowed_roots=allowed_roots)
        out.append(result)
        if requirement.required and not result["ok"]:
            failures.append(result)
    if failures:
        raise ScriptPreflightError(
            "Required script inputs failed preflight.",
            details={"script_id": definition.script_id, "failures": failures},
        )
    return out


def _check_input(
    requirement: InputRequirement,
    params: Mapping[str, Any],
    *,
    cwd: Path,
    allowed_roots: Iterable[str | Path] | str | Path | None,
) -> dict[str, Any]:
    try:
        raw = requirement.path_template.format(**params)
    except KeyError as exc:
        return {
            "ok": not requirement.required,
            "name": requirement.name,
            "kind": requirement.kind,
            "path_template": requirement.path_template,
            "reason": f"missing_param:{exc.args[0]}",
        }
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = cwd / candidate

    if requirement.kind == "glob":
        matches = [
            require_allowed_path(item, allowed_roots)
            for item in glob.glob(str(candidate))
        ]
        return {
            "ok": bool(matches) or not requirement.required,
            "name": requirement.name,
            "kind": requirement.kind,
            "path_template": requirement.path_template,
            "matches": [str(item) for item in matches],
        }

    try:
        resolved = require_allowed_path(candidate, allowed_roots)
    except Exception as exc:
        return {
            "ok": False,
            "name": requirement.name,
            "kind": requirement.kind,
            "path": str(candidate),
            "reason": str(exc),
        }

    ok, reason = _kind_matches(resolved, requirement)
    return {
        "ok": ok,
        "name": requirement.name,
        "kind": requirement.kind,
        "path": str(resolved),
        "reason": reason,
    }


def _kind_matches(path: Path, requirement: InputRequirement) -> tuple[bool, str | None]:
    if requirement.kind == "directory":
        return path.is_dir(), None if path.is_dir() else "not_a_directory"
    if requirement.kind in {"file", "hdf5", "npy", "npz"}:
        if not path.is_file():
            return False, "not_a_file"
        expected_suffix = {"hdf5": {".h5", ".hdf5"}, "npy": {".npy"}, "npz": {".npz"}}.get(requirement.kind)
        if expected_suffix and path.suffix.lower() not in expected_suffix:
            return False, "unexpected_suffix"
        if requirement.shape_hint and requirement.kind in {"npy", "npz"}:
            shape = np.load(path).shape
            if not _shape_matches(shape, requirement.shape_hint):
                return False, f"unexpected_shape:{shape}"
        return True, None
    return False, "unsupported_input_kind"


def _shape_matches(shape: tuple[int, ...], hint: tuple[int | None, ...]) -> bool:
    return len(shape) == len(hint) and all(expected is None or actual == expected for actual, expected in zip(shape, hint))


def _build_command(definition: ScriptDefinition, params: Mapping[str, Any]) -> list[str]:
    builder = definition.argv_builder or default_argv_builder
    return builder(definition, params)


def _require_approval(definition: ScriptDefinition, user_confirmation: Mapping[str, Any] | None) -> None:
    if not definition.approval_required:
        return
    confirmation = dict(user_confirmation or {})
    if confirmation.get("approved") is True and str(confirmation.get("text", "")).strip():
        return
    raise ScriptApprovalRequiredError(
        "Explicit user approval is required before executing a whitelisted script.",
        details={"script_id": definition.script_id},
    )


def _subprocess_env(*, output_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["DQMC_OUTPUT_ROOT"] = str(output_root)
    return env


def _output_manifest(
    definition: ScriptDefinition,
    params: Mapping[str, Any],
    *,
    cwd: Path,
    output_root: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    files: list[dict[str, Any]] = []
    warnings: list[str] = []
    for pattern in definition.output_patterns:
        try:
            rendered = pattern.format(output_root=output_root, cwd=cwd, **params)
        except KeyError as exc:
            warnings.append(f"output_pattern_missing_param:{pattern}:{exc.args[0]}")
            continue
        glob_path = Path(rendered).expanduser()
        if not glob_path.is_absolute():
            glob_path = cwd / glob_path
        for match in glob.glob(str(glob_path)):
            path = Path(match)
            if path.is_file():
                files.append({
                    "path": str(path.resolve(strict=False)),
                    "size_bytes": path.stat().st_size,
                    "mtime": path.stat().st_mtime,
                })
    return files, warnings


def _definition_summary(definition: ScriptDefinition, *, include_schema: bool = False) -> dict[str, Any]:
    out = {
        "script_id": definition.script_id,
        "description": definition.description,
        "category": definition.category,
        "mode": definition.mode,
        "path": str(definition.path),
        "parser_id": definition.parser_id,
        "requires_output_root": definition.requires_output_root,
        "approval_required": definition.approval_required,
        "required_inputs": [
            {
                "name": item.name,
                "kind": item.kind,
                "path_template": item.path_template,
                "required": item.required,
                "shape_hint": list(item.shape_hint) if item.shape_hint else None,
            }
            for item in definition.required_inputs
        ],
        "output_patterns": list(definition.output_patterns),
        "notes": list(definition.notes),
    }
    if include_schema:
        out["args_schema"] = definition.args_schema
    return out


def _tail(text: str, max_chars: int = 4000) -> str:
    return text[-max_chars:] if len(text) > max_chars else text
