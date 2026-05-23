# DQMC Hands MCP Task Plan

## Status Legend

- `[ ]` Not started
- `[~]` In progress
- `[x]` Complete

## Phase 0: Spec Baseline

- `[x]` Create SDD spec directory.
- `[x]` Define requirements and out-of-scope boundaries.
- `[x]` Define package architecture, tool contracts, and MCP adapter boundary.
- `[ ]` Review spec with Phoenix/user and resolve open questions that affect v1 implementation.

Exit criteria:

- Requirements, design, and tasks are committed.
- The first implementation milestone can be started without re-discussing the whole architecture.

## Phase 1: Python Package Skeleton

- `[ ]` Create `dqmc_tools/` package.
- `[ ]` Add `dqmc_tools/__init__.py` with a minimal public API surface.
- `[ ]` Add `dqmc_tools/errors.py` with typed exceptions and JSON-safe error helpers.
- `[ ]` Port only small generic helpers from existing code where useful, such as bounded text reads, skipped-directory constants, and generated-output safety checks.
- `[ ]` If JSONL helper code is needed later, copy only generic loading/tokenization ideas from `app/io_tools.py`, `app/retrieval.py`, or `app/semantic_tools.py`; do not port scoring or semantic interpretation behavior.
- `[ ]` Confirm `dqmc_tools` has no import dependency on `app/`, FastAPI, frontend code, or OpenAI Agents SDK modules.
- `[ ]` Add initial `tests/` structure.
- `[ ]` Add `pyproject.toml` with narrow core dependencies and optional `test` and `mcp` extras.

Exit criteria:

- `python -m pytest` or the selected test command can discover tests.
- Importing `dqmc_tools` does not require agent, FastAPI, or MCP dependencies.

## Phase 2: Observable Registry

- `[ ]` Implement `dqmc_tools.observables.load_observable_registry`.
- `[ ]` Implement `list_observables`.
- `[ ]` Implement `resolve_observable`.
- `[ ]` Support exact `repo_id`, exact HDF5 path, and unambiguous tail-name resolution.
- `[ ]` Add ambiguity errors for duplicated tail paths, using a small test registry fixture if the current `formal/observables.yaml` has no natural ambiguous example.
- `[ ]` Add tests using `formal/observables.yaml`.

Exit criteria:

- `resolve_observable("EqLt.density")` returns `/meas_eqlt/density`.
- `resolve_observable("density")` resolves only if unambiguous.
- Ambiguous names fail with candidate ids instead of guessing.

## Phase 3: Path Safety

- `[ ]` Implement `dqmc_tools.config` for environment-backed defaults.
- `[ ]` Implement `resolve_existing_path`.
- `[ ]` Implement `require_allowed_path`.
- `[ ]` Implement `require_output_path`.
- `[ ]` Adapt the restricted-write idea from `app/repo_tools.py`, but make the output root configurable instead of hard-coding `agent_outputs/`.
- `[ ]` Enforce fail-closed raw-data access when no allowed roots are configured or explicitly passed.
- `[ ]` Add tests for allowed root, rejected outside path, and output root behavior.

Exit criteria:

- All raw-data tools call path safety helpers before reading files or directories.
- Generated outputs cannot be placed outside the configured output root.

## Phase 4: HDF5 Inspection

- `[ ]` Add `h5py` and `numpy` dependency handling.
- `[ ]` Implement `inspect_hdf5`.
- `[ ]` Traverse groups and datasets read-only.
- `[ ]` Include shape, dtype, attrs, and bounded previews.
- `[ ]` Ensure large arrays are summarized, not fully returned.
- `[ ]` Add synthetic HDF5 fixture tests.

Exit criteria:

- Synthetic HDF5 files produce stable JSON-serializable inspection output.
- Inspection does not mutate files.
- Output records truncation when applicable.

## Phase 5: Observable Reading

- `[ ]` Implement `read_dataset`.
- `[ ]` Implement `read_observable`.
- `[ ]` Extract factual metadata from common `metadata/*`, `params/*`, `meas_eqlt/*`, and `meas_uneqlt/*` paths when present.
- `[ ]` Use parameter-name and HDF5-family ideas from `app/build_io_index.py` as hints only; always read facts from the actual HDF5 file.
- `[ ]` Return numeric summaries and bounded previews.
- `[ ]` Avoid scientific labels or recommendations.
- `[ ]` Add tests for successful read, missing dataset, and metadata extraction.

Exit criteria:

- `read_observable(sample_h5, "EqLt.density")` returns dataset facts and registry metadata.
- Missing registered dataset errors are structured and actionable.

## Phase 6: Run Discovery and Summary

- `[ ]` Implement `list_runs`.
- `[ ]` Implement conservative run candidate detection.
- `[ ]` Implement supported filters.
- `[ ]` Implement `summarize_run`.
- `[ ]` Report available and missing registered observable paths per HDF5 file.
- `[ ]` Add tests using temporary directory trees and synthetic HDF5 files.

Exit criteria:

- Run listing is bounded and filterable.
- Run summary reuses HDF5 and observable modules rather than duplicating logic.

## Phase 7: Read-only SLURM Query

- `[ ]` Implement `query_slurm`.
- `[ ]` Prefer JSON output where available.
- `[ ]` Add fallback parser for a stable custom `squeue` format.
- `[ ]` Return unavailable errors when SLURM commands are missing.
- `[ ]` Add tests that mock subprocess results.

Exit criteria:

- No SLURM submit/cancel behavior exists in v1.
- Query output is structured and records command arguments.

## Phase 8: MCP Adapter

- `[ ]` Use the official Python MCP SDK via `mcp.server.fastmcp.FastMCP`.
- `[ ]` Add `dqmc_mcp_server.py`.
- `[ ]` Register `list_runs`.
- `[ ]` Register `inspect_hdf5`.
- `[ ]` Register `resolve_observable`.
- `[ ]` Register `read_observable`.
- `[ ]` Register `summarize_run`.
- `[ ]` Register `query_slurm`.
- `[ ]` Write tool descriptions following the description standard in `design.md`.
- `[ ]` Use `app/agent_config.py` only as a writing-quality reference for descriptions; avoid copying workflow rules or repo-agent-specific instructions.
- `[ ]` Add minimal MCP forwarding tests if supported by the selected SDK.

Exit criteria:

- MCP adapter contains no domain logic beyond validation and forwarding.
- The same functions remain directly importable from Python without MCP.

## Phase 9: Analysis Registry

- `[ ]` Create `dqmc_tools/analyses/registry.py`.
- `[ ]` Define analysis metadata schema.
- `[ ]` Reuse the validation style from `formal/scripts/check_formal_registry.py`: required fields, duplicate-id checks, and clear schema errors.
- `[ ]` Implement `list_analyses`.
- `[ ]` Implement `run_analysis` for registry entries only.
- `[ ]` Add the first real analysis only after Phoenix identifies a concrete workflow.

Exit criteria:

- Arbitrary script paths are rejected.
- Analysis outputs are created only under the configured output root.

## Phase 10: Optional Existing App Integration

- `[ ]` Decide whether current `app/agent_config.py` should expose `dqmc_tools` tools directly.
- `[ ]` If yes, add OpenAI Agents SDK wrappers as a separate integration layer.
- `[ ]` Keep wrappers thin and avoid duplicating MCP descriptions.
- `[ ]` Update frontend/demo docs only if the existing app remains a supported demo.

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
