from __future__ import annotations
import json
from typing import Any
from agents import Agent, Runner
from agents.exceptions import MaxTurnsExceeded
from openai.types.responses import ResponseTextDeltaEvent
from app import agent_config


RunResponse = dict[str, Any]

def get_agent() -> Agent:
    return agent_config.build_agent()


def _make_ok_response(final_output: str, thread_id: str | None = None) -> RunResponse:
    return {
        "ok": True,
        "final_output": final_output,
        "thread_id": thread_id,
    }

def _make_error_response(
    error_type: str,
    message: str,
    thread_id: str | None = None,
) -> RunResponse:
    return {
        "ok": False,
        "error_type": error_type,
        "message": message,
        "thread_id": thread_id,
    }

def _make_stream_event(
        event_type: str, 
        thread_id: str | None = None, 
        **payload: Any
) -> dict[str, Any]:
    event = {
        "type": event_type,
        "thread_id": thread_id,
    }
    event.update(payload)
    return event

def _summarize_run_item(item: Any) -> str:
    item_type = type(item).__name__
    if hasattr(item, "raw_item"):
        raw_item = getattr(item, "raw_item")
        raw_type = getattr(raw_item, "type", None)
        if raw_type:
            return f"{item_type} ({raw_type})"
    return item_type


def _preview_text(value: Any, limit: int = 300) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "..."


def _extract_tool_info(item: Any) -> dict[str, Any]:
    raw_item = getattr(item, "raw_item", None)
    raw_type = getattr(raw_item, "type", None)

    tool_name = (
        getattr(raw_item, "name", None)
        or getattr(item, "name", None)
        or getattr(raw_item, "tool_name", None)
        or getattr(item, "tool_name", None)
        or "unknown_tool"
    )

    arguments = (
        getattr(raw_item, "arguments", None)
        or getattr(item, "arguments", None)
        or getattr(raw_item, "input", None)
        or getattr(item, "input", None)
    )

    output = (
        getattr(raw_item, "output", None)
        or getattr(item, "output", None)
    )

    return {
        "raw_type": raw_type,
        "tool_name": tool_name,
        "arguments_preview": _preview_text(arguments),
        "output_preview": _preview_text(output),
    }


def _to_sse(event: dict[str, Any]) -> str:
    event_name = event.get("type", "message")
    payload = json.dumps(event, ensure_ascii=False)
    return f"event: {event_name}\ndata: {payload}\n\n"

def _map_stream_event(
    event: Any,
    thread_id: str | None = None,
    stream_state: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Convert SDK stream events into a smaller client-facing event protocol.

    Mapping policy:
    - raw text deltas become `text_delta`
    - agent switches become `commentary`
    - the first reasoning item becomes `reasoning_summary`
    - run-item semantic events become `tool_start`, `tool_result`, or `commentary`
    """
    out: list[dict[str, Any]] = []
    state = stream_state or {}

    if event.type == "raw_response_event":
        if isinstance(event.data, ResponseTextDeltaEvent):
            out.append(
                _make_stream_event(
                    "text_delta",
                    thread_id=thread_id,
                    data=event.data.delta,
                )
            )
        return out

    if event.type == "agent_updated_stream_event":
        new_agent = getattr(event, "new_agent", None)
        agent_name = getattr(new_agent, "name", "unknown_agent")
        out.append(
            _make_stream_event(
                "commentary",
                thread_id=thread_id,
                data=f"Switched to agent: {agent_name}",
            )
        )
        return out

    if event.type == "run_item_stream_event":
        name = getattr(event, "name", "unknown")
        item = getattr(event, "item", None)
        item_summary = _summarize_run_item(item) if item is not None else "unknown_item"

        if name == "reasoning_item_created":
            if not state.get("reasoning_started", False):
                state["reasoning_started"] = True
                out.append(
                    _make_stream_event(
                        "reasoning_summary",
                        thread_id=thread_id,
                        data="Agent is reasoning...",
                    )
                )
            return out

        if name in {"tool_called", "tool_search_called", "mcp_list_tools"}:
            info = _extract_tool_info(item)
            out.append(
                _make_stream_event(
                    "tool_start",
                    thread_id=thread_id,
                    tool_name=info["tool_name"],
                    raw_type=info["raw_type"],
                    arguments_preview=info["arguments_preview"],
                    summary=item_summary,
                )
            )
        elif name in {"tool_output", "tool_search_output_created"}:
            info = _extract_tool_info(item)
            out.append(
                _make_stream_event(
                    "tool_result",
                    thread_id=thread_id,
                    tool_name=info["tool_name"],
                    raw_type=info["raw_type"],
                    output_preview=info["output_preview"],
                    summary=item_summary,
                )
            )
        elif name in {
            "message_output_created",
            "handoff_requested",
            "handoff_occured",
            "mcp_approval_requested",
            "mcp_approval_response",
        }:
            out.append(
                _make_stream_event(
                    "commentary",
                    thread_id=thread_id,
                    data=f"{name}: {item_summary}",
                )
            )
        else:
            out.append(
                _make_stream_event(
                    "commentary",
                    thread_id=thread_id,
                    data=f"stream event: {name} ({item_summary})",
                )
            )

    return out


def run_once(
    agent: Agent | None,
    user_input: str,
    thread_id: str | None = None,
    max_turns: int = 30,
) -> RunResponse:
    """Run one synchronous agent turn and normalize the result.

    Current role:
    - provide a single reusable execution entry point for CLI and tests
    - keep error normalization out of main.py

    Later this can grow to support:
    - session / memory injection
    - run IDs
    - cancellation
    - streaming event conversion for FastAPI + SSE
    """
    active_agent = agent or get_agent()

    try:
        result = Runner.run_sync(active_agent, user_input, max_turns=max_turns)
        return _make_ok_response(result.final_output, thread_id=thread_id)
    except MaxTurnsExceeded:
        return _make_error_response(
            "max_turns_exceeded",
            "Max turns exceeded. The agent likely kept searching instead of converging.",
            thread_id=thread_id,
        )
    except Exception as exc:
        return _make_error_response(
            "exception",
            str(exc),
            thread_id=thread_id,
        )


async def stream_run(
    agent: Agent | None,
    user_input: str,
    thread_id: str | None = None,
    max_turns: int = 30,
):
    """Run the agent with the SDK streaming interface and yield client-facing events.

    This version uses `Runner.run_streamed(...)` and consumes `result.stream_events()`.
    It is the correct bridge layer for a future FastAPI + SSE endpoint.

    Notes:
    - `final_output` is only stable after `stream_events()` finishes.
    - streamed terminal failures are raised while consuming the iterator.
    - later we can add run IDs and `result.cancel(...)` for user-triggered interruption.
    """
    active_agent = agent or get_agent()
    result = Runner.run_streamed(active_agent, user_input, max_turns=max_turns)
    stream_state: dict[str, Any] = {"reasoning_started": False}

    yield _to_sse(
        _make_stream_event(
            "commentary",
            thread_id=thread_id,
            data="Starting agent run...",
        )
    )

    try:
        async for event in result.stream_events():
            mapped_events = _map_stream_event(
                event,
                thread_id=thread_id,
                stream_state=stream_state,
            )
            for mapped in mapped_events:
                yield _to_sse(mapped)

        yield _to_sse(
            _make_stream_event(
                "done",
                thread_id=thread_id,
                final_output=result.final_output,
                is_complete=result.is_complete,
            )
        )
    except MaxTurnsExceeded:
        yield _to_sse(
            _make_stream_event(
                "error",
                thread_id=thread_id,
                error_type="max_turns_exceeded",
                message="Max turns exceeded. The agent likely kept searching instead of converging.",
            )
        )
    except Exception as exc:
        yield _to_sse(
            _make_stream_event(
                "error",
                thread_id=thread_id,
                error_type="exception",
                message=str(exc),
            )
        )