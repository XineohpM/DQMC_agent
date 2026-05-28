import io
import json
import os

from dqmc_tools import remote_call


def test_dispatch_remote_call_invokes_allowlisted_tool(monkeypatch):
    monkeypatch.setitem(
        remote_call.TOOL_DISPATCH,
        "query_slurm",
        lambda filters=None: {"ok": True, "filters": filters},
    )

    result = remote_call.dispatch_remote_call({
        "tool": "query_slurm",
        "args": {"filters": {"me": True}},
    })

    assert result == {"ok": True, "filters": {"me": True}}


def test_dispatch_remote_call_rejects_unknown_tool():
    result = remote_call.dispatch_remote_call({"tool": "sbatch", "args": {}})

    assert result["ok"] is False
    assert result["error_type"] == "invalid_argument"
    assert result["details"] == {
        "tool": "sbatch",
        "allowed_tools": [
            "get_slurm_job_detail",
            "query_slurm",
            "query_slurm_history",
            "summarize_run",
        ],
    }


def test_dispatch_remote_call_only_applies_allowlisted_env(monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.delenv("DQMC_ALLOWED_ROOTS", raising=False)
    monkeypatch.setitem(
        remote_call.TOOL_DISPATCH,
        "query_slurm",
        lambda filters=None: {
            "ok": True,
            "allowed_roots": os.environ.get("DQMC_ALLOWED_ROOTS"),
            "path": os.environ.get("PATH"),
        },
    )

    result = remote_call.dispatch_remote_call({
        "tool": "query_slurm",
        "args": {},
        "env": {
            "DQMC_ALLOWED_ROOTS": "/oak/user/run",
            "PATH": "/tmp/unsafe",
        },
    })

    assert result == {
        "ok": True,
        "allowed_roots": "/oak/user/run",
        "path": "/usr/bin",
    }


def test_main_prints_json_for_valid_payload(monkeypatch, tmp_path):
    monkeypatch.setitem(
        remote_call.TOOL_DISPATCH,
        "query_slurm",
        lambda filters=None: {"ok": True, "filters": filters},
    )
    stdin = io.StringIO(json.dumps({
        "tool": "query_slurm",
        "args": {"filters": {"me": True}},
    }))
    stdout = io.StringIO()

    exit_code = remote_call.main(
        ["--cwd", str(tmp_path)],
        stdin=stdin,
        stdout=stdout,
    )

    assert exit_code == 0
    assert json.loads(stdout.getvalue()) == {"ok": True, "filters": {"me": True}}


def test_main_returns_structured_error_for_invalid_json():
    stdout = io.StringIO()

    exit_code = remote_call.main([], stdin=io.StringIO("{not-json"), stdout=stdout)

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["ok"] is False
    assert payload["error_type"] == "invalid_argument"
    assert "JSON" in payload["message"]
