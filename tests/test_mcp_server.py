import asyncio
import json
from pathlib import Path

from dqmc_mcp_server import build_server


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


def test_mcp_tool_set_has_current_hands_surface():
    async def run():
        server = build_server()
        tools = await server.list_tools()
        return {tool.name for tool in tools}

    assert _run(run()) == {
        "summarize_run",
        "inspect_hdf5",
        "read_dataset",
        "resolve_registry_entry",
        "read_registered_quantity",
        "estimate_registered_observable",
        "list_script_adapters",
        "describe_script_adapter",
        "run_script_adapter",
        "query_slurm",
        "query_slurm_history",
        "get_slurm_job_detail",
        "infer_slurm_path_candidates",
        "sync_sherlock_artifacts",
    }


def test_mcp_descriptions_match_current_registry_and_run_rules():
    async def run():
        server = build_server()
        return await server.list_tools()

    descriptions = {tool.name: tool.description or "" for tool in _run(run())}
    assert "list_runs" not in descriptions
    assert "code.generation.variable" in descriptions["resolve_registry_entry"]
    assert "not HDF5 tree discovery" in descriptions["inspect_hdf5"]
    assert "does not estimate observable errors" in descriptions["read_registered_quantity"]
    assert "jackknife" in descriptions["estimate_registered_observable"]
    assert "explicit user_confirmation" in descriptions["run_script_adapter"]
    assert "grouped summary by job name and array job id" in descriptions["query_slurm"]
    assert "local sacct" in descriptions["query_slurm_history"]
    assert "current squeue first" in descriptions["get_slurm_job_detail"]
    assert "path candidates" in descriptions["infer_slurm_path_candidates"]
    assert "dry-run" in descriptions["sync_sherlock_artifacts"]


def test_resolve_registry_entry_uses_real_registry_shape():
    async def run():
        server = build_server()
        return await server.call_tool("resolve_registry_entry", {"name": "density"})

    payload = _tool_json(_run(run()))
    assert payload["id"] == "density"
    assert payload["entry_type"] == "observable"
    assert payload["dataset_key"] == "meas_eqlt/density"
    assert payload["code"]["generation"]["variable"] == "meas_eqlt/density"
    assert "repo_id" not in payload
    assert "h5_path" not in payload


def test_resolve_registry_entry_returns_json_safe_error():
    async def run():
        server = build_server()
        return await server.call_tool("resolve_registry_entry", {"name": "not-a-real-entry"})

    payload = _tool_json(_run(run()))
    assert payload["ok"] is False
    assert payload["error_type"] == "registry_not_found"
    assert payload["details"]["name"] == "not-a-real-entry"


def test_mcp_registry_path_reads_updated_registry_without_server_rebuild(tmp_path: Path):
    registry_path = tmp_path / "registry.yaml"

    def write_registry(entry_id: str, dataset_key: str) -> None:
        registry_path.write_text(
            f"""
observables:
  - id: {entry_id}
    aliases: [hot_density]
    code:
      generation:
        variable: {dataset_key}
parameters: []
""".strip(),
            encoding="utf-8",
        )

    async def run():
        server = build_server()
        write_registry("mcp_first", "meas_eqlt/mcp_first")
        first = _tool_json(
            await server.call_tool(
                "resolve_registry_entry",
                {"name": "hot_density", "registry_path": str(registry_path)},
            )
        )
        write_registry("mcp_second", "meas_eqlt/mcp_second")
        second = _tool_json(
            await server.call_tool(
                "resolve_registry_entry",
                {"name": "hot_density", "registry_path": str(registry_path)},
            )
        )
        return first, second

    first, second = _run(run())

    assert first["id"] == "mcp_first"
    assert first["dataset_key"] == "meas_eqlt/mcp_first"
    assert second["id"] == "mcp_second"
    assert second["dataset_key"] == "meas_eqlt/mcp_second"


def test_describe_script_adapter_exposes_secondary_script_preflight():
    async def run():
        server = build_server()
        return await server.call_tool("describe_script_adapter", {"script_id": "plot_JNJN"})

    payload = _tool_json(_run(run()))
    assert payload["script_id"] == "plot_JNJN"
    assert payload["approval_required"] is True
    assert payload["required_inputs"] == [
        {
            "name": "JNJN_perbin",
            "kind": "npy",
            "path_template": "{path}/JNJN_xx_perbin.npy",
            "required": True,
            "shape_hint": [None, None],
        }
    ]


def test_run_script_adapter_requires_approval_for_execution():
    async def run():
        server = build_server()
        return await server.call_tool(
            "run_script_adapter",
            {
                "script_id": "run_stack_owners",
                "params": {},
                "dry_run": False,
            },
        )

    payload = _tool_json(_run(run()))
    assert payload["ok"] is False
    assert payload["error_type"] == "user_approval_required"
