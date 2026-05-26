from pathlib import Path

from dqmc_tools.scripts import (
    DEFAULT_SCRIPT_CATALOG,
    EXCLUDED_FIRST_PHASE_SCRIPTS,
    ScriptDefinition,
    audit_script_adapters,
    describe_script_adapter,
    list_script_adapters,
)


def test_builtin_catalog_paths_exist_and_excludes_deferred_workflows():
    scripts = list_script_adapters()
    script_ids = {item["script_id"] for item in scripts}

    assert len(scripts) == len(DEFAULT_SCRIPT_CATALOG)
    assert "check_warm" in script_ids
    assert "plot_JNJN" in script_ids
    assert "gen_beta_mu_scan" in script_ids
    assert "check_sum_rule" not in script_ids
    assert "plot_compressibility_from_best_mu" not in script_ids
    assert "get_mu" not in script_ids
    assert "multi_dir_submit_sbatch" not in script_ids
    assert "check_sum_rule" in EXCLUDED_FIRST_PHASE_SCRIPTS
    assert all(item["approval_required"] is True for item in scripts)


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
