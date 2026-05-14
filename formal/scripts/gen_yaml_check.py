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

OUT_PATH.write_text("\n".join(lines) + "\n")
print(f"Wrote {OUT_PATH}")
print(f"Checked {len(seen_repo)} repo_variables from observables.yaml")