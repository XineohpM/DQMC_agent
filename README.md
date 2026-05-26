# DQMC Agent Hands

这是基于当前 `registry.yaml`、`code_map.md` 和 `diagnostics_playbook.md` 重写的 DQMC “手”层实现。它把领域逻辑放在 `dqmc_tools` 包中，MCP 入口 `dqmc_mcp_server.py` 只做薄适配。

## 安装

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[mcp,test]"
```

运行测试：

```bash
.venv/bin/python -m pytest
```

## 配置

- `DQMC_ALLOWED_ROOTS`：允许读取的原始数据根目录，多个路径按系统 path separator 分隔。没有配置时，原始数据读取 fail closed。
- `DQMC_OUTPUT_ROOT`：生成文件默认根目录。未设置时使用本工程 `outputs/`。
- `DQMC_REGISTRY_PATH`：registry 文件路径。未设置时使用本工程 `registry.yaml`。
- `DQMC_SCRIPT_TIMEOUT_SECONDS`：白名单脚本默认超时秒数，默认 `300`。
- `dqmc-dev` 固定路径：`/Users/phoenixm/Desktop/dqmc-dev`。

示例：

```bash
export DQMC_ALLOWED_ROOTS="/path/to/run:/path/to/another-root"
export DQMC_OUTPUT_ROOT="/Users/phoenixm/Desktop/DQMC_agent/outputs"
```

## MCP 启动

```bash
.venv/bin/python dqmc_mcp_server.py
```

MCP 暴露 10 个工具：

- `summarize_run`
- `inspect_hdf5`
- `read_dataset`
- `resolve_registry_entry`
- `read_registered_quantity`
- `estimate_registered_observable`
- `list_script_adapters`
- `describe_script_adapter`
- `run_script_adapter`
- `query_slurm`

不暴露 `list_runs`。run 目录、T 目录、脚本输入目录都必须由用户显式给出。

`query_slurm` 是只读队列查询：支持 `filters={"me": true}` 生成 `squeue --me`，
返回原始 job rows，并按 job name 和 array job id 生成 grouped summary。

## Registry 和 HDF5

registry 解析只使用真实字段：`id`、`aliases`、`code.generation.variable`。返回结果会附加运行期辅助字段 `entry_type` 和 `dataset_key`，但不会引入额外标识体系。

`inspect_hdf5` 只是 `/Users/phoenixm/Desktop/dqmc-dev/util/util.py` 中 `load_file()`、`load_firstfile()`、`load()` 的 wrapper；调用时必须显式给出 `dataset_keys`，它不做 HDF5 tree discovery。

单文件或直接读取不会估计 error。对 registry 中 observable 的整体误差估计使用 `estimate_registered_observable`，它会对一个目录下的一组 HDF5 文件调用 `util.py` 的 `jackknife()` 或 `jackknife_noniid()`。

## 脚本执行流程

已有 `dqmc-dev/scripts` 是复用资产，不把每个脚本都重写成独立 MCP tool。统一入口是 `run_script_adapter`。

推荐流程：

1. 用 `list_script_adapters` 找到脚本。
2. 用 `describe_script_adapter` 查看参数、required input、输出模式和是否会改 workflow 文件。
3. 先用 `run_script_adapter(..., dry_run=true)` 检查命令、cwd、输入和输出 root。
4. 向用户展示将执行的命令和读写路径。
5. 用户本次明确同意后，才允许真实执行，并传入 `user_confirmation={"approved": true, "text": "用户同意内容"}`。

每次真实执行任何白名单脚本都必须逐次征求用户显式同意。第一版允许真实 input generation，也允许 workflow-mutating 工具，但不允许提交或取消 SLURM job。

Python 白名单脚本的参数 schema 会从 `/Users/phoenixm/Desktop/dqmc-dev/scripts/` 中的 `argparse` 定义静态同步。同步只读取源码，不 import 或执行 `dqmc-dev` 脚本；shell 脚本仍保留 raw args。可用下面命令查看同步结果：

```bash
.venv/bin/python scripts/audit_script_adapters.py --json --no-fingerprints
```

## 暂不接入

第一版不接入：

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

`plot_JNJN` 这类二级脚本只处理已派生的数据文件；运行前会检查所需的 `.npy` 等输入是否存在。

## 兼容说明

旧的 `resolve_observable` 和 `read_observable` 作为兼容 wrapper 保留，但新代码优先使用 `resolve_registry_entry`、`read_registered_quantity` 和 `estimate_registered_observable`。兼容 wrapper 的返回仍遵循当前 registry 真实格式。

工具只返回事实、路径、数组摘要、脚本结果和 structured error，不做 sign quality、warmup 质量、Trotter 误差或物理可靠性判断。
