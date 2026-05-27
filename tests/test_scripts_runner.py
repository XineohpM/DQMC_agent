from pathlib import Path

import pytest

from dqmc_tools.errors import (
    ScriptApprovalRequiredError,
)
from dqmc_tools.scripts import (
    ScriptDefinition,
    run_script_adapter,
)
from dqmc_tools.scripts.runner import default_argv_builder


def test_run_script_adapter_requires_approval_for_real_catalog_script(tmp_path: Path):
    with pytest.raises(ScriptApprovalRequiredError):
        run_script_adapter(
            "run_stack_owners",
            {},
            cwd=tmp_path,
            allowed_roots=[tmp_path],
            output_root=tmp_path,
        )


def test_run_script_adapter_executes_real_catalog_script_with_approval_and_manifest(
    real_t01_subset: Path,
    tmp_path: Path,
):
    result = run_script_adapter(
        "check_h5_completion",
        {"root": str(real_t01_subset), "glob": "*.h5"},
        cwd=tmp_path,
        allowed_roots=[tmp_path],
        output_root=tmp_path,
        user_confirmation={"approved": True, "text": "run real completion adapter"},
    )

    assert result["returncode"] == 0
    assert result["output_files"][0]["path"] == str((real_t01_subset / "h5_completion_report.tsv").resolve())
    assert "Wrote" in result["stdout_tail"]


def test_default_argv_builder_supports_store_false_bool_flag(tmp_path: Path):
    script = tmp_path / "fake.py"
    script.write_text("print('ok')\n", encoding="utf-8")
    definition = ScriptDefinition(
        script_id="bool_flag",
        description="Boolean flag fixture.",
        category="analysis",
        mode="read_only",
        path=script,
        args_schema={
            "properties": {
                "sym": {
                    "flag": "--sym",
                    "false_flag": "--nonsym",
                    "action": "store_true",
                },
            },
        },
    )

    assert default_argv_builder(definition, {"sym": True})[-1] == "--sym"
    assert default_argv_builder(definition, {"sym": False})[-1] == "--nonsym"


def test_default_argv_builder_supports_single_store_false_flag(tmp_path: Path):
    script = tmp_path / "fake.py"
    script.write_text("print('ok')\n", encoding="utf-8")
    definition = ScriptDefinition(
        script_id="store_false_flag",
        description="Store-false flag fixture.",
        category="analysis",
        mode="read_only",
        path=script,
        args_schema={
            "properties": {
                "cache": {
                    "flag": "--no-cache",
                    "action": "store_false",
                },
            },
        },
    )

    assert default_argv_builder(definition, {"cache": False})[-1] == "--no-cache"
    assert "--no-cache" not in default_argv_builder(definition, {"cache": True})
