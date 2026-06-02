from pathlib import Path

from dqmc_tools.scripts import (
    DEFAULT_SCRIPT_CATALOG,
    EXCLUDED_FIRST_PHASE_SCRIPTS,
    ScriptDefinition,
    audit_script_adapters,
    describe_script_adapter,
    list_script_adapters,
)
from dqmc_tools.config import get_dqmc_dev_root


def test_builtin_catalog_paths_exist_and_excludes_deferred_workflows():
    scripts = list_script_adapters()
    script_ids = {item["script_id"] for item in scripts}

    assert len(scripts) == len(DEFAULT_SCRIPT_CATALOG)
    assert "check_warm" in script_ids
    assert "plot_JNJN" in script_ids
    assert "gen_beta_mu_scan" in script_ids
    assert "compute_specific_heat" in script_ids
    assert "make_bootstrap" not in script_ids
    assert "save_boot_stats" not in script_ids
    assert "run_maxent" not in script_ids
    assert "run_stack_simes" not in script_ids
    assert "gen_1band_unified_hub" not in script_ids
    assert "dqmc_info" not in script_ids
    assert "dqmc_summary" not in script_ids
    assert "print_n" not in script_ids
    assert "push" not in script_ids
    assert "check_sum_rule" not in script_ids
    assert "plot_compressibility_from_best_mu" not in script_ids
    assert "get_mu" not in script_ids
    assert "multi_dir_submit_sbatch" not in script_ids
    assert "check_sum_rule" in EXCLUDED_FIRST_PHASE_SCRIPTS
    assert "make_bootstrap" in EXCLUDED_FIRST_PHASE_SCRIPTS
    assert "save_boot_stats" in EXCLUDED_FIRST_PHASE_SCRIPTS
    assert "run_maxent" in EXCLUDED_FIRST_PHASE_SCRIPTS
    assert "run_stack_simes" in EXCLUDED_FIRST_PHASE_SCRIPTS
    assert "gen_1band_unified_hub" in EXCLUDED_FIRST_PHASE_SCRIPTS
    assert "dqmc_info" in EXCLUDED_FIRST_PHASE_SCRIPTS
    assert "dqmc_summary" in EXCLUDED_FIRST_PHASE_SCRIPTS
    assert "print_n" in EXCLUDED_FIRST_PHASE_SCRIPTS
    assert "push" in EXCLUDED_FIRST_PHASE_SCRIPTS
    assert all(item["approval_required"] is True for item in scripts)


def test_builtin_catalog_only_whitelists_dqmc_dev_scripts_directory():
    scripts_dir = (get_dqmc_dev_root() / "scripts").resolve()

    assert all(item.path.resolve().is_relative_to(scripts_dir) for item in DEFAULT_SCRIPT_CATALOG)


def test_builtin_catalog_syncs_schema_from_argparse_sources():
    description = describe_script_adapter("run_maxent_anneal")
    properties = description["args_schema"]["properties"]

    assert "args" not in properties
    assert properties["base"]["flag"] == "--base"
    assert properties["items"]["nargs"] == "+"
    assert properties["sym"]["flag"] == "--sym"
    assert properties["sym"]["false_flag"] == "--nonsym"
    assert "data_file" in description["args_schema"]["required"]


def test_plot_jnjn_documents_derived_input_preflight():
    description = describe_script_adapter("plot_JNJN")

    assert description["required_inputs"] == [{
        "name": "JNJN_perbin",
        "kind": "npy",
        "path_template": "{path}/JNJN_xx_perbin.npy",
        "required": True,
        "shape_hint": [None, None],
    }]


def test_check_warm_schema_uses_positional_root_and_output_dir():
    description = describe_script_adapter("check_warm")

    assert description["args_schema"]["properties"]["root"]["positional"] is True
    assert description["args_schema"]["properties"]["output_dir"]["path_role"] == "output"


def test_compute_specific_heat_documents_scan_input_and_outputs():
    description = describe_script_adapter("compute_specific_heat")

    assert description["category"] == "analysis"
    assert description["mode"] == "writes_output"
    assert description["args_schema"]["required"] == ["path", "mode"]
    assert description["args_schema"]["properties"]["path"]["path_role"] == "input"
    assert description["args_schema"]["properties"]["mode"]["choices"] == ["fluc", "diff", "both"]
    assert description["required_inputs"] == [{
        "name": "path",
        "kind": "directory",
        "path_template": "{path}",
        "required": True,
        "shape_hint": None,
    }]
    assert description["output_patterns"] == [
        "{path}/*_T_*.npy",
        "{path}/*_E_*_diff.npy",
        "{path}/*_specific_heat_*.npy",
        "{path}/*_C_vs_T_*.png",
    ]


def test_builtin_catalog_adapter_audit_passes():
    result = audit_script_adapters(include_fingerprints=False)

    assert result["ok"] is True
    assert result["adapter_count"] == len(DEFAULT_SCRIPT_CATALOG)
    assert result["summary"]["errors"] == 0
    assert result["summary"]["warnings"] == 0


def test_adapter_audit_detects_string_output_patterns(tmp_path: Path):
    script = tmp_path / "fake.py"
    script.write_text("print('ok')\n", encoding="utf-8")
    definition = ScriptDefinition(
        script_id="bad_output_patterns",
        description="Bad output_patterns type.",
        category="analysis",
        mode="writes_output",
        path=script,
        args_schema={"properties": {"out": {"flag": "--out"}}},
        output_patterns="{out}",  # type: ignore[arg-type]
    )

    result = audit_script_adapters([definition], include_fingerprints=False)

    assert result["ok"] is False
    adapter = result["adapters"][0]
    assert adapter["script_id"] == "bad_output_patterns"
    assert any(
        check["name"] == "output_patterns.type" and check["status"] == "error"
        for check in adapter["checks"]
    )
