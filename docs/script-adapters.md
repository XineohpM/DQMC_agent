# Script Adapter Registry

脚本 adapter 统一复用 `DQMC_DEV_ROOT/scripts/` 目录下已有脚本。MCP 层只暴露 `list_script_adapters`、`describe_script_adapter` 和 `run_script_adapter`，不把每个脚本注册成独立 MCP tool。

`DQMC_DEV_ROOT` 必须在 Codex 用户级 `~/.codex/config.toml` 的 `[mcp_servers.dqmc-hands.env]` 中显式设置；缺失、为空或路径不存在时会报 `configuration_error`，不会回退到硬编码路径。

## 执行约束

- 所有白名单脚本真实执行都要求 `user_confirmation.approved == true` 且 `user_confirmation.text` 非空。
- 真实执行前应先 dry-run，并把命令、cwd、输入路径和输出路径展示给用户。
- `required_inputs` 在启动脚本前检查；缺失输入时不会执行脚本。
- 输出路径默认限制在本工程 `outputs/`，除非显式设置 `DQMC_OUTPUT_ROOT` 或调用参数 `output_root`。
- 脚本通过 argv list 启动，不通过 shell 拼接命令。
- Python 脚本的 `args_schema` 会在 agent 侧通过静态读取 `dqmc-dev/scripts/` 下源码中的 `argparse` 定义自动同步；shell 脚本保留 raw args。

## Argparse 同步

`scripts/audit_script_adapters.py` 会报告 argparse 同步结果。同步逻辑只读取源码，不 import 或执行 `dqmc-dev` 脚本，因此不会修改 `dqmc-dev/` 或触发脚本副作用。

同步范围：

- 只处理当前白名单中位于 `DQMC_DEV_ROOT/scripts/` 的 Python 脚本。
- 解析直接的 `argparse.ArgumentParser()`、`add_argument()`、argument group 和 mutually-exclusive group。
- 将 flag、positional、required、type、choices、nargs、store_true/store_false 合并进 adapter `args_schema`。
- `path_role`、`required_inputs`、`output_patterns`、`parser_id` 和审批策略仍由 adapter catalog 维护。

## 已注册脚本

| script_id | 类别 | 模式 | 主要用途 |
| --- | --- | --- | --- |
| `gen_beta_scan` | generation | writes_output | 生成 beta-scan HDF5 input |
| `gen_beta_mu_scan` | generation | writes_output | 生成 beta-mu-scan HDF5 input |
| `check_h5_completion` | diagnostic | mutates_workflow_files | 检查 `.h5.log` completion marker，可写 workflow stack |
| `check_warm` | diagnostic | writes_output | warmup summary 和图 |
| `extract_energy_perfile` | analysis | writes_output | 按 HDF5 文件提取 energy |
| `extract_local_moment` | analysis | writes_output | 从 `T_*` 目录提取 local moment |
| `extract_1_particle_local_g` | analysis | writes_output | 提取 local one-particle Green function 数据 |
| `extract_perbin_jj` | analysis | writes_output | 提取 per-bin current-current 数据 |
| `run_maxent_anneal` | maxent | writes_output | MaxEnt annealing workflow |
| `run_maxent_phoenix` | maxent | writes_output | Phoenix MaxEnt workflow |
| `plot_dos` | maxent | writes_output | 从 MaxEnt 输出画 DOS |
| `plot_double_occ` | plot | writes_output | 画 double occupancy |
| `plot_charge_order` | plot | writes_output | 画 charge order |
| `s_wave_pairing` | analysis | writes_output | 计算/绘制 onsite s-wave pairing |
| `plot_JNJN` | plot | writes_output | 从派生 per-bin 数据画 JNJN/current-correlation |
| `conductivity_plot` | plot | writes_output | 画 conductivity |
| `resistivity_proxy` | analysis | writes_output | 计算 resistivity proxy |
| `resistivity_plot` | plot | writes_output | 画 resistivity |
| `run_stack_owners` | workflow | mutates_workflow_files | owner/worker stack 运行脚本 |
| `multi_dir_push_stack` | workflow | mutates_workflow_files | 多目录 push 到 stack files |

## 二级脚本输入保证

二级脚本处理的是前置脚本生成的派生数据，不应假设可以直接从单个原始 HDF5 文件读取。例如：

- `plot_JNJN` 要求 `{path}/JNJN_xx_perbin.npy` 存在，并检查为 `.npy` 文件。
- `plot_dos`、`conductivity_plot`、`resistivity_plot` 要求 base/output 数据目录或文件已经存在。

这些检查由 `required_inputs` preflight 完成；失败时返回 `script_preflight_error`。

## 输出解析

第一版提供轻量解析：

- `tsv`：读取 TSV 表头和行。
- `npy_manifest`：只记录 `.npy` shape、dtype、路径和大小。
- `image_manifest`：记录图片路径、大小和 mtime。
- `stdout_key_value`：提取基础 key-value 行。

解析失败不会覆盖脚本执行结果，只会追加 warning。

## 第一期排除项

以下工作流暂不注册：

- `scripts/check_sum_rule.py`
- `scripts/make_bootstrap.py`
- `scripts/save_boot_stats.py`
- `scripts/run_maxent.py`
- `util/gen_1band_unified_hub.py`
- `util/info.py`
- `util/summary.py`
- `util/print_n.py`
- `util/push.py`
- `scripts/plot_compressibility_from_best_mu.py`
- `scripts/plot_compressibility_from_n_mu.py`
- `scripts/get_n_from_best_mu.py`
- `util/get_mu.py`
- `scripts/mu_tuning_*`
- `scripts/multi_dir_submit_sbatch.sh`
- `scripts/run_stack_simes.sh`
