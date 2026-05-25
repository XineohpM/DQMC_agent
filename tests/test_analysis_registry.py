from pathlib import Path

import pytest

from dqmc_tools.analyses import AnalysisDefinition, list_analyses, run_analysis
from dqmc_tools.errors import AnalysisRegistryError, PathNotAllowedError


def _handler(run_path: Path, params: dict, output_dir: Path) -> dict:
    output_file = output_dir / "result.txt"
    output_file.write_text(f"{run_path.name}:{params.get('value', '')}", encoding="utf-8")
    return {"output_file": str(output_file), "value": params.get("value")}


def test_list_analyses_defaults_to_empty_registry():
    assert list_analyses() == []


def test_list_analyses_returns_metadata_without_handler():
    definition = AnalysisDefinition(
        analysis_id="summary",
        description="Summarize a run.",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        handler=_handler,
    )

    assert list_analyses([definition]) == [{
        "analysis_id": "summary",
        "description": "Summarize a run.",
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
    }]


def test_run_analysis_uses_whitelist_and_output_root(tmp_path: Path):
    run = tmp_path / "scratch" / "run1"
    output_root = tmp_path / "outputs"
    run.mkdir(parents=True)
    definition = AnalysisDefinition(
        analysis_id="summary",
        description="Summarize a run.",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        handler=_handler,
    )

    result = run_analysis(
        "summary",
        run,
        params={"value": 7},
        registry=[definition],
        output_root=output_root,
        allowed_roots=[tmp_path / "scratch"],
    )

    output_file = Path(result["result"]["output_file"])
    assert result["ok"] is True
    assert result["analysis_id"] == "summary"
    assert result["output_dir"] == str((output_root / "run1" / "summary").resolve(strict=False))
    assert output_file.read_text(encoding="utf-8") == "run1:7"


def test_run_analysis_rejects_unregistered_name(tmp_path: Path):
    run = tmp_path / "run1"
    run.mkdir()

    with pytest.raises(AnalysisRegistryError) as exc:
        run_analysis(
            "missing",
            run,
            registry=[],
            output_root=tmp_path / "outputs",
            allowed_roots=[tmp_path],
        )

    assert exc.value.details["registered_analyses"] == []


def test_run_analysis_rejects_path_like_analysis_id(tmp_path: Path):
    run = tmp_path / "run1"
    run.mkdir()

    with pytest.raises(AnalysisRegistryError):
        run_analysis(
            "../script.py",
            run,
            registry=[],
            output_root=tmp_path / "outputs",
            allowed_roots=[tmp_path],
        )


def test_run_analysis_fails_closed_without_output_root(tmp_path: Path):
    run = tmp_path / "run1"
    run.mkdir()
    definition = AnalysisDefinition(
        analysis_id="summary",
        description="Summarize a run.",
        input_schema={},
        output_schema={},
        handler=_handler,
    )

    with pytest.raises(PathNotAllowedError):
        run_analysis(
            "summary",
            run,
            registry=[definition],
            allowed_roots=[tmp_path],
        )


def test_registry_rejects_duplicate_ids():
    first = AnalysisDefinition("summary", "First.", {}, {}, _handler)
    second = AnalysisDefinition("summary", "Second.", {}, {}, _handler)

    with pytest.raises(AnalysisRegistryError) as exc:
        list_analyses([first, second])

    assert exc.value.details["analysis_id"] == "summary"
