# DQMC Agent Backlog

本文档记录当前 DQMC agent 项目的待办事项、优先级、依赖关系和已确认的设计边界。它是执行层面的 todo list；长期愿景放在 `specs/goals.md`。

## 当前基线

- [x] “手”层已经有第一版 MCP tools：`summarize_run`、`inspect_hdf5`、`read_dataset`、`resolve_registry_entry`、`read_registered_quantity`、`estimate_registered_observable`、`list_script_adapters`、`describe_script_adapter`、`run_script_adapter`、`query_slurm`、`query_slurm_history`、`get_slurm_job_detail`、`infer_slurm_path_candidates`、`sync_sherlock_artifacts`。
- [x] 当前测试可通过：`116 passed`。
- [x] `registry.yaml` 是当前“手”层唯一被运行时代码真正读取的三份“眼睛”文件之一。
- [x] `code_map.md` 和 `diagnostics_playbook.md` 目前没有被 `dqmc_tools/` 或 `dqmc_mcp_server.py` 运行时读取。
- [x] `diagnostics_playbook.md` 当前只作为设计输入和人工知识来源；“手”层不自动执行 sign、Trotter、warmup、mu tuning、MaxEnt binning 等诊断判断。
- [x] Slack bot 接入对象是 agent 整体，不是 MCP tools。
- [x] 本地 OpenACP backend helper scripts 已落地：`scripts/start-slackbot-backend`、`scripts/stop-slackbot-backend`、`scripts/test_slackbot_backend_commands.sh`。
- [x] 最新产品形态决策：不把 Sherlock login node 上的长连接 MCP server 作为推荐最终方案；改为本地 `sherlock-remote-gateway` MCP 按需短 SSH 到 Sherlock，远端执行白名单短命 Python 调用后立即断开。
- [x] 白名单 script adapter 当前只保留 `DQMC_DEV_ROOT/scripts/` 下的脚本；`util/` 路径脚本已经移出白名单。
- [x] 当前白名单 adapter 数量为 20；其中 18 个 Python 脚本可静态读取 `argparse`，2 个 shell 脚本保留 raw args。

## P0：先补质量和边界

- [ ] 提高测试质量。
  - 现状：测试能过；已新增 MCP 层 contract tests，`test_runs.py` 和 HDF5 读取类测试已改用真实 `data/T_0.1` fixture，runner subprocess 和输出 parser 集成测试已改用真实 dqmc-dev adapters + `data/T_0.1` 临时 fixture；仍保留少量 synthetic 测试用于缺失 dataset、精确 jackknife、argv builder、monkeypatched SLURM 和临时 registry。
  - 目标：把测试从“接口能跑”提升到“真实工作流不容易坏”。
  - 建议拆分：
    - [x] Contract tests：固定核心 MCP tools 输入输出 schema，避免 agent/Slack 层依赖字段漂移。
      - 覆盖文件：`tests/test_mcp_contracts.py`。
      - 成功路径：`summarize_run`、`read_dataset`、`inspect_hdf5`、`read_registered_quantity`、`estimate_registered_observable`、`list_script_adapters`、`describe_script_adapter`、`run_script_adapter(dry_run=true)`、`query_slurm`、`query_slurm_history`、`get_slurm_job_detail`、`infer_slurm_path_candidates`、`sync_sherlock_artifacts(dry_run=true)`。
      - 错误路径：`path_not_allowed`、`user_approval_required`、`tool_unavailable`、`invalid_argument` 的 MCP 层 JSON-safe error contract。
      - 记录 MCP 层细节：顶层 list 返回在 `FastMCP.call_tool` structured content 中表现为 `{"result": [...]}`。
    - [x] Adapter contract tests：固定真实 catalog 中 `run_maxent_anneal` argparse schema、shell raw args、approval 字段等关键契约。
    - [x] Golden fixture tests：用 `data/T_0.1` 覆盖 `summarize_run`、`estimate_registered_observable`、log parsing、completion facts。
    - [x] 将 `tests/test_runs.py` 从临时 synthetic run/HDF5/log 替换为真实 `data/T_0.1` run summary。
    - [x] 将 `tests/test_hdf5.py` 的通用读取类测试替换为真实 `data/T_0.1/C_U-6_T0.1__0.h5`；仅保留 missing dataset 和小数组 jackknife 精确数值测试。
    - [x] Adapter integration smoke：覆盖真实 dqmc-dev script adapter 的 dry-run、preflight 缺输入、output root 限制。
    - [x] Regression tests：覆盖 registry 变更、脚本参数变更、dqmc-dev 路径缺失、allowed roots fail-closed。
    - [x] 移除冗余 fake adapter tests：fake list/describe、fake dry-run、fake preflight、fake output-root rejection 已由真实 catalog 测试替代。
    - [x] 用真实 adapter 替代 fake subprocess/parser tests：`check_h5_completion` 覆盖 TSV parser，`extract_energy_perfile` 覆盖 NPY manifest parser，二者都使用 `data/T_0.1` 复制到 `tmp_path` 的临时真实 fixture。
    - [ ] 继续减少 fake tests：评估是否能用更真实的 fixture 替代剩余 monkeypatched SLURM、临时 registry 和纯 argv builder synthetic 测试。

- [x] 明确本轮“眼睛”更新机制：`registry.yaml` 和 dqmc-dev script adapter。
  - [x] `registry.yaml`：当前调用时读取，通常不需要重启 MCP server。
  - [x] 为显式 `registry_path` 更新后重新读取添加测试。
  - [x] 为 `DQMC_REGISTRY_PATH` override 更新后重新读取添加测试。
  - [x] 为 MCP server 同实例通过 `registry_path` 读取更新后 registry 添加测试。
  - [x] 新增 adapter audit：`scripts/audit_script_adapters.py`。
  - [x] audit 覆盖 script path、launcher、category/mode、args schema、required input templates、output patterns、parser id、script id uniqueness、mtime/size/SHA-256。
  - [x] 修正内置 catalog 中单元素 `output_patterns` 被误写成字符串的问题。
  - [x] 记录 `DQMC_DEV_ROOT` 指向的底层脚本更新后的 adapter 同步流程。
  - [x] 文档落盘：`docs/update-mechanism.md`。
  - [x] 手工 MCP 验证：修改后的 `registry.yaml` 新增条目可被当前会话读取。
    - `read_registered_quantity(sign_eqlt, mode=directory)` -> `meas_eqlt/sign`，shape `[100]`，mean `160000.0`。
    - `read_registered_quantity(n_sample_eqlt, mode=directory)` -> `meas_eqlt/n_sample`，shape `[100]`，mean `160000.0`。
    - `read_registered_quantity(sign_uneqlt, mode=directory)` -> `meas_uneqlt/sign`，shape `[100]`，mean `2000.0`。
    - `read_registered_quantity(n_sample_uneqlt, mode=directory)` -> `meas_uneqlt/n_sample`，shape `[100]`，mean `2000.0`。
  - [x] 白名单收缩：移除所有原脚本路径不在 `dqmc-dev/scripts/` 下的 adapter。
    - 移除项：`gen_1band_unified_hub`、`dqmc_info`、`dqmc_summary`、`print_n`、`push`。
    - 第一阶段排除项同时包含此前移除的 `make_bootstrap`、`save_boot_stats`、`run_maxent`、`run_stack_simes`。
  - [x] 新增静态 argparse 同步机制。
    - 从当前白名单 adapter 出发，只读访问 `DQMC_DEV_ROOT/scripts/` 下的对应源码。
    - 不 import、不执行 dqmc-dev 脚本，避免副作用和运行环境依赖。
    - 解析直接的 `argparse.ArgumentParser()`、`add_argument()`、argument group、mutually-exclusive group。
    - 同步 flag、positional、required、type、choices、nargs、`store_true`/`store_false` 到 adapter `args_schema`。
    - 保留 adapter 侧人工维护的 `path_role`、`required_inputs`、`output_patterns`、`parser_id` 和审批策略。
  - [x] `scripts/audit_script_adapters.py` 现在报告 argparse 同步状态。
    - 当前结果：`Argparse sync: 18 parsed, 2 skipped, 0 warnings`。
    - `--json` 输出包含 `argparse_sync`、`argparse_parsers`、每个 parser 的 `schema_diff`。
  - [x] runner 支持 `store_false` 和 `false_flag`，可处理 `--sym/--nonsym` 这类 argparse 互斥布尔参数。
  - [x] 增加 adapter schema diff/report，清晰显示 dqmc-dev 脚本更新导致的参数新增、移除、changed fields、required 增减。
  - [ ] 后续增强：为静态 argparse 同步补充更多边界场景。
    - [ ] 支持跨 helper 函数添加参数的复杂 parser。
    - [ ] 对 parser 中动态 default、动态 choices、无法静态解析的表达式输出 warning。
    - [ ] 评估是否需要从 `--help` 补充静态 AST 无法覆盖的参数信息。

- [ ] 明确其余“眼睛”文件的运行时接入方式。
  - [ ] `code_map.md`：当前不被运行时读取；若要生效，需要人工同步到 `dqmc_tools/scripts/builtin_catalog.py` 或新增生成/索引机制。
  - [x] `diagnostics_playbook.md`：第一阶段通过 agent-side skill 接入；skill 固定要求 agent 读取 playbook 相关段落、调用 MCP hands 获取事实，并区分工具事实、playbook 规则和 agent 推断。MCP hands 当前仍不在运行时读取 playbook。
  - [ ] `dqmc_tools/scripts/builtin_catalog.py` 等代码：改动后需要重启 MCP server。
  - [ ] `dqmc-dev/scripts/` 更新：重新运行 `scripts/audit_script_adapters.py` 可重新读取源码并更新当前 Python 进程内的 adapter schema；已运行的 MCP server 仍需要重启或重载。

- [ ] 记录并测试“手”层边界。
  - [ ] MCP tools 只返回事实、路径、数组摘要、脚本结果和 structured error。
  - [ ] MCP tools 不做 sign quality、warmup 质量、Trotter 误差、物理可靠性判断。
  - [ ] 高层物理解释和诊断建议应在 agent/眼睛层完成。

## P1：SLURM 只读能力增强

对应细化规格：`specs/sherlock-slurm-sdd/`。

- [x] 增强 `query_slurm` 的分类视图。
  - [x] 支持 `filters={"me": true}`，底层命令生成 `squeue --me`。
  - [x] 分类显示当前队列任务：`running`、`pending`、`held_blocked`、`other`。
  - [x] 保留当前 filters：user、job_id、state、partition；新增 `me`。
  - [x] 返回按 job name、array job id 分组的 `groups.by_job_name`。
  - [x] 返回全局 `summary`：total jobs、state counts、category counts、job name count、array job count。
  - [x] 保留原始 structured rows，供 agent/transport 层展示 partition、reason/runtime/limit/nodes 等细节。
  - [x] 覆盖 `squeue --json` 和 fallback delimited output 两种路径。
  - [x] normalize `squeue --json` wrapped fields，例如 list `job_state` 和 dict `array_job_id`/`array_task_id`。
  - [x] 保持只读：不接入 `sbatch`、`scancel`、`scontrol update`。
  - [ ] 在 Sherlock login node 上做真实 `squeue --me` 集成验证。
  - [x] 周期性查询暂不做阻塞式 MCP watcher；agent 层按用户指定 interval 重复调用 `query_slurm(filters={"me": true})`，用 `diff_slurm_snapshots` 比较 snapshots。

- [ ] Sherlock 当前运行状态入口。
  - [ ] agent 层提供“当前我的 Sherlock 任务状态”工作流；对应 `sherlock-slurm-sdd` Phase L1。
  - [ ] 底层仍调用 MCP `query_slurm`。
  - [ ] 返回面向用户的简洁摘要，同时保留原始 structured rows。

## P1：Agent 层 Slack/OpenACP Bot IM 接入

说明：本节是独立 transport backlog，不属于 `specs/sherlock-slurm-sdd/` 范围；Sherlock SLURM SDD 只定义 MCP hands 和非 Slack agent workflow。

- [x] 本地 OpenACP backend 启停脚本。
  - [x] `start-slackbot-backend`：读取本地私密 env 文件并启动 OpenACP backend。
  - [x] `stop-slackbot-backend`：停止当前 backend。
  - [x] `test_slackbot_backend_commands.sh`：覆盖 helper script 行为。
  - [ ] 在目标机器上完成真实 Slack/OpenACP token、allowlist 和 channel/thread smoke。

- [ ] 完整接入 Slack bot 作为 agent 的 transport adapter。
  - 注意：Slack bot 不应接进 MCP tools；MCP tools 不应知道 Slack user/channel/thread。
  - [ ] Slack Events API 或 Socket Mode 接收 IM/thread 消息。
  - [ ] Slack message -> agent session/thread 映射。
  - [ ] agent 决定调用哪些 MCP tools。
  - [ ] agent 将结果组织成 Slack 回复。

- [ ] Slack 只读命令优先。
  - [ ] `dqmc status`：调用 `query_slurm` 并分类显示。
  - [ ] `dqmc jobs`：列出 running/pending/other jobs。
  - [ ] `dqmc run-summary <path>`：调用 `summarize_run`。
  - [ ] `dqmc adapter <script_id>`：调用 `describe_script_adapter`。

- [ ] Slack 审批流程。
  - [ ] 对 `run_script_adapter(dry_run=false)` 等真实执行动作，先展示 dry-run command、cwd、读写路径、preflight。
  - [ ] 用 Slack interactive button/modal 收集本次显式确认。
  - [ ] 确认后由 agent 调用 MCP tool，传入 `user_confirmation`。
  - [ ] 记录审批人、Slack thread、命令、参数、输出 manifest。

## P1：Sherlock Remote Gateway

目标：把 Slack/OpenACP -> 本地 Codex 的入口和 Sherlock 真实环境能力连起来，但不在 Sherlock login node 上长期运行 Codex 或长连接 MCP server。

- [x] 新增独立规格：`specs/sherlock-remote-gateway-sdd/`。
  - [x] 明确推荐架构：本地 Codex 是唯一 agent 大脑，本地 gateway MCP 按需 SSH 到 Sherlock。
  - [x] 明确非目标：不启动远端 Codex，不提供任意 shell，不实现 `sbatch`，不在 Sherlock 上常驻 daemon。
  - [x] 明确安全边界：远端短命进程、硬 timeout、窄 allowed roots、专用 output root、`/scratch` fail-closed。

- [x] 实现第一版本地 gateway MCP 工具面。
  - [x] `sherlock_query_slurm`：短 SSH 调用远端 `query_slurm`。
  - [x] `sherlock_query_slurm_history`：短 SSH 调用远端 `query_slurm_history`。
  - [x] `sherlock_get_slurm_job_detail`：短 SSH 调用远端 `get_slurm_job_detail`。
  - [x] `sherlock_summarize_run`：只允许 bounded summary，例如 `max_files` 默认很小。
  - [x] 第一版只做只读查询，不做真实 script execution。
  - [ ] 后续评估 `sherlock_infer_path_candidates`：当前本地已有纯推断工具，只有需要 Sherlock 端路径可访问性语义时再补。

- [x] 实现远端短命 Python entrypoint。
  - [x] 形式：`.venv/bin/python -m dqmc_tools.remote_call --cwd <repo>`。
  - [x] stdin/stdout 只传 JSON，不输出杂音。
  - [x] 只允许白名单 tool name。
  - [x] 返回 JSON-safe structured result 或 structured error。
  - [x] 本地 gateway 对 SSH 子进程设置 timeout，默认 60 秒。

- [x] 实现 SSH 调用安全策略。
  - [x] 本地 subprocess 使用 argv list，不拼 shell string。
  - [x] SSH target 使用 allowlist，例如只允许 `sherlock`。
  - [x] 远端 repo path、`DQMC_DEV_ROOT`、`DQMC_ALLOWED_ROOTS`、`DQMC_OUTPUT_ROOT` 来自配置，不从用户消息直接拼接。
  - [x] SSH unavailable、timeout、nonzero exit、非 JSON stdout 返回 structured error。

- [x] 实现本地测试计划。
  - [x] 本地 gateway command builder test。
  - [x] remote_call whitelist/error contract tests。
  - [x] SSH unavailable / timeout / nonzero exit tests。
  - [x] JSON parse failure tests，防止 shell banner 或 `.bashrc` 输出污染协议。
  - [x] MCP contract tests。

- [ ] Sherlock smoke。
  - [ ] 先用 `specs/sherlock-slurm-sdd/sherlock-validation-handoff.md` 完成环境基线验证。
  - [ ] 再用 gateway 调 `sherlock_query_slurm` 和 `sherlock_query_slurm_history`。
  - [ ] 记录真实字段形态，必要时补脱敏 fixture。

## P1/P2：同步 SLURM 产物到本地

- [x] 设计并实现本地受限 rsync/同步能力。
  - 对应 `sherlock-slurm-sdd` Phase L5/R5。
  - [x] 先做 dry-run。
  - [x] 明确远端 allowlist、目标本地 output root、覆盖策略。
  - [x] 返回同步 manifest：新增文件、更新文件、跳过文件、unknown。
  - [ ] 同步完成后可衔接本地 HDF5/analysis tools。
  - [ ] 真实 Sherlock 小目录 dry-run 验证。

- [ ] 接入 Sherlock 产物同步工作流。
  - [ ] agent 根据 job/run path 提示同步命令。
  - [ ] 用户审批后执行同步。
  - [ ] 同步结果进入本地 `summarize_run` 或后处理脚本。

## P2：已结束任务状态补全

- [x] 实现 `query_slurm_history` / `sacct` 只读历史查询。
  - 对应 `sherlock-slurm-sdd` Phase L2。
  - [x] 新增 MCP tool：`query_slurm_history`。
  - [x] 使用 `sacct --parsable2 --noheader` 和字段白名单。
  - [x] 支持 filters：me、user、job_id、state、start、end、partition、max_rows。
  - [x] 返回 state counts、exit code counts、warnings。
  - [x] `sacct` 不可用时返回 structured `tool_unavailable`。
  - [ ] 在 Sherlock 上确认 `sacct` 可用性、默认时间窗口、`WorkDir` 和 array job 格式。

- [x] Job id 详情入口。
  - 对应 `sherlock-slurm-sdd` Phase L3。
  - [x] 新增 `get_slurm_job_detail`。
  - [x] 当前队列优先查 `query_slurm`，需要历史时查 `query_slurm_history`。
  - [x] 支持 array parent/task id。
  - [x] 多个匹配返回 candidates，不猜。

- [x] Job 到 run/output path 候选关联。
  - 对应 `sherlock-slurm-sdd` Phase L4。
  - [x] 候选来源：`sacct WorkDir`、stdout/stderr parent、用户显式 path。
  - [x] 不做大目录扫描。
  - [x] 路径必须在 allowed roots 内，越界 fail closed。
  - [ ] submit cwd 需要 Sherlock 真实字段确认后补 fixture。

## P3：提交 SLURM 任务

- [ ] 设计 `sbatch` 提交能力。
  - 对应 `sherlock-slurm-sdd` Phase L7/R7；这是高风险能力，应在测试、只读状态查询、历史查询、job detail、产物同步、逐次审批和 provenance 都稳定后再做。
  - Slack 审批是独立 transport 能力，不作为 Sherlock SLURM SDD 的前置条件。
  - [ ] 必须先 dry-run，展示 job script、命令、cwd、读写路径、资源参数。
  - [ ] 必须逐次用户审批。
  - [ ] 必须记录 provenance：提交人、参数、脚本、git hash、job id、输出路径。
  - [ ] 必须限制资源参数和提交目录。
  - [ ] 第一版不做 cancel；cancel 是单独高风险 backlog。

## 诊断知识接入

- [x] 决定 `diagnostics_playbook.md` 的第一阶段接入方式：新增 agent-side skill。
  - 已新增 repo-local skill：`skills/dqmc-diagnostics-playbook/SKILL.md`。
  - 已同步到 Codex 全局 skill 目录：`/Users/phoenixm/.codex/skills/dqmc-diagnostics-playbook/SKILL.md`。
  - 选项 D：agent-side skill 作为选项 A 的流程化实现。它不新增 MCP tool，不执行代码，只固定 agent 的读取、事实收集和分层解释流程。
  - 选项 A：只作为 agent 可读文档，由 agent 在需要时读取或检索。
  - 需要保持边界：MCP hands 默认不做物理可靠性结论，除非新增工具明确命名为 diagnostic guidance。

- [x] Agent-side skill 当前覆盖以下 playbook 内容。
  - [x] sign problem：平均 sign 小会放大统计误差；sign reweighting 需要 jackknife/bootstrap。
  - [x] Trotter error：`beta = L * dt`，经验条件 `dt^2 * U * t <= 1/8`。
  - [x] warmup/sweeps：早期 time series、running mean、前后半段均值差异。
  - [x] mu tuning：半填充约定、目标 filling、`|n_measured - n_target| <= 0.01`。
  - [x] compressibility：`dn/dmu` 通常应为正。
  - [x] MaxEnt binning：典型 bin 数建议 `n_bin = 2L`。

## 文档维护

- [ ] 更新 README，明确三份“眼睛”文件的实际依赖形式。
- [x] 更新 README，记录 script adapter 只复用 `dqmc-dev/scripts/`、argparse 静态同步和 audit 命令。
- [x] 更新 script adapter 文档，记录白名单范围、argparse 同步范围和 shell raw args 边界。
- [ ] 更新 script adapter 文档，说明 `code_map.md` 变化不会自动改变白名单。
- [ ] 新增 agent/Slack 架构文档，说明 Slack bot 属于 agent transport。
- [ ] 新增操作手册：registry 更新、playbook 更新、dqmc-dev 脚本更新、MCP server 重启条件。
