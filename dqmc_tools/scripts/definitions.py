"""Script adapter definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping


ArgvBuilder = Callable[["ScriptDefinition", Mapping[str, Any]], list[str]]


@dataclass(frozen=True)
class InputRequirement:
    """A required input checked before script execution."""

    name: str
    kind: str
    path_template: str
    required: bool = True
    shape_hint: tuple[int | None, ...] | None = None


@dataclass(frozen=True)
class ScriptDefinition:
    """Metadata and execution contract for one whitelisted script."""

    script_id: str
    description: str
    category: str
    mode: str
    path: Path
    args_schema: dict[str, Any] = field(default_factory=dict)
    default_timeout_seconds: int = 300
    parser_id: str | None = None
    output_patterns: tuple[str, ...] = ()
    required_inputs: tuple[InputRequirement, ...] = ()
    requires_output_root: bool = False
    approval_required: bool = True
    notes: tuple[str, ...] = ()
    argv_builder: ArgvBuilder | None = None
