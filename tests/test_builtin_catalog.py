from dqmc_tools.scripts import (
    DEFAULT_SCRIPT_CATALOG,
    EXCLUDED_FIRST_PHASE_SCRIPTS,
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
