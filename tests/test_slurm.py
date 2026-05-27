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


def test_query_slurm_supports_me_filter_and_groups_json_jobs(monkeypatch):
    monkeypatch.setattr("dqmc_tools.slurm.shutil.which", lambda _name: "squeue")

    def fake_run(args, **_kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=json_jobs([
                {
                    "job_id": "100_0",
                    "name": "scan_T",
                    "job_state": "RUNNING",
                    "array_job_id": 100,
                    "array_task_id": 0,
                    "reason": "None",
                },
                {
                    "job_id": "100_1",
                    "name": "scan_T",
                    "job_state": "PENDING",
                    "array_job_id": 100,
                    "array_task_id": 1,
                    "state_reason": "Priority",
                },
                {
                    "job_id": "101_0",
                    "name": "scan_T",
                    "job_state": "RUNNING",
                    "array_job_id": 101,
                    "array_task_id": 0,
                    "reason": "None",
                },
                {
                    "job_id": "200",
                    "name": "postprocess",
                    "job_state": "RUNNING",
                    "reason": "None",
                },
            ]),
            stderr="",
        )

    monkeypatch.setattr("dqmc_tools.slurm.subprocess.run", fake_run)

    result = query_slurm({"me": True})

    assert "--me" in result["command"]
    assert result["summary"] == {
        "total_jobs": 4,
        "state_counts": {"PENDING": 1, "RUNNING": 3},
        "category_counts": {"pending": 1, "running": 3},
        "job_name_count": 2,
        "array_job_count": 3,
    }

    scan_group = _group_by_name(result, "scan_T")
    assert scan_group["total_jobs"] == 3
    assert scan_group["state_counts"] == {"PENDING": 1, "RUNNING": 2}
    assert scan_group["category_counts"] == {"pending": 1, "running": 2}

    array_100 = _array_group(scan_group, "100")
    assert array_100["total_jobs"] == 2
    assert array_100["state_counts"] == {"PENDING": 1, "RUNNING": 1}
    assert array_100["category_counts"] == {"pending": 1, "running": 1}
    assert array_100["array_task_ids"] == ["0", "1"]
    assert [job["job_id"] for job in array_100["jobs"]] == ["100_0", "100_1"]


def test_query_slurm_normalizes_slurm_json_wrapped_fields(monkeypatch):
    monkeypatch.setattr("dqmc_tools.slurm.shutil.which", lambda _name: "squeue")

    def slurm_number(value, *, set=True, infinite=False):
        return {"set": set, "infinite": infinite, "number": value}

    def fake_run(args, **_kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=json_jobs([
                {
                    "job_id": 24921973,
                    "name": "U-2_12x12_hf",
                    "job_state": ["PENDING"],
                    "state_reason": "Priority",
                    "array_job_id": slurm_number(24884301),
                    "array_task_id": slurm_number(42),
                },
                {
                    "job_id": 26224762,
                    "name": "U6_8x8",
                    "job_state": ["RUNNING"],
                    "state_reason": "None",
                    "array_job_id": slurm_number(26224762),
                    "array_task_id": slurm_number(0, set=False),
                },
            ]),
            stderr="",
        )

    monkeypatch.setattr("dqmc_tools.slurm.subprocess.run", fake_run)

    result = query_slurm({"me": True})

    assert result["summary"]["state_counts"] == {"PENDING": 1, "RUNNING": 1}
    assert result["summary"]["category_counts"] == {"pending": 1, "running": 1}
    assert _array_group(_group_by_name(result, "U-2_12x12_hf"), "24884301")["array_task_ids"] == ["42"]
    assert _array_group(_group_by_name(result, "U6_8x8"), "26224762")["array_task_ids"] == []


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


def test_query_slurm_groups_fallback_array_rows(monkeypatch):
    monkeypatch.setattr("dqmc_tools.slurm.shutil.which", lambda _name: "squeue")

    def fake_run(args, **_kwargs):
        if "--json" in args:
            return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="no json")
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=(
                "300_0|scan_mu|phoenix|RUNNING|1:00|2:00|normal|node001\n"
                "300_1|scan_mu|phoenix|PENDING|0:00|2:00|normal|Priority\n"
                "301|analysis|phoenix|RUNNING|0:30|1:00|normal|node002\n"
            ),
            stderr="",
        )

    monkeypatch.setattr("dqmc_tools.slurm.subprocess.run", fake_run)

    result = query_slurm({"me": True, "partition": "normal"})

    assert "--me" in result["command"]
    assert "--partition" in result["command"]
    assert result["summary"]["total_jobs"] == 3
    assert result["summary"]["state_counts"] == {"PENDING": 1, "RUNNING": 2}
    assert result["summary"]["category_counts"] == {"pending": 1, "running": 2}

    scan_group = _group_by_name(result, "scan_mu")
    assert scan_group["array_job_count"] == 1
    assert _array_group(scan_group, "300")["array_task_ids"] == ["0", "1"]


def json_jobs(jobs):
    import json

    return json.dumps({"jobs": jobs})


def _group_by_name(result, name):
    return next(item for item in result["groups"]["by_job_name"] if item["job_name"] == name)


def _array_group(job_name_group, array_job_id):
    return next(item for item in job_name_group["array_jobs"] if item["array_job_id"] == array_job_id)
