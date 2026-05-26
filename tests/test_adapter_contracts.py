from pathlib import Path

import pytest

from dqmc_tools.errors import ScriptPreflightError
from dqmc_tools.scripts import describe_script_adapter, run_script_adapter


ROOT = Path(__file__).resolve().parents[1]
REAL_T01 = ROOT / "data" / "T_0.1"


def test_describe_script_adapter_exposes_argparse_synced_contract():
    description = describe_script_adapter("run_maxent_anneal")
    properties = description["args_schema"]["properties"]

    assert description["approval_required"] is True
    assert description["path"].endswith("/dqmc-dev/scripts/run_maxent_anneal.py")
    assert description["args_schema"]["required"] == [
        "base",
        "items",
        "data_file",
        "omega_max",
        "n_omega",
        "bs",
    ]
    assert properties["items"]["nargs"] == "+"
    assert properties["op_type"]["choices"] == ["boson", "fermion"]
    assert properties["sym"]["flag"] == "--sym"
    assert properties["sym"]["false_flag"] == "--nonsym"
    assert "args" not in properties


def test_shell_script_adapters_keep_raw_args_contract():
    description = describe_script_adapter("run_stack_owners")

    assert description["path"].endswith("/dqmc-dev/scripts/run_stack_owners.sh")
    assert description["args_schema"]["properties"] == {"args": {"raw_args": True}}


def test_real_check_warm_dry_run_uses_preflight_without_executing(tmp_path: Path):
    output_dir = tmp_path / "warmup"

    result = run_script_adapter(
        "check_warm",
        {"root": str(REAL_T01), "glob": ".", "output_dir": str(output_dir), "nn": True},
        cwd=ROOT,
        allowed_roots=[ROOT, REAL_T01],
        output_root=tmp_path,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["preflight"] == [
        {
            "ok": True,
            "name": "root",
            "kind": "directory",
            "path": str(REAL_T01.resolve()),
            "reason": None,
        }
    ]
    assert "--nn" in result["command"]
    assert output_dir.exists() is False


def test_real_adapter_preflight_rejects_missing_required_input(tmp_path: Path):
    with pytest.raises(ScriptPreflightError):
        run_script_adapter(
            "extract_energy_perfile",
            {"dir": str(tmp_path / "missing"), "out": "E_perfile.npy"},
            cwd=tmp_path,
            allowed_roots=[tmp_path],
            output_root=tmp_path,
            dry_run=True,
        )


def test_real_adapter_rejects_output_path_outside_output_root(tmp_path: Path):
    with pytest.raises(Exception):
        run_script_adapter(
            "check_warm",
            {
                "root": str(REAL_T01),
                "glob": ".",
                "output_dir": str(tmp_path / "outside"),
            },
            cwd=ROOT,
            allowed_roots=[ROOT, REAL_T01],
            output_root=tmp_path / "outputs",
            dry_run=True,
        )
