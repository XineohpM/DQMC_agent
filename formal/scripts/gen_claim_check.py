#!/usr/bin/env python3
"""Generate a Lean checker for agent-produced DQMC claims.

This script is the bridge between an agent's structured claims and the Lean
formal registry.

Typical usage from `formal/`:

    python scripts/gen_claim_check.py --claims claims.json
    lake env lean GeneratedClaimCheck.lean

The input claims file should be JSON with the shape:

    {
      "claims": [
        {
          "claim_id": "Uneqlt.jj_maps_to_raw_current_current",
          "claim_type": "repo_variable",
          "repo_id": "Uneqlt.jj"
        },
        {
          "claim_id": "Uneqlt.JNJN_from_jj",
          "claim_type": "derived_observable",
          "derived_id": "Uneqlt.JNJN"
        },
        {
          "claim_id": "EqLt.g00_spin_average",
          "claim_type": "observable_relation",
          "relation_id": "EqLt.g00_spin_average"
        }
      ]
    }

The generated Lean file checks that the referenced Lean constants and theorems
exist, and for repo-variable claims it also checks the registered `MeasToObs`
mapping by `rfl`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    print("Missing dependency: PyYAML. Install with: pip install pyyaml", file=sys.stderr)
    raise exc


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "observables.yaml"
DEFAULT_CLAIMS = ROOT / "claims.json"
DEFAULT_OUTPUT = ROOT / "GeneratedClaimCheck.lean"


class ClaimCheckError(Exception):
    """Raised when claims are malformed or inconsistent with the registry."""


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ClaimCheckError(f"Registry YAML not found: {path}")
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ClaimCheckError(f"Registry YAML must contain a mapping at top level: {path}")
    return data


def load_claims(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ClaimCheckError(f"Claims JSON not found: {path}")
    data = json.loads(path.read_text())
    if isinstance(data, list):
        claims = data
    elif isinstance(data, dict) and isinstance(data.get("claims"), list):
        claims = data["claims"]
    else:
        raise ClaimCheckError(
            "Claims JSON must be either a list or an object with a `claims` list"
        )

    out: list[dict[str, Any]] = []
    for idx, claim in enumerate(claims):
        if not isinstance(claim, dict):
            raise ClaimCheckError(f"claims[{idx}] must be an object")
        out.append(claim)
    return out


def require_str(item: dict[str, Any], key: str, where: str) -> str:
    if key not in item:
        raise ClaimCheckError(f"Missing required key `{key}` in {where}")
    value = item[key]
    if not isinstance(value, str) or not value.strip():
        raise ClaimCheckError(f"`{key}` in {where} must be a non-empty string")
    return value


def optional_str(item: dict[str, Any], key: str, where: str) -> str | None:
    if key not in item:
        return None
    value = item[key]
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ClaimCheckError(f"`{key}` in {where} must be a non-empty string when present")
    return value


def optional_str_list(item: dict[str, Any], key: str, where: str) -> list[str]:
    if key not in item or item[key] is None:
        return []
    value = item[key]
    if not isinstance(value, list):
        raise ClaimCheckError(f"`{key}` in {where} must be a list of strings")
    out: list[str] = []
    for idx, entry in enumerate(value):
        if not isinstance(entry, str) or not entry.strip():
            raise ClaimCheckError(f"`{key}[{idx}]` in {where} must be a non-empty string")
        out.append(entry)
    return out


def infer_lean_meas_var(repo_id: str) -> str:
    """Infer the Lean MeasVar name from a canonical repo_id."""
    return "DQMC.MeasVar." + repo_id.replace(".", "_")


def lean_comment(text: str) -> str:
    """Create a safe one-line Lean comment."""
    return "-- " + text.replace("\n", " ").replace("-/", "")


def index_by(items: list[Any], key: str, block_name: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for idx, item in enumerate(items):
        where = f"{block_name}[{idx}]"
        if not isinstance(item, dict):
            raise ClaimCheckError(f"{where} must be an object")
        value = require_str(item, key, where)
        if value in out:
            raise ClaimCheckError(f"Duplicate `{key}` value `{value}` in {block_name}")
        out[value] = item
    return out


def build_registry_indexes(registry: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    repo_variables = registry.get("repo_variables", []) or []
    derived_observables = registry.get("derived_observables", []) or []
    observable_relations = registry.get("observable_relations", []) or []
    measurement_patterns = registry.get("measurement_patterns", []) or []

    if not isinstance(repo_variables, list):
        raise ClaimCheckError("`repo_variables` must be a list")
    if not isinstance(derived_observables, list):
        raise ClaimCheckError("`derived_observables` must be a list")
    if not isinstance(observable_relations, list):
        raise ClaimCheckError("`observable_relations` must be a list")
    if not isinstance(measurement_patterns, list):
        raise ClaimCheckError("`measurement_patterns` must be a list")

    return {
        "repo_by_id": index_by(repo_variables, "repo_id", "repo_variables"),
        "derived_by_id": index_by(derived_observables, "derived_id", "derived_observables"),
        "relation_by_id": index_by(observable_relations, "relation_id", "observable_relations"),
        "pattern_by_id": index_by(measurement_patterns, "pattern_id", "measurement_patterns"),
    }


def add_repo_variable_check(
    lines: list[str],
    claim: dict[str, Any],
    registry_item: dict[str, Any],
    where: str,
    meas_map: str,
) -> None:
    repo_id = require_str(registry_item, "repo_id", where)
    lean_id = require_str(registry_item, "lean_id", where)
    lean_meas_var = optional_str(registry_item, "lean_meas_var", where) or infer_lean_meas_var(repo_id)

    expected_lean_id = optional_str(claim, "lean_id", where)
    if expected_lean_id is not None and expected_lean_id != lean_id:
        raise ClaimCheckError(
            f"{where} expected lean_id `{expected_lean_id}`, but registry maps `{repo_id}` to `{lean_id}`"
        )

    lines.append(lean_comment(f"claim repo variable: {repo_id}"))
    lines.append(f"#check {lean_meas_var}")
    lines.append(f"#check {lean_id}")
    lines.append("example :")
    lines.append(f"    {meas_map} {lean_meas_var} =")
    lines.append(f"      {lean_id} := rfl")
    lines.append("")


def add_derived_observable_check(
    lines: list[str],
    claim: dict[str, Any],
    registry_item: dict[str, Any],
    where: str,
) -> None:
    derived_id = require_str(registry_item, "derived_id", where)
    lean_id = require_str(registry_item, "lean_id", where)
    theorem = require_str(registry_item, "definition_theorem", where)

    expected_lean_id = optional_str(claim, "lean_id", where)
    if expected_lean_id is not None and expected_lean_id != lean_id:
        raise ClaimCheckError(
            f"{where} expected lean_id `{expected_lean_id}`, but registry maps `{derived_id}` to `{lean_id}`"
        )

    expected_theorem = optional_str(claim, "theorem", where)
    if expected_theorem is not None and expected_theorem != theorem:
        raise ClaimCheckError(
            f"{where} expected theorem `{expected_theorem}`, but registry uses `{theorem}`"
        )

    lines.append(lean_comment(f"claim derived observable: {derived_id}"))
    lines.append(f"#check {lean_id}")
    lines.append(f"#check {theorem}")

    input_repo_id = optional_str(registry_item, "input_repo_id", where)
    input_lean_id = optional_str(registry_item, "input_lean_id", where)
    input_lean_ids = optional_str_list(registry_item, "input_lean_ids", where)

    if input_repo_id:
        lines.append(f"#check {infer_lean_meas_var(input_repo_id)}")
    if input_lean_id:
        lines.append(f"#check {input_lean_id}")
    for lean_input in input_lean_ids:
        lines.append(f"#check {lean_input}")
    lines.append("")


def add_observable_relation_check(
    lines: list[str],
    claim: dict[str, Any],
    registry_item: dict[str, Any],
    where: str,
) -> None:
    relation_id = require_str(registry_item, "relation_id", where)
    theorem = require_str(registry_item, "theorem", where)
    output_lean_id = require_str(registry_item, "output_lean_id", where)
    input_lean_ids = optional_str_list(registry_item, "input_lean_ids", where)

    expected_theorem = optional_str(claim, "theorem", where)
    if expected_theorem is not None and expected_theorem != theorem:
        raise ClaimCheckError(
            f"{where} expected theorem `{expected_theorem}`, but registry uses `{theorem}`"
        )

    lines.append(lean_comment(f"claim observable relation: {relation_id}"))
    lines.append(f"#check {theorem}")
    lines.append(f"#check {output_lean_id}")
    for lean_input in input_lean_ids:
        lines.append(f"#check {lean_input}")
    lines.append("")


def add_measurement_pattern_check(
    lines: list[str],
    claim: dict[str, Any],
    registry_item: dict[str, Any],
    where: str,
) -> None:
    pattern_id = require_str(registry_item, "pattern_id", where)
    theorem = require_str(registry_item, "theorem", where)

    expected_theorem = optional_str(claim, "theorem", where)
    if expected_theorem is not None and expected_theorem != theorem:
        raise ClaimCheckError(
            f"{where} expected theorem `{expected_theorem}`, but registry uses `{theorem}`"
        )

    lines.append(lean_comment(f"claim measurement pattern: {pattern_id}"))
    lines.append(f"#check {theorem}")
    lines.append("")


def add_theorem_chain_check(lines: list[str], claim: dict[str, Any], where: str) -> None:
    theorem_chain = optional_str_list(claim, "theorem_chain", where)
    if not theorem_chain:
        raise ClaimCheckError(f"{where} with claim_type `theorem_chain` needs non-empty `theorem_chain`")

    output_lean_id = optional_str(claim, "output_lean_id", where)
    input_lean_ids = optional_str_list(claim, "input_lean_ids", where)

    lines.append(lean_comment(f"claim theorem chain: {require_str(claim, 'claim_id', where)}"))
    if output_lean_id:
        lines.append(f"#check {output_lean_id}")
    for lean_input in input_lean_ids:
        lines.append(f"#check {lean_input}")
    for theorem in theorem_chain:
        lines.append(f"#check {theorem}")
    lines.append("")


def generate_claim_check(
    registry: dict[str, Any],
    claims: list[dict[str, Any]],
    meas_map: str,
) -> str:
    indexes = build_registry_indexes(registry)
    repo_by_id = indexes["repo_by_id"]
    derived_by_id = indexes["derived_by_id"]
    relation_by_id = indexes["relation_by_id"]
    pattern_by_id = indexes["pattern_by_id"]

    lines: list[str] = []
    lines.append("import DQMC")
    lines.append("")
    lines.append("-- This file is generated from an agent claims JSON file.")
    lines.append("-- Do not edit by hand.")
    lines.append("")

    seen_claim_ids: set[str] = set()
    for idx, claim in enumerate(claims):
        where = f"claims[{idx}]"
        claim_id = require_str(claim, "claim_id", where)
        claim_type = require_str(claim, "claim_type", where)

        if claim_id in seen_claim_ids:
            raise ClaimCheckError(f"Duplicate claim_id `{claim_id}` in claims file")
        seen_claim_ids.add(claim_id)

        lines.append(lean_comment(f"claim_id: {claim_id}"))

        if claim_type == "repo_variable":
            repo_id = require_str(claim, "repo_id", where)
            if repo_id not in repo_by_id:
                raise ClaimCheckError(f"{where} references unknown repo_id `{repo_id}`")
            add_repo_variable_check(lines, claim, repo_by_id[repo_id], where, meas_map)

        elif claim_type == "derived_observable":
            derived_id = require_str(claim, "derived_id", where)
            if derived_id not in derived_by_id:
                raise ClaimCheckError(f"{where} references unknown derived_id `{derived_id}`")
            add_derived_observable_check(lines, claim, derived_by_id[derived_id], where)

        elif claim_type == "observable_relation":
            relation_id = require_str(claim, "relation_id", where)
            if relation_id not in relation_by_id:
                raise ClaimCheckError(f"{where} references unknown relation_id `{relation_id}`")
            add_observable_relation_check(lines, claim, relation_by_id[relation_id], where)

        elif claim_type == "measurement_pattern":
            pattern_id = require_str(claim, "pattern_id", where)
            if pattern_id not in pattern_by_id:
                raise ClaimCheckError(f"{where} references unknown pattern_id `{pattern_id}`")
            add_measurement_pattern_check(lines, claim, pattern_by_id[pattern_id], where)

        elif claim_type == "theorem_chain":
            add_theorem_chain_check(lines, claim, where)

        else:
            raise ClaimCheckError(
                f"{where} has unsupported claim_type `{claim_type}`. "
                "Supported types: repo_variable, derived_observable, observable_relation, "
                "measurement_pattern, theorem_chain"
            )

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Lean checker from agent-produced DQMC claims."
    )
    parser.add_argument(
        "--claims",
        type=Path,
        default=DEFAULT_CLAIMS,
        help=f"Path to claims JSON. Default: {DEFAULT_CLAIMS}",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY,
        help=f"Path to observables.yaml. Default: {DEFAULT_REGISTRY}",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output Lean file. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--meas-map",
        default="DQMC.MeasToObs",
        help="Lean function used for MeasVar -> Obs checks. Default: DQMC.MeasToObs",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        registry = load_yaml(args.registry)
        claims = load_claims(args.claims)
        output = generate_claim_check(registry, claims, args.meas_map)
    except (ClaimCheckError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    args.out.write_text(output)
    print(f"Wrote {args.out}")
    print(f"Checked {len(claims)} claims from {args.claims}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())