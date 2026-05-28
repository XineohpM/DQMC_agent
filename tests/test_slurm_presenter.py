from dqmc_tools.slurm_presenter import format_slurm_status_summary


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
