import json
from pathlib import Path
from typing import List, Dict, Any, Tuple


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


def tokenize(text: str) -> List[str]:
    text = text.replace("/", " ").replace("_", " ").replace("-", " ")
    return [tok.lower().strip() for tok in text.split() if tok.strip()]


def score_io_record(query: str, rec: Dict[str, Any]) -> float:
    q_tokens = tokenize(query)
    path = rec.get("path", "").lower()
    role = rec.get("role", "").lower()
    hdf5_paths = " ".join(rec.get("hdf5_paths", [])).lower()
    params = " ".join(rec.get("param_mentions", [])).lower()
    io_signals = rec.get("io_signals", {})

    score = 0.0
    for tok in q_tokens:
        if tok in path:
            score += 3.5
        if tok in role:
            score += 2.0
        if tok in hdf5_paths:
            score += 5.0
        if tok in params:
            score += 4.0

    low_q = query.lower()

    # intent boosts
    if "read" in low_q:
        if io_signals.get("np_load") or io_signals.get("np_loadtxt") or io_signals.get("json_load") or io_signals.get("pickle_load") or io_signals.get("open_read"):
            score += 1.5
    if "write" in low_q or "save" in low_q:
        if io_signals.get("np_save") or io_signals.get("np_savetxt") or io_signals.get("json_dump") or io_signals.get("pickle_dump") or io_signals.get("open_write") or io_signals.get("savefig"):
            score += 1.5
    if "reshape" in low_q and io_signals.get("reshape"):
        score += 1.5
    if "shape" in low_q and io_signals.get("shape"):
        score += 1.0

    return score


def search_io_index(query: str, io_index_path: str, top_k: int = 10) -> List[Dict[str, Any]]:
    rows = load_jsonl(io_index_path)
    scored: List[Tuple[float, Dict[str, Any]]] = []

    for rec in rows:
        s = score_io_record(query, rec)
        if s > 0:
            scored.append((s, rec))

    scored.sort(key=lambda x: (-x[0], x[1].get("path", "")))
    return [r for _, r in scored[:top_k]]


def format_io_hits(query: str, io_index_path: str, top_k: int = 10) -> str:
    hits = search_io_index(query, io_index_path, top_k=top_k)
    if not hits:
        return "No I/O index hits found."

    lines = [f"Top I/O index hits for query: {query}", ""]
    for i, rec in enumerate(hits, 1):
        lines.append(f"[{i}] {rec.get('path', '')}")
        lines.append(f"  role: {rec.get('role', '')}")

        hdf5_paths = rec.get("hdf5_paths", [])
        if hdf5_paths:
            lines.append(f"  hdf5_paths: {', '.join(hdf5_paths[:10])}")

        params = rec.get("param_mentions", [])
        if params:
            lines.append(f"  param_mentions: {', '.join(params[:15])}")

        io_signals = rec.get("io_signals", {})
        active_signals = [k for k, v in io_signals.items() if v]
        if active_signals:
            lines.append(f"  io_signals: {', '.join(active_signals)}")

        lines.append("")
    return "\n".join(lines)