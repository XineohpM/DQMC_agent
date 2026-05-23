from pathlib import Path

import h5py
import numpy as np

from dqmc_tools.hdf5 import inspect_hdf5


def _write_sample_h5(path: Path) -> None:
    with h5py.File(path, "w") as handle:
        metadata = handle.create_group("metadata")
        metadata.create_dataset("beta", data=4.0)
        metadata.create_dataset("U", data=-10.0)
        params = handle.create_group("params")
        params.create_dataset("L", data=40)
        params.create_dataset("dt", data=0.1)
        eqlt = handle.create_group("meas_eqlt")
        eqlt.create_dataset("density", data=np.array([0.95, 1.0, 1.05]))
        eqlt.create_dataset("sign", data=0.87)
        eqlt.create_dataset("n_sample", data=10000)
        uneqlt = handle.create_group("meas_uneqlt")
        uneqlt.create_dataset("gt0", data=np.arange(12).reshape(3, 4))


def test_inspect_hdf5_returns_groups_and_dataset_facts(tmp_path: Path):
    h5_path = tmp_path / "sample.h5"
    _write_sample_h5(h5_path)

    result = inspect_hdf5(h5_path, allowed_roots=[tmp_path])

    dataset_paths = {item["path"] for item in result["datasets"]}
    assert result["ok"] is True
    assert "/metadata" in {item["path"] for item in result["groups"]}
    assert "/meas_eqlt/density" in dataset_paths
    assert "/meas_uneqlt/gt0" in dataset_paths
    density_info = next(item for item in result["datasets"] if item["path"] == "/meas_eqlt/density")
    assert density_info["shape"] == [3]
    assert density_info["dtype"] == "float64"
    assert density_info["preview"] == [0.95, 1.0, 1.05]


def test_inspect_hdf5_does_not_preview_large_dataset(tmp_path: Path):
    h5_path = tmp_path / "sample.h5"
    with h5py.File(h5_path, "w") as handle:
        handle.create_dataset("large", data=np.arange(100))

    result = inspect_hdf5(h5_path, max_preview_items=8, allowed_roots=[tmp_path])
    large = result["datasets"][0]

    assert large["path"] == "/large"
    assert large["preview"] is None
    assert large["preview_truncated"] is True
