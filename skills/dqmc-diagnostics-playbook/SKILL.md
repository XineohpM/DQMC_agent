---
name: dqmc-diagnostics-playbook
description: Use when answering DQMC diagnostic, reliability, or interpretation questions involving sign problem, Trotter error, warmup or sweeps, mu tuning, filling, compressibility, MaxEnt binning, covariance, or diagnostics_playbook.md.
---

# DQMC Diagnostics Playbook

## Purpose

Use this as the agent-side entry point for DQMC diagnostic guidance in this project. The canonical project knowledge source is the workspace `diagnostics_playbook.md`; do not answer playbook-backed diagnostic questions from memory alone.

## Required Sources

- Playbook knowledge: read the relevant section of `diagnostics_playbook.md` in the current workspace.
- Hands facts: use available MCP hands tools when the user asks about a real run, HDF5 file, observable, script, or queue state.
- Project conventions: use `registry.yaml`, `code_map.md`, and dqmc-dev script metadata only as needed to resolve names, datasets, or workflow context.

## Workflow

1. Identify the diagnostic topic: sign problem, Trotter discretization, warmup/sweeps, mu tuning, filling, compressibility, MaxEnt binning, covariance, or a nearby DQMC reliability question.
2. Read the matching part of `diagnostics_playbook.md` before giving diagnostic guidance. Use `rg -n` to find topic terms or Markdown headings, then read enough surrounding context.
3. For questions about actual data, collect facts before drawing conclusions. Typical tools:
   - `summarize_run` for run contents, metadata, logs, and completion facts.
   - `read_registered_quantity`, `estimate_registered_observable`, `inspect_hdf5`, or `read_dataset` for measured values.
   - `describe_script_adapter` and `run_script_adapter(dry_run=true)` for diagnostic script capabilities and preflight.
   - `query_slurm` for queue facts.
4. Structure the answer so source layers are explicit:
   - Tool facts: values, paths, logs, schemas, or script results returned by tools.
   - Playbook rules: thresholds, conventions, or diagnostic heuristics from `diagnostics_playbook.md`.
   - Agent inference: conclusions that combine facts and playbook rules.
   - Next action: concrete follow-up reads, estimates, dry-runs, or scripts.
5. If required facts are missing, state the missing facts and suggest the next tool call or data check instead of presenting a confident diagnostic conclusion.

## Topic Pointers

- Sign problem: inspect average sign and uncertainty; small average sign amplifies statistical errors, and sign reweighting should use jackknife or bootstrap.
- Trotter error: use `beta = L * dt`; the playbook's empirical check is `dt^2 * U * t <= 1/8`.
- Warmup and sweeps: inspect early time series, running means under discarded data, and first-half versus second-half means; `check_warm` is the relevant dqmc-dev diagnostic script.
- Mu tuning and filling: for the project Hubbard convention, half filling is `n = 1` at `mu = 0`; compare measured and target filling, and normally require `|n_measured - n_target| <= 0.01` for production tuning when applicable.
- Compressibility: `dn/dmu` should normally be positive; unexpected negative slopes need data-quality and statistical-error checks before physical interpretation.
- MaxEnt binning: covariance quality depends on bin samples; the playbook's typical bin count is `n_bin = 2L`.

## Boundaries

- This skill is not an MCP tool and does not execute simulation code.
- MCP hands tools default to returning facts, paths, arrays, summaries, script results, and structured errors; do not attribute physical reliability conclusions to the hands layer unless a tool is explicitly named as diagnostic guidance.
- Keep high-risk actions on the existing dry-run and approval path.
- Preserve the project source hierarchy from `specs/goals.md`: tool facts, project conventions, playbook rules, then agent inference.
