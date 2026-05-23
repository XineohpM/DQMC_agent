# Existing App Integration Decision

## Decision

Do not wire `dqmc_tools` into the existing `app/agent_config.py` demo in v1.

The primary integration surface for the hands layer is the MCP adapter in
`dqmc_mcp_server.py`. The existing `app/` code remains a repo-question-answering
demo built on the OpenAI Agents SDK and offline repo indexes. It should not own,
wrap, or constrain the core DQMC hands package during the first MCP milestone.

## Rationale

- The v1 goal is a platform-neutral Python package plus MCP server.
- Adding OpenAI Agents SDK wrappers now would create a second tool surface before
  the MCP surface has been exercised by Phoenix.
- The existing `app/` startup requires `REPO_PATH` and is centered on target-repo
  retrieval, while `dqmc_tools` is centered on runtime DQMC files, run
  directories, and cluster status.
- Keeping the layers separate preserves the rule that `dqmc_tools` must be
  usable directly from Python/Jupyter without importing `app/`, FastAPI, the
  frontend, or OpenAI Agents SDK code.

## Future Trigger

Revisit this decision only if Phoenix needs the old web/CLI demo to expose the
same DQMC hands tools. If that happens, add a separate adapter module that wraps
`dqmc_tools` functions for the OpenAI Agents SDK, mirroring the MCP adapter while
keeping all domain logic in `dqmc_tools`.

## Verification

The existing import-boundary test continues to assert that importing
`dqmc_tools` does not import `app.agent_config`, `agents`, `fastapi`, or `mcp`.
