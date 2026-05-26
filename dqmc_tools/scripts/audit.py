"""Audit helpers for whitelisted script adapter definitions."""

from __future__ import annotations

import hashlib
import shutil
import string
import sys
from pathlib import Path
from typing import Any, Iterable

from dqmc_tools.scripts.definitions import ScriptDefinition


KNOWN_PARSERS = {None, "tsv", "npy_manifest", "image_manifest", "stdout_key_value"}
KNOWN_CATEGORIES = {"generation", "diagnostic", "analysis", "plot", "maxent", "workflow", "cluster"}
KNOWN_MODES = {"read_only", "writes_output", "mutates_workflow_files", "submits_jobs"}
KNOWN_PATH_ROLES = {"input", "output", "workflow"}
RESERVED_TEMPLATE_FIELDS = {"cwd", "output_root"}


def audit_script_adapters(
    registry: Iterable[ScriptDefinition] | None = None,
    *,
    include_fingerprints: bool = True,
) -> dict[str, Any]:
    """Audit script adapter metadata after dqmc-dev or catalog updates."""

    entries = _registry_entries(registry)
    adapters = []
    seen: dict[str, int] = {}
    for index, item in enumerate(entries):
        if isinstance(item, ScriptDefinition):
            seen[item.script_id] = seen.get(item.script_id, 0) + 1
        adapters.append(_audit_one(item, include_fingerprints=include_fingerprints))

    for adapter in adapters:
        script_id = adapter.get("script_id", "")
        if script_id and seen.get(script_id, 0) > 1:
            _add_check(
                adapter,
                "unique_script_id",
                "error",
                f"duplicate script_id: {script_id}",
            )
        elif script_id:
            _add_check(adapter, "unique_script_id", "ok", "script_id is unique")

    ok_count = sum(1 for item in adapters if item["ok"])
    warning_count = sum(1 for item in adapters if item["warning_count"])
    error_count = sum(1 for item in adapters if item["error_count"])
    return {
        "ok": error_count == 0,
        "adapter_count": len(adapters),
        "summary": {
            "ok": ok_count,
            "warnings": warning_count,
            "errors": error_count,
        },
        "adapters": adapters,
    }


def _registry_entries(registry: Iterable[ScriptDefinition] | None) -> tuple[Any, ...]:
    if registry is None:
        from dqmc_tools.scripts.builtin_catalog import DEFAULT_SCRIPT_CATALOG

        return DEFAULT_SCRIPT_CATALOG
    return tuple(registry)


def _audit_one(item: Any, *, include_fingerprints: bool) -> dict[str, Any]:
    if not isinstance(item, ScriptDefinition):
        adapter = {
            "ok": False,
            "script_id": None,
            "path": None,
            "checks": [],
            "error_count": 0,
            "warning_count": 0,
        }
        _add_check(adapter, "definition_type", "error", "entry is not a ScriptDefinition")
        return adapter

    adapter = {
        "ok": True,
        "script_id": item.script_id,
        "description": item.description,
        "category": item.category,
        "mode": item.mode,
        "path": str(item.path),
        "path_exists": item.path.exists(),
        "launcher": _launcher(item.path),
        "sha256": None,
        "size_bytes": None,
        "mtime": None,
        "checks": [],
        "error_count": 0,
        "warning_count": 0,
    }

    _check_basic_fields(adapter, item)
    _check_path(adapter, item, include_fingerprints=include_fingerprints)
    _check_args_schema(adapter, item)
    _check_required_inputs(adapter, item)
    _check_output_patterns(adapter, item)
    _check_parser(adapter, item)
    adapter["ok"] = adapter["error_count"] == 0
    return adapter


def _check_basic_fields(adapter: dict[str, Any], item: ScriptDefinition) -> None:
    if item.script_id and "/" not in item.script_id and "\\" not in item.script_id:
        _add_check(adapter, "script_id_shape", "ok", "script_id is a non-path key")
    else:
        _add_check(adapter, "script_id_shape", "error", "script_id must be a non-path key")

    if item.category in KNOWN_CATEGORIES:
        _add_check(adapter, "category", "ok", f"category={item.category}")
    else:
        _add_check(adapter, "category", "error", f"unknown category: {item.category}")

    if item.mode in KNOWN_MODES:
        _add_check(adapter, "mode", "ok", f"mode={item.mode}")
    else:
        _add_check(adapter, "mode", "error", f"unknown mode: {item.mode}")


def _check_path(adapter: dict[str, Any], item: ScriptDefinition, *, include_fingerprints: bool) -> None:
    path = item.path
    if path.exists() and path.is_file():
        _add_check(adapter, "script_path", "ok", "script path exists")
        stat = path.stat()
        adapter["size_bytes"] = stat.st_size
        adapter["mtime"] = stat.st_mtime
        if include_fingerprints:
            adapter["sha256"] = _sha256(path)
    elif path.exists():
        _add_check(adapter, "script_path", "error", "script path exists but is not a file")
    else:
        _add_check(adapter, "script_path", "error", "script path does not exist")

    launcher = adapter["launcher"]
    if launcher == "python":
        _add_check(adapter, "launcher", "ok", f"python={sys.executable}")
    elif launcher == "bash":
        bash = shutil.which("bash")
        if bash:
            _add_check(adapter, "launcher", "ok", f"bash={bash}")
        else:
            _add_check(adapter, "launcher", "error", "bash was not found")
    elif launcher == "direct":
        if path.exists() and path.is_file():
            _add_check(adapter, "launcher", "ok", "script can be invoked directly by path")
        else:
            _add_check(adapter, "launcher", "error", "direct script path is unavailable")
    else:
        _add_check(adapter, "launcher", "warning", f"unrecognized launcher: {launcher}")


def _check_args_schema(adapter: dict[str, Any], item: ScriptDefinition) -> None:
    schema = item.args_schema or {}
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    if isinstance(properties, dict):
        _add_check(adapter, "args_schema.properties", "ok", f"{len(properties)} properties")
    else:
        _add_check(adapter, "args_schema.properties", "error", "properties must be a mapping")
        properties = {}

    if isinstance(required, list):
        missing = sorted(name for name in required if name not in properties)
        if missing:
            _add_check(
                adapter,
                "args_schema.required",
                "error",
                f"required params missing from properties: {missing}",
            )
        else:
            _add_check(adapter, "args_schema.required", "ok", "required params are declared")
    else:
        _add_check(adapter, "args_schema.required", "error", "required must be a list")

    for name, spec in properties.items():
        if not isinstance(spec, dict):
            _add_check(adapter, f"args_schema.{name}", "error", "property spec must be a mapping")
            continue
        role = spec.get("path_role")
        if role is not None and role not in KNOWN_PATH_ROLES:
            _add_check(adapter, f"args_schema.{name}.path_role", "error", f"unknown path_role: {role}")
        if spec.get("positional") and "position" not in spec:
            _add_check(adapter, f"args_schema.{name}.position", "warning", "positional param has no position")


def _check_required_inputs(adapter: dict[str, Any], item: ScriptDefinition) -> None:
    known = _known_template_fields(item)
    for requirement in item.required_inputs:
        unknown = sorted(_template_fields(requirement.path_template) - known)
        check_name = f"required_input.{requirement.name}"
        if unknown:
            _add_check(adapter, check_name, "error", f"unknown template fields: {unknown}")
        else:
            _add_check(adapter, check_name, "ok", f"kind={requirement.kind}")


def _check_output_patterns(adapter: dict[str, Any], item: ScriptDefinition) -> None:
    if isinstance(item.output_patterns, str):
        _add_check(
            adapter,
            "output_patterns.type",
            "error",
            "output_patterns must be a tuple/list, not a string",
        )
        return
    if not isinstance(item.output_patterns, (tuple, list)):
        _add_check(
            adapter,
            "output_patterns.type",
            "error",
            "output_patterns must be a tuple or list",
        )
        return

    known = _known_template_fields(item)
    for pattern in item.output_patterns:
        if not isinstance(pattern, str):
            _add_check(adapter, "output_pattern.type", "error", "output pattern must be a string")
            continue
        unknown = sorted(_template_fields(pattern) - known)
        check_name = f"output_pattern.{pattern}"
        if unknown:
            _add_check(adapter, check_name, "warning", f"unknown template fields: {unknown}")
        else:
            _add_check(adapter, check_name, "ok", "template fields are known")


def _check_parser(adapter: dict[str, Any], item: ScriptDefinition) -> None:
    if item.parser_id in KNOWN_PARSERS:
        _add_check(adapter, "parser_id", "ok", f"parser_id={item.parser_id}")
    else:
        _add_check(adapter, "parser_id", "error", f"unknown parser_id: {item.parser_id}")


def _known_template_fields(item: ScriptDefinition) -> set[str]:
    properties = item.args_schema.get("properties", {}) if isinstance(item.args_schema, dict) else {}
    if not isinstance(properties, dict):
        properties = {}
    return set(properties) | RESERVED_TEMPLATE_FIELDS


def _template_fields(template: str) -> set[str]:
    fields = set()
    for _literal, field_name, _format_spec, _conversion in string.Formatter().parse(template):
        if field_name:
            fields.add(field_name.split(".", maxsplit=1)[0].split("[", maxsplit=1)[0])
    return fields


def _launcher(path: Path) -> str:
    if path.suffix == ".py":
        return "python"
    if path.suffix == ".sh":
        return "bash"
    return "direct"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _add_check(adapter: dict[str, Any], name: str, status: str, message: str) -> None:
    adapter["checks"].append({"name": name, "status": status, "message": message})
    if status == "error":
        adapter["error_count"] += 1
    elif status == "warning":
        adapter["warning_count"] += 1
