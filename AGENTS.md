# AGENTS.md

This document defines the project-level working conventions for every Codex
instance in this repository. It applies to local Codex sessions and to Codex
sessions created through Slack/OpenACP. Slack/OpenACP uses the project root as
the default workspace, so new sessions should read and follow this document
first.

## Project Role

This project is the local implementation and runtime workspace for the DQMC
agent. The core boundaries are:

- `dqmc_tools/` and `dqmc_mcp_server.py` provide testable, low-level,
  fact-oriented MCP hands.
- `dqmc_sherlock_gateway_mcp_server.py` provides the controlled short-SSH
  gateway from local execution to Sherlock.
- `registry.yaml`, `code_map.md`, and `diagnostics_playbook.md` are important
  sources for domain knowledge and data definitions.
- `scripts/start-slackbot-backend` and `scripts/stop-slackbot-backend` are only
  responsible for starting and stopping the local OpenACP backend.
- `.openacp/` is a local runtime directory containing tokens, sessions,
  history, and plugin installs. It should not be committed to git.

The default product shape is: local Codex is the only agent brain; Sherlock
does not run a long-lived Codex or MCP server. When Sherlock status is needed,
prefer the local `dqmc-sherlock-gateway` for short-lived, allowlisted, read-only
remote calls.

## Knowledge Source Routing

When the following topics come up, you must consult `code_map.md` first:

- The user asks which script, file, or module is responsible for something.
- The user asks about the dqmc-dev simulation pipeline, HDF5 generation, HDF5
  reading, run flow, measurement flow, or post-processing flow.
- The user asks where an observable, parameter, current-current quantity,
  MaxEnt result, density, Green function, or similar quantity comes from in the
  code flow.
- The user asks which script or adapter should be used for a class of input
  generation, completion checks, warmup checks, post-processing, plotting, or
  MaxEnt workflow.
- The user asks to add, modify, or explain a script adapter, and the task
  requires understanding dqmc-dev script capabilities, inputs, outputs, and
  workflow relationships.

When using `code_map.md`, remember that it is a functional map of dqmc-dev. It
is not the source of truth for current run data or current script parameters. If
the question involves real script arguments, file existence, the current adapter
schema, HDF5 dataset existence, or run results, verify against the current code,
`registry.yaml`, MCP tools, or real files under `DQMC_DEV_ROOT`.

When the following topics come up, you must consult the relevant section of
`diagnostics_playbook.md` first:

- Sign problem, average sign, sign reweighting, or whether statistical errors
  are trustworthy.
- Trotter error, `dt`, `L`, `beta = L * dt`, imaginary-time discretization, or
  whether parameters are reasonable.
- Warmup, sweeps, thermalization, running means, or whether first-half and
  second-half means are consistent.
- Mu tuning, target filling, density, hole doping, electron doping, or half
  filling.
- Compressibility, `dn/dmu`, negative slopes, or density trends that appear
  nonphysical.
- MaxEnt, binning, covariance matrix, or whether analytic continuation results
  are trustworthy.
- The user asks reliability or interpretation questions such as "is this run
  reliable", "can this result be trusted", "what should I diagnose next", or
  "are these parameters reasonable".

If the user asks about a real run, HDF5 file, observable, script output, or
SLURM job, first collect facts with MCP hands, then use
`diagnostics_playbook.md` for diagnostic judgment. Do not draw conclusions from
the playbook or memory alone.

## Workflow

1. Clarify the user's goal and risk level first.
   - Simple factual queries can be answered directly or with read-only tools.
   - For tasks involving file writes, script execution, artifact sync,
     configuration changes, or potentially expensive work, first explain what
     will be read or written and why.
   - If the user request is ambiguous and a reasonable assumption would create
     risk, ask one concrete question first.

2. Read context before acting.
   - Prefer reading `README.md`, `USAGE.md`, relevant `specs/`, tests, and
     current code.
   - Use `rg` / `rg --files` first when searching files or text.
   - Do not rely on stale memory in place of current file contents.

3. Keep facts and judgment layered.
   - Tool returns, HDF5, SLURM, registry, and logs are factual sources.
   - Sign, Trotter, warmup, MaxEnt, and related content in
     `diagnostics_playbook.md` are diagnostic rules and expert judgment.
   - When giving conclusions, state which parts come from tool facts and which
     parts are inference or diagnostic advice.

4. Dry-run first, then execute for real.
   - For allowlisted scripts, first use `describe_script_adapter` or
     `run_script_adapter(..., dry_run=true)`.
   - For Sherlock artifact sync, first dry-run and show the manifest, remote
     host/path, and local output root.
   - Real execution must receive explicit approval from the user for this
     specific action. Do not generalize earlier approval to new commands, paths,
     or parameters.

5. Keep code and documentation changes small and verifiable.
   - Modify only files relevant to the current task.
   - Do not refactor unrelated modules, clean up unrequested historical files,
     or modify private `.openacp/` runtime state.
   - Before editing, say what will be changed. After editing, run appropriate
     verification commands.
   - If verification cannot be run, state the reason clearly.

6. Reports should be short and auditable.
   - State which files changed, the core behavior change, and which
     verification commands were run.
   - Reference real file paths and key lines.
   - Do not overstate completion. Clearly state any unfinished, unverified, or
     environment-limited parts.

## Tools and Safety Boundaries

- run/HDF5 paths must be explicitly provided by the user. The agent should not
  scan parent directories to guess runs.
- Raw data reads must respect `DQMC_ALLOWED_ROOTS`; if it is not configured,
  fail closed.
- Generated files should default to `DQMC_OUTPUT_ROOT` or this project's
  `outputs/`; do not write to unknown remote directories.
- `inspect_hdf5` does not perform HDF5 tree discovery. Calls must provide
  explicit dataset keys.
- Single-file reads must not be presented as error estimates. For mean/error,
  use the registered observable jackknife estimation flow.
- The default Sherlock status profile only performs path-redacted SLURM status
  queries.
- When Slack/OpenACP presents the current Sherlock queue, prefer directly
  outputting the gateway's `formatted_summary`.
- When Slack/OpenACP presents job detail, prefer directly outputting the
  gateway's `formatted_detail`.
- Do not fall back to direct SSH, custom `squeue`, `awk` pipelines, or arbitrary
  shell commands just to fill missing fields.
- The Sherlock gateway does not submit or cancel SLURM jobs, does not provide
  arbitrary shell access, and does not expose real run/output paths.

## Common Verification

Default local development verification command:

```bash
.venv/bin/python -m pytest
```

Structural check for script adapters:

```bash
.venv/bin/python scripts/audit_script_adapters.py --json --no-fingerprints
```

Slack/OpenACP helper behavior test:

```bash
bash scripts/test_slackbot_backend_commands.sh
```

Choose verification commands based on task risk. Narrow changes may use focused
tests; cross-module or contract changes should broaden the test scope.

## Git and File Hygiene

- `.openacp/`, `.venv/`, `data/`, and `outputs/` should not be committed.
- Do not read or display `.openacp/tokens.json`, `api-secret`, `jwt-secret`,
  session history, or private env contents unless the user explicitly asks and
  there is a real need.
- Do not roll back existing user changes. If the task is affected by user
  changes, understand them and work on top of them.
- Do not use destructive git commands unless the user explicitly requests them
  and confirms the scope.

## Additional Slack/OpenACP Conventions

Slack sessions are usually the context for continuous research tasks. Replies
should read like operator reports:

- Give the conclusion first, then evidence and next steps.
- For approval requests, clearly list the tool name, parameters, read/write
  paths, expected outputs, and risks.
- For long output, prefer existing formatters or compact summaries. Do not run
  extra shell commands solely to compress presentation.
- When the user starts a new top-level conversation from the Slack app, it
  creates a new local Codex session. Do not assume an old session's
  configuration or MCP tool surface is still current.
