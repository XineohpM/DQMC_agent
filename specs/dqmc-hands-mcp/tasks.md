# DQMC Hands MCP Task Plan

## Status Legend

- `[ ]` Not started
- `[~]` In progress
- `[x]` Complete

## Phase 0: Spec Baseline

- `[x]` Create SDD spec directory.
- `[x]` Define requirements and out-of-scope boundaries.
- `[x]` Define package architecture, tool contracts, and MCP adapter boundary.
- `[x]` Review spec with Phoenix/user and resolve open questions that affect v1 implementation.

Exit criteria:

- Requirements, design, and tasks are committed.
- The first implementation milestone can be started without re-discussing the whole architecture.

## Phase 1: Python Package Skeleton

- `[x]` Create `dqmc_tools/` package.
- `[x]` Add `dqmc_tools/__init__.py` with a minimal public API surface.
- `[x]` Add `dqmc_tools/errors.py` with typed exceptions and JSON-safe error helpers.
- `[x]` Port only small generic helpers from existing code where useful, such as bounded text reads, skipped-directory constants, and generated-output safety checks.
- `[x]` If JSONL helper code is needed later, copy only generic loading/tokenization ideas from `app/io_tools.py`, `app/retrieval.py`, or `app/semantic_tools.py`; do not port scoring or semantic interpretation behavior.
- `[x]` Confirm `dqmc_tools` has no import dependency on `app/`, FastAPI, frontend code, or OpenAI Agents SDK modules.
- `[x]` Add initial `tests/` structure.
- `[x]` Add `pyproject.toml` with narrow core dependencies and optional `test` and `mcp` extras.

Exit criteria:

- `python -m pytest` or the selected test command can discover tests.
- Importing `dqmc_tools` does not require agent, FastAPI, or MCP dependencies.

## Phase 2: Observable Registry

- `[x]` Implement `dqmc_tools.observables.load_observable_registry`.
- `[x]` Implement `list_observables`.
- `[x]` Implement `resolve_observable`.
- `[x]` Support exact `repo_id`, exact HDF5 path, and unambiguous tail-name resolution.
- `[x]` Add ambiguity errors for duplicated tail paths, using a small test registry fixture if the current `formal/observables.yaml` has no natural ambiguous example.
- `[x]` Add tests using `formal/observables.yaml`.

Exit criteria:

- `resolve_observable("EqLt.density")` returns `/meas_eqlt/density`.
- `resolve_observable("density")` resolves only if unambiguous.
- Ambiguous names fail with candidate ids instead of guessing.

## Phase 3: Path Safety

- `[x]` Implement `dqmc_tools.config` for environment-backed defaults.
- `[x]` Implement `resolve_existing_path`.
- `[x]` Implement `require_allowed_path`.
- `[x]` Implement `require_output_path`.
- `[x]` Adapt the restricted-write idea from `app/repo_tools.py`, but make the output root configurable instead of hard-coding `agent_outputs/`.
- `[x]` Enforce fail-closed raw-data access when no allowed roots are configured or explicitly passed.
- `[x]` Add tests for allowed root, rejected outside path, and output root behavior.

Exit criteria:

- All raw-data tools call path safety helpers before reading files or directories.
- Generated outputs cannot be placed outside the configured output root.

## Phase 4: HDF5 Inspection

- `[x]` Add `h5py` and `numpy` dependency handling.
- `[x]` Implement `inspect_hdf5`.
- `[x]` Traverse groups and datasets read-only.
- `[x]` Include shape, dtype, attrs, and bounded previews.
- `[x]` Ensure large arrays are summarized, not fully returned.
- `[x]` Add synthetic HDF5 fixture tests.

Exit criteria:

- Synthetic HDF5 files produce stable JSON-serializable inspection output.
- Inspection does not mutate files.
- Output records truncation when applicable.

## Phase 5: Observable Reading

- `[x]` Implement `read_dataset`.
- `[x]` Implement `read_observable`.
- `[x]` Extract factual metadata from common `metadata/*`, `params/*`, `meas_eqlt/*`, and `meas_uneqlt/*` paths when present.
- `[x]` Use parameter-name and HDF5-family ideas from `app/build_io_index.py` as hints only; always read facts from the actual HDF5 file.
- `[x]` Return numeric summaries and bounded previews.
- `[x]` Avoid scientific labels or recommendations.
- `[x]` Add tests for successful read, missing dataset, and metadata extraction.

Exit criteria:

- `read_observable(sample_h5, "EqLt.density")` returns dataset facts and registry metadata.
- Missing registered dataset errors are structured and actionable.

## Phase 6: Run Discovery and Summary

- `[x]` Implement `list_runs`.
- `[x]` Implement conservative run candidate detection.
- `[x]` Implement supported filters.
- `[x]` Implement `summarize_run`.
- `[x]` Report available and missing registered observable paths per HDF5 file.
- `[x]` Add tests using temporary directory trees and synthetic HDF5 files.

Exit criteria:

- Run listing is bounded and filterable.
- Run summary reuses HDF5 and observable modules rather than duplicating logic.

## Phase 7: Read-only SLURM Query

- `[x]` Implement `query_slurm`.
- `[x]` Prefer JSON output where available.
- `[x]` Add fallback parser for a stable custom `squeue` format.
- `[x]` Return unavailable errors when SLURM commands are missing.
- `[x]` Add tests that mock subprocess results.

Exit criteria:

- No SLURM submit/cancel behavior exists in v1.
- Query output is structured and records command arguments.

## Phase 8: MCP Adapter

- `[x]` Use the official Python MCP SDK via `mcp.server.fastmcp.FastMCP`.
- `[x]` Add `dqmc_mcp_server.py`.
- `[x]` Register `list_runs`.
- `[x]` Register `inspect_hdf5`.
- `[x]` Register `resolve_observable`.
- `[x]` Register `read_observable`.
- `[x]` Register `summarize_run`.
- `[x]` Register `query_slurm`.
- `[x]` Write tool descriptions following the description standard in `design.md`.
- `[x]` Use `app/agent_config.py` only as a writing-quality reference for descriptions; avoid copying workflow rules or repo-agent-specific instructions.
- `[x]` Add minimal MCP forwarding tests if supported by the selected SDK.

Exit criteria:

- MCP adapter contains no domain logic beyond validation and forwarding.
- The same functions remain directly importable from Python without MCP.

## Phase 9: Analysis Registry

- `[x]` Create `dqmc_tools/analyses/registry.py`.
- `[x]` Define analysis metadata schema.
- `[x]` Reuse the validation style from `formal/scripts/check_formal_registry.py`: required fields, duplicate-id checks, and clear schema errors.
- `[x]` Implement `list_analyses`.
- `[x]` Implement `run_analysis` for registry entries only.
- `[x]` Add the first real analysis only after Phoenix identifies a concrete workflow.

Exit criteria:

- Arbitrary script paths are rejected.
- Analysis outputs are created only under the configured output root.

## Phase 10: Optional Existing App Integration

- `[x]` Decide whether current `app/agent_config.py` should expose `dqmc_tools` tools directly.
- `[x]` Do not add OpenAI Agents SDK wrappers in v1.
- `[x]` Keep any future wrappers thin and avoid duplicating MCP descriptions.
- `[x]` Leave frontend/demo docs unchanged because the existing app is not the v1 integration surface.

Decision:

- Do not expose `dqmc_tools` through the existing OpenAI Agents SDK app in v1.
- Keep MCP as the primary integration surface.
- Keep current `app/` and frontend demo unchanged.

Exit criteria:

- Core `dqmc_tools` package remains independent of the existing agent app.

## Verification Commands

Initial commands, subject to dependency setup:

```powershell
python -m pytest
python -m py_compile dqmc_mcp_server.py
python -m py_compile dqmc_tools\observables.py
python -m py_compile dqmc_tools\hdf5.py
```

Existing formal registry check, useful before implementing observable loading:

```powershell
python formal\scripts\check_formal_registry.py
```

## Commit Plan

Suggested commits:

1. `Add DQMC hands SDD specs`
2. `Scaffold dqmc_tools package`
3. `Load and resolve observable registry`
4. `Add path safety helpers`
5. `Inspect HDF5 files read-only`
6. `Read registered observables from HDF5`
7. `Discover and summarize DQMC runs`
8. `Add read-only SLURM query tool`
9. `Expose dqmc_tools through MCP`
10. `Add whitelisted analysis registry`

## Current Open Decisions

- Exact path allowlist values for Phoenix's scratch/home environment.
- Canonical precedence when `metadata/*` and `params/*` duplicate related HDF5 values.
- First analysis whitelist entries, deferred until Phoenix identifies concrete repeated workflows.
