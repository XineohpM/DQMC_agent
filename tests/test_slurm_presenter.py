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

    assert format_slurm_status_summary(payload) == "当前没有任务。"


def test_format_slurm_status_summary_reports_category_counts_and_job_details():
    payload = {
        "ok": True,
        "summary": {
            "total_jobs": 3,
            "category_counts": {"running": 1, "pending": 1, "held_blocked": 1},
            "state_counts": {"PENDING": 1, "RUNNING": 1, "TIMEOUT": 1},
            "job_name_count": 2,
            "array_job_count": 2,
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
                    "total_jobs": 2,
                    "state_counts": {"PENDING": 1, "RUNNING": 1},
                    "category_counts": {"pending": 1, "running": 1},
                    "array_job_count": 1,
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
                    ],
                },
            ],
        },
        "jobs": [],
    }

    summary = format_slurm_status_summary(payload)

    assert "当前共有 3 个任务：running=1, pending=1, held_blocked=1, other=0。" in summary
    assert "scan_mu: 2 个任务，PENDING=1, RUNNING=1；array 300: 2 个任务，tasks 0-1。" in summary
    assert "300_1 PENDING Priority" in summary
    assert "analysis: 1 个任务，TIMEOUT=1；array 301: 1 个任务。" in summary


def test_format_slurm_status_summary_keeps_array_output_compact():
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

    assert "array 900: 12 个任务，tasks 0-11。" in summary
    assert "900_0 RUNNING node000" in summary
    assert "900_3 RUNNING node003" not in summary
