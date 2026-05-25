import os
import re
import json
from pathlib import Path
from typing import Dict, List, Any, Set

TEXT_EXTS = {
    ".py", ".md", ".txt", ".rst",
    ".c", ".cc", ".cpp", ".h", ".hpp",
    ".f", ".f90", ".f95",
    ".jl", ".m", ".json", ".yaml", ".yml", ".toml"
}

SKIP_DIRS = {
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".venv", "venv", "node_modules", "build", "dist",
    "agent_outputs", "data"
}

KEY_PARAMS = {
    "beta", "dt", "L", "n_sample", "sign", "mu", "U", "tp", "tpp",
    "nflux", "bc", "Nx", "Ny", "hs_channel", "omega", "domega",
    "A_mean", "s_all", "sigma_dc", "resistivity", "density",
    "density_u", "density_d", "double_occ", "gt0", "gt0_u", "gt0_d",
    "jj", "kk", "pair_sw", "vn", "vv", "xx", "zz"
}

HDF5_PATH_PATTERNS = [
    r'["\']([A-Za-z0-9_\-]+(?:/[A-Za-z0-9_\-]+)+)["\']',
]

IO_PATTERNS = {
    "np_load": r"\bnp\.load\s*\(",
    "np_save": r"\bnp\.save\s*\(",
    "np_savetxt": r"\bnp\.savetxt\s*\(",
    "np_loadtxt": r"\bnp\.loadtxt\s*\(",
    "h5py_file": r"\bh5py\.File\s*\(",
    "open_read": r"\bopen\s*\([^)]*['\"]r['\"]",
    "open_write": r"\bopen\s*\([^)]*['\"]w['\"]",
    "json_load": r"\bjson\.load\s*\(",
    "json_dump": r"\bjson\.dump\s*\(",
    "pickle_load": r"\bpickle\.load\s*\(",
    "pickle_dump": r"\bpickle\.dump\s*\(",
    "savefig": r"\bplt\.savefig\s*\(",
    "reshape": r"\.reshape\s*\(",
    "shape": r"\.shape\b",
}

DATASET_HINTS = {
    "meas_eqlt", "meas_uneqlt", "metadata", "params", "state", "maxent_out"
}


def should_keep_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTS


def iter_repo_files(repo_path: Path):
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            p = Path(root) / f
            if should_keep_file(p):
                yield p


def safe_read_text(path: Path, max_chars: int = 100000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except Exception:
        return ""


def extract_hdf5_paths(text: str) -> List[str]:
    found: Set[str] = set()
    for pat in HDF5_PATH_PATTERNS:
        for m in re.finditer(pat, text):
            s = m.group(1)
            if "/" in s:
                head = s.split("/")[0]
                if head in DATASET_HINTS or len(s.split("/")) >= 2:
                    found.add(s)
    return sorted(found)


def extract_param_mentions(text: str) -> List[str]:
    found = []
    low = text.lower()
    for p in sorted(KEY_PARAMS):
        if re.search(rf"\b{re.escape(p.lower())}\b", low):
            found.append(p)
    return found


def extract_io_signals(text: str) -> Dict[str, bool]:
    out = {}
    for name, pat in IO_PATTERNS.items():
        out[name] = bool(re.search(pat, text))
    return out


def infer_file_role(path: Path, text: str, io_signals: Dict[str, bool]) -> str:
    low = f"{str(path).lower()} {text[:4000].lower()}"
    if "plot" in low or io_signals.get("savefig"):
        return "plotting"
    if "maxent" in low:
        return "continuation_or_spectral"
    if "measure" in low or "observable" in low:
        return "measurement"
    if "gen_" in path.name.lower() or "scan" in low:
        return "generation_or_driver"
    if any(io_signals.get(k) for k in ["np_load", "np_loadtxt", "json_load", "pickle_load"]) and not any(
        io_signals.get(k) for k in ["np_save", "json_dump", "pickle_dump", "savefig"]
    ):
        return "reader_or_analysis"
    if any(io_signals.get(k) for k in ["np_save", "json_dump", "pickle_dump", "savefig"]):
        return "writer_or_analysis"
    return "unknown"


def build_io_index(repo_path: str) -> List[Dict[str, Any]]:
    repo = Path(repo_path).resolve()
    rows: List[Dict[str, Any]] = []

    for p in iter_repo_files(repo):
        text = safe_read_text(p)
        if not text.strip():
            continue

        rel = str(p.relative_to(repo))
        hdf5_paths = extract_hdf5_paths(text)
        params = extract_param_mentions(text)
        io_signals = extract_io_signals(text)
        role = infer_file_role(p, text, io_signals)

        if not hdf5_paths and not params and not any(io_signals.values()):
            continue

        row = {
            "path": rel,
            "suffix": p.suffix.lower(),
            "role": role,
            "hdf5_paths": hdf5_paths[:100],
            "param_mentions": params[:100],
            "io_signals": io_signals,
        }
        rows.append(row)

    rows.sort(key=lambda x: x["path"])
    return rows


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="Absolute path to repo")
    parser.add_argument("--out", default="data/io_index.jsonl", help="Output path")
    args = parser.parse_args()

    rows = build_io_index(args.repo)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote {len(rows)} I/O index records to {out}")


if __name__ == "__main__":
    main()