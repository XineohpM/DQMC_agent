from pathlib import Path

from dqmc_tools.scripts import run_script_adapter


def test_real_completion_adapter_parses_tsv_report(real_t01_subset: Path, tmp_path: Path):
    result = run_script_adapter(
        "check_h5_completion",
        {"root": str(real_t01_subset), "glob": "*.h5"},
        cwd=tmp_path,
        allowed_roots=[tmp_path],
        output_root=tmp_path,
        user_confirmation={"approved": True, "text": "run check_h5_completion fixture"},
    )

    assert result["returncode"] == 0
    assert result["output_files"][0]["path"] == str((real_t01_subset / "h5_completion_report.tsv").resolve())
    report = result["parsed_outputs"]["tsv"][0]
    assert report["columns"] == [
        "dir",
        "file",
        "ok_log",
        "is_complete",
        "total_sweeps",
        "last_reported_sweeps",
    ]
    assert report["row_count"] == 2
    assert report["preview"][0]["ok_log"] == "1"
    assert report["preview"][0]["is_complete"] == "1"


def test_real_energy_adapter_parses_numeric_npy_outputs(real_t01_subset: Path, tmp_path: Path):
    result = run_script_adapter(
        "extract_energy_perfile",
        {"dir": str(real_t01_subset), "U": -6, "out": "E_perfile.npy"},
        cwd=tmp_path,
        allowed_roots=[tmp_path],
        output_root=tmp_path,
        user_confirmation={"approved": True, "text": "run extract_energy_perfile fixture"},
    )

    assert result["returncode"] == 0
    assert str((real_t01_subset / "E_perfile.npy").resolve()) in {
        item["path"] for item in result["output_files"]
    }
    arrays = result["parsed_outputs"]["arrays"]
    assert {
        "path": str((real_t01_subset / "E_perfile.npy").resolve()),
        "format": "npy",
        "shape": [2],
        "dtype": "float64",
    } in arrays
