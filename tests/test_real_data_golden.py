from pathlib import Path

import numpy as np

from dqmc_tools.hdf5 import estimate_registered_observable, read_registered_quantity
from dqmc_tools.runs import summarize_run


ROOT = Path(__file__).resolve().parents[1]
REAL_T01 = ROOT / "data" / "T_0.1"


def test_summarize_run_reports_real_t01_fixture_completion_and_metadata():
    result = summarize_run(
        REAL_T01,
        allowed_roots=[REAL_T01],
        max_files=3,
        max_registry_entries=20,
        max_log_chars=200,
    )

    assert result["ok"] is True
    assert result["hdf5_file_count"] == 100
    assert result["hdf5_files_truncated"] is True
    assert result["metadata"]["metadata/beta"] == 10.0
    assert result["metadata"]["metadata/U"] == -6.0
    assert result["metadata"]["params/L"] == 200
    assert result["metadata"]["params/period_uneqlt"] == 2
    assert result["metadata"]["meas_eqlt/sign"] == 160000.0
    assert result["hdf5_files"][0]["log"]["has_save_success_marker"] is True
    assert result["hdf5_files"][0]["log"]["last_sweep"] == {"completed": 4200, "total": 4200}
    assert any(item["id"] == "density" for item in result["available_registry_entries"])


def test_read_registered_quantity_reads_real_sign_and_nsamp_entries():
    checks = {
        "sign_eqlt": ("meas_eqlt/sign", 160000.0),
        "n_sample_eqlt": ("meas_eqlt/n_sample", 160000.0),
        "sign_uneqlt": ("meas_uneqlt/sign", 2000.0),
        "n_sample_uneqlt": ("meas_uneqlt/n_sample", 2000.0),
    }

    for name, (dataset_key, mean) in checks.items():
        result = read_registered_quantity(
            REAL_T01,
            name,
            mode="directory",
            max_items=200,
            allowed_roots=[REAL_T01],
        )

        assert result["dataset_key"] == dataset_key
        assert result["dataset"]["shape"] == [100]
        assert result["dataset"]["mean"] == mean


def test_estimate_registered_observable_uses_real_density_fixture():
    result = estimate_registered_observable(
        REAL_T01,
        "density",
        estimator="jackknife",
        max_items=16,
        allowed_roots=[REAL_T01],
    )

    assert result["hdf5_file_count"] == 100
    assert result["dataset_keys"]["value"] == "meas_eqlt/density"
    assert np.allclose(result["estimate"]["mean"], [0.999863143300189])
    assert np.allclose(result["estimate"]["error"], [0.001020153820681304])
