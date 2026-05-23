"""Whitelisted analysis registry for DQMC tools."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from dqmc_tools.errors import AnalysisRegistryError
from dqmc_tools.paths import require_allowed_path, require_output_path


AnalysisHandler = Callable[[Path, Mapping[str, Any], Path], dict[str, Any]]


@dataclass(frozen=True)
class AnalysisDefinition:
    """Metadata and callable for one whitelisted analysis."""

    analysis_id: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    handler: AnalysisHandler


DEFAULT_ANALYSES: tuple[AnalysisDefinition, ...] = ()


def list_analyses(
    registry: Iterable[AnalysisDefinition] | None = None,
) -> list[dict[str, Any]]:
    """List whitelisted analyses without exposing handler callables."""

    entries = _registry_map(registry)
    return [
        {
            "analysis_id": item.analysis_id,
            "description": item.description,
            "input_schema": item.input_schema,
            "output_schema": item.output_schema,
        }
        for item in entries.values()
    ]


def run_analysis(
    name: str,
    run_path: str | Path,
    params: dict[str, Any] | None = None,
    *,
    registry: Iterable[AnalysisDefinition] | None = None,
    output_root: str | Path | None = None,
    allowed_roots: Iterable[str | Path] | str | Path | None = None,
) -> dict[str, Any]:
    """Run one registered analysis against an allowed run directory."""

    entries = _registry_map(registry)
    analysis_id = _require_analysis_id(name, where="run_analysis.name")
    if analysis_id not in entries:
        raise AnalysisRegistryError(
            "Analysis is not registered in the whitelist.",
            details={
                "analysis_id": analysis_id,
                "registered_analyses": sorted(entries),
            },
        )

    resolved_run_path = require_allowed_path(run_path, allowed_roots)
    if not resolved_run_path.is_dir():
        raise AnalysisRegistryError(
            "Analysis run_path must be a directory.",
            details={"run_path": resolved_run_path},
        )

    output_dir = require_output_path(
        Path(resolved_run_path.name) / analysis_id,
        output_root,
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    analysis = entries[analysis_id]
    result = analysis.handler(resolved_run_path, params or {}, output_dir)
    if not isinstance(result, dict):
        raise AnalysisRegistryError(
            "Analysis handler must return a dictionary.",
            details={"analysis_id": analysis_id, "returned_type": type(result).__name__},
        )

    return {
        "ok": True,
        "analysis_id": analysis_id,
        "run_path": str(resolved_run_path),
        "output_dir": str(output_dir),
        "result": result,
    }


def _registry_map(
    registry: Iterable[AnalysisDefinition] | None,
) -> dict[str, AnalysisDefinition]:
    entries = DEFAULT_ANALYSES if registry is None else tuple(registry)
    out: dict[str, AnalysisDefinition] = {}
    for idx, item in enumerate(entries):
        where = f"analysis_registry[{idx}]"
        _validate_definition(item, where)
        if item.analysis_id in out:
            raise AnalysisRegistryError(
                "Duplicate analysis id in registry.",
                details={"analysis_id": item.analysis_id, "where": where},
            )
        out[item.analysis_id] = item
    return out


def _validate_definition(item: AnalysisDefinition, where: str) -> None:
    if not isinstance(item, AnalysisDefinition):
        raise AnalysisRegistryError(
            "Analysis registry entries must be AnalysisDefinition instances.",
            details={"where": where, "type": type(item).__name__},
        )
    _require_analysis_id(item.analysis_id, where=f"{where}.analysis_id")
    _require_nonempty_str(item.description, where=f"{where}.description")
    if not isinstance(item.input_schema, dict):
        raise AnalysisRegistryError(
            "Analysis input_schema must be a dictionary.",
            details={"where": where, "type": type(item.input_schema).__name__},
        )
    if not isinstance(item.output_schema, dict):
        raise AnalysisRegistryError(
            "Analysis output_schema must be a dictionary.",
            details={"where": where, "type": type(item.output_schema).__name__},
        )
    if not callable(item.handler):
        raise AnalysisRegistryError(
            "Analysis handler must be callable.",
            details={"where": where},
        )


def _require_nonempty_str(value: Any, *, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AnalysisRegistryError(
            "Expected a non-empty string.",
            details={"where": where, "value": value},
        )
    return value.strip()


def _require_analysis_id(value: Any, *, where: str) -> str:
    analysis_id = _require_nonempty_str(value, where=where)
    forbidden = {"/", "\\", ".."}
    if any(part in analysis_id for part in forbidden):
        raise AnalysisRegistryError(
            "Analysis id must be a registry key, not a filesystem path.",
            details={"where": where, "analysis_id": analysis_id},
        )
    return analysis_id
