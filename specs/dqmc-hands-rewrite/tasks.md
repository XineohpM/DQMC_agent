# DQMC Hands 重写任务拆解

状态：草案，等待审阅后再实现。

## Phase 0：审阅与冻结范围

- [ ] 审阅 `requirements.md` 和 `design.md`。
- [x] 第一版允许真实 input generation，同时保留 dry-run。
- [x] 第一版允许 workflow-mutating 脚本，但仍不允许提交/取消 SLURM job。
- [x] `dqmc-dev` 路径来自必填环境变量 `DQMC_DEV_ROOT`。
- [x] output root 默认当前工程 `outputs/`。
- [x] 不实现 `list_runs`，所有 run 目录由用户手动输入。
- [x] 第一期不做 `check_sum_rule.py`。
- [x] 第一期不做 best-mu 选择、compressibility 绘图、coarse/fine mu-tuning 目录工作流；`gen_beta_mu_scan.py` 仍作为 input generation 支持。
- [x] registry 解析只使用 `registry.yaml` 真实字段，不使用额外标识体系。
- [x] 单文件 HDF5 读取不返回误差；observable 误差来自多文件 jackknife 或后处理脚本。
- [x] 任何白名单脚本真实执行前都必须征求用户本次显式同意。
- [ ] 审阅后再开始代码实现。

## Phase 1：核心骨架

- [ ] 重建 `dqmc_tools` 包结构，保持 package import 不依赖 MCP。
- [ ] 定义统一错误类型和 JSON-safe `error_dict`。
- [ ] 实现 `config.py`：allowed roots、默认 output root、registry path、必填 dqmc-dev root、timeout。
- [ ] 实现 `paths.py`：read path、output path、script root path、workflow-mutating path 的 resolve 和越界拒绝。
- [ ] 添加基础 import 测试。

验收：

- [ ] `import dqmc_tools` 不导入 `mcp`。
- [ ] 未配置 allowed roots 时 raw data 读取 fail closed。
- [ ] 未配置 output root 时使用当前工程 `outputs/`，且输出不得逃逸该目录。

## Phase 2：Registry

- [ ] 实现 `registry.py` 读取 `registry.yaml`。
- [ ] 归一化 58 个 observables，但保留原始字段结构。
- [ ] 归一化 16 个 parameters，但保留原始字段结构。
- [ ] 只支持按 `id`、alias、`code.generation.variable` 和 variable tail resolve。
- [ ] 添加运行时辅助字段 `entry_type` 和 `dataset_key`，其中 `dataset_key` 从 `code.generation.variable` 派生。
- [ ] ambiguous 查询返回候选。
- [ ] 增加 `list_registry_entries(entry_type=None)`。
- [ ] 保留 `list_observables`、`resolve_observable` 兼容 wrapper。

验收：

- [ ] `density` 解析为 registry 中 `id: density` 的 observable。
- [ ] `mu` 解析为 parameter entry 或对应 alias；返回候选时不猜。
- [ ] 返回结果不包含不存在于 registry 的额外标识字段。

## Phase 3：HDF5 util.py wrapper 与 jackknife

- [ ] 实现 `inspect_hdf5`，但只作为 `util.py` wrapper：必须传入明确 dataset keys，不做 tree 枚举。
- [ ] 实现基于 `dqmc-dev/util/util.py::load_file()` 的 `read_dataset`。
- [ ] 实现基于 `dqmc-dev/util/util.py::load()` / `load_file()` / `load_firstfile()` 的 `read_registered_quantity`。
- [ ] 实现 `estimate_registered_observable`：对一组 `.h5` 文件使用 `jackknife()` 或 `jackknife_noniid()` 返回 mean/error。
- [ ] 保留 `read_observable` 兼容 wrapper。
- [ ] 抽取 metadata facts：`beta/dt/L/Nx/Ny/U/mu/sign/n_sample/sweep`，也通过 util.py 明确读取。
- [ ] 移除单文件误差读取逻辑。
- [ ] 添加大数组 bounded summary 测试。

验收：

- [ ] 小型 fixture 可读取 density、sign、n_sample 等单文件事实。
- [ ] 单文件读取结果不包含误差估计。
- [ ] 多文件 fixture 可用 `jackknife()` 或 `jackknife_noniid()` 产生 `{mean, error}`。
- [ ] `inspect_hdf5` 不使用新增 HDF5 tree inspection 逻辑。

## Phase 4：用户指定 run 摘要

- [ ] 移除/不暴露 `list_runs` 能力。
- [ ] 实现 `summarize_run`。
- [ ] `summarize_run` 只处理用户显式输入目录，不扫描父级 scratch 目录。
- [ ] 用 registry 的 `code.generation.variable` 和 `util.load_firstfile()` 检查关键量 available/missing。
- [ ] 增加 sibling log facts 的轻量读取。

验收：

- [ ] fixture run 目录可被 `summarize_run` 摘要。
- [ ] `summarize_run` 不读取大数组。

## Phase 5：脚本白名单模型

- [ ] 定义 `ScriptDefinition`。
- [ ] 定义 mode/category 枚举。
- [ ] 实现 `list_script_adapters`。
- [ ] 实现 `describe_script_adapter`。
- [ ] 实现参数 schema 校验，未知参数默认拒绝。
- [ ] 实现 `required_inputs` preflight：文件、目录、glob、后缀、必要 shape hint。
- [ ] 实现 argv 构造，不使用 shell。
- [ ] 实现 dry-run。
- [ ] 实现 timeout。
- [ ] 实现 stdout/stderr tail。
- [ ] 实现 output manifest。
- [ ] 实现 `user_confirmation` 检查：真实执行任何白名单脚本时，没有本次用户同意就拒绝执行。

验收：

- [ ] fake script 能被 dry-run。
- [ ] fake script timeout 返回结构化错误。
- [ ] fake script 写入 output root 后 manifest 能列出文件。
- [ ] output root 外写入请求被拒绝。
- [ ] 缺失 required input 时不启动脚本，返回结构化 preflight 错误。
- [ ] 缺少用户本次同意时不启动脚本，返回 `user_approval_required`。

## Phase 6：注册已有 dqmc-dev 脚本

- [ ] 使用必填环境变量 `DQMC_DEV_ROOT`。
- [ ] 注册输入生成脚本：`gen_beta_scan`、`gen_beta_mu_scan`、`gen_1band_unified_hub`。
- [ ] 注册基础信息脚本：`dqmc_info`、`dqmc_summary`、`print_n`。
- [ ] 注册诊断脚本：`check_h5_completion`、`check_warm`。
- [ ] 注册 extraction：`extract_energy_perfile`、`extract_local_moment`、`extract_1_particle_local_g`、`extract_perbin_jj`。
- [ ] 注册 bootstrap/MaxEnt：`make_bootstrap`、`save_boot_stats`、`run_maxent*`、`plot_dos`。
- [ ] 注册 plot/transport：`plot_double_occ`、`plot_charge_order`、`plot_JNJN`、`conductivity_plot`、`resistivity_proxy`、`resistivity_plot`。
- [ ] 注册 workflow-mutating：`push.py`、`run_stack_*.sh`、`multi_dir_push_stack.sh`。
- [ ] 为 `check_h5_completion --push_stack` 和 `push.py` 添加 workflow-mutating path policy。
- [ ] 为所有注册脚本设置 `approval_required=True`。
- [ ] 不注册 `check_sum_rule.py`。
- [ ] 不注册 `plot_compressibility_*`、`get_n_from_best_mu.py`、`get_mu.py`、`scripts/mu_tuning_*`。
- [ ] 不注册 `multi_dir_submit_sbatch.sh`。

验收：

- [ ] `list_script_adapters` 能显示脚本类别、安全模式、是否需要用户同意、暂不接入清单。
- [ ] `describe_script_adapter("check_warm")` 返回 root/glob/output_dir/可选 observable flags。
- [ ] `describe_script_adapter("plot_JNJN")` 返回 `JNJN_xx_perbin.npy` 或指定 correlator 文件 preflight 要求。
- [ ] `gen_beta_scan` 支持 dry-run provenance 和真实 input generation；真实执行前必须带用户同意。

## Phase 7：脚本输出解析器

- [ ] TSV parser：`h5_completion_report.tsv`、`warmup_summary.tsv`。
- [ ] NPY/NPZ manifest parser：只记录 shape/dtype/path，不默认加载大数组。
- [ ] Image manifest：记录 png/pdf 路径、大小、mtime。
- [ ] Stdout parser：基础 key-value 行和原始 tail。
- [ ] 输出文件 provenance：脚本、命令、参数、cwd、dqmc-dev git hash、用户同意记录。

验收：

- [ ] `check_warm` 输出 summary TSV 和 plots manifest。
- [ ] `plot_JNJN` 缺少 per-bin `.npy` 时 preflight 失败。
- [ ] `make_bootstrap` 输出 bootstrap `.npy` manifest。
- [ ] parser 失败不抹掉脚本执行结果，只添加 warning。

## Phase 8：SLURM 只读查询

- [ ] 实现 `query_slurm`。
- [ ] 支持 filters：user、job_id、state、partition。
- [ ] 优先 `squeue --json`，失败后 fallback delimited output。
- [ ] 缺少 `squeue` 返回 `tool_unavailable`。

验收：

- [ ] monkeypatch `squeue` unavailable/fallback/json 三类测试通过。
- [ ] 不存在 submit/cancel/scancel/sbatch 工具。

## Phase 9：MCP adapter

- [ ] 重写 `dqmc_mcp_server.py` 为薄 adapter。
- [ ] 注册 10 个通用 MCP tools。
- [ ] 每个 description 写清楚何时用、何时不用、路径限制、返回事实。
- [ ] `run_script_adapter` description 明确要求先向用户展示命令和读写路径，并获得本次同意。
- [ ] adapter 捕获异常并转成 JSON-safe error。
- [ ] MCP 层不包含领域逻辑。

验收：

- [ ] MCP tools 集合稳定。
- [ ] `resolve_registry_entry`、`read_registered_quantity`、`estimate_registered_observable`、`run_script_adapter` 转发测试通过。
- [ ] 没有用户同意时 MCP 调用 `run_script_adapter` 返回结构化拒绝。

## Phase 10：文档和迁移

- [ ] 更新 README：安装、环境变量、MCP 启动、示例。
- [ ] 添加脚本 adapter registry 文档。
- [ ] 标注第一版暂不接入的 sum-rule、mu-tuning/compressibility 和 submitting 脚本。
- [ ] 保留旧 API 兼容说明。
- [ ] 记录“不做物理判断”的工具边界。
- [ ] 记录“脚本真实执行必须逐次征求用户显式同意”的操作流程。

验收：

- [ ] 用户能按 README 配置 allowed roots，默认写入 `outputs/` 并跑一个 fixture 示例。
- [ ] 文档明确说明已有 `dqmc-dev/scripts` 是复用资产。

## Phase 11：最终验证

- [ ] `pytest` 全量通过。
- [ ] 在本地 fixture 上跑 HDF5/read/run/script/MCP smoke tests。
- [ ] `git status` 只包含本次实现相关文件和用户已有改动。
- [ ] 最终回复列出实现文件、验证命令、未启用能力。

## 第一版明确不做

- [ ] 不提交 SLURM job。
- [ ] 不取消 job。
- [ ] 不修改原始 HDF5。
- [ ] 不把每个已有分析脚本注册成独立 MCP tool。
- [ ] 不重新实现 MaxEnt、warmup 物理逻辑。
- [ ] 不重新实现 HDF5 读取和 jackknife 逻辑。
- [ ] 第一期不做 compressibility、best-mu 选择、coarse/fine mu-tuning 目录工作流、sum rule。
- [ ] 不把 `JNJN` 当成可直接从单个原始 HDF5 读取并带误差的量。
- [ ] 不把 sign/Trotter/warmup 诊断结论写进工具返回值。
