"""Observable registry loading and resolution."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from dqmc_tools.errors import ObservableAmbiguousError, ObservableNotFoundError


DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "formal" / "observables.yaml"


def load_observable_registry(path: str | Path | None = None) -> dict[str, Any]:
    """Load the DQMC observable registry YAML.

    The default registry is `observables.yaml` in the project root.
    """

    registry_path = Path(path) if path is not None else DEFAULT_REGISTRY_PATH
    if not registry_path.exists():
        raise ObservableNotFoundError(
            "Observable registry file was not found.",
            details={"path": registry_path},
        )

    with registry_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        raise ObservableNotFoundError(
            "Observable registry must be a YAML mapping.",
            details={"path": registry_path},
        )

    return data


def list_observables(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Return registered repo-variable observables from the registry."""

    registry = load_observable_registry(path)
    repo_variables = registry.get("repo_variables", [])
    if repo_variables is None:
        return []
    if not isinstance(repo_variables, list):
        raise ObservableNotFoundError(
            "`repo_variables` in observable registry must be a list.",
            details={"path": path or DEFAULT_REGISTRY_PATH},
        )

    return [deepcopy(item) for item in repo_variables if isinstance(item, dict)]


def resolve_observable(
    name: str,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    """Resolve an observable by repo id, HDF5 path, or unambiguous tail name."""

    query = _require_nonempty_name(name)
    observables = list_observables(registry_path)

    exact_repo_id = [obs for obs in observables if obs.get("repo_id") == query]
    if exact_repo_id:
        return deepcopy(exact_repo_id[0])

    normalized_query_path = _normalize_h5_path(query)
    exact_h5_path = [
        obs for obs in observables
        if _normalize_h5_path(str(obs.get("h5_path", ""))) == normalized_query_path
    ]
    if exact_h5_path:
        return deepcopy(exact_h5_path[0])

    tail_matches = [
        obs for obs in observables
        if _matches_tail(query, obs)
    ]
    if len(tail_matches) == 1:
        return deepcopy(tail_matches[0])
    if len(tail_matches) > 1:
        raise ObservableAmbiguousError(
            "Observable name is ambiguous.",
            details={
                "name": query,
                "candidates": [_candidate_summary(obs) for obs in tail_matches],
            },
        )

    raise ObservableNotFoundError(
        "Observable was not found in the registry.",
        details={"name": query},
    )


def _require_nonempty_name(name: str) -> str:
    query = str(name).strip()
    if not query:
        raise ObservableNotFoundError(
            "Observable name must be a non-empty string.",
            details={"name": name},
        )
    return query


def _normalize_h5_path(path: str) -> str:
    stripped = path.strip()
    if not stripped:
        return ""
    return stripped if stripped.startswith("/") else f"/{stripped}"


def _matches_tail(query: str, observable: dict[str, Any]) -> bool:
    repo_id = str(observable.get("repo_id", ""))
    h5_path = str(observable.get("h5_path", ""))

    repo_tail = repo_id.split(".")[-1] if repo_id else ""
    h5_tail = h5_path.rstrip("/").split("/")[-1] if h5_path else ""

    return query in {repo_tail, h5_tail}


def _candidate_summary(observable: dict[str, Any]) -> dict[str, Any]:
    return {
        "repo_id": observable.get("repo_id"),
        "h5_path": observable.get("h5_path"),
        "kind": observable.get("kind"),
        "time_kind": observable.get("time_kind"),
        "spin": observable.get("spin"),
    }
