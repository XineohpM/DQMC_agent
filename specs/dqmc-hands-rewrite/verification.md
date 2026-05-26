# Phase 11 Verification

Branch: `hands-rewrite-sdd`

## Commands

```bash
.venv/bin/python -m pytest
```

Result: `44 passed in 5.46s`

Smoke coverage:

- registry resolution for `density`
- direct HDF5 dataset read through `dqmc-dev/util/util.py`
- `read_observable` compatibility wrapper
- explicit-key `inspect_hdf5`
- multi-file `estimate_registered_observable` with jackknife
- `plot_JNJN` script adapter dry-run with required `.npy` preflight
- MCP tool list and `resolve_registry_entry` call

Smoke result:

```text
registry_dataset_key=meas_eqlt/density
read_shape=[2]
observable_dataset_key=meas_eqlt/density
inspect_count=1
jackknife_mean=[2.0, 3.0]
script_dry_run=True
script_preflight_ok=True
mcp_tool_count=10
mcp_dataset_key=meas_eqlt/density
```

`git status --short --branch` before this verification record:

```text
## hands-rewrite-sdd
```

## Deliberately Not Enabled

- run discovery / `list_runs`
- SLURM submit/cancel tools
- raw HDF5 mutation
- `scripts/check_sum_rule.py`
- compressibility, best-mu, `util/get_mu.py`, and `scripts/mu_tuning_*` workflows
- `scripts/multi_dir_submit_sbatch.sh`
