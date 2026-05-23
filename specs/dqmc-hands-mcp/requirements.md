# DQMC Hands MCP Requirements

## Purpose

Build the "hands" layer for a DQMC domain agent: a reusable Python package that performs controlled DQMC data and cluster operations, plus a thin MCP server that exposes those operations to upstream agents.

This spec intentionally does not define a new agent, planning loop, chat backend, or UI. Existing general-purpose agents remain responsible for orchestration and interpretation.

## Scope

In scope:

- A plain Python package, `dqmc_tools`, importable from notebooks and scripts.
- Deterministic tool functions for run discovery, HDF5 inspection, observable lookup, observable reading, and read-only SLURM queries.
- A thin MCP adapter that registers `dqmc_tools` functions as MCP tools.
- A small analysis registry for whitelisted analysis functions, added after the core read-only tools are stable.
- Safety checks for allowed paths and non-mutating access to raw simulation files.
- Unit tests for core functions without requiring an agent runtime.

Out of scope for the first implementation:

- Replacing `app/` agent orchestration, FastAPI, CLI, or frontend.
- Creating an agent framework, plugin framework, task queue, or custom planning loop.
- Submitting, cancelling, or modifying SLURM jobs.
- Running arbitrary shell commands or arbitrary script paths.
- Mutating original HDF5 simulation data.
- Implementing physics interpretation or diagnostic judgment inside tools.

## Core Principles

1. The Python package is the source of truth.
   MCP wrappers must be thin transport adapters over `dqmc_tools`.

2. Tools return facts, not judgments.
   They may return measured values, metadata, shapes, missing datasets, sample counts, and mechanically derived summary statistics. They must not decide whether a run is scientifically good or bad.

3. Existing assets should be reused.
   The observable registry in `formal/observables.yaml` is the canonical starting point for mapping observable names to HDF5 paths.

4. Tool interfaces must be stable and simple.
   Inputs and outputs should be JSON-serializable dictionaries, lists, numbers, strings, and booleans.

5. Tools must be useful without an agent.
   Phoenix should be able to call the same functions directly from Jupyter.

## User Stories and Acceptance Criteria

### R1: List candidate run directories

As a researcher, I want to list candidate DQMC run directories under known scratch/home roots so that I can select data for analysis.

Acceptance criteria:

- Given an allowed root path, `list_runs(root, filters=None)` returns a JSON-serializable list of run summaries.
- Each run summary includes at least `path`, `name`, `mtime`, and discovered file counts.
- The function rejects paths outside configured allowlisted roots.
- If no allowed roots are configured or explicitly passed, raw-data path access fails closed with a structured path error.
- Filters are optional and conservative. Unsupported filters fail with a clear error.

### R2: Inspect HDF5 file structure

As a researcher or agent, I want to inspect an HDF5 file without loading large arrays so that I can understand what data is available.

Acceptance criteria:

- `inspect_hdf5(path)` returns groups and datasets with `path`, `shape`, `dtype`, and selected attributes.
- Large dataset contents are not read by default.
- Small scalar datasets and short arrays may be previewed with explicit size limits recorded in the output.
- Missing or invalid HDF5 files return structured errors.
- Raw HDF5 files are opened read-only.

### R3: Resolve observable names to HDF5 paths

As an agent, I want to resolve canonical observable names to HDF5 paths so that I can read the correct measurement data without guessing.

Acceptance criteria:

- `load_observable_registry(path=None)` reads `formal/observables.yaml` by default.
- `resolve_observable(name)` accepts canonical ids such as `EqLt.density` and common storage tails such as `density` when unambiguous.
- The returned mapping includes `repo_id`, `h5_path`, `kind`, `time_kind`, `spin`, and `measured_as` when present.
- Ambiguous names return a structured ambiguity error listing candidate repo ids.

### R4: Read an observable from HDF5

As a researcher, I want to read a registered observable from a DQMC HDF5 file so that I can inspect its values and metadata.

Acceptance criteria:

- `read_observable(h5_path, observable_name, options=None)` uses the observable registry to locate the dataset.
- The output includes `observable`, `dataset_path`, `shape`, `dtype`, and a bounded value summary.
- The output includes related factual metadata when available, such as `sign`, `n_sample`, `beta`, `dt`, `L`, `Nx`, `Ny`, `U`, and `mu`.
- The function does not apply scientific quality labels such as "bad sign" or "large Trotter error".
- The function does not mutate the HDF5 file.

### R5: Summarize a run

As an agent, I want a compact factual summary of a run directory so that I can decide what additional tools to call.

Acceptance criteria:

- `summarize_run(path)` returns discovered HDF5 files, basic metadata, available registered observables, and missing registered observables per file.
- The result is bounded in size and records truncation when applicable.
- The function uses `inspect_hdf5` and the observable registry rather than duplicating HDF5 traversal logic.

### R6: Query SLURM read-only status

As a researcher, I want to query current or recent SLURM job status so that the agent can answer operational questions about running jobs.

Acceptance criteria:

- `query_slurm(filters=None)` wraps read-only commands such as `squeue` and optionally `sacct`.
- It never submits, cancels, or modifies jobs.
- It returns parsed structured rows plus the command used.
- If SLURM commands are unavailable, it returns a structured unavailable error.

### R7: Run whitelisted analyses

As a researcher, I want the agent to run a small set of trusted analysis routines so that common workflows can be automated safely.

Acceptance criteria:

- `run_analysis(name, run_path, params=None)` only runs registered analysis functions.
- It rejects arbitrary filesystem script paths and arbitrary shell commands.
- Each registered analysis declares an input schema, output schema, and description.
- Outputs are written only under an allowed generated-output directory.
- Raw HDF5 input files are never modified.

### R8: Expose tools through MCP

As an upstream agent, I want to access these functions through MCP so that I can use them from Claude Code, Codex, or another MCP-compatible client.

Acceptance criteria:

- `dqmc_mcp_server.py` exposes the core tools with clear descriptions and JSON-compatible schemas.
- MCP tool handlers contain no domain logic beyond input validation and forwarding to `dqmc_tools`.
- Tool descriptions state when to use the tool, when not to use it, input examples, and return structure.
- The Python package remains usable without starting the MCP server.

## Nonfunctional Requirements

- Functions should be deterministic for the same filesystem and cluster state.
- Core tests should run without OpenAI, Anthropic, FastAPI, or frontend dependencies.
- HDF5 tests should use temporary synthetic files.
- The package should avoid importing heavy optional dependencies at module import time when possible.
- Errors should be structured and actionable, not stack traces unless debug mode is explicitly enabled.
- Default outputs must be bounded to avoid sending huge arrays or huge directory listings to an agent context.

## Fixed Implementation Decisions

- Path safety is fail-closed. Phoenix's exact scratch/home roots are deployment configuration, not hard-coded package logic.
- The first implementation should add `pyproject.toml` with only direct `dqmc_tools` dependencies and optional extras for tests and MCP.
- The MCP adapter should use the official Python MCP SDK with `mcp.server.fastmcp.FastMCP`.
- The analysis registry should exist before real analyses are added, but the first concrete analysis entries are deferred until Phoenix identifies real repeated workflows.
- `dqmc_tools` functions raise typed exceptions for direct Python callers. MCP wrappers catch those exceptions and return JSON-safe error dictionaries.

## Reuse Targets

- Reuse `formal/observables.yaml` as the observable mapping source.
- Reuse the safety mindset from `app/repo_tools.py`, especially bounded reads, text-file filtering, restricted writes, and explicit syntax checks.
- Adapt small implementation patterns from `app/build_index.py`, such as skipped directory names, safe text reading, and conservative file iteration, only where they help filesystem discovery.
- Adapt vocabulary and metadata-field ideas from `app/build_io_index.py`, such as known DQMC parameter names and HDF5 path conventions, without using its static source-code scan as runtime HDF5 inspection.
- Borrow only tiny generic utilities from `app/io_tools.py`, `app/retrieval.py`, and `app/semantic_tools.py`, such as JSONL loading or simple tokenization, if they reduce duplication. Their retrieval, scoring, and semantic interpretation behavior belongs to the "eyes" layer and must not be exposed as MCP hands tools.
- Treat `app/agent_config.py` as a reference for how much tool documentation matters, but not as an interface model. New MCP descriptions should describe each tool's action boundary and return facts, not prescribe an agent workflow such as "search first, then read files."
- Reuse the validation style from `formal/scripts/check_formal_registry.py` when building the analysis registry, especially duplicate-id checks and actionable schema errors.
- Reuse existing index concepts from `data/io_index.jsonl` and `data/semantic_map.jsonl` as future "eyes" inputs, not as core "hands" logic.
- Do not import `app.agent_config`, `app.agent_service`, or other OpenAI Agents SDK code from `dqmc_tools`.
- Keep current `app/` agent demo intact until the new package is stable.

## Open Questions

- What exact scratch/home path allowlist should be configured for Phoenix's environment?
- Which HDF5 convention should be considered canonical when `metadata/*` and `params/*` duplicate related values?
- Which real Phoenix workflows should become the first analysis whitelist entries after the read-only tools are stable?
