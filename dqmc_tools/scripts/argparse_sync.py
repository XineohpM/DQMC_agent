"""Static argparse extraction for whitelisted dqmc-dev script adapters."""

from __future__ import annotations

import ast
import warnings
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable

from dqmc_tools.scripts.definitions import ScriptDefinition


@dataclass(frozen=True)
class ArgparseSchemaResult:
    """Argument parser facts extracted from one script source file."""

    path: Path
    status: str
    properties: dict[str, dict[str, Any]]
    required: list[str]
    warnings: tuple[str, ...] = ()
    script_id: str | None = None
    schema_diff: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ArgparseSyncResult:
    """Adapters with argparse-derived schemas plus extraction metadata."""

    adapters: tuple[ScriptDefinition, ...]
    parser_results: tuple[ArgparseSchemaResult, ...]
    summary: dict[str, int]


def extract_argparse_schema(
    path: str | Path,
    *,
    scripts_root: str | Path | None = None,
) -> ArgparseSchemaResult:
    """Read one Python script and statically extract direct argparse calls."""

    script_path = Path(path)
    if scripts_root is not None and not script_path.resolve().is_relative_to(Path(scripts_root).resolve()):
        return ArgparseSchemaResult(script_path, "outside_scripts_root", {}, [])
    if script_path.suffix != ".py":
        return ArgparseSchemaResult(script_path, "non_python", {}, [])

    try:
        source = script_path.read_text(encoding="utf-8")
    except OSError as exc:
        return ArgparseSchemaResult(script_path, "read_error", {}, [], (str(exc),))

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source, filename=str(script_path))
    except SyntaxError as exc:
        return ArgparseSchemaResult(script_path, "syntax_error", {}, [], (str(exc),))

    visitor = _ArgparseVisitor()
    visitor.visit(tree)
    if not visitor.parser_found:
        return ArgparseSchemaResult(script_path, "no_argparse", {}, [])
    if not visitor.properties:
        return ArgparseSchemaResult(
            script_path,
            "unresolved",
            {},
            [],
            ("argparse.ArgumentParser was found but no static add_argument calls were resolved.",),
        )
    return ArgparseSchemaResult(
        script_path,
        "parsed",
        visitor.properties,
        visitor.required,
        tuple(visitor.warnings),
    )


def sync_argparse_adapters(
    registry: Iterable[ScriptDefinition],
    *,
    scripts_root: str | Path | None = None,
) -> ArgparseSyncResult:
    """Return adapters whose args_schema is refreshed from static argparse facts."""

    adapters: list[ScriptDefinition] = []
    parser_results: list[ArgparseSchemaResult] = []
    summary = {"parsed": 0, "skipped": 0, "warnings": 0}

    for adapter in registry:
        result = extract_argparse_schema(adapter.path, scripts_root=scripts_root)
        result = replace(
            result,
            script_id=adapter.script_id,
            schema_diff=args_schema_diff(adapter.args_schema, result),
        )
        parser_results.append(result)
        summary["warnings"] += len(result.warnings)
        if result.status == "parsed":
            adapters.append(replace(adapter, args_schema=_merged_args_schema(adapter.args_schema, result)))
            summary["parsed"] += 1
        else:
            adapters.append(adapter)
            summary["skipped"] += 1

    return ArgparseSyncResult(tuple(adapters), tuple(parser_results), summary)


def args_schema_diff(
    existing_schema: dict[str, Any],
    parser_result: ArgparseSchemaResult,
) -> dict[str, Any]:
    """Compare an adapter schema with static argparse facts."""

    existing_properties = existing_schema.get("properties", {}) if isinstance(existing_schema, dict) else {}
    if not isinstance(existing_properties, dict):
        existing_properties = {}
    existing_required = existing_schema.get("required", []) if isinstance(existing_schema, dict) else []
    if not isinstance(existing_required, list):
        existing_required = []

    existing_keys = set(existing_properties)
    parser_keys = set(parser_result.properties)
    changed: dict[str, dict[str, Any]] = {}
    for name in sorted(existing_keys & parser_keys):
        before = _cli_contract_subset(existing_properties.get(name, {}))
        after = _cli_contract_subset(parser_result.properties.get(name, {}))
        if before != after:
            changed[name] = {"before": before, "after": after}

    required_before = set(str(item) for item in existing_required)
    required_after = set(parser_result.required)
    return {
        "added": sorted(parser_keys - existing_keys),
        "removed": sorted(existing_keys - parser_keys),
        "changed": changed,
        "required_added": sorted(required_after - required_before),
        "required_removed": sorted(required_before - required_after),
    }


def _merged_args_schema(
    existing_schema: dict[str, Any],
    parser_result: ArgparseSchemaResult,
) -> dict[str, Any]:
    existing_properties = existing_schema.get("properties", {}) if isinstance(existing_schema, dict) else {}
    if not isinstance(existing_properties, dict):
        existing_properties = {}

    properties: dict[str, dict[str, Any]] = {}
    for name, parser_spec in parser_result.properties.items():
        merged = dict(parser_spec)
        existing_spec = existing_properties.get(name)
        if isinstance(existing_spec, dict):
            _preserve_adapter_metadata(merged, existing_spec)
        properties[name] = merged

    return {"required": list(parser_result.required), "properties": properties}


def _preserve_adapter_metadata(target: dict[str, Any], existing: dict[str, Any]) -> None:
    for key in ("path_role",):
        if key in existing:
            target[key] = existing[key]


def _cli_contract_subset(spec: Any) -> dict[str, Any]:
    if not isinstance(spec, dict):
        return {}
    keys = (
        "flag",
        "aliases",
        "positional",
        "position",
        "action",
        "false_flag",
        "nargs",
        "type",
        "choices",
        "default",
        "raw_args",
    )
    return {key: spec[key] for key in keys if key in spec}


class _ArgparseVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.parser_found = False
        self._containers: set[str] = set()
        self._positional_count = 0
        self.properties: dict[str, dict[str, Any]] = {}
        self.required: list[str] = []
        self.warnings: list[str] = []

    def visit_Assign(self, node: ast.Assign) -> Any:
        if _is_argument_parser_call(node.value):
            self.parser_found = True
            self._containers.update(_assigned_names(node.targets))
        elif _is_parser_group_call(node.value, self._containers):
            self._containers.update(_assigned_names(node.targets))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        if _is_add_argument_call(node, self._containers):
            self._record_argument(node)
        self.generic_visit(node)

    def _record_argument(self, node: ast.Call) -> None:
        arg_strings = [_literal(arg) for arg in node.args]
        arg_strings = [item for item in arg_strings if isinstance(item, str)]
        if not arg_strings:
            self.warnings.append(f"Could not resolve add_argument at line {node.lineno}.")
            return

        option_strings = [item for item in arg_strings if item.startswith("-")]
        is_optional = bool(option_strings)
        name = _keyword_literal(node, "dest")
        if not isinstance(name, str):
            name = _dest_from_options(option_strings) if is_optional else arg_strings[0].replace("-", "_")

        spec: dict[str, Any] = {}
        if is_optional:
            spec["flag"] = _preferred_flag(option_strings)
            if len(option_strings) > 1:
                spec["aliases"] = option_strings
        else:
            spec["positional"] = True
            spec["position"] = self._positional_count
            self._positional_count += 1

        for key in ("action", "nargs", "default"):
            value = _keyword_literal(node, key)
            if value is not None and value is not _UNRESOLVED:
                spec[key] = value

        arg_type = _keyword_type_name(node, "type")
        if arg_type is not None:
            spec["type"] = arg_type

        choices = _keyword_literal(node, "choices")
        if isinstance(choices, (list, tuple)):
            spec["choices"] = list(choices)

        self._merge_property(name, spec)
        if not is_optional or _keyword_literal(node, "required") is True:
            self._append_required(name)

    def _merge_property(self, name: str, spec: dict[str, Any]) -> None:
        existing = self.properties.get(name)
        if existing is None:
            self.properties[name] = spec
            return

        existing_action = existing.get("action")
        new_action = spec.get("action")
        if existing_action == "store_true" and new_action == "store_false":
            existing["false_flag"] = spec.get("flag")
            existing["action"] = "store_true"
            _extend_aliases(existing, spec)
            return
        if existing_action == "store_false" and new_action == "store_true":
            false_flag = existing.get("flag")
            existing.update(spec)
            existing["false_flag"] = false_flag
            existing["action"] = "store_true"
            _extend_aliases(existing, spec)
            return

        _extend_aliases(existing, spec)
        for key, value in spec.items():
            existing.setdefault(key, value)

    def _append_required(self, name: str) -> None:
        if name not in self.required:
            self.required.append(name)


def _assigned_names(targets: list[ast.expr]) -> set[str]:
    names: set[str] = set()
    for target in targets:
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            names.update(item.id for item in target.elts if isinstance(item, ast.Name))
    return names


def _is_argument_parser_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "ArgumentParser"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "argparse"
    ) or (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "ArgumentParser"
    )


def _is_parser_group_call(node: ast.AST, containers: set[str]) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"add_argument_group", "add_mutually_exclusive_group"}
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in containers
    )


def _is_add_argument_call(node: ast.Call, containers: set[str]) -> bool:
    return (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_argument"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in containers
    )


def _keyword_literal(node: ast.Call, name: str) -> Any:
    for keyword in node.keywords:
        if keyword.arg == name:
            return _literal(keyword.value)
    return None


def _keyword_type_name(node: ast.Call, name: str) -> str | None:
    for keyword in node.keywords:
        if keyword.arg == name:
            return _type_name(keyword.value)
    return None


def _literal(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values = [_literal(item) for item in node.elts]
        if all(value is not _UNRESOLVED for value in values):
            return values
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        value = _literal(node.operand)
        if isinstance(value, (int, float)):
            return -value
    return _UNRESOLVED


def _type_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _type_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _preferred_flag(option_strings: list[str]) -> str:
    long_options = [item for item in option_strings if item.startswith("--")]
    if long_options:
        return max(long_options, key=len)
    return option_strings[0]


def _dest_from_options(option_strings: list[str]) -> str:
    flag = _preferred_flag(option_strings)
    return flag.lstrip("-").replace("-", "_")


def _extend_aliases(existing: dict[str, Any], spec: dict[str, Any]) -> None:
    aliases = list(existing.get("aliases", []))
    for value in spec.get("aliases", []):
        if value not in aliases:
            aliases.append(value)
    flag = spec.get("flag")
    if flag and flag not in aliases and flag != existing.get("flag"):
        aliases.append(flag)
    if aliases:
        existing["aliases"] = aliases


class _Unresolved:
    pass


_UNRESOLVED = _Unresolved()
