from pathlib import Path
import os
import subprocess
import sys

import pytest

from dqmc_tools.config import DQMC_DEV_ROOT_ENV, get_dqmc_dev_root
from dqmc_tools.errors import DQMCError


def test_get_dqmc_dev_root_reads_required_env_var(tmp_path: Path, monkeypatch):
    dqmc_dev = tmp_path / "dqmc-dev"
    dqmc_dev.mkdir()
    monkeypatch.setenv(DQMC_DEV_ROOT_ENV, str(dqmc_dev))

    assert get_dqmc_dev_root() == dqmc_dev.resolve()


def test_get_dqmc_dev_root_fails_when_env_var_is_missing(monkeypatch):
    monkeypatch.delenv(DQMC_DEV_ROOT_ENV, raising=False)

    with pytest.raises(DQMCError) as exc_info:
        get_dqmc_dev_root()

    assert exc_info.value.code == "configuration_error"
    assert DQMC_DEV_ROOT_ENV in exc_info.value.message


def test_get_dqmc_dev_root_fails_when_env_var_is_empty(monkeypatch):
    monkeypatch.setenv(DQMC_DEV_ROOT_ENV, "  ")

    with pytest.raises(DQMCError) as exc_info:
        get_dqmc_dev_root()

    assert exc_info.value.code == "configuration_error"
    assert DQMC_DEV_ROOT_ENV in exc_info.value.message


def test_get_dqmc_dev_root_fails_when_configured_path_is_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(DQMC_DEV_ROOT_ENV, str(tmp_path / "missing"))

    with pytest.raises(DQMCError) as exc_info:
        get_dqmc_dev_root()

    assert exc_info.value.code == "configuration_error"


def test_script_catalog_fails_in_fresh_process_without_dqmc_dev_root():
    env = os.environ.copy()
    env.pop(DQMC_DEV_ROOT_ENV, None)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from dqmc_tools.scripts import list_script_adapters\nlist_script_adapters()\n",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode != 0
    assert "configuration_error" in result.stderr or "DQMC_DEV_ROOT" in result.stderr
