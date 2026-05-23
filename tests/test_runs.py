from pathlib import Path

import h5py
import numpy as np
import pytest

from dqmc_tools.errors import InvalidFilterError, PathNotAllowedError
from dqmc_tools.runs import list_runs, summarize_run


def _write_run_h5(path: Path) -> None:
    with h5py.File(path, "w") as handle:
        metadata = handle.create_group("metadata")
        metadata.create_dataset("beta", data=4.0)
        metadata.create_dataset("U", data=-10.0)
        eqlt = handle.create_group("meas_eqlt")
        eqlt.create_dataset("density", data=np.array([0.9, 1.0]))
        eqlt.create_dataset("sign", data=0.8)
        eqlt.create_dataset("n_sample", data=25)


def test_list_runs_finds_hdf5_run_directories(tmp_path: Path):
    root = tmp_path / "scratch"
    run_a = root / "run_a"
    run_b = root / "run_b"
    run_a.mkdir(parents=True)
    run_b.mkdir()
    _write_run_h5(run_a / "data.h5")
    (run_b / "slurm.out").write_text("queued", encoding="utf-8")

    runs = list_runs(root, allowed_roots=[tmp_path])
    names = {item["name"] for item in runs}

    assert names == {"run_a", "run_b"}
    run_a_summary = next(item for item in runs if item["name"] == "run_a")
    assert run_a_summary["hdf5_file_count"] == 1
    assert run_a_summary["log_file_count"] == 0


def test_list_runs_filters_by_name_and_hdf5(tmp_path: Path):
    root = tmp_path / "scratch"
    keep = root / "beta4_keep"
    skip = root / "beta8_skip"
    keep.mkdir(parents=True)
    skip.mkdir()
    _write_run_h5(keep / "data.h5")
    (skip / "slurm.out").write_text("queued", encoding="utf-8")

    runs = list_runs(
        root,
        filters={"name_contains": "keep", "has_hdf5": True},
        allowed_roots=[tmp_path],
    )

    assert [item["name"] for item in runs] == ["beta4_keep"]


def test_list_runs_rejects_unsupported_filters(tmp_path: Path):
    root = tmp_path / "scratch"
    root.mkdir()

    with pytest.raises(InvalidFilterError):
        list_runs(root, filters={"unknown": True}, allowed_roots=[tmp_path])


def test_list_runs_fails_closed_without_allowed_roots(tmp_path: Path, monkeypatch):
    root = tmp_path / "scratch"
    root.mkdir()
    monkeypatch.delenv("DQMC_ALLOWED_ROOTS", raising=False)

    with pytest.raises(PathNotAllowedError):
        list_runs(root)


def test_summarize_run_reports_available_and_missing_observables(tmp_path: Path):
    run = tmp_path / "run_a"
    run.mkdir()
    _write_run_h5(run / "data.h5")

    result = summarize_run(run, allowed_roots=[tmp_path])
    file_summary = result["hdf5_files"][0]

    assert result["ok"] is True
    assert result["hdf5_file_count"] == 1
    assert file_summary["metadata"]["beta"] == 4.0
    assert file_summary["metadata"]["U"] == -10.0
    assert file_summary["metadata"]["sign"] == 0.8
    assert {"repo_id": "EqLt.density", "h5_path": "/meas_eqlt/density"} in file_summary["available_observables"]
    assert {"repo_id": "Uneqlt.gt0", "h5_path": "/meas_uneqlt/gt0"} in file_summary["missing_observables"]
