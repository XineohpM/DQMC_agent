from pathlib import Path

import pytest

from dqmc_tools.config import ALLOWED_ROOTS_ENV, get_output_root
from dqmc_tools.errors import PathNotAllowedError, PathResolutionError
from dqmc_tools.paths import (
    require_allowed_path,
    require_output_path,
    require_workflow_path,
    resolve_existing_path,
)


def test_resolve_existing_path(tmp_path: Path):
    target = tmp_path / "file.h5"
    target.write_text("placeholder", encoding="utf-8")

    assert resolve_existing_path(target) == target.resolve()


def test_resolve_existing_path_missing(tmp_path: Path):
    with pytest.raises(PathResolutionError):
        resolve_existing_path(tmp_path / "missing.h5")


def test_require_allowed_path_fails_closed_without_roots(tmp_path: Path, monkeypatch):
    run = tmp_path / "run"
    run.mkdir()
    monkeypatch.delenv(ALLOWED_ROOTS_ENV, raising=False)

    with pytest.raises(PathNotAllowedError):
        require_allowed_path(run)


def test_require_allowed_path_accepts_path_inside_root(tmp_path: Path):
    root = tmp_path / "scratch"
    run = root / "run"
    run.mkdir(parents=True)

    assert require_allowed_path(run, [root]) == run.resolve()


def test_require_allowed_path_rejects_path_outside_root(tmp_path: Path):
    root = tmp_path / "scratch"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()

    with pytest.raises(PathNotAllowedError):
        require_allowed_path(outside, [root])


def test_require_output_path_defaults_to_project_outputs(monkeypatch):
    monkeypatch.delenv("DQMC_OUTPUT_ROOT", raising=False)

    expected = (get_output_root() / "run" / "result.json").resolve(strict=False)
    assert require_output_path("run/result.json") == expected


def test_require_output_path_rejects_absolute_path_outside_root(tmp_path: Path):
    root = tmp_path / "outputs"
    outside = tmp_path / "outside" / "result.json"

    with pytest.raises(PathNotAllowedError):
        require_output_path(outside, root)


def test_require_workflow_path_accepts_allowed_root(tmp_path: Path):
    allowed = tmp_path / "scratch"
    stack = allowed / "stack.txt"
    allowed.mkdir()
    stack.write_text("", encoding="utf-8")

    assert require_workflow_path(stack, allowed_roots=[allowed], must_exist=True) == stack.resolve()
