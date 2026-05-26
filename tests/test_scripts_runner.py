from pathlib import Path

import pytest

from dqmc_tools.errors import (
    ScriptApprovalRequiredError,
    ScriptPreflightError,
)
from dqmc_tools.scripts import (
    InputRequirement,
    ScriptDefinition,
    describe_script_adapter,
    list_script_adapters,
    run_script_adapter,
)


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


def test_list_and_describe_script_adapters(tmp_path: Path):
    script = tmp_path / "fake.py"
    _fake_script(script)
    registry = [_definition(script)]

    listed = list_script_adapters(registry)
    described = describe_script_adapter("fake_copy", registry=registry)

    assert listed[0]["script_id"] == "fake_copy"
    assert listed[0]["approval_required"] is True
    assert described["args_schema"]["required"] == ["input", "out"]


def test_run_script_adapter_dry_run_does_not_require_approval(tmp_path: Path):
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
        dry_run=True,
        registry=[_definition(script)],
    )

    assert result["dry_run"] is True
    assert output_file.exists() is False
    assert result["preflight"][0]["ok"] is True


def test_run_script_adapter_requires_approval(tmp_path: Path):
    script = tmp_path / "fake.py"
    input_file = tmp_path / "input.txt"
    output_file = tmp_path / "output.txt"
    _fake_script(script)
    input_file.write_text("data", encoding="utf-8")

    with pytest.raises(ScriptApprovalRequiredError):
        run_script_adapter(
            "fake_copy",
            {"input": str(input_file), "out": str(output_file)},
            cwd=tmp_path,
            allowed_roots=[tmp_path],
            output_root=tmp_path,
            registry=[_definition(script)],
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


def test_run_script_adapter_preflight_failure(tmp_path: Path):
    script = tmp_path / "fake.py"
    output_file = tmp_path / "output.txt"
    _fake_script(script)

    with pytest.raises(ScriptPreflightError):
        run_script_adapter(
            "fake_copy",
            {"input": str(tmp_path / "missing.txt"), "out": str(output_file)},
            cwd=tmp_path,
            allowed_roots=[tmp_path],
            output_root=tmp_path,
            dry_run=True,
            registry=[_definition(script)],
        )


def test_run_script_adapter_rejects_output_outside_root(tmp_path: Path):
    script = tmp_path / "fake.py"
    input_file = tmp_path / "input.txt"
    outside_root = tmp_path / "outputs"
    output_file = tmp_path / "outside.txt"
    _fake_script(script)
    input_file.write_text("data", encoding="utf-8")

    with pytest.raises(Exception):
        run_script_adapter(
            "fake_copy",
            {"input": str(input_file), "out": str(output_file)},
            cwd=tmp_path,
            allowed_roots=[tmp_path],
            output_root=outside_root,
            dry_run=True,
            registry=[_definition(script)],
        )
