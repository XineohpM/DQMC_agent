from pathlib import Path

import h5py
import numpy as np
import pytest

from dqmc_tools.errors import HDF5ReadError
from dqmc_tools.hdf5 import (
    estimate_registered_observable,
    inspect_hdf5,
    read_dataset,
    read_observable,
    read_registered_quantity,
)


def _write_h5(path: Path, density, sign=1.0, n_sample=10, mu=0.25):
    with h5py.File(path, "w") as handle:
        metadata = handle.create_group("metadata")
        metadata.create_dataset("mu", data=mu)
        metadata.create_dataset("beta", data=4.0)
        params = handle.create_group("params")
        params.create_dataset("L", data=40)
        eqlt = handle.create_group("meas_eqlt")
        eqlt.create_dataset("density", data=np.asarray(density, dtype=float))
        eqlt.create_dataset("sign", data=sign)
        eqlt.create_dataset("n_sample", data=n_sample)


def test_read_dataset_uses_explicit_dataset_key(tmp_path: Path):
    h5_path = tmp_path / "sample.h5"
    _write_h5(h5_path, [1.0, 1.2])

    result = read_dataset(h5_path, "meas_eqlt/density", allowed_roots=[tmp_path])

    assert result["util_function"] == "load_file"
    assert result["dataset"]["shape"] == [2]
    assert result["dataset"]["preview"] == [1.0, 1.2]
    assert "error" not in result


def test_inspect_hdf5_requires_explicit_keys_and_does_not_list_tree(tmp_path: Path):
    h5_path = tmp_path / "sample.h5"
    _write_h5(h5_path, [1.0, 1.2])

    result = inspect_hdf5(
        h5_path,
        ["density", "meas_eqlt/sign"],
        allowed_roots=[tmp_path],
    )

    assert [item["dataset_key"] for item in result["datasets"]] == [
        "meas_eqlt/density",
        "meas_eqlt/sign",
    ]
    assert "groups" not in result


def test_read_registered_quantity_uses_registry_generation_variable(tmp_path: Path):
    h5_path = tmp_path / "sample.h5"
    _write_h5(h5_path, [1.0, 1.2])

    density = read_registered_quantity(h5_path, "density", allowed_roots=[tmp_path])
    mu = read_registered_quantity(h5_path, "mu", allowed_roots=[tmp_path])

    assert density["registry_entry"]["id"] == "density"
    assert density["dataset_key"] == "meas_eqlt/density"
    assert density["error"] is None
    assert mu["registry_entry"]["id"] == "chemical_potential"
    assert mu["dataset_key"] == "metadata/mu"
    assert mu["dataset"]["value"] == 0.25


def test_read_observable_compatibility_wrapper_is_observable_only(tmp_path: Path):
    h5_path = tmp_path / "sample.h5"
    _write_h5(h5_path, [1.0, 1.2])

    density = read_observable(h5_path, "density", allowed_roots=[tmp_path])

    assert density["registry_entry"]["entry_type"] == "observable"
    assert density["dataset_key"] == "meas_eqlt/density"


def test_read_registered_quantity_reports_missing_dataset(tmp_path: Path):
    h5_path = tmp_path / "sample.h5"
    with h5py.File(h5_path, "w") as handle:
        handle.create_group("meas_eqlt")

    with pytest.raises(HDF5ReadError):
        read_registered_quantity(h5_path, "density", allowed_roots=[tmp_path])


def test_estimate_registered_observable_uses_jackknife(tmp_path: Path):
    _write_h5(tmp_path / "a.h5", [1.0, 2.0], sign=1.0)
    _write_h5(tmp_path / "b.h5", [3.0, 4.0], sign=1.0)
    _write_h5(tmp_path / "c.h5", [5.0, 6.0], sign=1.0)

    result = estimate_registered_observable(
        tmp_path,
        "density",
        estimator="jackknife",
        allowed_roots=[tmp_path],
    )

    assert result["hdf5_file_count"] == 3
    assert result["dataset_keys"]["value"] == "meas_eqlt/density"
    assert result["dataset_keys"]["sign"] == "meas_eqlt/sign"
    assert result["estimate"]["mean"] == [3.0, 4.0]
    assert np.allclose(result["estimate"]["error"], [1.154700538, 1.154700538])
