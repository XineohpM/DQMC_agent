import json
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple

CANONICAL_CONCEPTS = {
    "density": "density",
    "density_u": "spin-resolved density",
    "density_d": "spin-resolved density",
    "double_occ": "double occupancy",
    "gt0": "unequal-time Green function",
    "gt0_u": "spin-resolved unequal-time Green function",
    "gt0_d": "spin-resolved unequal-time Green function",
    "g00": "equal-time Green function",
    "g00_u": "spin-resolved equal-time Green function",
    "g00_d": "spin-resolved equal-time Green function",
    "jj": "current-current correlator",
    "kk": "kinetic-energy-related quantity",
    "pair_sw": "s-wave pair correlator",
    "sign": "Monte Carlo sign",
    "n_sample": "sample count",
    "beta": "inverse temperature",
    "dt": "imaginary-time discretization",
    "L": "imaginary-time slices",
    "mu": "chemical potential",
    "U": "interaction strength",
    "tp": "next-nearest-neighbor hopping or secondary hopping parameter",
    "tpp": "higher-order hopping parameter",
    "nflux": "flux parameter",
    "bc": "boundary condition parameter",
    "hs_channel": "Hubbard-Stratonovich channel",
    "omega": "real-frequency grid",
    "domega": "frequency spacing",
    "A_mean": "mean spectral function",
    "s_all": "spectral samples or bootstrap spectra",
    "sigma_dc": "dc conductivity",
    "resistivity": "resistivity",
    "vn": "density-related correlator or vertex-like quantity",
    "vv": "current- or bond-related correlator or vertex-like quantity",
    "xx": "correlator component or structure quantity",
    "zz": "correlator component or structure quantity",
}

DEFAULT_CONFIDENCE = {
    "density": "high",
    "density_u": "high",
    "density_d": "high",
    "double_occ": "high",
    "gt0": "high",
    "gt0_u": "high",
    "gt0_d": "high",
    "g00": "medium",
    "g00_u": "medium",
    "g00_d": "medium",
    "jj": "medium",
    "kk": "low",
    "pair_sw": "medium",
    "sign": "high",
    "n_sample": "high",
    "beta": "high",
    "dt": "high",
    "L": "medium",
    "mu": "high",
    "U": "high",
    "tp": "medium",
    "tpp": "medium",
    "nflux": "medium",
    "bc": "medium",
    "hs_channel": "medium",
    "omega": "high",
    "domega": "high",
    "A_mean": "medium",
    "s_all": "medium",
    "sigma_dc": "medium",
    "resistivity": "high",
    "vn": "low",
    "vv": "low",
    "xx": "low",
    "zz": "low",
}


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    rows = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def collect_candidates(repo_rows: List[Dict[str, Any]], io_rows: List[Dict[str, Any]]) -> Set[str]:
    candidates: Set[str] = set()

    for row in repo_rows:
        for f in row.get("key_functions", []):
            if f in CANONICAL_CONCEPTS:
                candidates.add(f)
        for cls in row.get("key_classes", []):
            if cls in CANONICAL_CONCEPTS:
                candidates.add(cls)
        for tag in row.get("physics_tags", []):
            for k in CANONICAL_CONCEPTS:
                if k.lower() in tag.lower():
                    candidates.add(k)

    for row in io_rows:
        for p in row.get("param_mentions", []):
            if p in CANONICAL_CONCEPTS:
                candidates.add(p)
        for hp in row.get("hdf5_paths", []):
            tail = hp.split("/")[-1]
            if tail in CANONICAL_CONCEPTS:
                candidates.add(tail)

    return set(sorted(candidates))


def gather_locations(name: str, repo_rows: List[Dict[str, Any]], io_rows: List[Dict[str, Any]]) -> List[str]:
    locs: Set[str] = set()

    for row in repo_rows:
        if name in row.get("key_functions", []) or name in row.get("key_classes", []):
            locs.add(row["path"])
        if any(name.lower() in tag.lower() for tag in row.get("physics_tags", [])):
            locs.add(row["path"])

    for row in io_rows:
        if name in row.get("param_mentions", []):
            locs.add(row["path"])
        for hp in row.get("hdf5_paths", []):
            if hp.split("/")[-1] == name:
                locs.add(row["path"])

    return sorted(locs)


def gather_hdf5_paths(name: str, io_rows: List[Dict[str, Any]]) -> List[str]:
    out: Set[str] = set()
    for row in io_rows:
        for hp in row.get("hdf5_paths", []):
            if hp.split("/")[-1] == name:
                out.add(hp)
    return sorted(out)


def build_entry(name: str, repo_rows: List[Dict[str, Any]], io_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    concept = CANONICAL_CONCEPTS.get(name, "unknown")
    confidence = DEFAULT_CONFIDENCE.get(name, "low")
    code_locations = gather_locations(name, repo_rows, io_rows)
    hdf5_paths = gather_hdf5_paths(name, io_rows)

    code_evidence_parts = []
    if hdf5_paths:
        code_evidence_parts.append(f"Observed in HDF5-like paths: {', '.join(hdf5_paths[:6])}.")
    if code_locations:
        code_evidence_parts.append(f"Referenced in repository files such as {', '.join(code_locations[:6])}.")
    if not code_evidence_parts:
        code_evidence_parts.append("Current evidence is indirect and based on naming patterns.")

    physics_interpretation = concept

    inference_notes = ""
    if confidence == "low":
        inference_notes = (
            "Interpretation is tentative and mainly inferred from naming conventions or standard computational-physics usage. "
            "Exact normalization, tensor meaning, or storage convention should be checked in measurement and analysis code."
        )
    elif confidence == "medium":
        inference_notes = (
            "Interpretation is plausible from code naming and storage context, but exact definition or normalization may still require file-level inspection."
        )
    else:
        inference_notes = (
            "Interpretation is strongly supported by code naming and repository context, though implementation conventions should still be checked when precision matters."
        )

    kind = "parameter" if name in {
        "beta", "dt", "L", "mu", "U", "tp", "tpp", "nflux", "bc", "hs_channel"
    } else "dataset_or_analysis_quantity"

    aliases = []
    if name == "gt0":
        aliases = ["gt0_u", "gt0_d"]
    elif name == "density":
        aliases = ["density_u", "density_d"]

    return {
        "name": name,
        "kind": kind,
        "aliases": aliases,
        "code_locations": code_locations,
        "hdf5_paths": hdf5_paths,
        "related_concepts": [concept],
        "code_evidence": " ".join(code_evidence_parts),
        "physics_interpretation": concept,
        "inference_notes": inference_notes,
        "confidence": confidence,
        "source": "auto_generated"
    }


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-index", default="data/repo_index.jsonl")
    parser.add_argument("--io-index", default="data/io_index.jsonl")
    parser.add_argument("--out", default="data/semantic_map.jsonl")
    args = parser.parse_args()

    repo_rows = load_jsonl(args.repo_index)
    io_rows = load_jsonl(args.io_index)

    candidates = collect_candidates(repo_rows, io_rows)
    entries = [build_entry(name, repo_rows, io_rows) for name in sorted(candidates)]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"Wrote {len(entries)} semantic-map records to {out}")


if __name__ == "__main__":
    main()