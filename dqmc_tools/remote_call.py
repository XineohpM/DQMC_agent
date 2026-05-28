"""Short-lived remote JSON entrypoint for Sherlock gateway calls."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, TextIO

from dqmc_tools.errors import InvalidArgumentError, error_dict
from dqmc_tools.runs import summarize_run
from dqmc_tools.slurm import get_slurm_job_detail, query_slurm, query_slurm_history


ALLOWED_ENV_VARS = {
    "DQMC_ALLOWED_ROOTS",
    "DQMC_OUTPUT_ROOT",
    "DQMC_REGISTRY_PATH",
    "DQMC_DEV_ROOT",
    "DQMC_SCRIPT_TIMEOUT_SECONDS",
}

TOOL_DISPATCH: dict[str, Callable[..., dict[str, Any]]] = {
    "get_slurm_job_detail": get_slurm_job_detail,
    "query_slurm": query_slurm,
    "query_slurm_history": query_slurm_history,
    "summarize_run": summarize_run,
}


def dispatch_remote_call(payload: dict[str, Any]) -> dict[str, Any]:
    """Dispatch one allowlisted remote tool call from a JSON payload."""

    try:
        if not isinstance(payload, dict):
            raise InvalidArgumentError(
                "Remote call payload must be a JSON object.",
                details={"payload_type": type(payload).__name__},
            )
        tool_name = str(payload.get("tool") or "").strip()
        if tool_name not in TOOL_DISPATCH:
            raise InvalidArgumentError(
                "Remote tool is not allowlisted.",
                details={"tool": tool_name, "allowed_tools": sorted(TOOL_DISPATCH)},
            )
        args = payload.get("args") or {}
        if not isinstance(args, dict):
            raise InvalidArgumentError(
                "Remote tool args must be a JSON object.",
                details={"tool": tool_name, "args_type": type(args).__name__},
            )
        env = payload.get("env") or {}
        if not isinstance(env, dict):
            raise InvalidArgumentError(
                "Remote environment must be a JSON object.",
                details={"env_type": type(env).__name__},
            )
        with _temporary_allowed_env(env):
            return TOOL_DISPATCH[tool_name](**args)
    except Exception as exc:
        return error_dict(exc)


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> int:
    """Run one remote call from stdin JSON and print one JSON object."""

    parser = argparse.ArgumentParser(description="Run one allowlisted DQMC remote tool call.")
    parser.add_argument("--cwd", default=None, help="Optional working directory before dispatch.")
    parsed = parser.parse_args(argv)
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout

    try:
        if parsed.cwd:
            os.chdir(Path(parsed.cwd).expanduser())
        raw = stdin.read()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InvalidArgumentError(
                "Remote call stdin must be valid JSON.",
                details={"lineno": exc.lineno, "colno": exc.colno},
            ) from exc
        result = dispatch_remote_call(payload)
    except Exception as exc:
        result = error_dict(exc)

    stdout.write(json.dumps(result, sort_keys=True))
    stdout.write("\n")
    stdout.flush()
    return 0


class _temporary_allowed_env:
    def __init__(self, env: dict[str, Any]) -> None:
        self._env = {str(key): str(value) for key, value in env.items() if str(key) in ALLOWED_ENV_VARS}
        self._previous: dict[str, str | None] = {}

    def __enter__(self) -> None:
        for key, value in self._env.items():
            self._previous[key] = os.environ.get(key)
            os.environ[key] = value

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        for key, value in self._previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    raise SystemExit(main())
