from pathlib import Path

import pytest

from dqmc_tools.errors import (
    ScriptApprovalRequiredError,
)
from dqmc_tools.scripts import (
    InputRequirement,
    ScriptDefinition,
    run_script_adapter,
)
from dqmc_tools.scripts.runner import default_argv_builder


def _fake_script(path: Path):
    path.write_text(
        """
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--out", required=True)
args = parser.parse_args()
Path(args.out).write_text(Path(args.input).read_text(encoding="utf-8"), encoding="utf-8")
print("wrote", args.out)
""".strip(),
        encoding="utf-8",
    )


def _definition(script: Path) -> ScriptDefinition:
    return ScriptDefinition(
        script_id="fake_copy",
        description="Copy input to output.",
        category="analysis",
        mode="writes_output",
        path=script,
        args_schema={
            "required": ["input", "out"],
            "properties": {
                "input": {"flag": "--input", "path_role": "input"},
                "out": {"flag": "--out", "path_role": "output"},
            },
        },
        required_inputs=(
            InputRequirement("input", "file", "{input}"),
        ),
        output_patterns=("{out}",),
    )


def test_run_script_adapter_requires_approval_for_real_catalog_script(tmp_path: Path):
    with pytest.raises(ScriptApprovalRequiredError):
        run_script_adapter(
            "run_stack_owners",
            {},
            cwd=tmp_path,
            allowed_roots=[tmp_path],
            output_root=tmp_path,
        )


def test_run_script_adapter_executes_with_approval_and_manifest(tmp_path: Path):
    script = tmp_path / "fake.py"
    input_file = tmp_path / "input.txt"
    output_file = tmp_path / "output.txt"
    _fake_script(script)
    input_file.write_text("data", encoding="utf-8")

    result = run_script_adapter(
        "fake_copy",
        {"input": str(input_file), "out": str(output_file)},
        cwd=tmp_path,
        allowed_roots=[tmp_path],
        output_root=tmp_path,
        registry=[_definition(script)],
        user_confirmation={"approved": True, "text": "run fake_copy now"},
    )

    assert result["returncode"] == 0
    assert output_file.read_text(encoding="utf-8") == "data"
    assert result["output_files"][0]["path"] == str(output_file.resolve())


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
