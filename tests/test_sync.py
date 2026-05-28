import subprocess
from pathlib import Path

import pytest

from dqmc_tools.errors import (
    InvalidArgumentError,
    PathNotAllowedError,
    ScriptApprovalRequiredError,
    ToolUnavailableError,
)
from dqmc_tools.sync import sync_sherlock_artifacts


def test_sync_dry_run_builds_rsync_command_and_manifest(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("dqmc_tools.sync.shutil.which", lambda _name: "rsync")

    def fake_run(args, **_kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=(
                ">f+++++++++ new.h5\n"
                ">f.st...... updated.h5\n"
                ".f......... same.h5\n"
                "cd+++++++++ nested/\n"
            ),
            stderr="",
        )

    monkeypatch.setattr("dqmc_tools.sync.subprocess.run", fake_run)

    result = sync_sherlock_artifacts(
        remote_host="sherlock",
        remote_path="/oak/user/run1",
        remote_allowed_hosts=["sherlock"],
        remote_allowed_roots=["/oak/user"],
        local_subdir="sherlock/run1",
        output_root=tmp_path,
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert "--dry-run" in result["command"]
    assert result["command"][-2:] == [
        "sherlock:/oak/user/run1/",
        str((tmp_path / "sherlock" / "run1").resolve(strict=False)),
    ]
    assert result["remote"] == {"host": "sherlock", "path": "/oak/user/run1"}
    assert result["destination"] == str((tmp_path / "sherlock" / "run1").resolve(strict=False))
    assert result["manifest"] == {
        "created": [{"path": "new.h5", "change": "created", "itemize": ">f+++++++++"}],
        "updated": [{"path": "updated.h5", "change": "updated", "itemize": ">f.st......"}],
        "deleted": [],
        "skipped": [{"path": "same.h5", "change": "skipped", "itemize": ".f........."}],
        "unknown": [{"path": "nested/", "change": "unknown", "itemize": "cd+++++++++"}],
        "total_items": 4,
    }


def test_sync_rejects_remote_host_outside_allowlist(tmp_path: Path):
    with pytest.raises(InvalidArgumentError):
        sync_sherlock_artifacts(
            remote_host="other",
            remote_path="/oak/user/run1",
            remote_allowed_hosts=["sherlock"],
            remote_allowed_roots=["/oak/user"],
            output_root=tmp_path,
        )


def test_sync_rejects_remote_path_outside_allowlist(tmp_path: Path):
    with pytest.raises(PathNotAllowedError):
        sync_sherlock_artifacts(
            remote_host="sherlock",
            remote_path="/scratch/user/run1",
            remote_allowed_hosts=["sherlock"],
            remote_allowed_roots=["/oak/user"],
            output_root=tmp_path,
        )


def test_sync_rejects_unsafe_remote_path(tmp_path: Path):
    with pytest.raises(InvalidArgumentError):
        sync_sherlock_artifacts(
            remote_host="sherlock",
            remote_path="../run1",
            remote_allowed_hosts=["sherlock"],
            remote_allowed_roots=["/oak/user"],
            output_root=tmp_path,
        )


def test_sync_rejects_destination_outside_output_root(tmp_path: Path):
    with pytest.raises(PathNotAllowedError):
        sync_sherlock_artifacts(
            remote_host="sherlock",
            remote_path="/oak/user/run1",
            remote_allowed_hosts=["sherlock"],
            remote_allowed_roots=["/oak/user"],
            local_subdir="../escape",
            output_root=tmp_path / "outputs",
        )


def test_sync_requires_approval_for_real_run(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("dqmc_tools.sync.shutil.which", lambda _name: "rsync")

    with pytest.raises(ScriptApprovalRequiredError):
        sync_sherlock_artifacts(
            remote_host="sherlock",
            remote_path="/oak/user/run1",
            remote_allowed_hosts=["sherlock"],
            remote_allowed_roots=["/oak/user"],
            output_root=tmp_path,
            dry_run=False,
        )


def test_sync_real_run_uses_approval_and_omits_dry_run(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("dqmc_tools.sync.shutil.which", lambda _name: "rsync")

    def fake_run(args, **_kwargs):
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("dqmc_tools.sync.subprocess.run", fake_run)

    result = sync_sherlock_artifacts(
        remote_host="sherlock",
        remote_path="/oak/user/run1",
        remote_allowed_hosts=["sherlock"],
        remote_allowed_roots=["/oak/user"],
        output_root=tmp_path,
        dry_run=False,
        user_confirmation={"approved": True, "text": "sync run1"},
    )

    assert "--dry-run" not in result["command"]
    assert result["user_confirmation"] == {"approved": True, "text": "sync run1"}


def test_sync_reports_rsync_unavailable(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("dqmc_tools.sync.shutil.which", lambda _name: None)

    with pytest.raises(ToolUnavailableError):
        sync_sherlock_artifacts(
            remote_host="sherlock",
            remote_path="/oak/user/run1",
            remote_allowed_hosts=["sherlock"],
            remote_allowed_roots=["/oak/user"],
            output_root=tmp_path,
        )
