from pathlib import Path

from dqmc_tools.scripts.argparse_sync import (
    args_schema_diff,
    extract_argparse_schema,
    sync_argparse_adapters,
)
from dqmc_tools.scripts.definitions import ScriptDefinition


def _write_argparse_fixture(path: Path) -> None:
    path.write_text(
        """
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=str)
    parser.add_argument("--count", type=int, required=True, choices=[1, 2])
    parser.add_argument("--name-with-dash", dest="name", default="dqmc")
    parser.add_argument("--items", nargs="+", required=True)
    parser.add_argument("--dynamic", default=SOME_CONST)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--sym", dest="sym", action="store_true")
    group.add_argument("--nonsym", dest="sym", action="store_false")
    parser.parse_args()
""".strip(),
        encoding="utf-8",
    )


def test_extract_argparse_schema_reads_direct_parser_calls(tmp_path: Path):
    script = tmp_path / "with_parser.py"
    _write_argparse_fixture(script)

    result = extract_argparse_schema(script)

    assert result.status == "parsed"
    assert result.properties["root"]["positional"] is True
    assert result.properties["root"]["position"] == 0
    assert result.properties["count"]["flag"] == "--count"
    assert result.properties["count"]["type"] == "int"
    assert result.properties["count"]["choices"] == [1, 2]
    assert result.properties["items"]["nargs"] == "+"
    assert "default" not in result.properties["dynamic"]
    assert result.properties["sym"]["flag"] == "--sym"
    assert result.properties["sym"]["false_flag"] == "--nonsym"
    assert result.required == ["root", "count", "items"]


def test_sync_argparse_adapters_updates_schema_and_preserves_path_metadata(tmp_path: Path):
    script = tmp_path / "with_parser.py"
    _write_argparse_fixture(script)
    adapter = ScriptDefinition(
        script_id="with_parser",
        description="Fixture with argparse.",
        category="analysis",
        mode="writes_output",
        path=script,
        args_schema={
            "required": ["root"],
            "properties": {
                "root": {"positional": True, "position": 0, "path_role": "input"},
                "args": {"raw_args": True},
            },
        },
    )

    result = sync_argparse_adapters([adapter])

    synced = result.adapters[0]
    properties = synced.args_schema["properties"]
    assert result.summary["parsed"] == 1
    assert properties["root"]["path_role"] == "input"
    assert properties["count"]["flag"] == "--count"
    assert properties["sym"]["false_flag"] == "--nonsym"
    assert "args" not in properties
    assert synced.args_schema["required"] == ["root", "count", "items"]


def test_args_schema_diff_reports_cli_contract_changes(tmp_path: Path):
    script = tmp_path / "with_parser.py"
    _write_argparse_fixture(script)
    parser_result = extract_argparse_schema(script)
    old_schema = {
        "required": ["root", "old_required"],
        "properties": {
            "root": {"positional": True, "position": 0},
            "count": {"flag": "--old-count"},
            "old_required": {"flag": "--old-required"},
            "args": {"raw_args": True},
        },
    }

    diff = args_schema_diff(old_schema, parser_result)

    assert "items" in diff["added"]
    assert "old_required" in diff["removed"]
    assert "args" in diff["removed"]
    assert diff["changed"]["count"]["before"]["flag"] == "--old-count"
    assert diff["changed"]["count"]["after"]["flag"] == "--count"
    assert diff["required_added"] == ["count", "items"]
    assert diff["required_removed"] == ["old_required"]
