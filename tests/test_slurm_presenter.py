from dqmc_tools.slurm_presenter import format_slurm_job_detail, format_slurm_status_summary


def test_format_slurm_status_summary_reports_empty_queue():
    payload = {
        "ok": True,
        "summary": {
            "total_jobs": 0,
            "category_counts": {},
            "state_counts": {},
            "job_name_count": 0,
            "array_job_count": 0,
        },
        "groups": {"by_job_name": []},
        "jobs": [],
    }

    assert format_slurm_status_summary(payload) == "No current SLURM jobs."


def test_format_slurm_status_summary_reports_error_in_english():
    payload = {"ok": False, "message": "squeue is unavailable"}

    assert format_slurm_status_summary(payload) == "SLURM status query failed: squeue is unavailable"


def test_format_slurm_status_summary_reports_array_group_table():
    payload = {
        "ok": True,
        "summary": {
            "total_jobs": 6,
            "category_counts": {"running": 3, "pending": 3, "held_blocked": 1},
            "state_counts": {"PENDING": 3, "RUNNING": 3, "TIMEOUT": 1},
            "job_name_count": 3,
            "array_job_count": 4,
        },
        "groups": {
            "by_job_name": [
                {
                    "job_name": "analysis",
                    "total_jobs": 1,
                    "state_counts": {"TIMEOUT": 1},
                    "category_counts": {"held_blocked": 1},
                    "array_job_count": 1,
                    "array_jobs": [
                        {
                            "array_job_id": "301",
                            "total_jobs": 1,
                            "state_counts": {"TIMEOUT": 1},
                            "category_counts": {"held_blocked": 1},
                            "array_task_ids": [],
                            "jobs": [
                                {
                                    "job_id": "301",
                                    "name": "analysis",
                                    "state": "TIMEOUT",
                                    "nodes": "TIMEOUT",
                                },
                            ],
                        },
                    ],
                },
                {
                    "job_name": "scan_mu",
                    "total_jobs": 4,
                    "state_counts": {"PENDING": 3, "RUNNING": 1},
                    "category_counts": {"pending": 3, "running": 1},
                    "array_job_count": 2,
                    "array_jobs": [
                        {
                            "array_job_id": "300",
                            "total_jobs": 2,
                            "state_counts": {"PENDING": 1, "RUNNING": 1},
                            "category_counts": {"pending": 1, "running": 1},
                            "array_task_ids": ["0", "1"],
                            "jobs": [
                                {
                                    "job_id": "300_0",
                                    "name": "scan_mu",
                                    "state": "RUNNING",
                                    "nodes": "node001",
                                },
                                {
                                    "job_id": "300_1",
                                    "name": "scan_mu",
                                    "state": "PENDING",
                                    "nodes": "Priority",
                                },
                            ],
                        },
                        {
                            "array_job_id": "302",
                            "total_jobs": 2,
                            "state_counts": {"PENDING": 2},
                            "category_counts": {"pending": 2},
                            "array_task_ids": ["0", "1"],
                            "jobs": [
                                {
                                    "job_id": "302_0",
                                    "name": "scan_mu",
                                    "state": "PENDING",
                                    "nodes": "Priority",
                                },
                                {
                                    "job_id": "302_1",
                                    "name": "scan_mu",
                                    "state": "PENDING",
                                    "nodes": "Priority",
                                },
                            ],
                        },
                    ],
                },
                {
                    "job_name": "single_job",
                    "total_jobs": 1,
                    "state_counts": {"RUNNING": 1},
                    "category_counts": {"running": 1},
                    "array_job_count": 1,
                    "array_jobs": [
                        {
                            "array_job_id": "999",
                            "total_jobs": 1,
                            "state_counts": {"RUNNING": 1},
                            "category_counts": {"running": 1},
                            "array_task_ids": [],
                            "jobs": [
                                {
                                    "job_id": "999",
                                    "name": "single_job",
                                    "state": "RUNNING",
                                    "nodes": "node009",
                                },
                            ],
                        },
                    ],
                },
            ],
        },
        "jobs": [],
    }

    summary = format_slurm_status_summary(payload)

    assert summary == (
        "```\n"
        "Job Name    Array Job ID  Total  Pending  Running\n"
        "analysis    301           1      0        0\n"
        "scan_mu     300           2      1        1\n"
        "scan_mu     302           2      2        0\n"
        "single_job  999           1      0        1\n"
        "```\n"
        "Total jobs: 6\n"
        "Pending: 3\n"
        "Running: 3"
    )


def test_format_slurm_status_summary_reports_all_array_rows_without_examples():
    payload = {
        "ok": True,
        "summary": {
            "total_jobs": 12,
            "category_counts": {"running": 12},
            "state_counts": {"RUNNING": 12},
            "job_name_count": 1,
            "array_job_count": 1,
        },
        "groups": {
            "by_job_name": [
                {
                    "job_name": "scan_T",
                    "total_jobs": 12,
                    "state_counts": {"RUNNING": 12},
                    "category_counts": {"running": 12},
                    "array_job_count": 1,
                    "array_jobs": [
                        {
                            "array_job_id": "900",
                            "total_jobs": 12,
                            "state_counts": {"RUNNING": 12},
                            "category_counts": {"running": 12},
                            "array_task_ids": [str(i) for i in range(12)],
                            "jobs": [
                                {
                                    "job_id": f"900_{i}",
                                    "name": "scan_T",
                                    "state": "RUNNING",
                                    "nodes": f"node{i:03d}",
                                }
                                for i in range(12)
                            ],
                        },
                    ],
                },
            ],
        },
        "jobs": [],
    }

    summary = format_slurm_status_summary(payload)

    assert summary == (
        "```\n"
        "Job Name  Array Job ID  Total  Pending  Running\n"
        "scan_T    900           12     0        12\n"
        "```\n"
        "Total jobs: 12\n"
        "Pending: 0\n"
        "Running: 12"
    )


def test_format_slurm_status_summary_counts_completing_and_configuring_as_running():
    payload = {
        "ok": True,
        "summary": {
            "total_jobs": 4,
            "state_counts": {"CG": 1, "CF": 1, "COMPLETING": 1, "CONFIGURING": 1},
            "job_name_count": 1,
            "array_job_count": 1,
        },
        "groups": {
            "by_job_name": [
                {
                    "job_name": "startup_or_cleanup",
                    "total_jobs": 4,
                    "state_counts": {"CG": 1, "CF": 1, "COMPLETING": 1, "CONFIGURING": 1},
                    "array_job_count": 1,
                    "array_jobs": [
                        {
                            "array_job_id": "850",
                            "total_jobs": 4,
                            "state_counts": {"CG": 1, "CF": 1, "COMPLETING": 1, "CONFIGURING": 1},
                            "array_task_ids": ["0", "1", "2", "3"],
                            "jobs": [],
                        },
                    ],
                },
            ],
        },
        "jobs": [],
    }

    assert format_slurm_status_summary(payload) == (
        "```\n"
        "Job Name            Array Job ID  Total  Pending  Running\n"
        "startup_or_cleanup  850           4      0        4\n"
        "```\n"
        "Total jobs: 4\n"
        "Pending: 0\n"
        "Running: 4"
    )


def test_format_slurm_job_detail_reports_error_in_english():
    payload = {"ok": False, "message": "sacct is unavailable"}

    assert format_slurm_job_detail(payload) == "SLURM job detail query failed: sacct is unavailable"


def test_format_slurm_job_detail_reports_no_matches():
    payload = {
        "ok": True,
        "job_id": "999",
        "match_count": 0,
        "multiple_matches": False,
        "candidates": [],
        "warnings": [],
    }

    assert format_slurm_job_detail(payload) == "No SLURM job detail found for job 999."


def test_format_slurm_job_detail_summarizes_large_array_parent_without_raw_row_dump():
    payload = {
        "ok": True,
        "job_id": "25536166",
        "match_count": 17,
        "multiple_matches": True,
        "candidates": [
            {
                "source": "squeue",
                "job_id": f"25536166_{task_id}",
                "job_name": "scan_mu",
                "state": "RUNNING" if task_id < 12 else "PENDING",
                "category": "running" if task_id < 12 else "pending",
                "partition": "owners",
                "elapsed": "01:23:45" if task_id < 12 else "00:00:00",
                "time_limit": "2-00:00:00",
                "node_or_reason": f"sh03-{task_id:02d}" if task_id < 12 else "Priority",
            }
            for task_id in range(17)
        ],
        "warnings": [],
    }

    detail = format_slurm_job_detail(payload)

    assert detail == (
        "SLURM job detail for 25536166\n"
        "Job name: scan_mu\n"
        "Source: squeue\n"
        "Matches: 17\n"
        "State counts: PENDING=5, RUNNING=12\n"
        "Category counts: pending=5, running=12\n"
        "Sample jobs: 25536166_0, 25536166_1, 25536166_2, 25536166_3, 25536166_4, ... (+12 more)"
    )
    assert "sh03-16" not in detail


def test_format_slurm_job_detail_reports_specific_array_task_table():
    payload = {
        "ok": True,
        "job_id": "25381905_509",
        "match_count": 1,
        "multiple_matches": False,
        "candidates": [
            {
                "source": "squeue",
                "job_id": "25381905_509",
                "job_name": "scan_T",
                "state": "RUNNING",
                "category": "running",
                "partition": "owners",
                "elapsed": "03:14:15",
                "time_limit": "2-00:00:00",
                "node_or_reason": "sh03-01",
                "submit": "2026-05-28T09:00:00",
                "start": "2026-05-28T09:05:00",
                "end": "2026-05-30T09:05:00",
            }
        ],
        "warnings": [],
    }

    assert format_slurm_job_detail(payload) == (
        "SLURM job detail for 25381905_509\n"
        "```\n"
        "Field         Value\n"
        "Job ID        25381905_509\n"
        "Job Name      scan_T\n"
        "Source        squeue\n"
        "State         RUNNING\n"
        "Category      running\n"
        "Partition     owners\n"
        "Elapsed       03:14:15\n"
        "Time Limit    2-00:00:00\n"
        "Node/Reason   sh03-01\n"
        "Submit        2026-05-28T09:00:00\n"
        "Start         2026-05-28T09:05:00\n"
        "End           2026-05-30T09:05:00\n"
        "```"
    )


def test_format_slurm_job_detail_reports_completed_task_step_group():
    payload = {
        "ok": True,
        "job_id": "26238039_509",
        "match_count": 4,
        "multiple_matches": True,
        "candidates": [
            {
                "source": "sacct",
                "job_id": "26238039_509",
                "job_name": "scan_T",
                "state": "COMPLETED",
                "category": "completed",
                "partition": "owners",
                "elapsed": "00:10:00",
                "time_limit": "01:00:00",
                "node_or_reason": "sh03-01",
                "raw": {"exit_code": "0:0"},
            },
            {
                "source": "sacct",
                "job_id": "26238039_509.batch",
                "job_name": "batch",
                "state": "COMPLETED",
                "category": "completed",
                "elapsed": "00:10:00",
                "raw": {"exit_code": "0:0"},
            },
            {
                "source": "sacct",
                "job_id": "26238039_509.extern",
                "job_name": "extern",
                "state": "COMPLETED",
                "category": "completed",
                "elapsed": "00:10:01",
                "raw": {"exit_code": "0:0"},
            },
            {
                "source": "sacct",
                "job_id": "26238039_509.0",
                "job_name": "0",
                "state": "COMPLETED",
                "category": "completed",
                "elapsed": "00:09:59",
                "raw": {"exit_code": "0:0"},
            },
        ],
        "warnings": [],
    }

    assert format_slurm_job_detail(payload) == (
        "SLURM job detail for 26238039_509\n"
        "Job name: scan_T\n"
        "Source: sacct\n"
        "Matches: 4\n"
        "Step group: task-level sacct rows; no unique step row was guessed.\n"
        "State counts: COMPLETED=4\n"
        "Exit code counts: 0:0=4\n"
        "Rows:\n"
        "```\n"
        "Job ID                 State      Exit Code  Elapsed   Node/Reason\n"
        "26238039_509           COMPLETED  0:0        00:10:00  sh03-01\n"
        "26238039_509.batch     COMPLETED  0:0        00:10:00\n"
        "26238039_509.extern    COMPLETED  0:0        00:10:01\n"
        "26238039_509.0         COMPLETED  0:0        00:09:59\n"
        "```"
    )
