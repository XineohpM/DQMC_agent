"""Built-in script catalog for the fixed dqmc-dev checkout."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dqmc_tools.config import get_dqmc_dev_root
from dqmc_tools.scripts.argparse_sync import sync_argparse_adapters
from dqmc_tools.scripts.definitions import InputRequirement, ScriptDefinition


ROOT = get_dqmc_dev_root()


def _script(relpath: str) -> Path:
    return ROOT / relpath


def _props(*names: str, raw_args: bool = True) -> dict[str, Any]:
    properties: dict[str, Any] = {name: {"flag": f"--{name}"} for name in names}
    if raw_args:
        properties["args"] = {"raw_args": True}
    return {"properties": properties}


def _path_prop(flag: str, *, role: str | None = None, positional: bool = False, position: int = 0):
    out: dict[str, Any] = {"flag": flag}
    if role:
        out["path_role"] = role
    if positional:
        out["positional"] = True
        out["position"] = position
    return out


_BASE_SCRIPT_CATALOG: tuple[ScriptDefinition, ...] = (
    ScriptDefinition(
        "gen_beta_scan",
        "Generate beta-scan HDF5 input files using dqmc-dev/scripts/gen_beta_scan.py.",
        "generation",
        "writes_output",
        _script("scripts/gen_beta_scan.py"),
        args_schema={
            "properties": {
                "output_path": _path_prop("--output_path", role="output"),
                "generator_path": {"flag": "--generator_path"},
                "dry_run": {"flag": "--dry_run"},
                "args": {"raw_args": True},
            },
        },
        required_inputs=(InputRequirement("generator", "file", "{generator_path}", required=False),),
        output_patterns=("{output_path}/**/*.h5", "{output_path}/**/*.params", "{output_path}/**/gen.log"),
    ),
    ScriptDefinition(
        "gen_beta_mu_scan",
        "Generate beta-mu-scan HDF5 input files using dqmc-dev/scripts/gen_beta_mu_scan.py.",
        "generation",
        "writes_output",
        _script("scripts/gen_beta_mu_scan.py"),
        args_schema={
            "properties": {
                "output_path": _path_prop("--output_path", role="output"),
                "generator_path": {"flag": "--generator_path"},
                "dry_run": {"flag": "--dry_run"},
                "args": {"raw_args": True},
            },
        },
        required_inputs=(InputRequirement("generator", "file", "{generator_path}", required=False),),
        output_patterns=("{output_path}/**/*.h5", "{output_path}/**/*.params", "{output_path}/**/gen.log"),
    ),
    ScriptDefinition(
        "check_h5_completion",
        "Check completion markers from sibling .h5.log files.",
        "diagnostic",
        "mutates_workflow_files",
        _script("scripts/check_h5_completion.py"),
        args_schema={
            "required": ["root"],
            "properties": {
                "root": _path_prop("--root", role="input"),
                "glob": {"flag": "--glob"},
                "push_stack": {"flag": "--push_stack"},
            },
        },
        required_inputs=(InputRequirement("root", "directory", "{root}"),),
        parser_id="tsv",
        output_patterns=("{root}/h5_completion_report.tsv", "{root}/{push_stack}"),
    ),
    ScriptDefinition(
        "check_warm",
        "Run warmup diagnostics and write warmup_summary.tsv plus plots.",
        "diagnostic",
        "writes_output",
        _script("scripts/check_warm.py"),
        args_schema={
            "required": ["root", "glob"],
            "properties": {
                "root": _path_prop("", role="input", positional=True, position=0),
                "glob": {"flag": "--glob"},
                "output_dir": _path_prop("--output_dir", role="output"),
                "kk": {"flag": "--kk"},
                "kv": {"flag": "--kv"},
                "vv": {"flag": "--vv"},
                "nn": {"flag": "--nn"},
                "JNJN": {"flag": "--JNJN"},
                "g1p": {"flag": "--g1p"},
            },
        },
        required_inputs=(InputRequirement("root", "directory", "{root}"),),
        parser_id="tsv",
        output_patterns=("{output_dir}/warmup_summary.tsv", "{output_dir}/**/*.png"),
    ),
    ScriptDefinition(
        "extract_energy_perfile",
        "Extract energy estimates per HDF5 file.",
        "analysis",
        "writes_output",
        _script("scripts/extract_energy_perfile.py"),
        args_schema={"required": ["dir"], "properties": {"dir": _path_prop("--dir", role="input"), "U": {"flag": "--U"}, "out": {"flag": "--out"}}},
        required_inputs=(InputRequirement("dir", "directory", "{dir}"),),
        parser_id="npy_manifest",
        output_patterns=("{dir}/{out}", "{dir}/{out}.meta.npy"),
    ),
    ScriptDefinition(
        "extract_local_moment",
        "Extract local moment versus temperature from T_* folders.",
        "analysis",
        "writes_output",
        _script("scripts/extract_local_moment.py"),
        args_schema=_props("root", "U", "h5_glob", "out_prefix", "skip_missing", "tol_density", "tol_spin", "strict_checks"),
        required_inputs=(InputRequirement("root", "directory", "{root}"),),
        output_patterns=("{root}/**/*local_moment*",),
    ),
    ScriptDefinition(
        "extract_1_particle_local_g",
        "Extract local one-particle Green function data from HDF5 bins.",
        "analysis",
        "writes_output",
        _script("scripts/extract_1_particle_local_g.py"),
        args_schema=_props("path", "output_path", "out_prefix", "dt"),
        required_inputs=(InputRequirement("path", "directory", "{path}"),),
        output_patterns=("{output_path}/*.npy",),
    ),
    ScriptDefinition(
        "extract_perbin_jj",
        "Extract per-bin current-current data for downstream transport analysis.",
        "analysis",
        "writes_output",
        _script("scripts/extract_perbin_jj.py"),
        args_schema={"properties": {"args": {"raw_args": True}}},
        required_inputs=(),
        output_patterns=("**/*perbin*.npy",),
    ),
    ScriptDefinition("run_maxent_anneal", "Run MaxEnt annealing workflow.", "maxent", "writes_output", _script("scripts/run_maxent_anneal.py"), args_schema={"properties": {"args": {"raw_args": True}}}),
    ScriptDefinition("run_maxent_phoenix", "Run Phoenix MaxEnt workflow.", "maxent", "writes_output", _script("scripts/run_maxent_phoenix.py"), args_schema={"properties": {"args": {"raw_args": True}}}),
    ScriptDefinition("plot_dos", "Plot density of states from MaxEnt outputs.", "maxent", "writes_output", _script("scripts/plot_dos.py"), args_schema=_props("base", "items", "out", "output_name", "xmin", "xmax", "ymin", "ymax", "no_band"), required_inputs=(InputRequirement("base", "directory", "{base}"),), output_patterns=("{out}",)),
    ScriptDefinition("plot_double_occ", "Plot double occupancy.", "plot", "writes_output", _script("scripts/plot_double_occ.py"), args_schema=_props("path", "glob", "output_path", "out_prefix"), required_inputs=(InputRequirement("path", "directory", "{path}"),), output_patterns=("{output_path}/*double_occ*",)),
    ScriptDefinition("plot_charge_order", "Plot charge order observables.", "plot", "writes_output", _script("scripts/plot_charge_order.py"), args_schema=_props("path", "glob", "out_prefix", "vlim"), required_inputs=(InputRequirement("path", "directory", "{path}"),), output_patterns=("{path}/**/*charge*", "{path}/**/*S_cdw*")),
    ScriptDefinition("s_wave_pairing", "Compute and plot onsite s-wave pairing estimates.", "analysis", "writes_output", _script("scripts/s_wave_pairing.py"), args_schema=_props("path", "output_path", "out_prefix", "relpath_list"), required_inputs=(InputRequirement("path", "directory", "{path}"),), output_patterns=("{output_path}/*s_wave*",)),
    ScriptDefinition(
        "plot_JNJN",
        "Plot JNJN or related current-correlation curves from derived per-bin data.",
        "plot",
        "writes_output",
        _script("scripts/plot_JNJN.py"),
        args_schema=_props("path", "beta", "dt", "out"),
        required_inputs=(InputRequirement("JNJN_perbin", "npy", "{path}/JNJN_xx_perbin.npy", shape_hint=(None, None)),),
        output_patterns=("{out}",),
    ),
    ScriptDefinition("conductivity_plot", "Plot conductivity results.", "plot", "writes_output", _script("scripts/conductivity_plot.py"), args_schema=_props("base", "items", "out", "divide_pi", "xmax", "ymin", "ymax", "no_band"), required_inputs=(InputRequirement("base", "directory", "{base}"),), output_patterns=("{out}",)),
    ScriptDefinition("resistivity_proxy", "Compute resistivity proxy quantities.", "analysis", "writes_output", _script("scripts/resistivity_proxy.py"), args_schema={"properties": {"args": {"raw_args": True}}}),
    ScriptDefinition("resistivity_plot", "Plot resistivity from MaxEnt/proxy outputs.", "plot", "writes_output", _script("scripts/resistivity_plot.py"), args_schema=_props("base", "items", "out", "dc_method", "maxent_prefix", "maxent_subdir", "proxy1", "proxy2", "divide_pi", "convergence_plots", "linear_fit", "highT_slope"), required_inputs=(InputRequirement("base", "directory", "{base}"),), output_patterns=("{out}",)),
    ScriptDefinition("run_stack_owners", "Run stack jobs with owner/worker organization.", "workflow", "mutates_workflow_files", _script("scripts/run_stack_owners.sh"), args_schema={"properties": {"args": {"raw_args": True}}}),
    ScriptDefinition("multi_dir_push_stack", "Push simulation files from multiple directories into stack files.", "workflow", "mutates_workflow_files", _script("scripts/multi_dir_push_stack.sh"), args_schema={"properties": {"args": {"raw_args": True}}}),
)


ARGPARSE_SYNC_RESULT = sync_argparse_adapters(_BASE_SCRIPT_CATALOG, scripts_root=ROOT / "scripts")
DEFAULT_SCRIPT_CATALOG = ARGPARSE_SYNC_RESULT.adapters


EXCLUDED_FIRST_PHASE_SCRIPTS = (
    "check_sum_rule",
    "make_bootstrap",
    "save_boot_stats",
    "run_maxent",
    "gen_1band_unified_hub",
    "dqmc_info",
    "dqmc_summary",
    "print_n",
    "push",
    "plot_compressibility_from_best_mu",
    "plot_compressibility_from_n_mu",
    "get_n_from_best_mu",
    "get_mu",
    "scripts/mu_tuning_*",
    "multi_dir_submit_sbatch",
    "run_stack_simes",
)
