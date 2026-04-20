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


def score_semantic(query: str, rec: Dict[str, Any]) -> float:
    q = tokenize(query)
    name = rec.get("name", "").lower()
    aliases = " ".join(rec.get("aliases", [])).lower()
    concepts = " ".join(rec.get("related_concepts", [])).lower()
    interp = rec.get("physics_interpretation", "").lower()
    evidence = rec.get("code_evidence", "").lower()
    confidence = rec.get("confidence", "").lower()

    score = 0.0
    for tok in q:
        if tok in name:
            score += 5.0
        if tok in aliases:
            score += 4.0
        if tok in concepts:
            score += 3.0
        if tok in interp:
            score += 2.5
        if tok in evidence:
            score += 1.5

    if "physical" in query.lower() or "meaning" in query.lower():
        score += 1.0
    if confidence == "high":
        score += 0.8
    elif confidence == "medium":
        score += 0.4

    return score


def score_glossary(query: str, rec: Dict[str, Any]) -> float:
    q = tokenize(query)
    term = rec.get("term", "").lower()
    definition = rec.get("definition", "").lower()
    notes = rec.get("notes", "").lower()

    score = 0.0
    for tok in q:
        if tok in term:
            score += 4.0
        if tok in definition:
            score += 2.0
        if tok in notes:
            score += 1.0
    return score


def search_semantic_map(query: str, semantic_path: str, top_k: int = 8) -> List[Dict[str, Any]]:
    rows = load_jsonl(semantic_path)
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for rec in rows:
        s = score_semantic(query, rec)
        if s > 0:
            scored.append((s, rec))
    scored.sort(key=lambda x: (-x[0], x[1].get("name", "")))
    return [r for _, r in scored[:top_k]]


def search_theory_glossary(query: str, glossary_path: str, top_k: int = 6) -> List[Dict[str, Any]]:
    rows = load_jsonl(glossary_path)
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for rec in rows:
        s = score_glossary(query, rec)
        if s > 0:
            scored.append((s, rec))
    scored.sort(key=lambda x: (-x[0], x[1].get("term", "")))
    return [r for _, r in scored[:top_k]]


def format_semantic_hits(query: str, semantic_path: str, top_k: int = 8) -> str:
    hits = search_semantic_map(query, semantic_path, top_k)
    if not hits:
        return "No semantic-map hits found."

    lines = [f"Top semantic-map hits for query: {query}", ""]
    for i, rec in enumerate(hits, 1):
        lines.append(f"[{i}] {rec['name']}")
        lines.append(f"  kind: {rec.get('kind', '')}")
        lines.append(f"  related_concepts: {', '.join(rec.get('related_concepts', []))}")
        lines.append(f"  physics_interpretation: {rec.get('physics_interpretation', '')}")
        lines.append(f"  confidence: {rec.get('confidence', '')}")
        if rec.get("code_locations"):
            lines.append(f"  code_locations: {', '.join(rec['code_locations'][:6])}")
        if rec.get("hdf5_paths"):
            lines.append(f"  hdf5_paths: {', '.join(rec['hdf5_paths'][:6])}")
        lines.append(f"  code_evidence: {rec.get('code_evidence', '')}")
        lines.append(f"  inference_notes: {rec.get('inference_notes', '')}")
        lines.append("")
    return "\n".join(lines)


def format_glossary_hits(query: str, glossary_path: str, top_k: int = 6) -> str:
    hits = search_theory_glossary(query, glossary_path, top_k)
    if not hits:
        return "No glossary hits found."

    lines = [f"Top theory-glossary hits for query: {query}", ""]
    for i, rec in enumerate(hits, 1):
        lines.append(f"[{i}] {rec['term']}")
        lines.append(f"  definition: {rec.get('definition', '')}")
        lines.append(f"  notes: {rec.get('notes', '')}")
        lines.append("")
    return "\n".join(lines)