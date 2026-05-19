#!/usr/bin/env python3
"""Validate the DQMC formal observable registry.

This script checks the internal graph consistency of `observables.yaml`.

- `gen_yaml_check.py` generates Lean code and checks that Lean names/theorems exist.
- `check_formal_registry.py` checks that the YAML registry is self-consistent:
  no duplicate ids, no dangling inputs, and no malformed registry entries.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    print("Missing dependency: PyYAML. Install with: pip install pyyaml", file=sys.stderr)
    raise exc


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_YAML = DEFAULT_ROOT / "observables.yaml"


class RegistryError(Exception):
    """Raised when the formal registry is internally inconsistent."""


def require_mapping(obj: Any, where: str) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise RegistryError(f"{where} must be a mapping/dict, got {type(obj).__name__}")
    return obj


def require_list(obj: Any, where: str) -> list[Any]:
    if obj is None:
        return []
    if not isinstance(obj, list):
        raise RegistryError(f"{where} must be a list, got {type(obj).__name__}")
    return obj


def require_str(item: dict[str, Any], key: str, where: str) -> str:
    if key not in item:
        raise RegistryError(f"Missing required key `{key}` in {where}")
    value = item[key]
    if not isinstance(value, str) or not value.strip():
        raise RegistryError(f"`{key}` in {where} must be a non-empty string")
    return value


def optional_str(item: dict[str, Any], key: str, where: str) -> str | None:
    if key not in item:
        return None
    value = item[key]
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise RegistryError(f"`{key}` in {where} must be a non-empty string when present")
    return value


def require_str_list(item: dict[str, Any], key: str, where: str) -> list[str]:
    value = item.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list):
        raise RegistryError(f"`{key}` in {where} must be a list of strings")
    out: list[str] = []
    for idx, entry in enumerate(value):
        if not isinstance(entry, str) or not entry.strip():
            raise RegistryError(f"`{key}[{idx}]` in {where} must be a non-empty string")
        out.append(entry)
    return out


def infer_lean_meas_var(repo_id: str) -> str:
    """Infer Lean MeasVar from canonical repo_id.

    Example:
      EqLt.density -> DQMC.MeasVar.EqLt_density
      Uneqlt.gt0_u -> DQMC.MeasVar.Uneqlt_gt0_u
    """
    return "DQMC.MeasVar." + repo_id.replace(".", "_")


def check_unique(value: str, seen: dict[str, str], kind: str, where: str) -> None:
    if value in seen:
        raise RegistryError(
            f"Duplicate {kind} `{value}` in {where}; first seen in {seen[value]}"
        )
    seen[value] = where


def check_prefix(value: str, prefix: str, where: str, key: str) -> None:
    if not value.startswith(prefix):
        raise RegistryError(f"`{key}` in {where} must start with `{prefix}`, got `{value}`")


def check_repo_id_shape(repo_id: str, where: str) -> None:
    if "." not in repo_id:
        raise RegistryError(f"`repo_id` in {where} must contain a namespace dot, got `{repo_id}`")
    namespace, name = repo_id.split(".", 1)
    if namespace not in {"EqLt", "Uneqlt"}:
        raise RegistryError(
            f"`repo_id` in {where} must start with `EqLt.` or `Uneqlt.`, got `{repo_id}`"
        )
    if not name:
        raise RegistryError(f"`repo_id` in {where} has an empty name after the dot")


def load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RegistryError(f"Registry YAML not found: {path}")
    data = yaml.safe_load(path.read_text())
    if data is None:
        raise RegistryError(f"Registry YAML is empty: {path}")
    return require_mapping(data, str(path))


def validate_registry(data: dict[str, Any]) -> dict[str, int]:
    repo_variables = require_list(data.get("repo_variables"), "repo_variables")
    derived_observables = require_list(data.get("derived_observables"), "derived_observables")
    observable_relations = require_list(data.get("observable_relations"), "observable_relations")
    measurement_patterns = require_list(data.get("measurement_patterns"), "measurement_patterns")

    seen_repo_id: dict[str, str] = {}
    seen_repo_lean_id: dict[str, str] = {}
    seen_h5_path: dict[str, str] = {}
    known_repo_ids: set[str] = set()
    known_lean_ids: set[str] = set()
    known_derived_ids: set[str] = set()

    for idx, raw_item in enumerate(repo_variables):
        where = f"repo_variables[{idx}]"
        item = require_mapping(raw_item, where)

        repo_id = require_str(item, "repo_id", where)
        lean_id = require_str(item, "lean_id", where)
        h5_path = require_str(item, "h5_path", where)
        c_field = require_str(item, "c_field", where)
        lean_meas_var = optional_str(item, "lean_meas_var", where) or infer_lean_meas_var(repo_id)

        check_repo_id_shape(repo_id, where)
        check_prefix(lean_id, "DQMC.Obs.", where, "lean_id")
        check_prefix(lean_meas_var, "DQMC.MeasVar.", where, "lean_meas_var")
        if not h5_path.startswith("/"):
            raise RegistryError(f"`h5_path` in {where} must be absolute, got `{h5_path}`")
        if not c_field.startswith("m->"):
            raise RegistryError(f"`c_field` in {where} should start with `m->`, got `{c_field}`")

        check_unique(repo_id, seen_repo_id, "repo_id", where)
        check_unique(lean_id, seen_repo_lean_id, "repo lean_id", where)
        check_unique(h5_path, seen_h5_path, "h5_path", where)

        known_repo_ids.add(repo_id)
        known_lean_ids.add(lean_id)

    seen_derived_id: dict[str, str] = {}
    seen_derived_lean_id: dict[str, str] = {}
    for idx, raw_item in enumerate(derived_observables):
        where = f"derived_observables[{idx}]"
        item = require_mapping(raw_item, where)

        derived_id = require_str(item, "derived_id", where)
        lean_id = require_str(item, "lean_id", where)
        theorem = require_str(item, "definition_theorem", where)
        check_prefix(lean_id, "DQMC.Obs.", where, "lean_id")
        check_prefix(theorem, "DQMC.", where, "definition_theorem")

        check_unique(derived_id, seen_derived_id, "derived_id", where)
        check_unique(lean_id, seen_derived_lean_id, "derived lean_id", where)

        input_repo_id = optional_str(item, "input_repo_id", where)
        input_lean_id = optional_str(item, "input_lean_id", where)
        input_lean_ids = require_str_list(item, "input_lean_ids", where)

        if input_repo_id is None and input_lean_id is None and not input_lean_ids:
            raise RegistryError(
                f"{where} must specify at least one of `input_repo_id`, `input_lean_id`, or `input_lean_ids`"
            )

        if input_repo_id is not None and input_repo_id not in known_repo_ids:
            raise RegistryError(
                f"{where} references unknown input_repo_id `{input_repo_id}`"
            )

        if input_lean_id is not None:
            check_prefix(input_lean_id, "DQMC.Obs.", where, "input_lean_id")
            if input_lean_id not in known_lean_ids:
                raise RegistryError(
                    f"{where} references unknown input_lean_id `{input_lean_id}`"
                )

        for lean_input in input_lean_ids:
            check_prefix(lean_input, "DQMC.Obs.", where, "input_lean_ids")
            if lean_input not in known_lean_ids:
                raise RegistryError(
                    f"{where} references unknown input_lean_ids entry `{lean_input}`"
                )

        known_derived_ids.add(derived_id)
        known_lean_ids.add(lean_id)

    seen_relation_id: dict[str, str] = {}
    for idx, raw_item in enumerate(observable_relations):
        where = f"observable_relations[{idx}]"
        item = require_mapping(raw_item, where)

        relation_id = require_str(item, "relation_id", where)
        theorem = require_str(item, "theorem", where)
        output_lean_id = require_str(item, "output_lean_id", where)
        input_lean_ids = require_str_list(item, "input_lean_ids", where)

        check_unique(relation_id, seen_relation_id, "relation_id", where)
        check_prefix(theorem, "DQMC.", where, "theorem")
        check_prefix(output_lean_id, "DQMC.Obs.", where, "output_lean_id")
        if output_lean_id not in known_lean_ids:
            raise RegistryError(
                f"{where} references unknown output_lean_id `{output_lean_id}`"
            )
        if not input_lean_ids:
            raise RegistryError(f"{where} must contain at least one input_lean_ids entry")
        for lean_input in input_lean_ids:
            check_prefix(lean_input, "DQMC.Obs.", where, "input_lean_ids")
            if lean_input not in known_lean_ids:
                raise RegistryError(
                    f"{where} references unknown input_lean_ids entry `{lean_input}`"
                )

    seen_pattern_id: dict[str, str] = {}
    for idx, raw_item in enumerate(measurement_patterns):
        where = f"measurement_patterns[{idx}]"
        item = require_mapping(raw_item, where)

        pattern_id = require_str(item, "pattern_id", where)
        theorem = require_str(item, "theorem", where)
        check_unique(pattern_id, seen_pattern_id, "pattern_id", where)
        check_prefix(theorem, "DQMC.Measurement.", where, "theorem")

    return {
        "repo_variables": len(repo_variables),
        "derived_observables": len(derived_observables),
        "observable_relations": len(observable_relations),
        "measurement_patterns": len(measurement_patterns),
        "known_lean_ids": len(known_lean_ids),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate observables.yaml graph consistency for the DQMC formal registry."
    )
    parser.add_argument(
        "--yaml",
        type=Path,
        default=DEFAULT_YAML,
        help=f"Path to observables.yaml. Default: {DEFAULT_YAML}",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print errors.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        data = load_registry(args.yaml)
        counts = validate_registry(data)
    except RegistryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"Registry OK: {args.yaml}")
        print(f"  repo_variables:       {counts['repo_variables']}")
        print(f"  derived_observables:  {counts['derived_observables']}")
        print(f"  observable_relations: {counts['observable_relations']}")
        print(f"  measurement_patterns: {counts['measurement_patterns']}")
        print(f"  known_lean_ids:       {counts['known_lean_ids']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
