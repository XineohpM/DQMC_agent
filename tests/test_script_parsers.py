from pathlib import Path

import numpy as np

from dqmc_tools.scripts import InputRequirement, ScriptDefinition, run_script_adapter


def _write_outputs_script(path: Path):
    path.write_text(
        """
import argparse
from pathlib import Path
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--outdir", required=True)
args = parser.parse_args()
outdir = Path(args.outdir)
outdir.mkdir(parents=True, exist_ok=True)
(outdir / "summary.tsv").write_text("a\\tb\\n1\\t2\\n", encoding="utf-8")
np.save(outdir / "values.npy", np.arange(6).reshape(2, 3))
print("status=ok")
""".strip(),
        encoding="utf-8",
    )


def _definition(script: Path, parser_id: str) -> ScriptDefinition:
    return ScriptDefinition(
        script_id="write_outputs",
        description="Write parser fixture outputs.",
        category="analysis",
        mode="writes_output",
        path=script,
        args_schema={
            "required": ["input", "outdir"],
            "properties": {
                "input": {"flag": "--input"},
                "outdir": {"flag": "--outdir", "path_role": "output"},
            },
        },
        required_inputs=(InputRequirement("input", "file", "{input}"),),
        output_patterns=("{outdir}/*",),
        parser_id=parser_id,
    )


def test_tsv_parser_adds_preview_without_losing_result(tmp_path: Path):
    script = tmp_path / "outputs.py"
    input_file = tmp_path / "input.txt"
    outdir = tmp_path / "out"
    _write_outputs_script(script)
    input_file.write_text("data", encoding="utf-8")

    result = run_script_adapter(
        "write_outputs",
        {"input": str(input_file), "outdir": str(outdir)},
        cwd=tmp_path,
        allowed_roots=[tmp_path],
        output_root=tmp_path,
        registry=[_definition(script, "tsv")],
        user_confirmation={"approved": True, "text": "run parser fixture"},
    )

    assert result["returncode"] == 0
    assert result["parsed_outputs"]["tsv"][0]["columns"] == ["a", "b"]
    assert result["parsed_outputs"]["tsv"][0]["preview"] == [{"a": "1", "b": "2"}]


def test_npy_parser_records_shape_and_dtype(tmp_path: Path):
    script = tmp_path / "outputs.py"
    input_file = tmp_path / "input.txt"
    outdir = tmp_path / "out"
    _write_outputs_script(script)
    input_file.write_text("data", encoding="utf-8")

    result = run_script_adapter(
        "write_outputs",
        {"input": str(input_file), "outdir": str(outdir)},
        cwd=tmp_path,
        allowed_roots=[tmp_path],
        output_root=tmp_path,
        registry=[_definition(script, "npy_manifest")],
        user_confirmation={"approved": True, "text": "run parser fixture"},
    )

    arrays = result["parsed_outputs"]["arrays"]
    assert {"path": str(outdir / "values.npy"), "format": "npy", "shape": [2, 3], "dtype": "int64"} in arrays
