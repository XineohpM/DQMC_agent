import os
import subprocess
from pathlib import Path
from typing import List, Dict

TEXT_EXTS = {
    ".py", ".ipynb", ".md", ".txt", ".rst",
    ".c", ".cc", ".cpp", ".h", ".hpp",
    ".f", ".f90", ".f95",
    ".jl", ".m", ".json", ".yaml", ".yml", ".toml"
}

SKIP_DIRS = {
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".venv", "venv", "node_modules", "build", "dist"
}


def get_repo_tree(repo_path: str, max_entries: int = 400) -> str:
    repo = Path(repo_path)
    if not repo.exists():
        return f"Repo path not found: {repo_path}"

    lines = []
    count = 0
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel_root = Path(root).relative_to(repo)
        depth = len(rel_root.parts)

        if str(rel_root) != ".":
            lines.append("  " * depth + f"[DIR] {rel_root.name}")

        for f in sorted(files):
            p = Path(root) / f
            if p.suffix.lower() in TEXT_EXTS:
                rel = p.relative_to(repo)
                lines.append("  " * (depth + 1) + rel.name)
                count += 1
                if count >= max_entries:
                    lines.append("... [truncated]")
                    return "\n".join(lines)

    return "\n".join(lines)


def read_file(repo_path: str, relative_path: str, max_chars: int = 20000) -> str:
    p = Path(repo_path) / relative_path
    if not p.exists():
        return f"File not found: {relative_path}"
    if p.suffix.lower() not in TEXT_EXTS:
        return f"Unsupported file type: {relative_path}"

    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return f"Error reading file {relative_path}: {e}"

    if len(text) > max_chars:
        return text[:max_chars] + "\n\n... [truncated]"
    return text


def search_repo(repo_path: str, query: str, max_hits: int = 20) -> List[Dict]:
    repo = Path(repo_path)
    hits = []
    q = query.lower()

    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            p = Path(root) / f
            if p.suffix.lower() not in TEXT_EXTS:
                continue
            rel = str(p.relative_to(repo))
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            idx = text.lower().find(q)
            if idx != -1:
                start = max(0, idx - 300)
                end = min(len(text), idx + 500)
                snippet = text[start:end]
                hits.append({
                    "path": rel,
                    "snippet": snippet
                })
                if len(hits) >= max_hits:
                    return hits
    return hits


def write_agent_file(repo_path: str, relative_path: str, content: str) -> str:
    """
    Only allow writes under agent_outputs/ to avoid touching core source by mistake.
    """
    rel = Path(relative_path)
    if rel.is_absolute():
        return "Only relative paths are allowed."

    parts = rel.parts
    if not parts or parts[0] != "agent_outputs":
        return "Write rejected. Only paths under agent_outputs/ are allowed."

    full = Path(repo_path) / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return f"Wrote file: {rel}"


def check_python_file(repo_path: str, relative_path: str) -> str:
    rel = Path(relative_path)
    full = Path(repo_path) / rel
    if not full.exists():
        return f"File not found: {relative_path}"
    if full.suffix.lower() != ".py":
        return "Only Python files can be syntax-checked."

    try:
        result = subprocess.run(
            ["python", "-m", "py_compile", str(full)],
            capture_output=True,
            text=True,
            cwd=str(Path(repo_path))
        )
    except Exception as e:
        return f"Failed to run syntax check: {e}"

    if result.returncode == 0:
        return f"Syntax check passed: {relative_path}"

    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    msg = stderr if stderr else stdout
    return f"Syntax check failed for {relative_path}:\n{msg}"