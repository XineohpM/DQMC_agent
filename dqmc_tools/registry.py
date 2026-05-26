"""Registry loading and resolution using the real registry.yaml schema."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

import yaml

from dqmc_tools.config import get_registry_path
from dqmc_tools.errors import RegistryAmbiguousError, RegistryError, RegistryNotFoundError


ENTRY_TYPES = {"observable", "parameter"}


def load_registry(path: str | Path | None = None) -> dict[str, Any]:
    """Load registry.yaml as a mapping."""

    registry_path = get_registry_path(path)
    if not registry_path.exists():
        raise RegistryNotFoundError(
            "Registry file was not found.",
            details={"path": registry_path},
        )
    with registry_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise RegistryError(
            "Registry must be a YAML mapping.",
            details={"path": registry_path},
        )
    return data


def list_registry_entries(
    entry_type: str | None = None,
    *,
    registry_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """List registry entries with runtime helper fields."""

    if entry_type is not None and entry_type not in ENTRY_TYPES:
        raise RegistryError(
            "Unsupported registry entry type.",
            details={"entry_type": entry_type, "supported": sorted(ENTRY_TYPES)},
        )

    registry = load_registry(registry_path)
    entries: list[dict[str, Any]] = []
    if entry_type in {None, "observable"}:
        entries.extend(_entries_from_section(registry, "observables", "observable"))
    if entry_type in {None, "parameter"}:
        entries.extend(_entries_from_section(registry, "parameters", "parameter"))
    return entries


def resolve_registry_entry(
    name: str,
    *,
    entry_type: str | None = None,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    """Resolve a registry entry by id, alias, generation variable, or tail."""

    query = _require_query(name)
    entries = list_registry_entries(entry_type=entry_type, registry_path=registry_path)

    for matcher in (
        _matches_id,
        _matches_alias,
        _matches_dataset_key,
        _matches_dataset_tail,
    ):
        matches = _dedupe_entries(entry for entry in entries if matcher(query, entry))
        if len(matches) == 1:
            return deepcopy(matches[0])
        if len(matches) > 1:
            raise RegistryAmbiguousError(
                "Registry entry query is ambiguous.",
                details={
                    "name": query,
                    "candidates": [_candidate(item) for item in matches],
                },
            )

    raise RegistryNotFoundError(
        "Registry entry was not found.",
        details={"name": query, "entry_type": entry_type},
    )


def list_observables(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Compatibility wrapper for observable entries."""

    return list_registry_entries(entry_type="observable", registry_path=path)


def resolve_observable(
    name: str,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    """Compatibility wrapper for resolving an observable only."""

    return resolve_registry_entry(name, entry_type="observable", registry_path=registry_path)


def _entries_from_section(
    registry: dict[str, Any],
    section: str,
    entry_type: str,
) -> list[dict[str, Any]]:
    raw_entries = registry.get(section, [])
    if raw_entries is None:
        return []
    if not isinstance(raw_entries, list):
        raise RegistryError(
            "Registry section must be a list.",
            details={"section": section, "type": type(raw_entries).__name__},
        )
    entries = []
    for idx, item in enumerate(raw_entries):
        if not isinstance(item, dict):
            raise RegistryError(
                "Registry entry must be a mapping.",
                details={"section": section, "index": idx, "type": type(item).__name__},
            )
        entries.append(_with_runtime_fields(item, entry_type))
    return entries


def _with_runtime_fields(entry: dict[str, Any], entry_type: str) -> dict[str, Any]:
    out = deepcopy(entry)
    out["entry_type"] = entry_type
    out["dataset_key"] = _generation_variable(entry)
    out["source_entry"] = deepcopy(entry)
    return out


def _generation_variable(entry: dict[str, Any]) -> str:
    code = entry.get("code")
    if not isinstance(code, dict):
        return ""
    generation = code.get("generation")
    if not isinstance(generation, dict):
        return ""
    value = generation.get("variable", "")
    return str(value).strip()


def _require_query(name: str) -> str:
    query = str(name).strip()
    if not query:
        raise RegistryNotFoundError(
            "Registry query must be a non-empty string.",
            details={"name": name},
        )
    return query


def _matches_id(query: str, entry: dict[str, Any]) -> bool:
    return str(entry.get("id", "")).strip() == query


def _matches_alias(query: str, entry: dict[str, Any]) -> bool:
    aliases = entry.get("aliases", [])
    if isinstance(aliases, str):
        aliases = [aliases]
    if not isinstance(aliases, Iterable):
        return False
    return query in {str(item).strip() for item in aliases}


def _matches_dataset_key(query: str, entry: dict[str, Any]) -> bool:
    return str(entry.get("dataset_key", "")).strip() == query.strip("/")


def _matches_dataset_tail(query: str, entry: dict[str, Any]) -> bool:
    dataset_key = str(entry.get("dataset_key", "")).strip("/")
    tail = dataset_key.rsplit("/", maxsplit=1)[-1] if dataset_key else ""
    return tail == query


def _dedupe_entries(entries: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for entry in entries:
        key = (
            str(entry.get("entry_type", "")),
            str(entry.get("id", "")),
            str(entry.get("dataset_key", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(entry)
    return out


def _candidate(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "entry_type": entry.get("entry_type"),
        "id": entry.get("id"),
        "aliases": entry.get("aliases", []),
        "dataset_key": entry.get("dataset_key"),
    }
