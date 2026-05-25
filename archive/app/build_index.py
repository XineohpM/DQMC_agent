import os
import re
import json
import ast
from pathlib import Path
from typing import Dict, List, Any

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

PHYSICS_KEYWORDS = {
    "green": "Green function",
    "greens": "Green function",
    "green function": "Green function",
    "conductivity": "conductivity",
    "optical conductivity": "optical conductivity",
    "density": "density",
    "double occupancy": "double occupancy",
    "dos": "DOS",
    "spectral": "spectral function",
    "current": "current-current correlator",
    "correlator": "correlator",
    "monte carlo": "Monte Carlo",
    "dqmc": "DQMC",
    "hubbard": "Hubbard model",
    "lattice": "lattice",
    "pair": "pairing",
    "susceptibility": "susceptibility",
    "self energy": "self-energy",
    "imaginary time": "imaginary time",
    "maxent": "MaxEnt",
    "anneal": "annealing",
    "hdf5": "HDF5 I/O",
    "jackknife": "jackknife",
    "bootstrap": "bootstrap",
}

READ_PATTERNS = [
    r"open\(",
    r"np\.load\(",
    r"np\.loadtxt\(",
    r"h5py\.File\(",
    r"json\.load\(",
    r"pickle\.load\(",
]

WRITE_PATTERNS = [
    r"np\.save\(",
    r"np\.savetxt\(",
    r"h5py\.File\(",
    r"open\(.*['\"]w['\"]",
    r"json\.dump\(",
    r"plt\.savefig\(",
]

ROLE_HINTS = {
    "plot": "plotting",
    "draw": "plotting",
    "visual": "plotting",
    "postprocess": "postprocess",
    "analysis": "postprocess",
    "measure": "measurement",
    "observable": "measurement",
    "solver": "solver",
    "dqmc": "solver",
    "util": "utils",
    "helper": "utils",
    "io": "io",
    "read": "io",
    "write": "io",
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


def safe_read_text(path: Path, max_chars: int = 50000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    return text[:max_chars]


def extract_python_symbols(text: str) -> Dict[str, List[str]]:
    result = {"functions": [], "classes": [], "imports": []}
    try:
        tree = ast.parse(text)
    except Exception:
        return result

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            result["functions"].append(node.name)
        elif isinstance(node, ast.AsyncFunctionDef):
            result["functions"].append(node.name)
        elif isinstance(node, ast.ClassDef):
            result["classes"].append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                if mod:
                    result["imports"].append(f"{mod}.{alias.name}")
                else:
                    result["imports"].append(alias.name)

    result["functions"] = sorted(set(result["functions"]))
    result["classes"] = sorted(set(result["classes"]))
    result["imports"] = sorted(set(result["imports"]))
    return result


def extract_keywords(text: str) -> List[str]:
    low = text.lower()
    tags = []
    for k, tag in PHYSICS_KEYWORDS.items():
        if k in low:
            tags.append(tag)
    return sorted(set(tags))


def infer_io_patterns(text: str) -> Dict[str, bool]:
    low = text
    reads = any(re.search(p, low) for p in READ_PATTERNS)
    writes = any(re.search(p, low) for p in WRITE_PATTERNS)
    return {"reads_data": reads, "writes_data": writes}


def infer_role(path: Path, text: str) -> str:
    low = f"{str(path).lower()} {text[:5000].lower()}"
    for hint, role in ROLE_HINTS.items():
        if hint in low:
            return role
    return "unknown"


def short_summary(path: Path, text: str, symbols: Dict[str, List[str]], tags: List[str], io_info: Dict[str, bool], role: str) -> str:
    parts = [f"File `{path.name}`"]
    if role != "unknown":
        parts.append(f"likely serves as `{role}`")
    if symbols["functions"]:
        parts.append(f"defines functions such as {', '.join(symbols['functions'][:6])}")
    if symbols["classes"]:
        parts.append(f"defines classes such as {', '.join(symbols['classes'][:4])}")
    if tags:
        parts.append(f"contains physics-related topics: {', '.join(tags[:6])}")
    if io_info["reads_data"] and io_info["writes_data"]:
        parts.append("appears to both read and write data")
    elif io_info["reads_data"]:
        parts.append("appears to read data")
    elif io_info["writes_data"]:
        parts.append("appears to write data")
    return "; ".join(parts) + "."


def build_index(repo_path: str) -> List[Dict[str, Any]]:
    repo = Path(repo_path).resolve()
    records = []

    for file_path in iter_repo_files(repo):
        rel = str(file_path.relative_to(repo))
        text = safe_read_text(file_path)
        if not text.strip():
            continue

        if file_path.suffix.lower() == ".py":
            symbols = extract_python_symbols(text)
        else:
            symbols = {"functions": [], "classes": [], "imports": []}

        tags = extract_keywords(text)
        io_info = infer_io_patterns(text)
        role = infer_role(file_path, text)
        summary = short_summary(file_path, text, symbols, tags, io_info, role)

        record = {
            "path": rel,
            "suffix": file_path.suffix.lower(),
            "module_summary": summary,
            "key_functions": symbols["functions"][:20],
            "key_classes": symbols["classes"][:20],
            "imports": symbols["imports"][:40],
            "physics_tags": tags,
            "reads_data": io_info["reads_data"],
            "writes_data": io_info["writes_data"],
            "script_role": role,
        }
        records.append(record)

    records.sort(key=lambda x: x["path"])
    return records


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="Absolute path to the target repo")
    parser.add_argument("--out", default="data/repo_index.jsonl", help="Output jsonl path")
    args = parser.parse_args()

    records = build_index(args.repo)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"Wrote {len(records)} records to {out_path}")


if __name__ == "__main__":
    main()