#!/usr/bin/env python3
from pathlib import Path
import sys

try:
    import yaml
except ImportError:
    print("Missing dependency: PyYAML. Install with: pip install pyyaml", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[1]
YAML_PATH = ROOT / "observables.yaml"
OUT_PATH = ROOT / "GeneratedYamlCheck.lean"

data = yaml.safe_load(YAML_PATH.read_text())

lines = []
lines.append("import DQMC.RepoMap")
lines.append("import DQMC.Density")
lines.append("import DQMC.Green")
lines.append("import DQMC.Current")
lines.append("import DQMC.Measurement")
lines.append("")
lines.append("-- This file is generated from observables.yaml.")
lines.append("-- Do not edit by hand.")
lines.append("")


seen_repo = set()
seen_lean = set()

def infer_lean_meas_var(repo_id: str) -> str:
    """Infer the Lean MeasVar name from a canonical repo_id.

    Example:
      EqLt.density -> DQMC.MeasVar.EqLt_density
      Uneqlt.gt0_u -> DQMC.MeasVar.Uneqlt_gt0_u
    """
    return "DQMC.MeasVar." + repo_id.replace(".", "_")

for item in data.get("repo_variables", []):
    repo_id = item["repo_id"]
    lean_meas_var = item.get("lean_meas_var") or infer_lean_meas_var(repo_id)
    lean_id = item["lean_id"]

    if repo_id in seen_repo:
        raise ValueError(f"Duplicate repo_id in observables.yaml: {repo_id}")
    if lean_id in seen_lean:
        raise ValueError(f"Duplicate lean_id in observables.yaml: {lean_id}")

    seen_repo.add(repo_id)
    seen_lean.add(lean_id)

    lines.append(f"-- {repo_id}")
    lines.append(f"#check {lean_meas_var}")
    lines.append(f"#check {lean_id}")
    lines.append("example :")
    lines.append(f"    DQMC.MeasToObs {lean_meas_var} =")
    lines.append(f"      {lean_id} := rfl")
    lines.append("")

relation_count = 0
for item in data.get("observable_relations", []):
    relation_id = item["relation_id"]
    theorem = item["theorem"]
    output_lean_id = item["output_lean_id"]
    input_lean_ids = item.get("input_lean_ids", [])

    lines.append(f"-- observable relation: {relation_id}")
    lines.append(f"#check {theorem}")
    lines.append(f"#check {output_lean_id}")
    for lean_id in input_lean_ids:
        lines.append(f"#check {lean_id}")
    lines.append("")
    relation_count += 1

derived_count = 0
for item in data.get("derived_observables", []):
    derived_id = item["derived_id"]
    lean_id = item["lean_id"]
    theorem = item["definition_theorem"]

    lines.append(f"-- derived observable: {derived_id}")
    lines.append(f"#check {lean_id}")
    lines.append(f"#check {theorem}")

    if "input_lean_id" in item:
        lines.append(f"#check {item['input_lean_id']}")

    if "input_repo_id" in item:
        input_meas_var = infer_lean_meas_var(item["input_repo_id"])
        lines.append(f"#check {input_meas_var}")

    lines.append("")
    derived_count += 1

measurement_pattern_count = 0
for item in data.get("measurement_patterns", []):
    pattern_id = item["pattern_id"]
    theorem = item["theorem"]

    lines.append(f"-- measurement pattern: {pattern_id}")
    lines.append(f"#check {theorem}")
    lines.append("")
    measurement_pattern_count += 1

OUT_PATH.write_text("\n".join(lines) + "\n")
print(f"Wrote {OUT_PATH}")
print(f"Checked {len(seen_repo)} repo_variables from observables.yaml")
print(f"Checked {relation_count} observable_relations from observables.yaml")
print(f"Checked {derived_count} derived_observables from observables.yaml")
print(f"Checked {measurement_pattern_count} measurement_patterns from observables.yaml")