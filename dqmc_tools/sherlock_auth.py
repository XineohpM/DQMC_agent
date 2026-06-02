"""Local Sherlock SSH authentication preflight and keepalive helpers."""

from __future__ import annotations

import argparse
import getpass
import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Callable


REMOTE_HOST_ENV = "DQMC_SHERLOCK_REMOTE_HOST"
ALLOWED_HOSTS_ENV = "DQMC_SHERLOCK_ALLOWED_HOSTS"
PREFLIGHT_ENV = "DQMC_SHERLOCK_PREFLIGHT"
PREFLIGHT_TIMEOUT_ENV = "DQMC_SHERLOCK_PREFLIGHT_TIMEOUT_SECONDS"
KEEPALIVE_SECONDS_ENV = "DQMC_SHERLOCK_KEEPALIVE_SECONDS"
KRB5_CONFIG_ENV = "DQMC_SHERLOCK_KRB5_CONFIG"
SUNETID_ENV = "DQMC_SHERLOCK_SUNETID"

DEFAULT_REMOTE_HOST = "sherlock"
DEFAULT_PREFLIGHT_TIMEOUT_SECONDS = 8
DEFAULT_KEEPALIVE_SECONDS = 1800
DEFAULT_KRB5_CONFIG_PATH = "/etc/krb5.conf"
UNSAFE_SSH_ARG_CHARS = {"\x00", "\n", "\r", ";", "&", "|", "`", "$", "<", ">", " ", "\t"}


@dataclass(frozen=True)
class KeepaliveHandle:
    thread: threading.Thread
    stop_event: threading.Event

    def stop(self) -> None:
        self.stop_event.set()


def classify_ssh_auth_failure(stderr: str) -> str:
    lower = stderr.lower()
    if "permission denied" in lower and "gssapi-with-mic,password" in lower:
        return "auth_required"
    if "could not resolve hostname" in lower or "nodename nor servname provided" in lower:
        return "host_unavailable"
    if "connection timed out" in lower or "operation timed out" in lower:
        return "timeout"
    return "ssh_failed"


def run_preflight(
    *,
    remote_host: str | None = None,
    allowed_hosts: list[str] | None = None,
    timeout_seconds: int = DEFAULT_PREFLIGHT_TIMEOUT_SECONDS,
    krb5_config_path: str = DEFAULT_KRB5_CONFIG_PATH,
) -> dict:
    host = (remote_host or os.environ.get(REMOTE_HOST_ENV) or DEFAULT_REMOTE_HOST).strip()
    allowed = allowed_hosts or _allowed_hosts_from_env(host)
    sunetid = os.environ.get(SUNETID_ENV, "").strip() or getpass.getuser()
    details = {"host": host, "krb5_config_path": krb5_config_path}

    if not _is_safe_ssh_arg(host) or host not in allowed:
        return _failure(
            "invalid_host",
            "Sherlock SSH host is invalid or outside the allowed host list.",
            {**details, "allowed_hosts": allowed},
        )
    if timeout_seconds < 1:
        return _failure(
            "invalid_timeout",
            "Sherlock SSH preflight timeout must be at least 1 second.",
            {**details, "timeout_seconds": timeout_seconds},
        )
    if not os.access(krb5_config_path, os.R_OK):
        return _failure(
            "krb5_config_missing",
            "Stanford Kerberos config is not readable.",
            {**details, "recovery": _full_recovery_commands(sunetid, host)},
        )

    ssh_path = shutil.which("ssh")
    if not ssh_path:
        return _failure("ssh_unavailable", "Command `ssh` is not available.", details)

    command = [
        ssh_path,
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={timeout_seconds}",
        host,
        "true",
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds + 2,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return _failure(
            "timeout",
            "Sherlock SSH preflight timed out.",
            {**details, "timeout_seconds": timeout_seconds},
        )
    except OSError as exc:
        return _failure(
            "ssh_unavailable",
            "Command `ssh` could not be executed.",
            {**details, "reason": str(exc)},
        )

    if completed.returncode == 0:
        return {
            "ok": True,
            "status": "ok",
            "message": "Sherlock SSH preflight succeeded.",
            "details": details,
        }

    status = classify_ssh_auth_failure(completed.stderr)
    recovery = _interactive_recovery_commands(sunetid, host) if status == "auth_required" else []
    return _failure(
        status,
        "Sherlock SSH preflight failed.",
        {
            **details,
            "returncode": completed.returncode,
            "stderr_tail": _tail(completed.stderr),
            "recovery": recovery,
        },
    )


def start_keepalive(
    *,
    remote_host: str | None = None,
    allowed_hosts: list[str] | None = None,
    interval_seconds: float = DEFAULT_KEEPALIVE_SECONDS,
    timeout_seconds: int = DEFAULT_PREFLIGHT_TIMEOUT_SECONDS,
    krb5_config_path: str = DEFAULT_KRB5_CONFIG_PATH,
    logger: Callable[[str], None] | None = None,
) -> KeepaliveHandle | None:
    if interval_seconds <= 0:
        return None

    stop_event = threading.Event()
    log = logger or _default_logger

    def loop() -> None:
        while not stop_event.wait(interval_seconds):
            result = run_preflight(
                remote_host=remote_host,
                allowed_hosts=allowed_hosts,
                timeout_seconds=timeout_seconds,
                krb5_config_path=krb5_config_path,
            )
            if not result["ok"]:
                log(_format_result(result))

    thread = threading.Thread(target=loop, name="sherlock-ssh-keepalive", daemon=True)
    thread.start()
    return KeepaliveHandle(thread=thread, stop_event=stop_event)


def start_monitor_from_env(logger: Callable[[str], None] | None = None) -> KeepaliveHandle | None:
    log = logger or _default_logger
    host = os.environ.get(REMOTE_HOST_ENV, DEFAULT_REMOTE_HOST).strip() or DEFAULT_REMOTE_HOST
    allowed_hosts = _allowed_hosts_from_env(host)
    timeout_seconds = _parse_positive_int(
        os.environ.get(PREFLIGHT_TIMEOUT_ENV, ""),
        DEFAULT_PREFLIGHT_TIMEOUT_SECONDS,
    )
    krb5_config_path = os.environ.get(KRB5_CONFIG_ENV, DEFAULT_KRB5_CONFIG_PATH).strip()
    preflight_mode = os.environ.get(PREFLIGHT_ENV, "warn").strip().lower() or "warn"
    keepalive_seconds = _parse_nonnegative_float(
        os.environ.get(KEEPALIVE_SECONDS_ENV, ""),
        DEFAULT_KEEPALIVE_SECONDS,
    )

    if preflight_mode not in {"off", "warn", "require"}:
        log(f"Unsupported {PREFLIGHT_ENV} value {preflight_mode!r}; using warn.")
        preflight_mode = "warn"

    if preflight_mode != "off":
        result = run_preflight(
            remote_host=host,
            allowed_hosts=allowed_hosts,
            timeout_seconds=timeout_seconds,
            krb5_config_path=krb5_config_path,
        )
        if not result["ok"]:
            log(_format_result(result))
            if preflight_mode == "require":
                raise SystemExit(1)

    return start_keepalive(
        remote_host=host,
        allowed_hosts=allowed_hosts,
        interval_seconds=keepalive_seconds,
        timeout_seconds=timeout_seconds,
        krb5_config_path=krb5_config_path,
        logger=log,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check non-interactive Sherlock SSH authentication.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--host", default=os.environ.get(REMOTE_HOST_ENV, DEFAULT_REMOTE_HOST))
    preflight.add_argument("--timeout-seconds", type=int, default=DEFAULT_PREFLIGHT_TIMEOUT_SECONDS)
    preflight.add_argument("--krb5-config", default=os.environ.get(KRB5_CONFIG_ENV, DEFAULT_KRB5_CONFIG_PATH))
    args = parser.parse_args(argv)

    if args.command == "preflight":
        result = run_preflight(
            remote_host=args.host,
            allowed_hosts=_allowed_hosts_from_env(args.host),
            timeout_seconds=args.timeout_seconds,
            krb5_config_path=args.krb5_config,
        )
        print(_format_result(result), file=sys.stderr)
        return 0 if result["ok"] else 1
    return 2


def _failure(status: str, message: str, details: dict) -> dict:
    return {"ok": False, "status": status, "message": message, "details": details}


def _allowed_hosts_from_env(default_host: str) -> list[str]:
    raw = os.environ.get(ALLOWED_HOSTS_ENV, "").strip()
    if not raw:
        return [default_host]
    return [item.strip() for item in raw.replace(",", ":").split(":") if item.strip()]


def _is_safe_ssh_arg(value: str) -> bool:
    return bool(value) and not any(char in value for char in UNSAFE_SSH_ARG_CHARS)


def _full_recovery_commands(sunetid: str, host: str) -> list[str]:
    return [
        "sudo curl -o /etc/krb5.conf https://web.stanford.edu/dept/its/support/kerberos/dist/krb5.conf",
        f"kinit {sunetid}@stanford.edu",
        f"ssh {host} hostname",
    ]


def _interactive_recovery_commands(sunetid: str, host: str) -> list[str]:
    return [f"kinit {sunetid}@stanford.edu", f"ssh {host} hostname"]


def _tail(value: str, limit: int = 2000) -> str:
    return value[-limit:]


def _format_result(result: dict) -> str:
    lines = [f"{result['status']}: {result['message']}"]
    recovery = result.get("details", {}).get("recovery", [])
    if recovery:
        lines.append("Recovery:")
        lines.extend(f"  {command}" for command in recovery)
    return "\n".join(lines)


def _default_logger(message: str) -> None:
    print(f"dqmc-sherlock-gateway: {message}", file=sys.stderr)


def _parse_positive_int(raw_value: str, default: int) -> int:
    if not raw_value.strip():
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return value if value >= 1 else default


def _parse_nonnegative_float(raw_value: str, default: float) -> float:
    if not raw_value.strip():
        return default
    try:
        value = float(raw_value)
    except ValueError:
        return default
    return value if value >= 0 else default


if __name__ == "__main__":
    raise SystemExit(main())
