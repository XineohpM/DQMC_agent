"""Local SSH gateway helpers for short-lived Sherlock remote calls."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from dqmc_tools.errors import ConfigurationError, InvalidArgumentError, ScriptRegistryError, ToolUnavailableError


REMOTE_HOST_ENV = "DQMC_SHERLOCK_REMOTE_HOST"
ALLOWED_HOSTS_ENV = "DQMC_SHERLOCK_ALLOWED_HOSTS"
REMOTE_PYTHON_ENV = "DQMC_SHERLOCK_REMOTE_PYTHON"
REMOTE_CWD_ENV = "DQMC_SHERLOCK_REMOTE_CWD"
TIMEOUT_ENV = "DQMC_SHERLOCK_TIMEOUT_SECONDS"
REMOTE_ENV_JSON_ENV = "DQMC_SHERLOCK_REMOTE_ENV_JSON"

DEFAULT_REMOTE_HOST = "sherlock"
DEFAULT_REMOTE_PYTHON = ".venv/bin/python"
DEFAULT_TIMEOUT_SECONDS = 60
UNSAFE_REMOTE_COMMAND_CHARS = {"\x00", "\n", "\r", ";", "&", "|", "`", "$", "<", ">", " ", "\t"}
GATEWAY_ALLOWED_TOOLS = {
    "get_slurm_job_detail",
    "query_slurm",
    "query_slurm_history",
    "summarize_run",
}
STATUS_ONLY_TOOLS = {
    "get_slurm_job_detail",
    "query_slurm",
    "query_slurm_history",
}
PATH_FIELD_NAMES = {
    "batchscript",
    "command",
    "currentworkingdirectory",
    "currentworkdir",
    "stderr",
    "stderrpath",
    "stderrexpanded",
    "stdin",
    "stdinpath",
    "stdout",
    "stdoutpath",
    "stdoutexpanded",
    "standarderror",
    "standarderrorexpanded",
    "standardinput",
    "standardoutput",
    "standardoutputexpanded",
    "stdinput",
    "submitline",
    "workdir",
}
REMOTE_ENV_ALLOWLIST = {
    "DQMC_ALLOWED_ROOTS",
    "DQMC_OUTPUT_ROOT",
    "DQMC_REGISTRY_PATH",
    "DQMC_DEV_ROOT",
    "DQMC_SCRIPT_TIMEOUT_SECONDS",
}


@dataclass(frozen=True)
class SherlockGatewayConfig:
    remote_host: str = DEFAULT_REMOTE_HOST
    allowed_hosts: list[str] = field(default_factory=lambda: [DEFAULT_REMOTE_HOST])
    remote_python: str = DEFAULT_REMOTE_PYTHON
    remote_cwd: str = ""
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    remote_env: dict[str, str] = field(default_factory=dict)


def config_from_env() -> SherlockGatewayConfig:
    """Build a gateway config from DQMC_SHERLOCK_* environment variables."""

    remote_host = os.environ.get(REMOTE_HOST_ENV, DEFAULT_REMOTE_HOST).strip() or DEFAULT_REMOTE_HOST
    raw_allowed_hosts = os.environ.get(ALLOWED_HOSTS_ENV, "").strip()
    allowed_hosts = _split_env_list(raw_allowed_hosts) if raw_allowed_hosts else [remote_host]
    remote_python = os.environ.get(REMOTE_PYTHON_ENV, DEFAULT_REMOTE_PYTHON).strip() or DEFAULT_REMOTE_PYTHON
    remote_cwd = os.environ.get(REMOTE_CWD_ENV, "").strip()
    if not remote_cwd:
        raise ConfigurationError(
            f"`{REMOTE_CWD_ENV}` must be set to the Sherlock repo path.",
            details={"env_var": REMOTE_CWD_ENV},
        )
    timeout_seconds = _parse_timeout(os.environ.get(TIMEOUT_ENV, ""))
    remote_env = _parse_remote_env(os.environ.get(REMOTE_ENV_JSON_ENV, ""))
    return SherlockGatewayConfig(
        remote_host=remote_host,
        allowed_hosts=allowed_hosts,
        remote_python=remote_python,
        remote_cwd=remote_cwd,
        timeout_seconds=timeout_seconds,
        remote_env=remote_env,
    )


def build_ssh_command(ssh_path: str, config: SherlockGatewayConfig) -> list[str]:
    """Return the argv list for one remote_call SSH invocation."""

    _validate_config(config)
    return [
        ssh_path,
        config.remote_host,
        config.remote_python,
        "-m",
        "dqmc_tools.remote_call",
        "--cwd",
        config.remote_cwd,
    ]


def call_sherlock_tool(
    tool_name: str,
    args: dict[str, Any] | None = None,
    *,
    config: SherlockGatewayConfig | None = None,
    include_remote_env: bool = False,
    redact_paths: bool | None = None,
) -> dict[str, Any]:
    """Call one allowlisted Sherlock tool through a short SSH process."""

    config = config or config_from_env()
    _validate_tool_name(tool_name)
    _validate_config(config)
    ssh_path = shutil.which("ssh")
    if not ssh_path:
        raise ToolUnavailableError("Command `ssh` is not available.", details={"command": "ssh"})

    command = build_ssh_command(ssh_path, config)
    payload = json.dumps(
        {
            "tool": tool_name,
            "args": args or {},
            "env": _allowed_remote_env(config.remote_env) if include_remote_env else {},
        },
        sort_keys=True,
    )
    completed = _run_ssh(command, payload=payload, timeout_seconds=config.timeout_seconds)
    if completed.returncode != 0:
        raise ScriptRegistryError(
            "Sherlock remote call failed.",
            details={
                "command": command,
                "returncode": completed.returncode,
                "stdout_tail": _tail(completed.stdout),
                "stderr_tail": _tail(completed.stderr),
            },
        )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ScriptRegistryError(
            "Sherlock remote call did not return valid JSON.",
            details={
                "command": command,
                "stdout_tail": _tail(completed.stdout),
                "stderr_tail": _tail(completed.stderr),
                "lineno": exc.lineno,
                "colno": exc.colno,
            },
        ) from exc
    if not isinstance(result, dict):
        raise ScriptRegistryError(
            "Sherlock remote call JSON result must be an object.",
            details={"command": command, "result_type": type(result).__name__},
        )
    should_redact_paths = tool_name in STATUS_ONLY_TOOLS if redact_paths is None else redact_paths
    if should_redact_paths:
        result = _redact_path_fields(result)
    return {
        "ok": True,
        "remote": {
            "host": config.remote_host,
            "tool": tool_name,
        },
        "result": result,
    }


def _validate_tool_name(tool_name: str) -> None:
    if tool_name not in GATEWAY_ALLOWED_TOOLS:
        raise InvalidArgumentError(
            "Sherlock gateway tool is not allowlisted.",
            details={"tool": tool_name, "allowed_tools": sorted(GATEWAY_ALLOWED_TOOLS)},
        )


def _validate_config(config: SherlockGatewayConfig) -> None:
    host = str(config.remote_host).strip()
    allowed_hosts = [str(item).strip() for item in config.allowed_hosts if str(item).strip()]
    if _has_unsafe_remote_command_chars(host):
        raise InvalidArgumentError(
            "Sherlock remote host contains unsupported characters.",
            details={"field": "remote_host"},
        )
    if not host or host not in allowed_hosts:
        raise InvalidArgumentError(
            "Sherlock remote host is outside the allowed host list.",
            details={"remote_host": host, "allowed_hosts": allowed_hosts},
        )
    remote_python = str(config.remote_python).strip()
    if not remote_python:
        raise ConfigurationError(
            "Sherlock remote Python must be configured.",
            details={"field": "remote_python"},
        )
    if _has_unsafe_remote_command_chars(remote_python):
        raise InvalidArgumentError(
            "Sherlock remote Python contains unsupported characters.",
            details={"field": "remote_python"},
        )
    cwd = str(config.remote_cwd).strip()
    if not cwd:
        raise ConfigurationError(
            f"`{REMOTE_CWD_ENV}` must be set to the Sherlock repo path.",
            details={"env_var": REMOTE_CWD_ENV},
        )
    if _has_unsafe_remote_command_chars(cwd):
        raise InvalidArgumentError(
            "Sherlock remote cwd contains unsupported characters.",
            details={"field": "remote_cwd"},
        )
    path = PurePosixPath(cwd)
    if not path.is_absolute() or ".." in path.parts:
        raise InvalidArgumentError(
            "Sherlock remote cwd must be an absolute POSIX path without parent traversal.",
            details={"remote_cwd": cwd},
        )
    if int(config.timeout_seconds) < 1:
        raise InvalidArgumentError(
            "Sherlock gateway timeout must be at least 1 second.",
            details={"timeout_seconds": config.timeout_seconds},
        )


def _run_ssh(
    command: list[str],
    *,
    payload: str,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            input=payload,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
            shell=False,
        )
    except OSError as exc:
        raise ToolUnavailableError(
            "Command `ssh` could not be executed.",
            details={"command": command, "reason": str(exc)},
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ToolUnavailableError(
            "Sherlock remote call timed out.",
            details={"command": command, "timeout_seconds": exc.timeout},
        ) from exc


def _parse_timeout(raw_value: str) -> int:
    if not raw_value.strip():
        return DEFAULT_TIMEOUT_SECONDS
    try:
        timeout = int(raw_value)
    except ValueError as exc:
        raise ConfigurationError(
            f"`{TIMEOUT_ENV}` must be an integer.",
            details={"env_var": TIMEOUT_ENV, "value": raw_value},
        ) from exc
    if timeout < 1:
        raise InvalidArgumentError(
            "Sherlock gateway timeout must be at least 1 second.",
            details={"timeout_seconds": timeout},
        )
    return timeout


def _parse_remote_env(raw_value: str) -> dict[str, str]:
    if not raw_value.strip():
        return {}
    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ConfigurationError(
            f"`{REMOTE_ENV_JSON_ENV}` must be valid JSON.",
            details={"env_var": REMOTE_ENV_JSON_ENV, "lineno": exc.lineno, "colno": exc.colno},
        ) from exc
    if not isinstance(decoded, dict):
        raise ConfigurationError(
            f"`{REMOTE_ENV_JSON_ENV}` must be a JSON object.",
            details={"env_var": REMOTE_ENV_JSON_ENV, "type": type(decoded).__name__},
        )
    return _allowed_remote_env(decoded)


def _allowed_remote_env(env: dict[str, Any]) -> dict[str, str]:
    return {str(key): str(value) for key, value in env.items() if str(key) in REMOTE_ENV_ALLOWLIST}


def _redact_path_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _redact_path_fields(item)
            for key, item in value.items()
            if not _is_path_field_name(key)
        }
    if isinstance(value, list):
        return [_redact_path_fields(item) for item in value]
    return value


def _is_path_field_name(key: Any) -> bool:
    normalized = "".join(char for char in str(key).lower() if char.isalnum())
    return normalized in PATH_FIELD_NAMES


def _split_env_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(os.pathsep) if item.strip()]


def _has_unsafe_remote_command_chars(value: str) -> bool:
    return any(char in value for char in UNSAFE_REMOTE_COMMAND_CHARS)


def _tail(value: str, max_chars: int = 4000) -> str:
    return value[-max_chars:]
