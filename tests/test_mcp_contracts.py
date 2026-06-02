import asyncio
import json
import subprocess
from pathlib import Path

from dqmc_mcp_server import build_server


ROOT = Path(__file__).resolve().parents[1]
REAL_T01 = ROOT / "data" / "T_0.1"
REAL_T01_FIRST_H5 = REAL_T01 / "C_U-6_T0.1__0.h5"


def _run(coro):
    return asyncio.run(coro)


def _tool_json(result):
    if isinstance(result, tuple):
        content, structured = result
        if structured is not None:
            return structured
        result = content
    assert len(result) == 1
    return json.loads(result[0].text)


async def _call_tool(name: str, arguments: dict | None = None):
    server = build_server()
    return _tool_json(await server.call_tool(name, arguments or {}))


def test_summarize_run_mcp_output_contract_on_real_fixture():
    payload = _run(_call_tool(
        "summarize_run",
        {
            "path": str(REAL_T01),
            "allowed_roots": [str(REAL_T01)],
            "max_files": 1,
            "max_registry_entries": 8,
            "max_log_chars": 80,
        },
    ))

    assert set(payload) == {
        "ok",
        "path",
        "name",
        "hdf5_file_count",
        "reported_hdf5_file_count",
        "hdf5_files_truncated",
        "hdf5_files",
        "metadata",
        "available_registry_entries",
        "missing_registry_entries",
        "limits",
    }
    assert payload["ok"] is True
    assert payload["path"] == str(REAL_T01.resolve())
    assert payload["hdf5_file_count"] == 100
    assert payload["reported_hdf5_file_count"] == 1
    assert payload["hdf5_files_truncated"] is True
    assert payload["limits"] == {
        "max_files": 1,
        "max_registry_entries": 8,
        "max_log_chars": 80,
    }

    hdf5_file = payload["hdf5_files"][0]
    assert set(hdf5_file) == {"path", "relative_path", "size_bytes", "log"}
    assert set(hdf5_file["log"]) == {
        "exists",
        "path",
        "size_bytes",
        "tail",
        "has_saving_data_marker",
        "has_save_success_marker",
        "last_sweep",
    }
    assert payload["metadata"]["metadata/beta"] == 10.0
    assert isinstance(payload["available_registry_entries"], list)
    assert isinstance(payload["missing_registry_entries"], list)


def test_hdf5_mcp_read_contracts_on_real_fixture():
    read_dataset = _run(_call_tool(
        "read_dataset",
        {
            "path": str(REAL_T01_FIRST_H5),
            "dataset_key": "meas_eqlt/density",
            "allowed_roots": [str(REAL_T01)],
        },
    ))
    assert set(read_dataset) == {"ok", "path", "mode", "util_function", "dataset_key", "dataset"}
    assert read_dataset["ok"] is True
    assert read_dataset["mode"] == "file"
    assert read_dataset["util_function"] == "load_file"
    assert read_dataset["dataset_key"] == "meas_eqlt/density"
    assert set(read_dataset["dataset"]) == {
        "shape",
        "dtype",
        "size",
        "truncated",
        "preview",
        "value",
        "min",
        "max",
        "mean",
    }

    inspect = _run(_call_tool(
        "inspect_hdf5",
        {
            "path": str(REAL_T01_FIRST_H5),
            "dataset_keys": ["density", "meas_eqlt/sign"],
            "allowed_roots": [str(REAL_T01)],
        },
    ))
    assert set(inspect) == {"ok", "path", "mode", "util_function", "datasets", "errors", "limits"}
    assert inspect["ok"] is True
    assert inspect["errors"] == []
    assert inspect["limits"] == {"max_items": 1024}
    assert [item["dataset_key"] for item in inspect["datasets"]] == [
        "meas_eqlt/density",
        "meas_eqlt/sign",
    ]

    registered = _run(_call_tool(
        "read_registered_quantity",
        {
            "path": str(REAL_T01_FIRST_H5),
            "name": "density",
            "allowed_roots": [str(REAL_T01)],
        },
    ))
    assert set(registered) == {
        "ok",
        "path",
        "mode",
        "util_function",
        "registry_entry",
        "dataset_key",
        "candidate_dataset_keys",
        "dataset",
        "error",
        "error_note",
    }
    assert registered["ok"] is True
    assert registered["error"] is None
    assert registered["error_note"] == "Single-file/direct reads do not estimate observable errors."
    assert registered["registry_entry"]["id"] == "density"
    assert registered["dataset_key"] == "meas_eqlt/density"


def test_estimate_registered_observable_mcp_output_contract_on_real_fixture():
    payload = _run(_call_tool(
        "estimate_registered_observable",
        {
            "directory": str(REAL_T01),
            "observable_name": "density",
            "allowed_roots": [str(REAL_T01)],
            "max_items": 16,
        },
    ))

    assert set(payload) == {
        "ok",
        "directory",
        "registry_entry",
        "dataset_keys",
        "estimator",
        "util_function",
        "hdf5_file_count",
        "estimate",
        "raw_estimate",
    }
    assert payload["ok"] is True
    assert payload["directory"] == str(REAL_T01.resolve())
    assert payload["registry_entry"]["id"] == "density"
    assert payload["dataset_keys"] == {
        "value": "meas_eqlt/density",
        "sign": "meas_eqlt/sign",
        "n_sample": "meas_eqlt/n_sample",
    }
    assert payload["estimator"] == "jackknife"
    assert payload["util_function"] == "jackknife"
    assert payload["hdf5_file_count"] == 100
    assert set(payload["estimate"]) == {"mean", "error", "shape"}
    assert set(payload["raw_estimate"]) >= {"shape", "dtype", "size", "truncated", "preview"}


def test_script_adapter_mcp_contracts_for_list_describe_and_dry_run(tmp_path: Path):
    list_payload = _run(_call_tool("list_script_adapters"))
    assert set(list_payload) == {"result"}
    scripts = list_payload["result"]
    assert isinstance(scripts, list)
    assert len(scripts) == 21
    assert all("args_schema" not in item for item in scripts)
    assert set(scripts[0]) == {
        "script_id",
        "description",
        "category",
        "mode",
        "path",
        "parser_id",
        "requires_output_root",
        "approval_required",
        "required_inputs",
        "output_patterns",
        "notes",
    }

    description = _run(_call_tool("describe_script_adapter", {"script_id": "run_maxent_anneal"}))
    assert set(description) == {
        "script_id",
        "description",
        "category",
        "mode",
        "path",
        "parser_id",
        "requires_output_root",
        "approval_required",
        "required_inputs",
        "output_patterns",
        "notes",
        "args_schema",
    }
    assert description["approval_required"] is True
    assert "data_file" in description["args_schema"]["required"]

    output_dir = tmp_path / "warmup"
    dry_run = _run(_call_tool(
        "run_script_adapter",
        {
            "script_id": "check_warm",
            "params": {
                "root": str(REAL_T01),
                "glob": ".",
                "output_dir": str(output_dir),
                "nn": True,
            },
            "cwd": str(ROOT),
            "allowed_roots": [str(ROOT), str(REAL_T01)],
            "output_root": str(tmp_path),
            "dry_run": True,
        },
    ))
    assert set(dry_run) == {
        "ok",
        "script_id",
        "command",
        "cwd",
        "dry_run",
        "preflight",
        "output_root",
        "user_confirmation",
        "returncode",
        "stdout_tail",
        "stderr_tail",
        "output_files",
        "parsed_outputs",
        "warnings",
    }
    assert dry_run["ok"] is True
    assert dry_run["dry_run"] is True
    assert dry_run["returncode"] is None
    assert dry_run["output_files"] == []
    assert dry_run["parsed_outputs"] == {}
    assert output_dir.exists() is False


def test_mcp_error_contracts_are_json_safe(tmp_path: Path):
    path_error = _run(_call_tool(
        "summarize_run",
        {
            "path": str(REAL_T01),
            "allowed_roots": [str(tmp_path)],
        },
    ))
    assert set(path_error) == {"ok", "error_type", "message", "details"}
    assert path_error["ok"] is False
    assert path_error["error_type"] == "path_not_allowed"
    assert set(path_error["details"]) == {"path", "allowed_roots"}

    approval_error = _run(_call_tool(
        "run_script_adapter",
        {
            "script_id": "run_stack_owners",
            "params": {},
            "dry_run": False,
        },
    ))
    assert set(approval_error) == {"ok", "error_type", "message", "details"}
    assert approval_error["ok"] is False
    assert approval_error["error_type"] == "user_approval_required"
    assert approval_error["details"] == {"script_id": "run_stack_owners"}


def test_query_slurm_mcp_success_contract(monkeypatch):
    monkeypatch.setattr("dqmc_tools.slurm.shutil.which", lambda _name: "squeue")

    def fake_run(args, **_kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout='{"jobs": [{"job_id": 123, "name": "dqmc", "job_state": "RUNNING"}]}',
            stderr="",
        )

    monkeypatch.setattr("dqmc_tools.slurm.subprocess.run", fake_run)

    payload = _run(_call_tool("query_slurm", {"filters": {"user": "phoenix"}}))

    assert set(payload) == {
        "ok",
        "source",
        "command",
        "commands_attempted",
        "jobs",
        "summary",
        "groups",
        "raw",
    }
    assert payload["ok"] is True
    assert payload["source"] == "squeue_json"
    assert payload["jobs"] == [{"job_id": 123, "name": "dqmc", "job_state": "RUNNING"}]
    assert "--user" in payload["command"]
    assert payload["summary"] == {
        "total_jobs": 1,
        "state_counts": {"RUNNING": 1},
        "category_counts": {"running": 1},
        "job_name_count": 1,
        "array_job_count": 1,
    }
    assert payload["groups"]["by_job_name"][0]["job_name"] == "dqmc"
    assert payload["raw"] == {"jobs": payload["jobs"]}


def test_query_slurm_mcp_error_contract(monkeypatch):
    monkeypatch.setattr("dqmc_tools.slurm.shutil.which", lambda _name: None)

    payload = _run(_call_tool("query_slurm"))

    assert set(payload) == {"ok", "error_type", "message", "details"}
    assert payload["ok"] is False
    assert payload["error_type"] == "tool_unavailable"
    assert payload["details"] == {"command": "squeue"}


def test_query_slurm_history_mcp_success_contract(monkeypatch):
    monkeypatch.setattr("dqmc_tools.slurm.shutil.which", lambda _name: "sacct")

    def fake_run(args, **_kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=(
                "123|dqmc|phoenix|COMPLETED|0:0|00:10:00|01:00:00|"
                "2026-05-26T10:00:00|2026-05-26T10:01:00|2026-05-26T10:11:00|normal|node001|/oak/run123\n"
            ),
            stderr="",
        )

    monkeypatch.setattr("dqmc_tools.slurm.subprocess.run", fake_run)

    payload = _run(_call_tool("query_slurm_history", {"filters": {"user": "phoenix"}}))

    assert set(payload) == {"ok", "source", "command", "jobs", "summary", "warnings"}
    assert payload["ok"] is True
    assert payload["source"] == "sacct_parsable2"
    assert payload["jobs"][0]["job_id"] == "123"
    assert payload["summary"]["state_counts"] == {"COMPLETED": 1}
    assert payload["summary"]["exit_code_counts"] == {"0:0": 1}


def test_query_slurm_history_mcp_error_contract(monkeypatch):
    monkeypatch.setattr("dqmc_tools.slurm.shutil.which", lambda _name: None)

    payload = _run(_call_tool("query_slurm_history"))

    assert set(payload) == {"ok", "error_type", "message", "details"}
    assert payload["ok"] is False
    assert payload["error_type"] == "tool_unavailable"
    assert payload["details"] == {"command": "sacct"}


def test_get_slurm_job_detail_mcp_success_contract(monkeypatch):
    monkeypatch.setattr(
        "dqmc_tools.slurm.query_slurm",
        lambda filters=None: {
            "ok": True,
            "source": "squeue_json",
            "command": ["squeue", "--json", "--jobs", filters["job_id"]],
            "jobs": [{"job_id": 123, "name": "dqmc", "job_state": "RUNNING"}],
        },
    )
    monkeypatch.setattr(
        "dqmc_tools.slurm.query_slurm_history",
        lambda _filters=None: (_ for _ in ()).throw(AssertionError("history should not be queried")),
    )

    payload = _run(_call_tool("get_slurm_job_detail", {"job_id": "123"}))

    assert set(payload) == {
        "ok",
        "job_id",
        "include_history",
        "match_count",
        "multiple_matches",
        "candidates",
        "queries",
        "warnings",
    }
    assert payload["ok"] is True
    assert payload["job_id"] == "123"
    assert payload["match_count"] == 1
    assert payload["candidates"][0]["source"] == "squeue"
    assert payload["candidates"][0]["state"] == "RUNNING"


def test_get_slurm_job_detail_mcp_error_contract():
    payload = _run(_call_tool("get_slurm_job_detail", {"job_id": " "}))

    assert set(payload) == {"ok", "error_type", "message", "details"}
    assert payload["ok"] is False
    assert payload["error_type"] == "invalid_argument"
    assert payload["details"] == {"job_id": " "}


def test_infer_slurm_path_candidates_mcp_success_contract(tmp_path: Path):
    run_path = tmp_path / "run123"
    run_path.mkdir()

    payload = _run(_call_tool(
        "infer_slurm_path_candidates",
        {
            "job_detail": {
                "candidates": [
                    {
                        "source": "sacct",
                        "job_id": "123",
                        "work_dir": str(run_path),
                    }
                ],
            },
            "allowed_roots": [str(tmp_path)],
        },
    ))

    assert set(payload) == {"ok", "path_candidates", "warnings"}
    assert payload["ok"] is True
    assert payload["path_candidates"] == [
        {
            "path": str(run_path.resolve()),
            "confidence": "high",
            "evidence": "sacct.WorkDir",
            "accessible": True,
            "within_allowed_roots": True,
            "rejection_reason": "",
            "source_job_id": "123",
        }
    ]
    assert payload["warnings"] == []


def test_sync_sherlock_artifacts_mcp_success_contract(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("dqmc_tools.sync.shutil.which", lambda _name: "rsync")

    def fake_run(args, **_kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=">f+++++++++ result.h5\n",
            stderr="",
        )

    monkeypatch.setattr("dqmc_tools.sync.subprocess.run", fake_run)

    payload = _run(_call_tool(
        "sync_sherlock_artifacts",
        {
            "remote_host": "sherlock",
            "remote_path": "/oak/user/run1",
            "remote_allowed_hosts": ["sherlock"],
            "remote_allowed_roots": ["/oak/user"],
            "local_subdir": "run1",
            "output_root": str(tmp_path),
            "dry_run": True,
        },
    ))

    assert set(payload) == {
        "ok",
        "dry_run",
        "command",
        "remote",
        "destination",
        "user_confirmation",
        "manifest",
        "stdout_tail",
        "stderr_tail",
        "warnings",
    }
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["manifest"]["created"] == [
        {"path": "result.h5", "change": "created", "itemize": ">f+++++++++"}
    ]


def test_sync_sherlock_artifacts_mcp_approval_error_contract(tmp_path: Path):
    payload = _run(_call_tool(
        "sync_sherlock_artifacts",
        {
            "remote_host": "sherlock",
            "remote_path": "/oak/user/run1",
            "remote_allowed_hosts": ["sherlock"],
            "remote_allowed_roots": ["/oak/user"],
            "output_root": str(tmp_path),
            "dry_run": False,
        },
    ))

    assert set(payload) == {"ok", "error_type", "message", "details"}
    assert payload["ok"] is False
    assert payload["error_type"] == "user_approval_required"
    assert payload["details"] == {"operation": "sync_sherlock_artifacts"}
