# DQMC Hands 重写需求规格

状态：草案，等待审阅后再实现。

## 背景

这次重写的输入材料是当前工程里的三份“眼睛”：

- `registry.yaml`：58 个 observable、16 个参数条目的物理定义、存储变量、归一化、测量条件和代码位置。
- `code_map.md`：`dqmc-dev` 的数据流、C 核心、`util/` 和 `scripts/` 已有能力地图。
- `diagnostics_playbook.md`：sign problem、Trotter error、sweep/warmup、mu tuning、MaxEnt binning 等诊断经验。

同时参考工程计划文件中对“手”的定位：手只提供可调用动作和事实结果，不替上游 agent 做物理判断。

## 总目标

从零重写 `dqmc_tools/` 和 MCP adapter，使其成为一个薄、安全、可测试的 DQMC 操作层：

- 普通 Python 包先成立，MCP 只是薄包装。
- 工具返回事实、元数据、输出文件路径、命令 provenance；不返回“可信/不可信”“物理上合理/不合理”等判断。
- 优先复用 `DQMC_DEV_ROOT` 指向的 `dqmc-dev` checkout 中已有 `util/` 和 `scripts/` 能力；不要把每个分析需求重新实现成一个新 MCP tool。
- 原始 HDF5 不允许被修改；会写文件的动作只能写到 output root 或被允许的 workflow 文件位置。
- `dqmc-dev` 路径来自必填环境变量 `DQMC_DEV_ROOT`，第一版不做路径自动发现。
- output root 默认是当前工程的 `outputs/`，也可用显式参数覆盖到该根目录下的子路径。

## 非目标

- 不写独立 FastAPI 后台。
- 不写 agent 编排框架。
- 不做向量数据库、RAG 服务或知识图谱。
- 不重新实现 `dqmc-dev/scripts` 已经覆盖的分析、绘图、MaxEnt、stack workflow。
- 第一版暂不接入 sum rule 诊断：`scripts/check_sum_rule.py`。
- 第一版暂不接入 best-mu 选择、compressibility 绘图、coarse/fine mu-tuning 目录工作流：`scripts/plot_compressibility_from_best_mu.py`、`scripts/plot_compressibility_from_n_mu.py`、`scripts/get_n_from_best_mu.py`、`util/get_mu.py`、`scripts/mu_tuning_*`。
- 第一版不提交、取消或修改 SLURM 作业；只查询队列事实。
- 第一版不修改原始 `.h5` 数据。

## 用户场景

1. 摘要用户指定的 run：
   用户显式给出一个 run 目录，agent 只对该目录做摘要，不自行扫描 scratch 根目录来发现 run。

2. 读取单个 HDF5 文件中的原始量：
   用户问某个文件里的 density、double occupancy、sign、`gt0` 或参数，agent 根据 `registry.yaml` 的 `id/aliases/code.generation.variable` 找到对应 dataset key，再通过 `dqmc-dev/util/util.py` 的 `load_file()` 读取事实。单个 HDF5 文件不返回误差估计。

3. 对一组 HDF5 文件估计 observable 和误差：
   用户给一个目录作为同一组 bins/files，agent 通过 `util.load()` 读取多文件数组，并用 `util.jackknife()` 或 `util.jackknife_noniid()` 计算均值和误差。误差不是直接从单个 HDF5 文件里读出来的。

4. 处理派生数据脚本：
   用户问 `JNJN` 这类二级结果时，agent 不把它当成可直接从单个 HDF5 读取的量。必须先确认一级脚本产物存在，例如 `JNJN_xx_perbin.npy`，再在用户显式同意后调用 `scripts/plot_JNJN.py` 等脚本。

5. 调已有诊断脚本：
   用户问 warmup 是否需要看、HDF5 是否完成，agent 先做输入 preflight，再向用户展示将执行的命令；用户明确同意后才运行 `check_warm.py` 或 `check_h5_completion.py`，并返回命令、输出文件、stdout/stderr 摘要、解析出的 TSV/数值事实。sum rule 第一期不做。

6. 调已有后处理脚本：
   用户要求抽取 local moment、energy per file、local one-particle G、per-bin current-current、bootstrap、MaxEnt 输入，agent 通过脚本白名单复用对应 `scripts/*.py`，但每次执行前都必须征求用户显式同意。

7. 生成输入文件或 scan：
   用户要求生成 beta scan 或 beta-mu scan，agent 复用 `scripts/gen_beta_scan.py`、`scripts/gen_beta_mu_scan.py` 和 `util/gen_1band_unified_hub.py`。第一版允许真实运行 input generation，也必须支持 dry-run/provenance；真实写入只允许在 output root 下，且执行前必须获得用户本次同意。

8. 查询队列：
   用户问当前 SLURM 状态，agent 只读调用 `squeue` 并返回结构化 job rows。不能 submit/cancel。

## 功能需求

### R1 路径与权限

- 所有读取路径必须在 `DQMC_ALLOWED_ROOTS` 或调用参数 `allowed_roots` 内。
- 所有写入路径必须在 output root 内；未配置时使用当前工程 `outputs/`。
- workflow-mutating 工具写 stack/workflow 文件时，目标文件也必须在允许范围内，并在脚本定义中显式声明。
- 路径必须 resolve 后再判断包含关系，拒绝 `..`、symlink 逃逸和不存在的 allowed root。
- 原始 `.h5` 文件只能只读打开。
- 子进程执行不能使用 shell string；必须使用 argv list。

### R2 Registry 是事实源

`registry.yaml` 的真实条目没有额外的派生标识字段。手层只能依赖并暴露这些真实字段：

- observable：`id`、`aliases`、`physics`、`code.measurement`、`code.generation.variable`、`code.generation.flags`、`requirements`、`normalization`、`units`、`data_layout`。
- parameter：`id`、`aliases`、`physics`、`code.generation.variable`、`type`、`required`、`default`、`units`、`normalization`。
- 支持按 `id`、alias、`code.generation.variable` 精确匹配或尾部匹配。
- 若 shorthand 匹配多个条目，必须返回候选列表，不猜测。
- 返回 registry entry 时保留原始字段名，并可额外标注 `entry_type` 和 `dataset_key`，其中 `dataset_key` 只是由 `code.generation.variable` 派生出的运行时字段，不是 registry 原字段。

### R3 HDF5 事实读取

- HDF5 数据读取调用 `DQMC_DEV_ROOT` 指向的 `util/util.py` 中已有的 `load()`、`load_file()`、`load_firstfile()`。手层不重新实现读取、bin 聚合或 jackknife 约定。
- `inspect_hdf5` 只做 `util.py` 相关函数的 wrapper：输入必须包含明确的 dataset keys 或 registry entry names；它不做 HDF5 tree 枚举、不新增 shape discovery 逻辑、不直接使用 `h5py`。
- `read_dataset` 是 `util.load_file(path, dataset_key)` 的安全包装，返回 shape、dtype、bounded preview、size、numeric summary。
- `read_registered_quantity` 根据 registry 的 `id/aliases/code.generation.variable` 找到 dataset key，然后调用 `load_file()`、`load_firstfile()` 或 `load()` 读取事实。
- 单文件读取不返回误差估计，也不尝试从单文件读取误差。
- 对 registry observable 的误差估计应通过一组 HDF5 文件完成：使用 `util.load()` 读取多个 bin/file 后，再用 `util.jackknife()` 或 `util.jackknife_noniid()` 计算 `{mean, error}`。
- 自动提取常用 metadata：`beta`、`dt`、`L`、`Nx`、`Ny`、`U`、`mu`、`sign`、`n_sample`、sweep 信息、measurement periods。

### R4 用户指定 run 摘要

- 不实现 `list_runs`。agent 不应自行扫描 scratch 根目录来寻找 run；每次由用户显式输入需要读取或处理的目录。
- `summarize_run` 只对用户显式给出的 run 目录做 bounded 摘要。
- `summarize_run` 可尝试用 registry 的 `code.generation.variable` 和 `util.load_firstfile()` 检查关键量是否可读取，但不做全仓库扫描。
- 对 sibling `.h5.log` 的 completion 信息，优先复用 `scripts/check_h5_completion.py`；如果内置轻量摘要，也必须只返回 log markers 和 sweep counts，不做物理判断。

### R5 已有脚本白名单

必须建立脚本注册表，而不是为每个脚本创建独立 MCP tool。注册表条目至少包含：

- `script_id`
- `script_path`
- category：`generation`、`diagnostic`、`analysis`、`plot`、`maxent`、`workflow`、`cluster`
- mode：`read_only`、`writes_output`、`mutates_workflow_files`、`submits_jobs`
- 参数 schema
- allowed input roots / output root 约束
- input preflight：每个脚本运行前必须检查所需输入文件是否存在、shape/后缀是否符合预期。尤其是二级脚本，例如 `scripts/plot_JNJN.py`，它消费的是一级脚本生成的 `JNJN_xx_perbin.npy` 等派生数据，而不是原始 HDF5；MCP 层必须在调用前明确检查这些派生文件。
- user approval policy：每次真实执行白名单脚本前，agent 必须向用户展示脚本 id、命令、cwd、将读写的路径、preflight 结果，并获得用户本次明确同意。dry-run、describe 和 preflight 可以不要求执行同意。
- stdout/stderr 捕获策略
- 输出文件 manifest 规则
- 解析器：none、stdout、tsv、npy/npz manifest、image manifest

第一版脚本注册表应覆盖这些已有能力：

| 类别 | 复用脚本 | 手层职责 |
| --- | --- | --- |
| 输入生成 | `scripts/gen_beta_scan.py`、`scripts/gen_beta_mu_scan.py`、`util/gen_1band_unified_hub.py` | 参数校验、dry-run、输出目录限制、命令 provenance、执行前征求用户同意 |
| 基础信息 | `util/info.py`、`util/summary.py`、`util/print_n.py` | 运行并解析/保留 stdout；执行前征求用户同意 |
| 完成度诊断 | `scripts/check_h5_completion.py` | 允许 `--push_stack` 这类 workflow-mutating 参数，但必须做路径和 stack 文件 preflight；执行前征求用户同意；解析 `h5_completion_report.tsv` |
| warmup | `scripts/check_warm.py` | 输出 `warmup_summary.tsv` 和 plot manifest；执行前征求用户同意 |
| equal-time analysis | `scripts/plot_double_occ.py`、`scripts/plot_charge_order.py`、`scripts/s_wave_pairing.py`、`scripts/extract_local_moment.py`、`scripts/extract_energy_perfile.py` | 产物 manifest、stdout 摘要、输入输出路径约束、执行前征求用户同意 |
| unequal-time / transport | `scripts/extract_1_particle_local_g.py`、`scripts/extract_perbin_jj.py`、`scripts/plot_JNJN.py`、`scripts/resistivity_proxy.py`、`scripts/conductivity_plot.py`、`scripts/resistivity_plot.py` | 复用现有脚本；对二级脚本先检查一级脚本产物，例如 per-bin `.npy`、MaxEnt 输出 `.npy/.npz`；执行前征求用户同意 |
| MaxEnt | `scripts/make_bootstrap.py`、`scripts/save_boot_stats.py`、`scripts/run_maxent.py`、`scripts/run_maxent_anneal.py`、`scripts/run_maxent_phoenix.py`、`scripts/plot_dos.py`、`util/maxent.py` | 调度白名单脚本和记录产物，不重写 MaxEnt；执行前征求用户同意 |
| workflow/stack | `util/push.py`、`scripts/run_stack_*.sh`、`scripts/multi_dir_push_stack.sh` | 第一版允许 workflow-mutating 工具；必须做路径、输入文件和 stack 文件 preflight；执行前征求用户同意；提交作业类脚本仍不做 |

说明：`scripts/gen_beta_mu_scan.py` 属于 input generation 范围，第一版允许真实运行；暂不接入的是后续根据已跑结果选择 best mu、画 compressibility、自动组织 coarse/fine mu-tuning 目录的特殊工作流。

第一版明确暂不注册：

- `scripts/check_sum_rule.py`
- `scripts/plot_compressibility_from_best_mu.py`
- `scripts/plot_compressibility_from_n_mu.py`
- `scripts/get_n_from_best_mu.py`
- `util/get_mu.py`
- `scripts/mu_tuning_*`
- `scripts/multi_dir_submit_sbatch.sh`

### R6 脚本执行结果

每次脚本执行返回：

- `ok`
- `script_id`
- `command`
- `cwd`
- `env_overrides`
- `user_confirmation`：记录本次用户同意的事实；没有本次同意时不得执行
- `started_at`、`ended_at`、`duration_seconds`
- `returncode`
- stdout/stderr tail
- `output_files`
- `parsed_outputs`
- `warnings`

### R7 MCP 工具面

MCP 层应保持少量通用工具：

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

不要把 `check_warm`、`plot_double_occ`、`run_maxent` 等各自注册成 MCP tool；它们应是 `run_script_adapter` 的白名单条目。`run_script_adapter` 的 description 必须明确：真实执行前必须先向用户征求本次同意。

### R8 错误处理

- 所有预期错误返回 JSON-safe shape：`ok=false`、`error_type`、`message`、`details`。
- 子进程失败不抛出未结构化 traceback；返回 returncode、stderr tail、已生成文件清单。
- timeout、缺依赖、脚本不存在、路径越界、参数 schema 失败、缺少用户同意要区分 error type。

### R9 Provenance

- 对任何读取或执行动作，结果必须可追溯到路径、registry 版本、脚本路径、命令参数、工作目录、输出文件。
- 若 `dqmc-dev` 是 git repo，脚本执行结果应尽量记录 `git rev-parse --short HEAD`；拿不到时返回 null。

### R10 测试

- 核心 Python 包不依赖 MCP 即可测试。
- MCP adapter 只测试注册和转发。
- HDF5 使用小型临时 fixture。
- 脚本 runner 用 fake script 覆盖安全、timeout、stdout/stderr、manifest、schema、缺少用户同意。
- 对真实 `dqmc-dev` 脚本至少做 `--help` 或 dry-run smoke test；input generation 还需要真实写入临时 output root 的集成测试。

## 验收标准

- `pytest` 通过。
- import `dqmc_tools` 不导入 `mcp`、FastAPI 或 agent SDK。
- 未配置 allowed roots 时 raw data 工具 fail closed。
- 未配置 output root 时使用当前工程 `outputs/`，且输出不得逃逸该目录。
- `resolve_registry_entry("density")` 能唯一解析到 registry 中 `id: density` 的条目；歧义项返回候选。
- `read_registered_quantity` 能按 registry 的 `code.generation.variable` 读取单文件事实，但不返回误差。
- `estimate_registered_observable` 能对同一目录下多个 `.h5` 文件使用 `jackknife()` 或 `jackknife_noniid()` 返回 `{mean, error}`。
- `run_script_adapter("check_warm", ...)` 没有本次用户同意时拒绝执行；有本次用户同意时能在 fixture output root 下生成 manifest。
- MCP tool descriptions 明确写明“何时使用/何时不用/返回事实而非判断/脚本执行前必须征求用户同意”。

## 已确认的一期决策

- 第一版允许真实运行 input generation。
- 第一版允许 workflow-mutating 工具，例如 `util/push.py` 和 `check_h5_completion.py --push_stack`，但不允许提交/取消 SLURM job。
- `dqmc-dev` 路径来自必填环境变量 `DQMC_DEV_ROOT`。
- output root 默认是当前工程 `outputs/`。
- 不实现 `list_runs`；所有 run 目录由用户手动输入。
