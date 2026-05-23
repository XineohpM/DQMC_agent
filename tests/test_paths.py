from pathlib import Path

import pytest

from dqmc_tools.config import ALLOWED_ROOTS_ENV, OUTPUT_ROOT_ENV, get_allowed_roots
from dqmc_tools.errors import PathNotAllowedError, PathResolutionError
from dqmc_tools.paths import (
    require_allowed_path,
    require_output_path,
    resolve_existing_path,
)


def test_resolve_existing_path(tmp_path: Path):
    target = tmp_path / "run.h5"
    target.write_text("placeholder", encoding="utf-8")

    assert resolve_existing_path(target) == target.resolve()


def test_resolve_existing_path_missing(tmp_path: Path):
    with pytest.raises(PathResolutionError):
        resolve_existing_path(tmp_path / "missing.h5")


def test_require_allowed_path_accepts_path_inside_root(tmp_path: Path):
    root = tmp_path / "scratch"
    run = root / "run1"
    run.mkdir(parents=True)

    assert require_allowed_path(run, [root]) == run.resolve()


def test_require_allowed_path_fails_closed_without_roots(tmp_path: Path, monkeypatch):
    run = tmp_path / "run1"
    run.mkdir()
    monkeypatch.delenv(ALLOWED_ROOTS_ENV, raising=False)

    with pytest.raises(PathNotAllowedError) as exc:
        require_allowed_path(run)

    assert exc.value.details["env_var"] == ALLOWED_ROOTS_ENV


def test_require_allowed_path_rejects_outside_path(tmp_path: Path):
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()

    with pytest.raises(PathNotAllowedError):
        require_allowed_path(outside, [allowed])


def test_allowed_roots_can_come_from_environment(tmp_path: Path, monkeypatch):
    root = tmp_path / "scratch"
    root.mkdir()
    monkeypatch.setenv(ALLOWED_ROOTS_ENV, str(root))

    assert get_allowed_roots() == [root]
    assert require_allowed_path(root) == root.resolve()


def test_require_output_path_places_relative_path_under_root(tmp_path: Path):
    output_root = tmp_path / "outputs"

    result = require_output_path("run1/result.json", output_root)

    assert result == (output_root / "run1" / "result.json").resolve(strict=False)


def test_require_output_path_rejects_absolute_path_outside_root(tmp_path: Path):
    output_root = tmp_path / "outputs"
    outside = tmp_path / "outside" / "result.json"

    with pytest.raises(PathNotAllowedError):
        require_output_path(outside, output_root)


def test_require_output_path_uses_environment(tmp_path: Path, monkeypatch):
    output_root = tmp_path / "outputs"
    monkeypatch.setenv(OUTPUT_ROOT_ENV, str(output_root))

    assert require_output_path("x.txt") == (output_root / "x.txt").resolve(strict=False)
