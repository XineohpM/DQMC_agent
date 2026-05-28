from dqmc_tools.slurm_monitor import diff_slurm_snapshots, format_slurm_snapshot_diff


def test_diff_slurm_snapshots_reports_added_removed_and_state_changed():
    previous = {
        "jobs": [
            {"job_id": "100", "name": "old", "job_state": "RUNNING"},
            {"job_id": "101", "name": "scan", "job_state": "PENDING"},
            {"job_id": "102", "name": "same", "job_state": "RUNNING"},
        ]
    }
    current = {
        "jobs": [
            {"job_id": "101", "name": "scan", "job_state": "RUNNING"},
            {"job_id": "102", "name": "same", "job_state": "RUNNING"},
            {"job_id": "103", "name": "new", "job_state": "PENDING"},
        ]
    }

    result = diff_slurm_snapshots(previous, current)

    assert result == {
        "ok": True,
        "added": [{"job_id": "103", "job_name": "new", "state": "PENDING", "raw": current["jobs"][2]}],
        "removed": [{"job_id": "100", "job_name": "old", "state": "RUNNING", "raw": previous["jobs"][0]}],
        "state_changed": [
            {
                "job_id": "101",
                "job_name": "scan",
                "previous_state": "PENDING",
                "current_state": "RUNNING",
                "previous": previous["jobs"][1],
                "current": current["jobs"][0],
            }
        ],
        "unchanged_count": 1,
    }


def test_format_slurm_snapshot_diff_reports_changes():
    diff = {
        "ok": True,
        "added": [{"job_id": "103", "job_name": "new", "state": "PENDING"}],
        "removed": [{"job_id": "100", "job_name": "old", "state": "RUNNING"}],
        "state_changed": [
            {
                "job_id": "101",
                "job_name": "scan",
                "previous_state": "PENDING",
                "current_state": "RUNNING",
            }
        ],
        "unchanged_count": 1,
    }

    assert format_slurm_snapshot_diff(diff) == (
        "新增 1 个任务：103 new PENDING。\n"
        "消失 1 个任务：100 old RUNNING。\n"
        "状态变化 1 个任务：101 scan PENDING -> RUNNING。"
    )


def test_format_slurm_snapshot_diff_reports_no_changes():
    diff = {"ok": True, "added": [], "removed": [], "state_changed": [], "unchanged_count": 3}

    assert format_slurm_snapshot_diff(diff) == "没有任务状态变化。"
