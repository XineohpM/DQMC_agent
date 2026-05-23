# DQMC Hands MCP Design

## Overview

The implementation has two layers:

1. `dqmc_tools`: a normal Python package containing all domain operations.
2. `dqmc_mcp_server.py`: a thin MCP adapter that exposes selected `dqmc_tools` functions to upstream agents.

The existing `app/` agent, FastAPI server, and frontend are not part of the core hands layer. They may later consume `dqmc_tools`, but they should not own the tool logic.

## Proposed Layout

```text
pyproject.toml

dqmc_tools/
  __init__.py
  config.py
  errors.py
  paths.py
  observables.py
  hdf5.py
  runs.py
  slurm.py
  analyses/
    __init__.py
    registry.py

dqmc_mcp_server.py

tests/
  test_observables.py
  test_hdf5.py
  test_paths.py
  test_runs.py
```

Optional later files:

```text
tests/fixtures/
  sample_run/
```

## Existing Asset Reuse

### Observable registry

`formal/observables.yaml` remains the canonical source for initial observable metadata. `dqmc_tools.observables` should read it directly instead of copying values into code.

The first reader supports these sections:

- `repo_variables`
- `derived_observables`
- `observable_relations`
- `measurement_patterns`

Only `repo_variables` are required for `read_observable` v1.

### Repository tools

`app/repo_tools.py` is not imported directly because it is repo-agent specific, but its design constraints are reused:

- avoid broad writes
- reject absolute or unsafe paths where appropriate
- keep outputs bounded
- return clear text or structured errors

The reusable implementation ideas are the constrained filesystem operations:

- bounded text reads
- conservative repository tree walking
- text-file extension filtering
- explicit Python syntax checks for generated scripts
- generated-output writes that are restricted to a configured output root

The old function names and string-returning API do not become the public
`dqmc_tools` API. The new package should return JSON-compatible dictionaries
or raise typed exceptions that the MCP adapter can convert to structured
errors.

### Index builder utilities

`app/build_index.py` and `app/build_io_index.py` are implementation references,
not runtime dependencies. Useful pieces to adapt include:

- skipped directory names such as `.git`, `__pycache__`, `.venv`, `node_modules`,
  `build`, and `dist`
- safe text reading with character limits
- known DQMC parameter names such as `beta`, `dt`, `L`, `U`, `mu`, `sign`, and
  `n_sample`
- common HDF5 path families such as `metadata/*`, `params/*`, `meas_eqlt/*`, and
  `meas_uneqlt/*`

Do not reuse the static source-code scanners as substitutes for HDF5 runtime
inspection. `inspect_hdf5` must open the target HDF5 file read-only and inspect
the actual file structure.

### Retrieval and semantic helpers

`app/io_tools.py`, `app/retrieval.py`, and `app/semantic_tools.py` mostly belong
to the existing repo-agent "eyes" layer. They should not become MCP tools and
should not be used to decide scientific meaning inside `dqmc_tools`.

Small generic helper ideas may be copied when useful:

- loading JSONL files into dictionaries
- simple tokenization helpers
- deterministic sorting of scored records

The scoring, semantic-map formatting, theory-glossary lookup, and "most relevant
file" behavior should stay out of the hands package. Those are interpretation
and retrieval affordances for an upstream agent, not controlled domain actions.

### Existing agent tool descriptions

`app/agent_config.py` is useful as a reminder that tool descriptions shape agent
behavior, but its workflow rules are not a model for the MCP layer. MCP
descriptions should document:

- what action the tool performs
- when that specific action is appropriate
- when a different hands tool should be used
- parameter shapes and examples
- returned factual structure and truncation behavior

They should not encode global orchestration rules such as "always search this
index before reading a file." The upstream agent owns planning and sequencing.

### Formal registry scripts

`formal/scripts/check_formal_registry.py` is a useful model for validating
small registries. The analysis whitelist should use the same style:

- require explicit ids
- reject duplicate ids
- validate required fields up front
- return actionable schema errors

It should not depend on Lean or the formal proof files.

### Current agent app

No initial dependency from `dqmc_tools` to `app/` is allowed. A later integration commit may add wrappers in `app/agent_config.py`.

## Module Responsibilities

### `dqmc_tools.errors`

Defines typed exceptions and JSON-safe error conversion.

Suggested exception types:

- `DQMCError`
- `PathNotAllowedError`
- `ObservableNotFoundError`
- `ObservableAmbiguousError`
- `HDF5ReadError`
- `ToolUnavailableError`

Public helper:

```python
def error_dict(exc: Exception) -> dict:
    ...
```

### `dqmc_tools.config`

Loads simple configuration from environment variables.

Suggested environment variables:

- `DQMC_ALLOWED_ROOTS`: path list for readable run data.
- `DQMC_OUTPUT_ROOT`: root for generated analysis outputs.
- `DQMC_OBSERVABLE_REGISTRY`: optional override for observable YAML.

The package should also allow explicit function arguments so tests do not depend
on environment state. Raw-data path access is fail-closed: if neither explicit
allowed roots nor `DQMC_ALLOWED_ROOTS` are provided, functions that read run
data must reject the path with `PathNotAllowedError`.

### `dqmc_tools.paths`

Owns path normalization and safety checks.

Public functions:

```python
def resolve_existing_path(path: str | Path) -> Path
def require_allowed_path(path: str | Path, allowed_roots: list[str | Path] | None = None) -> Path
def require_output_path(path: str | Path, output_root: str | Path | None = None) -> Path
```

Rules:

- Resolve symlinks before allowlist comparison when possible.
- A path is allowed if it is equal to or inside one configured root.
- Empty or missing allowed-root configuration means no raw-data path is allowed.
- Raw data paths are read-only.
- Generated outputs must be under `DQMC_OUTPUT_ROOT` or an explicit test output root.

### `dqmc_tools.observables`

Loads and resolves observable metadata.

Public functions:

```python
def load_observable_registry(path: str | Path | None = None) -> dict
def list_observables(path: str | Path | None = None) -> list[dict]
def resolve_observable(name: str, registry_path: str | Path | None = None) -> dict
```

Resolution rules:

- Exact `repo_id` match wins, for example `EqLt.density`.
- Exact `h5_path` match is accepted, with or without leading slash.
- Tail match, such as `density`, is accepted only if it maps to exactly one repo variable.
- Ambiguous tail matches return an ambiguity error with candidates.

Output shape for a resolved observable:

```python
{
  "repo_id": "EqLt.density",
  "c_field": "m->density",
  "h5_path": "/meas_eqlt/density",
  "lean_id": "DQMC.Obs.eq_density_total",
  "time_kind": "equal_time",
  "spin": "summed",
  "kind": "density",
  "measured_as": "sign_weighted_accumulator",
  "relation_notes": ["density_sum_rule"]
}
```

### `dqmc_tools.hdf5`

Owns HDF5 inspection and bounded reading.

Public functions:

```python
def inspect_hdf5(path: str | Path, *, max_preview_items: int = 8) -> dict
def read_dataset(path: str | Path, dataset_path: str, *, max_items: int = 1024) -> dict
def read_observable(path: str | Path, observable_name: str, *, max_items: int = 1024) -> dict
```

`inspect_hdf5` output:

```python
{
  "path": "...",
  "ok": True,
  "groups": [{"path": "/metadata", "attrs": {...}}],
  "datasets": [
    {
      "path": "/meas_eqlt/density",
      "shape": [16],
      "dtype": "float64",
      "attrs": {},
      "preview": [0.9, 1.0]
    }
  ],
  "truncated": False
}
```

`read_observable` output:

```python
{
  "path": "...",
  "ok": True,
  "observable": {...},
  "dataset_path": "/meas_eqlt/density",
  "dataset": {
    "shape": [16],
    "dtype": "float64",
    "summary": {
      "size": 16,
      "min": 0.81,
      "max": 1.02,
      "mean": 0.94,
      "preview": [...]
    }
  },
  "metadata": {
    "beta": 4.0,
    "dt": 0.1,
    "L": 40,
    "U": -10.0,
    "mu": 0.0,
    "sign": 0.87,
    "n_sample": 10000
  }
}
```

Summary statistics are facts. They should not be turned into labels or recommendations.

### `dqmc_tools.runs`

Discovers and summarizes run directories.

Public functions:

```python
def list_runs(root: str | Path, filters: dict | None = None, *, max_runs: int = 200) -> list[dict]
def summarize_run(path: str | Path, *, max_files: int = 20) -> dict
```

`list_runs` should start conservative:

- A run candidate is a directory containing at least one `.h5` or `.hdf5` file, or a known job/log marker.
- Filters may include `name_contains`, `modified_after`, `modified_before`, and `has_hdf5`.
- Unsupported filters raise a clear error.

`summarize_run` should:

- list discovered HDF5 files
- inspect each HDF5 file up to `max_files`
- report registered observable paths found/missing
- include bounded metadata facts

### `dqmc_tools.slurm`

Read-only wrapper around local SLURM commands.

Public function:

```python
def query_slurm(filters: dict | None = None) -> dict
```

Implementation rules:

- Use `subprocess.run` with argument lists, not shell strings.
- Prefer `squeue --json` if available; otherwise parse a stable custom output format.
- Include the command arguments in the returned result.
- Do not expose submit/cancel operations in v1.
- Return `ToolUnavailableError` style output if commands are missing.

### `dqmc_tools.analyses.registry`

Whitelisted analysis functions. This is not part of the first read-only milestone unless needed for a real workflow.

Public functions:

```python
def list_analyses() -> list[dict]
def run_analysis(name: str, run_path: str | Path, params: dict | None = None) -> dict
```

Rules:

- `name` must be a registry key.
- Each analysis must declare a description and schema.
- Analysis functions may create new files only under the configured output root.
- No arbitrary script path execution.

## MCP Adapter

`dqmc_mcp_server.py` registers these first tools:

- `list_runs`
- `inspect_hdf5`
- `resolve_observable`
- `read_observable`
- `summarize_run`
- `query_slurm`

The adapter uses the official Python MCP SDK:

```python
from mcp.server.fastmcp import FastMCP
```

Later:

- `list_analyses`
- `run_analysis`

The adapter should contain:

- tool descriptions
- argument schema
- conversion of exceptions into JSON-safe tool results
- direct forwarding to `dqmc_tools`

The adapter should not contain:

- HDF5 traversal logic
- observable resolution logic
- analysis implementations
- agent-specific instructions or planning behavior

## Tool Description Standard

Each MCP tool description should include:

- What the tool does.
- When to use it.
- When not to use it.
- Parameter format with one example.
- Return structure and truncation behavior.
- Safety notes.

Example description shape:

```text
Read a registered DQMC observable from an HDF5 file. Use this when you know the
file path and need factual values/metadata for an observable such as EqLt.density
or Uneqlt.gt0. Do not use this to inspect the whole file structure; call
inspect_hdf5 first when the available datasets are unknown. The tool opens the
file read-only and returns bounded summaries, not full large arrays.
```

## Testing Strategy

Unit tests:

- Use temporary directories and synthetic HDF5 files.
- Test path allowlist behavior.
- Test registry loading and ambiguous observable resolution.
- Test HDF5 inspection output shape and bounded previews.
- Test observable reading with metadata extraction.
- Test SLURM unavailable behavior without requiring a real cluster.

Integration tests, later:

- Run MCP server in-process if the selected MCP SDK supports it.
- Verify each MCP tool forwards to the corresponding Python function.

Manual tests:

- Import `dqmc_tools` from a Python REPL or notebook.
- Run MCP server from the command line.
- Connect Claude Code/Codex MCP client after the server is stable.

## Implementation Order

1. Package skeleton, `pyproject.toml`, and test harness.
2. Observable registry loader.
3. Path safety helpers.
4. HDF5 inspection.
5. Observable reading.
6. Run discovery and summary.
7. SLURM read-only query.
8. MCP adapter.
9. Whitelisted analysis registry.
10. Optional integration with existing `app/`.

## Compatibility Notes

The first implementation should add `pyproject.toml` now so imports, tests, and
direct dependencies are explicit. Keep it narrow:

- core dependencies: `numpy`, `h5py`, `PyYAML`
- test extra: `pytest`
- MCP extra: `mcp`

Do not include OpenAI Agents SDK, FastAPI, or frontend dependencies in the core
package dependency set. The existing `app/` demo can keep its own environment.
