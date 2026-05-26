from pathlib import Path

from dqmc_tools.runs import summarize_run


ROOT = Path(__file__).resolve().parents[1]
REAL_T01 = ROOT / "data" / "T_0.1"


def test_summarize_run_uses_user_provided_real_directory():
    result = summarize_run(
        REAL_T01,
        allowed_roots=[REAL_T01],
        max_files=2,
        max_registry_entries=100,
        max_log_chars=200,
    )

    assert result["ok"] is True
    assert result["path"] == str(REAL_T01.resolve())
    assert result["name"] == "T_0.1"
    assert result["hdf5_file_count"] == 100
    assert result["reported_hdf5_file_count"] == 2
    assert result["hdf5_files_truncated"] is True
    assert result["metadata"]["metadata/beta"] == 10.0
    assert result["metadata"]["params/L"] == 200
    assert result["hdf5_files"][0]["log"]["has_save_success_marker"] is True
    assert result["hdf5_files"][0]["log"]["last_sweep"] == {"completed": 4200, "total": 4200}
    assert any(item["id"] == "density" for item in result["available_registry_entries"])
    assert any(item["id"] == "jnjn" for item in result["missing_registry_entries"])
