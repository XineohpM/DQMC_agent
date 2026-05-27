from pathlib import Path

from dqmc_tools.slurm_paths import infer_slurm_path_candidates


def test_infer_path_candidates_uses_sacct_work_dir(tmp_path: Path):
    run_path = tmp_path / "runs" / "run456"
    run_path.mkdir(parents=True)
    detail = {
        "ok": True,
        "candidates": [
            {
                "source": "sacct",
                "job_id": "456",
                "work_dir": str(run_path),
                "stdout_path": "",
                "stderr_path": "",
            }
        ],
    }

    result = infer_slurm_path_candidates(detail, allowed_roots=[tmp_path])

    assert result == {
        "ok": True,
        "path_candidates": [
            {
                "path": str(run_path.resolve()),
                "confidence": "high",
                "evidence": "sacct.WorkDir",
                "accessible": True,
                "within_allowed_roots": True,
                "rejection_reason": "",
                "source_job_id": "456",
            }
        ],
        "warnings": [],
    }


def test_infer_path_candidates_uses_stdout_and_stderr_parents_without_guessing(tmp_path: Path):
    stdout_parent = tmp_path / "stdout_run"
    stderr_parent = tmp_path / "stderr_run"
    stdout_parent.mkdir()
    stderr_parent.mkdir()
    detail = {
        "candidates": [
            {
                "source": "squeue",
                "job_id": "800",
                "stdout_path": str(stdout_parent / "slurm-800.out"),
                "stderr_path": str(stderr_parent / "slurm-800.err"),
            }
        ],
    }

    result = infer_slurm_path_candidates(detail, allowed_roots=[tmp_path])

    assert result["warnings"] == []
    assert result["path_candidates"] == [
        {
            "path": str(stdout_parent.resolve()),
            "confidence": "medium",
            "evidence": "stdout_path_parent",
            "accessible": True,
            "within_allowed_roots": True,
            "rejection_reason": "",
            "source_job_id": "800",
        },
        {
            "path": str(stderr_parent.resolve()),
            "confidence": "medium",
            "evidence": "stderr_path_parent",
            "accessible": True,
            "within_allowed_roots": True,
            "rejection_reason": "",
            "source_job_id": "800",
        },
    ]


def test_infer_path_candidates_marks_outside_allowed_roots_inaccessible(tmp_path: Path):
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    detail = {"candidates": [{"source": "sacct", "job_id": "900", "work_dir": str(outside)}]}

    result = infer_slurm_path_candidates(detail, allowed_roots=[allowed])

    assert result["path_candidates"] == [
        {
            "path": str(outside.resolve()),
            "confidence": "high",
            "evidence": "sacct.WorkDir",
            "accessible": False,
            "within_allowed_roots": False,
            "rejection_reason": "outside_allowed_roots",
            "source_job_id": "900",
        }
    ]


def test_infer_path_candidates_deduplicates_and_keeps_highest_confidence(tmp_path: Path):
    run_path = tmp_path / "run"
    run_path.mkdir()
    detail = {
        "candidates": [
            {
                "source": "sacct",
                "job_id": "901",
                "work_dir": str(run_path),
                "stdout_path": str(run_path / "slurm-901.out"),
            }
        ],
    }

    result = infer_slurm_path_candidates(detail, allowed_roots=[tmp_path])

    assert result["path_candidates"] == [
        {
            "path": str(run_path.resolve()),
            "confidence": "high",
            "evidence": "sacct.WorkDir",
            "accessible": True,
            "within_allowed_roots": True,
            "rejection_reason": "",
            "source_job_id": "901",
        }
    ]


def test_infer_path_candidates_accepts_user_path(tmp_path: Path):
    user_path = tmp_path / "user_selected_run"
    user_path.mkdir()

    result = infer_slurm_path_candidates({"candidates": []}, allowed_roots=[tmp_path], user_path=user_path)

    assert result["path_candidates"] == [
        {
            "path": str(user_path.resolve()),
            "confidence": "high",
            "evidence": "user_provided_path",
            "accessible": True,
            "within_allowed_roots": True,
            "rejection_reason": "",
            "source_job_id": "",
        }
    ]
