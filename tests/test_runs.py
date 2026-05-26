from pathlib import Path

import h5py
import numpy as np

from dqmc_tools.runs import summarize_run


def _write_run_h5(path: Path):
    with h5py.File(path, "w") as handle:
        metadata = handle.create_group("metadata")
        metadata.create_dataset("beta", data=4.0)
        metadata.create_dataset("U", data=-6.0)
        metadata.create_dataset("mu", data=0.0)
        params = handle.create_group("params")
        params.create_dataset("dt", data=0.1)
        params.create_dataset("L", data=40)
        eqlt = handle.create_group("meas_eqlt")
        eqlt.create_dataset("density", data=np.array([1.0]))
        eqlt.create_dataset("sign", data=1.0)
        eqlt.create_dataset("n_sample", data=10)


def test_summarize_run_uses_user_provided_directory(tmp_path: Path):
    run = tmp_path / "run"
    run.mkdir()
    h5_path = run / "sample.h5"
    _write_run_h5(h5_path)
    Path(str(h5_path) + ".log").write_text(
        "10 / 10 sweeps completed\nsaving data to disk\nsim_data_save() succeeded\n",
        encoding="utf-8",
    )

    result = summarize_run(run, allowed_roots=[tmp_path])

    assert result["ok"] is True
    assert result["hdf5_file_count"] == 1
    assert result["metadata"]["metadata/beta"] == 4.0
    assert result["metadata"]["params/L"] == 40
    assert result["hdf5_files"][0]["log"]["has_save_success_marker"] is True
    assert {
        "entry_type": "observable",
        "id": "density",
        "dataset_key": "meas_eqlt/density",
        "resolved_dataset_key": "meas_eqlt/density",
        "shape": [1],
        "dtype": "float64",
    } in result["available_registry_entries"]
    assert any(item["id"] == "gt0" for item in result["missing_registry_entries"])
