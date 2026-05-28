import json
import subprocess

import pytest

from dqmc_tools.errors import ConfigurationError, InvalidArgumentError, ScriptRegistryError, ToolUnavailableError
from dqmc_tools.remote_gateway import (
    SherlockGatewayConfig,
    build_ssh_command,
    call_sherlock_tool,
    config_from_env,
)


def test_config_from_env_reads_gateway_settings(monkeypatch):
    monkeypatch.setenv("DQMC_SHERLOCK_REMOTE_HOST", "sherlock")
    monkeypatch.setenv("DQMC_SHERLOCK_ALLOWED_HOSTS", "sherlock:login.sherlock")
    monkeypatch.setenv("DQMC_SHERLOCK_REMOTE_PYTHON", ".venv/bin/python")
    monkeypatch.setenv("DQMC_SHERLOCK_REMOTE_CWD", "/home/user/DQMC_agent")
    monkeypatch.setenv("DQMC_SHERLOCK_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv(
        "DQMC_SHERLOCK_REMOTE_ENV_JSON",
        '{"DQMC_ALLOWED_ROOTS":"/oak/user/run","DQMC_DEV_ROOT":"/home/user/dqmc-dev"}',
    )

    config = config_from_env()

    assert config == SherlockGatewayConfig(
        remote_host="sherlock",
        allowed_hosts=["sherlock", "login.sherlock"],
        remote_python=".venv/bin/python",
        remote_cwd="/home/user/DQMC_agent",
        timeout_seconds=45,
        remote_env={
            "DQMC_ALLOWED_ROOTS": "/oak/user/run",
            "DQMC_DEV_ROOT": "/home/user/dqmc-dev",
        },
    )


def test_config_from_env_requires_remote_cwd(monkeypatch):
    monkeypatch.delenv("DQMC_SHERLOCK_REMOTE_CWD", raising=False)

    with pytest.raises(ConfigurationError) as exc_info:
        config_from_env()

    assert exc_info.value.details == {"env_var": "DQMC_SHERLOCK_REMOTE_CWD"}


def test_build_ssh_command_uses_argv_list():
    config = SherlockGatewayConfig(
        remote_host="sherlock",
        allowed_hosts=["sherlock"],
        remote_python=".venv/bin/python",
        remote_cwd="/home/user/DQMC_agent",
    )

    command = build_ssh_command("/usr/bin/ssh", config)

    assert command == [
        "/usr/bin/ssh",
        "sherlock",
        ".venv/bin/python",
        "-m",
        "dqmc_tools.remote_call",
        "--cwd",
        "/home/user/DQMC_agent",
    ]


def test_call_sherlock_tool_sends_json_stdin_and_wraps_result(monkeypatch):
    monkeypatch.setattr("dqmc_tools.remote_gateway.shutil.which", lambda _name: "/usr/bin/ssh")
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout='{"ok": true, "source": "squeue_json"}',
            stderr="",
        )

    monkeypatch.setattr("dqmc_tools.remote_gateway.subprocess.run", fake_run)
    config = SherlockGatewayConfig(
        remote_host="sherlock",
        allowed_hosts=["sherlock"],
        remote_python=".venv/bin/python",
        remote_cwd="/home/user/DQMC_agent",
        timeout_seconds=60,
        remote_env={"DQMC_ALLOWED_ROOTS": "/oak/user/run"},
    )

    result = call_sherlock_tool("query_slurm", {"filters": {"me": True}}, config=config)

    assert result == {
        "ok": True,
        "remote": {
            "host": "sherlock",
            "tool": "query_slurm",
        },
        "result": {"ok": True, "source": "squeue_json"},
    }
    assert captured["args"] == [
        "/usr/bin/ssh",
        "sherlock",
        ".venv/bin/python",
        "-m",
        "dqmc_tools.remote_call",
        "--cwd",
        "/home/user/DQMC_agent",
    ]
    sent = json.loads(captured["kwargs"]["input"])
    assert sent == {
        "tool": "query_slurm",
        "args": {"filters": {"me": True}},
        "env": {},
    }
    assert captured["kwargs"]["timeout"] == 60
    assert captured["kwargs"]["shell"] is False


def test_call_sherlock_tool_can_send_remote_env_for_nondefault_profile(monkeypatch):
    monkeypatch.setattr("dqmc_tools.remote_gateway.shutil.which", lambda _name: "/usr/bin/ssh")
    captured = {}

    def fake_run(args, **kwargs):
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout='{"ok": true, "path": "/oak/user/run"}',
            stderr="",
        )

    monkeypatch.setattr("dqmc_tools.remote_gateway.subprocess.run", fake_run)
    config = SherlockGatewayConfig(
        remote_host="sherlock",
        allowed_hosts=["sherlock"],
        remote_python=".venv/bin/python",
        remote_cwd="/home/user/DQMC_agent",
        remote_env={"DQMC_ALLOWED_ROOTS": "/oak/user/run"},
    )

    result = call_sherlock_tool(
        "summarize_run",
        {"path": "/oak/user/run"},
        config=config,
        include_remote_env=True,
        redact_paths=False,
    )

    sent = json.loads(captured["kwargs"]["input"])
    assert sent["env"] == {"DQMC_ALLOWED_ROOTS": "/oak/user/run"}
    assert result["remote"] == {"host": "sherlock", "tool": "summarize_run"}
    assert result["result"]["path"] == "/oak/user/run"


def test_call_sherlock_tool_redacts_status_paths(monkeypatch):
    monkeypatch.setattr("dqmc_tools.remote_gateway.shutil.which", lambda _name: "/usr/bin/ssh")

    def fake_run(args, **_kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps({
                "ok": True,
                "command": ["/usr/bin/sacct", "--jobs", "123"],
                "jobs": [
                    {
                        "job_id": "123",
                        "work_dir": "/scratch/user/run",
                        "standard_output": "/scratch/user/run/slurm.out",
                        "standard_input": "/scratch/user/run/slurm.in",
                        "current_working_directory": "/scratch/user/run",
                        "submit_line": "sbatch /scratch/user/run/job.slurm",
                        "raw": {
                            "WorkDir": "/scratch/user/run",
                            "standard_error": "/scratch/user/run/slurm.err",
                            "stderr_expanded": "/scratch/user/run/slurm-expanded.err",
                            "std_out": "/scratch/user/run/slurm.out",
                            "std_err": "/scratch/user/run/slurm.err",
                            "stdout_expanded": "/scratch/user/run/slurm-expanded.out",
                            "state": "COMPLETED",
                        },
                    }
                ],
                "candidates": [
                    {
                        "job_id": "123",
                        "stdout_path": "/scratch/user/run/slurm.out",
                        "stdout_expanded": "/scratch/user/run/slurm-expanded.out",
                        "stderr_path": "/scratch/user/run/slurm.err",
                        "stderr_expanded": "/scratch/user/run/slurm-expanded.err",
                    }
                ],
            }),
            stderr="",
        )

    monkeypatch.setattr("dqmc_tools.remote_gateway.subprocess.run", fake_run)
    config = SherlockGatewayConfig(
        remote_host="sherlock",
        allowed_hosts=["sherlock"],
        remote_python=".venv/bin/python",
        remote_cwd="/home/user/DQMC_agent",
    )

    result = call_sherlock_tool("get_slurm_job_detail", {"job_id": "123"}, config=config)

    assert result["remote"] == {"host": "sherlock", "tool": "get_slurm_job_detail"}
    assert result["result"] == {
        "ok": True,
        "jobs": [{"job_id": "123", "raw": {"state": "COMPLETED"}}],
        "candidates": [{"job_id": "123"}],
    }


def test_call_sherlock_tool_rejects_host_outside_allowlist(monkeypatch):
    monkeypatch.setattr("dqmc_tools.remote_gateway.shutil.which", lambda _name: "/usr/bin/ssh")
    config = SherlockGatewayConfig(
        remote_host="other",
        allowed_hosts=["sherlock"],
        remote_python=".venv/bin/python",
        remote_cwd="/home/user/DQMC_agent",
    )

    with pytest.raises(InvalidArgumentError) as exc_info:
        call_sherlock_tool("query_slurm", {}, config=config)

    assert exc_info.value.details == {
        "remote_host": "other",
        "allowed_hosts": ["sherlock"],
    }


def test_call_sherlock_tool_rejects_unsafe_remote_command_parts(monkeypatch):
    monkeypatch.setattr("dqmc_tools.remote_gateway.shutil.which", lambda _name: "/usr/bin/ssh")
    config = SherlockGatewayConfig(
        remote_host="sherlock",
        allowed_hosts=["sherlock"],
        remote_python=".venv/bin/python",
        remote_cwd="/home/user/DQMC_agent; rm -rf /scratch",
    )

    with pytest.raises(InvalidArgumentError) as exc_info:
        call_sherlock_tool("query_slurm", {}, config=config)

    assert exc_info.value.details == {"field": "remote_cwd"}


def test_call_sherlock_tool_reports_ssh_unavailable(monkeypatch):
    monkeypatch.setattr("dqmc_tools.remote_gateway.shutil.which", lambda _name: None)
    config = SherlockGatewayConfig(
        remote_host="sherlock",
        allowed_hosts=["sherlock"],
        remote_python=".venv/bin/python",
        remote_cwd="/home/user/DQMC_agent",
    )

    with pytest.raises(ToolUnavailableError) as exc_info:
        call_sherlock_tool("query_slurm", {}, config=config)

    assert exc_info.value.details == {"command": "ssh"}


def test_call_sherlock_tool_reports_timeout(monkeypatch):
    monkeypatch.setattr("dqmc_tools.remote_gateway.shutil.which", lambda _name: "/usr/bin/ssh")

    def fake_run(args, **_kwargs):
        raise subprocess.TimeoutExpired(args, timeout=60)

    monkeypatch.setattr("dqmc_tools.remote_gateway.subprocess.run", fake_run)
    config = SherlockGatewayConfig(
        remote_host="sherlock",
        allowed_hosts=["sherlock"],
        remote_python=".venv/bin/python",
        remote_cwd="/home/user/DQMC_agent",
    )

    with pytest.raises(ToolUnavailableError) as exc_info:
        call_sherlock_tool("query_slurm", {}, config=config)

    assert exc_info.value.details["timeout_seconds"] == 60


def test_call_sherlock_tool_reports_nonzero_exit(monkeypatch):
    monkeypatch.setattr("dqmc_tools.remote_gateway.shutil.which", lambda _name: "/usr/bin/ssh")

    def fake_run(args, **_kwargs):
        return subprocess.CompletedProcess(args=args, returncode=2, stdout="", stderr="remote failure")

    monkeypatch.setattr("dqmc_tools.remote_gateway.subprocess.run", fake_run)
    config = SherlockGatewayConfig(
        remote_host="sherlock",
        allowed_hosts=["sherlock"],
        remote_python=".venv/bin/python",
        remote_cwd="/home/user/DQMC_agent",
    )

    with pytest.raises(ScriptRegistryError) as exc_info:
        call_sherlock_tool("query_slurm", {}, config=config)

    assert exc_info.value.details["returncode"] == 2
    assert exc_info.value.details["stderr_tail"] == "remote failure"


def test_call_sherlock_tool_reports_invalid_json_stdout(monkeypatch):
    monkeypatch.setattr("dqmc_tools.remote_gateway.shutil.which", lambda _name: "/usr/bin/ssh")

    def fake_run(args, **_kwargs):
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="banner\n{}", stderr="")

    monkeypatch.setattr("dqmc_tools.remote_gateway.subprocess.run", fake_run)
    config = SherlockGatewayConfig(
        remote_host="sherlock",
        allowed_hosts=["sherlock"],
        remote_python=".venv/bin/python",
        remote_cwd="/home/user/DQMC_agent",
    )

    with pytest.raises(ScriptRegistryError) as exc_info:
        call_sherlock_tool("query_slurm", {}, config=config)

    assert exc_info.value.details["stdout_tail"] == "banner\n{}"
