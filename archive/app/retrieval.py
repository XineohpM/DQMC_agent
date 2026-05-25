import json
from pathlib import Path
from typing import List, Dict, Any, Tuple


def load_index(index_path: str) -> List[Dict[str, Any]]:
    p = Path(index_path)
    if not p.exists():
        return []
    rows = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def tokenize(text: str) -> List[str]:
    return [tok.strip().lower() for tok in text.replace("/", " ").replace("_", " ").split() if tok.strip()]


def score_record(query: str, rec: Dict[str, Any]) -> float:
    q_tokens = tokenize(query)
    path = rec.get("path", "").lower()
    summary = rec.get("module_summary", "").lower()
    funcs = " ".join(rec.get("key_functions", [])).lower()
    classes = " ".join(rec.get("key_classes", [])).lower()
    tags = " ".join(rec.get("physics_tags", [])).lower()
    role = rec.get("script_role", "").lower()

    score = 0.0
    for tok in q_tokens:
        if tok in path:
            score += 4.0
        if tok in funcs:
            score += 3.0
        if tok in classes:
            score += 2.5
        if tok in tags:
            score += 3.0
        if tok in summary:
            score += 2.0
        if tok == role:
            score += 2.0

    low_q = query.lower()

    if "plot" in low_q and rec.get("script_role") == "plotting":
        score += 3.0
    if "postprocess" in low_q and rec.get("script_role") == "postprocess":
        score += 3.0
    if "measure" in low_q and rec.get("script_role") == "measurement":
        score += 3.0
    if "read" in low_q and rec.get("reads_data"):
        score += 1.5
    if "write" in low_q and rec.get("writes_data"):
        score += 1.5

    return score


def retrieve_candidates(query: str, index_path: str, top_k: int = 8) -> List[Dict[str, Any]]:
    rows = load_index(index_path)
    if not rows:
        return []

    scored: List[Tuple[float, Dict[str, Any]]] = []
    for rec in rows:
        s = score_record(query, rec)
        if s > 0:
            scored.append((s, rec))

    scored.sort(key=lambda x: (-x[0], x[1]["path"]))
    return [rec for _, rec in scored[:top_k]]


def format_candidates_for_agent(query: str, index_path: str, top_k: int = 8) -> str:
    hits = retrieve_candidates(query, index_path, top_k=top_k)
    if not hits:
        return "No index candidates found."

    lines = [f"Top index candidates for query: {query}", ""]
    for i, rec in enumerate(hits, 1):
        lines.append(f"[{i}] {rec['path']}")
        lines.append(f"  role: {rec.get('script_role', 'unknown')}")
        lines.append(f"  summary: {rec.get('module_summary', '')}")
        if rec.get("physics_tags"):
            lines.append(f"  physics_tags: {', '.join(rec['physics_tags'])}")
        if rec.get("key_functions"):
            lines.append(f"  key_functions: {', '.join(rec['key_functions'][:8])}")
        lines.append("")
    return "\n".join(lines)