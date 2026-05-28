import subprocess

import pytest

from dqmc_tools.errors import InvalidArgumentError, ToolUnavailableError
from dqmc_tools.slurm import get_slurm_job_detail, query_slurm, query_slurm_history


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


def test_query_slurm_history_unavailable(monkeypatch):
    monkeypatch.setattr("dqmc_tools.slurm.shutil.which", lambda _name: None)

    with pytest.raises(ToolUnavailableError):
        query_slurm_history()


def test_query_slurm_history_rejects_unknown_filter(monkeypatch):
    monkeypatch.setattr("dqmc_tools.slurm.shutil.which", lambda _name: "sacct")

    with pytest.raises(InvalidArgumentError):
        query_slurm_history({"account": "abc"})


def test_query_slurm_history_timeout(monkeypatch):
    monkeypatch.setattr("dqmc_tools.slurm.shutil.which", lambda _name: "sacct")

    def fake_run(args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=args, timeout=30)

    monkeypatch.setattr("dqmc_tools.slurm.subprocess.run", fake_run)

    with pytest.raises(ToolUnavailableError) as exc_info:
        query_slurm_history()

    assert exc_info.value.details == {
        "command": [
            "sacct",
            "--parsable2",
            "--noheader",
            "--format=JobID,JobName,User,State,ExitCode,Elapsed,Timelimit,Submit,Start,End,Partition,NodeList,WorkDir",
        ],
        "timeout_seconds": 30,
    }


def test_query_slurm_history_builds_sacct_command_and_parses_rows(monkeypatch):
    monkeypatch.setattr("dqmc_tools.slurm.shutil.which", lambda _name: "sacct")
    monkeypatch.setattr("dqmc_tools.slurm.getpass.getuser", lambda: "phoenix")

    def fake_run(args, **_kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=(
                "100|scan_T|phoenix|COMPLETED|0:0|00:10:00|01:00:00|"
                "2026-05-26T10:00:00|2026-05-26T10:01:00|2026-05-26T10:11:00|normal|node001|/oak/run100\n"
                "101|scan_T|phoenix|FAILED|1:0|00:05:00|01:00:00|"
                "2026-05-26T11:00:00|2026-05-26T11:01:00|2026-05-26T11:06:00|normal|node002|/oak/run101\n"
                "102|scan_T|phoenix|TIMEOUT|0:1|01:00:00|01:00:00|"
                "2026-05-26T12:00:00|2026-05-26T12:01:00|2026-05-26T13:01:00|normal|node003|/oak/run102\n"
                "103|scan_T|phoenix|OUT_OF_MEMORY|0:125|00:20:00|01:00:00|"
                "2026-05-26T14:00:00|2026-05-26T14:01:00|2026-05-26T14:21:00|normal|node004|/oak/run103\n"
            ),
            stderr="",
        )

    monkeypatch.setattr("dqmc_tools.slurm.subprocess.run", fake_run)

    result = query_slurm_history({
        "me": True,
        "state": "FAILED,TIMEOUT",
        "start": "2026-05-25",
        "end": "2026-05-27",
        "partition": "normal",
    })

    assert result["ok"] is True
    assert result["source"] == "sacct_parsable2"
    assert result["command"][:3] == ["sacct", "--parsable2", "--noheader"]
    assert "--user" in result["command"]
    assert "phoenix" in result["command"]
    assert "--state" in result["command"]
    assert "--starttime" in result["command"]
    assert "--endtime" in result["command"]
    assert "--partition" in result["command"]
    assert result["jobs"][0] == {
        "job_id": "100",
        "job_name": "scan_T",
        "user": "phoenix",
        "state": "COMPLETED",
        "exit_code": "0:0",
        "elapsed": "00:10:00",
        "time_limit": "01:00:00",
        "submit": "2026-05-26T10:00:00",
        "start": "2026-05-26T10:01:00",
        "end": "2026-05-26T10:11:00",
        "partition": "normal",
        "node_list": "node001",
        "work_dir": "/oak/run100",
    }
    assert result["summary"] == {
        "total_jobs": 4,
        "state_counts": {
            "COMPLETED": 1,
            "FAILED": 1,
            "OUT_OF_MEMORY": 1,
            "TIMEOUT": 1,
        },
        "exit_code_counts": {"0:0": 1, "0:1": 1, "0:125": 1, "1:0": 1},
    }
    assert result["warnings"] == []


def test_query_slurm_history_applies_job_filter_and_max_rows(monkeypatch):
    monkeypatch.setattr("dqmc_tools.slurm.shutil.which", lambda _name: "sacct")

    def fake_run(args, **_kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=(
                "200|a|phoenix|COMPLETED|0:0|00:01:00|01:00:00||||normal|node001|/run/a\n"
                "201|b|phoenix|FAILED|1:0|00:01:00|01:00:00||||normal|node002|/run/b\n"
            ),
            stderr="",
        )

    monkeypatch.setattr("dqmc_tools.slurm.subprocess.run", fake_run)

    result = query_slurm_history({"job_id": "200", "max_rows": 1})

    assert "--jobs" in result["command"]
    assert "200" in result["command"]
    assert len(result["jobs"]) == 1
    assert result["summary"]["total_jobs"] == 1
    assert result["warnings"] == ["Result truncated to max_rows=1."]


def test_query_slurm_history_warns_on_short_rows(monkeypatch):
    monkeypatch.setattr("dqmc_tools.slurm.shutil.which", lambda _name: "sacct")

    def fake_run(args, **_kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="300|short|phoenix|COMPLETED|0:0\n",
            stderr="",
        )

    monkeypatch.setattr("dqmc_tools.slurm.subprocess.run", fake_run)

    result = query_slurm_history()

    assert result["jobs"][0]["job_id"] == "300"
    assert result["jobs"][0]["work_dir"] == ""
    assert result["warnings"] == ["1 sacct row(s) had fewer fields than expected."]


def test_get_slurm_job_detail_prefers_current_queue(monkeypatch):
    def fake_query_slurm(filters=None):
        assert filters == {"job_id": "123"}
        return {
            "ok": True,
            "source": "squeue_json",
            "command": ["squeue", "--json", "--jobs", "123"],
            "commands_attempted": [["squeue", "--json", "--jobs", "123"]],
            "jobs": [
                {
                    "job_id": 123,
                    "name": "dqmc_scan",
                    "job_state": ["RUNNING"],
                    "partition": "normal",
                    "time_used": "00:12:00",
                    "time_limit": "01:00:00",
                    "nodes": "node001",
                    "standard_output": "/oak/runs/123/slurm-%j.out",
                    "standard_error": "/oak/runs/123/slurm-%j.err",
                }
            ],
        }

    def fake_query_slurm_history(_filters=None):
        raise AssertionError("history should not be queried when current queue has a match")

    monkeypatch.setattr("dqmc_tools.slurm.query_slurm", fake_query_slurm)
    monkeypatch.setattr("dqmc_tools.slurm.query_slurm_history", fake_query_slurm_history)

    result = get_slurm_job_detail("123")

    assert result == {
        "ok": True,
        "job_id": "123",
        "include_history": True,
        "match_count": 1,
        "multiple_matches": False,
        "candidates": [
            {
                "source": "squeue",
                "job_id": "123",
                "job_name": "dqmc_scan",
                "state": "RUNNING",
                "category": "running",
                "partition": "normal",
                "elapsed": "00:12:00",
                "time_limit": "01:00:00",
                "node_or_reason": "node001",
                "submit": "",
                "start": "",
                "end": "",
                "work_dir": "",
                "stdout_path": "/oak/runs/123/slurm-%j.out",
                "stderr_path": "/oak/runs/123/slurm-%j.err",
                "raw": {
                    "job_id": 123,
                    "name": "dqmc_scan",
                    "job_state": ["RUNNING"],
                    "partition": "normal",
                    "time_used": "00:12:00",
                    "time_limit": "01:00:00",
                    "nodes": "node001",
                    "standard_output": "/oak/runs/123/slurm-%j.out",
                    "standard_error": "/oak/runs/123/slurm-%j.err",
                },
            }
        ],
        "queries": [{"source": "squeue", "job_count": 1, "command": ["squeue", "--json", "--jobs", "123"]}],
        "warnings": [],
    }


def test_get_slurm_job_detail_uses_history_when_current_queue_is_empty(monkeypatch):
    monkeypatch.setattr(
        "dqmc_tools.slurm.query_slurm",
        lambda filters=None: {
            "ok": True,
            "source": "squeue_json",
            "command": ["squeue", "--json", "--jobs", filters["job_id"]],
            "jobs": [],
        },
    )
    monkeypatch.setattr(
        "dqmc_tools.slurm.query_slurm_history",
        lambda filters=None: {
            "ok": True,
            "source": "sacct_parsable2",
            "command": ["sacct", "--parsable2", "--jobs", filters["job_id"]],
            "jobs": [
                {
                    "job_id": "456",
                    "job_name": "finished_scan",
                    "user": "phoenix",
                    "state": "COMPLETED",
                    "exit_code": "0:0",
                    "elapsed": "00:42:00",
                    "time_limit": "01:00:00",
                    "submit": "2026-05-26T10:00:00",
                    "start": "2026-05-26T10:02:00",
                    "end": "2026-05-26T10:44:00",
                    "partition": "normal",
                    "node_list": "node007",
                    "work_dir": "/oak/run456",
                }
            ],
            "warnings": ["history warning"],
        },
    )

    result = get_slurm_job_detail("456")

    assert result["match_count"] == 1
    assert result["queries"] == [
        {"source": "squeue", "job_count": 0, "command": ["squeue", "--json", "--jobs", "456"]},
        {"source": "sacct", "job_count": 1, "command": ["sacct", "--parsable2", "--jobs", "456"]},
    ]
    assert result["warnings"] == ["history warning"]
    assert result["candidates"][0] == {
        "source": "sacct",
        "job_id": "456",
        "job_name": "finished_scan",
        "state": "COMPLETED",
        "category": "completed",
        "partition": "normal",
        "elapsed": "00:42:00",
        "time_limit": "01:00:00",
        "node_or_reason": "node007",
        "submit": "2026-05-26T10:00:00",
        "start": "2026-05-26T10:02:00",
        "end": "2026-05-26T10:44:00",
        "work_dir": "/oak/run456",
        "stdout_path": "",
        "stderr_path": "",
        "raw": {
            "job_id": "456",
            "job_name": "finished_scan",
            "user": "phoenix",
            "state": "COMPLETED",
            "exit_code": "0:0",
            "elapsed": "00:42:00",
            "time_limit": "01:00:00",
            "submit": "2026-05-26T10:00:00",
            "start": "2026-05-26T10:02:00",
            "end": "2026-05-26T10:44:00",
            "partition": "normal",
            "node_list": "node007",
            "work_dir": "/oak/run456",
        },
    }


def test_get_slurm_job_detail_preserves_failed_history_candidate(monkeypatch):
    monkeypatch.setattr(
        "dqmc_tools.slurm.query_slurm",
        lambda filters=None: {
            "ok": True,
            "source": "squeue_json",
            "command": ["squeue", "--json", "--jobs", filters["job_id"]],
            "jobs": [],
        },
    )
    monkeypatch.setattr(
        "dqmc_tools.slurm.query_slurm_history",
        lambda filters=None: {
            "ok": True,
            "source": "sacct_parsable2",
            "command": ["sacct", "--parsable2", "--jobs", filters["job_id"]],
            "jobs": [
                {
                    "job_id": "457",
                    "job_name": "failed_scan",
                    "state": "FAILED",
                    "exit_code": "1:0",
                    "elapsed": "00:03:00",
                    "time_limit": "01:00:00",
                    "partition": "normal",
                    "node_list": "node009",
                    "work_dir": "/oak/run457",
                }
            ],
            "warnings": [],
        },
    )

    result = get_slurm_job_detail("457")

    assert result["match_count"] == 1
    assert result["candidates"][0]["state"] == "FAILED"
    assert result["candidates"][0]["category"] == "held_blocked"
    assert result["candidates"][0]["raw"]["exit_code"] == "1:0"


def test_get_slurm_job_detail_returns_stable_empty_result_without_history(monkeypatch):
    history_called = False

    def fake_history(_filters=None):
        nonlocal history_called
        history_called = True
        return {"ok": True, "jobs": []}

    monkeypatch.setattr(
        "dqmc_tools.slurm.query_slurm",
        lambda filters=None: {"ok": True, "command": ["squeue", "--jobs", filters["job_id"]], "jobs": []},
    )
    monkeypatch.setattr("dqmc_tools.slurm.query_slurm_history", fake_history)

    result = get_slurm_job_detail("999", include_history=False)

    assert history_called is False
    assert result == {
        "ok": True,
        "job_id": "999",
        "include_history": False,
        "match_count": 0,
        "multiple_matches": False,
        "candidates": [],
        "queries": [{"source": "squeue", "job_count": 0, "command": ["squeue", "--jobs", "999"]}],
        "warnings": [],
    }


def test_get_slurm_job_detail_returns_array_candidates_without_guessing(monkeypatch):
    monkeypatch.setattr(
        "dqmc_tools.slurm.query_slurm",
        lambda filters=None: {
            "ok": True,
            "source": "squeue_json",
            "command": ["squeue", "--json", "--jobs", filters["job_id"]],
            "jobs": [
                {"job_id": "700_0", "name": "scan", "job_state": "RUNNING", "array_job_id": 700, "array_task_id": 0},
                {"job_id": "700_1", "name": "scan", "job_state": "PENDING", "array_job_id": 700, "array_task_id": 1},
            ],
        },
    )
    monkeypatch.setattr(
        "dqmc_tools.slurm.query_slurm_history",
        lambda _filters=None: (_ for _ in ()).throw(AssertionError("history should not be queried")),
    )

    result = get_slurm_job_detail("700")

    assert result["match_count"] == 2
    assert result["multiple_matches"] is True
    assert [candidate["job_id"] for candidate in result["candidates"]] == ["700_0", "700_1"]


def test_get_slurm_job_detail_filters_specific_array_task(monkeypatch):
    monkeypatch.setattr(
        "dqmc_tools.slurm.query_slurm",
        lambda filters=None: {
            "ok": True,
            "source": "squeue_json",
            "command": ["squeue", "--json", "--jobs", filters["job_id"]],
            "jobs": [
                {"job_id": "700_0", "name": "scan", "job_state": "RUNNING", "array_job_id": 700, "array_task_id": 0},
                {"job_id": "700_1", "name": "scan", "job_state": "PENDING", "array_job_id": 700, "array_task_id": 1},
            ],
        },
    )
    monkeypatch.setattr(
        "dqmc_tools.slurm.query_slurm_history",
        lambda _filters=None: (_ for _ in ()).throw(AssertionError("history should not be queried")),
    )

    result = get_slurm_job_detail("700_1")

    assert result["match_count"] == 1
    assert result["multiple_matches"] is False
    assert result["candidates"][0]["job_id"] == "700_1"


def test_get_slurm_job_detail_filters_specific_array_task_from_separate_fields(monkeypatch):
    captured_filters = []

    def fake_query_slurm(filters=None):
        captured_filters.append(filters)
        return {
            "ok": True,
            "source": "squeue_json",
            "command": ["squeue", "--json", "--jobs", filters["job_id"]],
            "jobs": [
                {
                    "job_id": "900001",
                    "name": "scan",
                    "job_state": "RUNNING",
                    "array_job_id": {"set": True, "number": 700},
                    "array_task_id": {"set": True, "number": 0},
                },
                {
                    "job_id": "900002",
                    "name": "scan",
                    "job_state": "PENDING",
                    "array_job_id": {"set": True, "number": 700},
                    "array_task_id": {"set": True, "number": 1},
                },
            ],
        }

    monkeypatch.setattr(
        "dqmc_tools.slurm.query_slurm",
        fake_query_slurm,
    )
    monkeypatch.setattr(
        "dqmc_tools.slurm.query_slurm_history",
        lambda _filters=None: (_ for _ in ()).throw(AssertionError("history should not be queried")),
    )

    result = get_slurm_job_detail("700_1")

    assert captured_filters == [{"job_id": "700"}]
    assert result["match_count"] == 1
    assert result["multiple_matches"] is False
    assert result["candidates"][0]["job_id"] == "900002"


def test_get_slurm_job_detail_rejects_empty_job_id():
    with pytest.raises(InvalidArgumentError):
        get_slurm_job_detail(" ")


def json_jobs(jobs):
    import json

    return json.dumps({"jobs": jobs})


def _group_by_name(result, name):
    return next(item for item in result["groups"]["by_job_name"] if item["job_name"] == name)


def _array_group(job_name_group, array_job_id):
    return next(item for item in job_name_group["array_jobs"] if item["array_job_id"] == array_job_id)
