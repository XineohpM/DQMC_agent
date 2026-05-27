"""Whitelisted DQMC script adapters."""

from dqmc_tools.scripts.definitions import InputRequirement, ScriptDefinition
from dqmc_tools.scripts.audit import audit_script_adapters
from dqmc_tools.scripts.runner import (
    describe_script_adapter,
    list_script_adapters,
    run_script_adapter,
)
from dqmc_tools.scripts.parsers import parse_outputs

__all__ = [
    "InputRequirement",
    "ScriptDefinition",
    "DEFAULT_SCRIPT_CATALOG",
    "ARGPARSE_SYNC_RESULT",
    "EXCLUDED_FIRST_PHASE_SCRIPTS",
    "audit_script_adapters",
    "list_script_adapters",
    "describe_script_adapter",
    "run_script_adapter",
    "parse_outputs",
]


def __getattr__(name: str):
    if name in {"ARGPARSE_SYNC_RESULT", "DEFAULT_SCRIPT_CATALOG", "EXCLUDED_FIRST_PHASE_SCRIPTS"}:
        from dqmc_tools.scripts import builtin_catalog

        return getattr(builtin_catalog, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
