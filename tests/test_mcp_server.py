import asyncio
import json

from dqmc_mcp_server import build_server


def _tool_result_json(result):
    if isinstance(result, tuple):
        result = result[0]
    assert len(result) == 1
    return json.loads(result[0].text)


def test_mcp_server_registers_phase_8_tools():
    async def run():
        server = build_server()
        tools = await server.list_tools()
        return {tool.name: tool.description for tool in tools}

    descriptions = asyncio.run(run())

    assert set(descriptions) == {
        "list_runs",
        "inspect_hdf5",
        "resolve_observable",
        "read_observable",
        "summarize_run",
        "query_slurm",
    }
    assert "fails closed" in descriptions["list_runs"]
    assert "read-only" in descriptions["query_slurm"]


def test_mcp_resolve_observable_forwards_to_dqmc_tools():
    async def run():
        server = build_server()
        return await server.call_tool("resolve_observable", {"name": "EqLt.density"})

    payload = _tool_result_json(asyncio.run(run()))

    assert payload["repo_id"] == "EqLt.density"
    assert payload["h5_path"] == "/meas_eqlt/density"


def test_mcp_errors_are_json_safe():
    async def run():
        server = build_server()
        return await server.call_tool("resolve_observable", {"name": "missing"})

    payload = _tool_result_json(asyncio.run(run()))

    assert payload["ok"] is False
    assert payload["error_type"] == "observable_not_found"
    assert payload["details"] == {"name": "missing"}
