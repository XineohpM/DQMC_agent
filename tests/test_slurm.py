import subprocess

import pytest

from dqmc_tools.errors import InvalidArgumentError, ToolUnavailableError
from dqmc_tools.slurm import query_slurm


def test_query_slurm_unavailable(monkeypatch):
    monkeypatch.setattr("dqmc_tools.slurm.shutil.which", lambda _name: None)

    with pytest.raises(ToolUnavailableError):
        query_slurm()


def test_query_slurm_rejects_unknown_filter(monkeypatch):
    monkeypatch.setattr("dqmc_tools.slurm.shutil.which", lambda _name: "squeue")

    with pytest.raises(InvalidArgumentError):
        query_slurm({"account": "abc"})


def test_query_slurm_uses_json_output(monkeypatch):
    monkeypatch.setattr("dqmc_tools.slurm.shutil.which", lambda _name: "squeue")

    def fake_run(args, **_kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout='{"jobs": [{"job_id": 123, "name": "dqmc"}]}',
            stderr="",
        )

    monkeypatch.setattr("dqmc_tools.slurm.subprocess.run", fake_run)

    result = query_slurm({"user": "phoenix"})

    assert result["source"] == "squeue_json"
    assert result["jobs"] == [{"job_id": 123, "name": "dqmc"}]
    assert "--user" in result["command"]


def test_query_slurm_falls_back_to_delimited_output(monkeypatch):
    monkeypatch.setattr("dqmc_tools.slurm.shutil.which", lambda _name: "squeue")

    def fake_run(args, **_kwargs):
        if "--json" in args:
            return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="no json")
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="123|dqmc|phoenix|RUNNING|1:00|2:00|normal|node001\n",
            stderr="",
        )

    monkeypatch.setattr("dqmc_tools.slurm.subprocess.run", fake_run)

    result = query_slurm({"state": "RUNNING"})

    assert result["source"] == "squeue_fallback"
    assert result["jobs"] == [{
        "job_id": "123",
        "name": "dqmc",
        "user": "phoenix",
        "state": "RUNNING",
        "time_used": "1:00",
        "time_limit": "2:00",
        "partition": "normal",
        "nodes": "node001",
    }]
