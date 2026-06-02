import asyncio
import json

from dqmc_sherlock_gateway_mcp_server import build_server


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


def test_sherlock_gateway_tool_set():
    async def run():
        server = build_server()
        return await server.list_tools()

    tools = {tool.name for tool in _run(run())}

    assert tools == {
        "sherlock_query_slurm",
        "sherlock_query_slurm_history",
        "sherlock_get_slurm_job_detail",
    }


def test_sherlock_query_slurm_description_requires_formatted_summary():
    async def run():
        server = build_server()
        return await server.list_tools()

    descriptions = {tool.name: tool.description or "" for tool in _run(run())}

    assert "formatted_summary" in descriptions["sherlock_query_slurm"]
    assert "user-facing" in descriptions["sherlock_query_slurm"]


def test_sherlock_get_slurm_job_detail_description_requires_formatted_detail():
    async def run():
        server = build_server()
        return await server.list_tools()

    descriptions = {tool.name: tool.description or "" for tool in _run(run())}

    assert "formatted_detail" in descriptions["sherlock_get_slurm_job_detail"]
    assert "direct SSH" in descriptions["sherlock_get_slurm_job_detail"]


def test_sherlock_gateway_data_reading_profile_exposes_summarize_run():
    async def run():
        server = build_server(profile="data-reading")
        return await server.list_tools()

    tools = {tool.name for tool in _run(run())}

    assert tools == {
        "sherlock_query_slurm",
        "sherlock_query_slurm_history",
        "sherlock_get_slurm_job_detail",
        "sherlock_summarize_run",
    }


def test_sherlock_query_slurm_mcp_contract(monkeypatch):
    def fake_call(tool_name, args, *, config=None):
        return {
            "ok": True,
            "remote": {"host": "sherlock", "tool": tool_name},
            "result": {"ok": True, "args": args},
            "formatted_summary": "formatted table",
        }

    monkeypatch.setattr("dqmc_tools.remote_gateway.call_sherlock_tool", fake_call)

    payload = _run(_call_tool("sherlock_query_slurm", {"filters": {"me": True}}))

    assert payload == {
        "ok": True,
        "remote": {"host": "sherlock", "tool": "query_slurm"},
        "result": {"ok": True, "args": {"filters": {"me": True}}},
        "formatted_summary": "formatted table",
    }


def test_sherlock_query_slurm_history_mcp_contract(monkeypatch):
    def fake_call(tool_name, args, *, config=None):
        return {
            "ok": True,
            "remote": {"host": "sherlock", "tool": tool_name},
            "result": {"ok": True, "args": args},
        }

    monkeypatch.setattr("dqmc_tools.remote_gateway.call_sherlock_tool", fake_call)

    payload = _run(_call_tool("sherlock_query_slurm_history", {"filters": {"max_rows": 5}}))

    assert payload["remote"]["tool"] == "query_slurm_history"
    assert payload["result"]["args"] == {"filters": {"max_rows": 5}}


def test_sherlock_get_slurm_job_detail_mcp_contract(monkeypatch):
    def fake_call(tool_name, args, *, config=None):
        return {
            "ok": True,
            "remote": {"host": "sherlock", "tool": tool_name},
            "result": {"ok": True, "args": args},
            "formatted_detail": "formatted detail",
        }

    monkeypatch.setattr("dqmc_tools.remote_gateway.call_sherlock_tool", fake_call)

    payload = _run(_call_tool(
        "sherlock_get_slurm_job_detail",
        {"job_id": "123", "include_history": False},
    ))

    assert payload["remote"]["tool"] == "get_slurm_job_detail"
    assert payload["result"]["args"] == {"job_id": "123", "include_history": False}
    assert payload["formatted_detail"] == "formatted detail"


def test_sherlock_summarize_run_mcp_contract(monkeypatch):
    def fake_call(tool_name, args, *, config=None, **_kwargs):
        return {
            "ok": True,
            "remote": {"host": "sherlock", "tool": tool_name},
            "result": {"ok": True, "args": args},
        }

    monkeypatch.setattr("dqmc_tools.remote_gateway.call_sherlock_tool", fake_call)

    async def call_tool():
        server = build_server(profile="data-reading")
        return _tool_json(await server.call_tool("sherlock_summarize_run", {"path": "/oak/run"}))

    payload = _run(call_tool())

    assert payload["remote"]["tool"] == "summarize_run"
    assert payload["result"]["args"] == {
        "path": "/oak/run",
        "max_files": 5,
        "max_registry_entries": 50,
        "max_log_chars": 1000,
        "allowed_roots": None,
        "registry_path": None,
    }


def test_sherlock_gateway_mcp_returns_json_safe_gateway_error(monkeypatch):
    def fake_call(_tool_name, _args, *, config=None):
        raise RuntimeError("boom")

    monkeypatch.setattr("dqmc_tools.remote_gateway.call_sherlock_tool", fake_call)

    payload = _run(_call_tool("sherlock_query_slurm"))

    assert payload == {
        "ok": False,
        "error_type": "RuntimeError",
        "message": "boom",
        "details": {},
    }


def test_run_main_starts_auth_monitor_before_mcp_run(monkeypatch):
    import dqmc_sherlock_gateway_mcp_server as server_module

    events = []

    monkeypatch.setattr(
        server_module.sherlock_auth,
        "start_monitor_from_env",
        lambda: events.append("monitor"),
    )
    monkeypatch.setattr(server_module.mcp, "run", lambda: events.append("run"))

    server_module.run_main()

    assert events == ["monitor", "run"]
