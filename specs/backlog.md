# DQMC Agent Backlog

本文档记录当前 DQMC agent 项目的待办事项、优先级、依赖关系和已确认的设计边界。它是执行层面的 todo list；长期愿景放在 `specs/goals.md`。

## 当前基线

- [x] “手”层已经有第一版 MCP tools：`summarize_run`、`inspect_hdf5`、`read_dataset`、`resolve_registry_entry`、`read_registered_quantity`、`estimate_registered_observable`、`list_script_adapters`、`describe_script_adapter`、`run_script_adapter`、`query_slurm`。
- [x] 当前测试可通过：`49 passed`。
- [x] `registry.yaml` 是当前“手”层唯一被运行时代码真正读取的三份“眼睛”文件之一。
- [x] `code_map.md` 和 `diagnostics_playbook.md` 目前没有被 `dqmc_tools/` 或 `dqmc_mcp_server.py` 运行时读取。
- [x] `diagnostics_playbook.md` 当前只作为设计输入和人工知识来源；“手”层不自动执行 sign、Trotter、warmup、mu tuning、MaxEnt binning 等诊断判断。
- [x] Slack bot 接入对象是 agent 整体，不是 MCP tools。

## P0：先补质量和边界

- [ ] 提高测试质量。
  - 现状：测试能过，但大量测试仍是 mock、临时 HDF5、fake script 或 schema 检查。
  - 目标：把测试从“接口能跑”提升到“真实工作流不容易坏”。
  - 建议拆分：
    - [ ] Contract tests：固定 MCP tools 输入输出 schema，避免 agent/Slack 层依赖字段漂移。
    - [ ] Golden fixture tests：用 `data/T_0.1` 覆盖 `summarize_run`、`estimate_registered_observable`、log parsing、completion facts。
    - [ ] Adapter integration smoke：覆盖真实 dqmc-dev script adapter 的 dry-run、preflight、缺输入、输出 manifest。
    - [ ] Regression tests：覆盖 registry 变更、脚本参数变更、dqmc-dev 路径缺失、allowed roots fail-closed。

- [x] 明确本轮“眼睛”更新机制：`registry.yaml` 和 dqmc-dev script adapter。
  - [x] `registry.yaml`：当前调用时读取，通常不需要重启 MCP server。
  - [x] 为显式 `registry_path` 更新后重新读取添加测试。
  - [x] 为 `DQMC_REGISTRY_PATH` override 更新后重新读取添加测试。
  - [x] 为 MCP server 同实例通过 `registry_path` 读取更新后 registry 添加测试。
  - [x] 新增 adapter audit：`scripts/audit_script_adapters.py`。
  - [x] audit 覆盖 script path、launcher、category/mode、args schema、required input templates、output patterns、parser id、script id uniqueness、mtime/size/SHA-256。
  - [x] 修正内置 catalog 中单元素 `output_patterns` 被误写成字符串的问题。
  - [x] 记录 `/Users/phoenixm/Desktop/dqmc-dev` 底层脚本更新后的 adapter 同步流程。
  - [x] 文档落盘：`docs/update-mechanism.md`。
  - [x] 手工 MCP 验证：修改后的 `registry.yaml` 新增条目可被当前会话读取。
    - `read_registered_quantity(sign_eqlt, mode=directory)` -> `meas_eqlt/sign`，shape `[100]`，mean `160000.0`。
    - `read_registered_quantity(n_sample_eqlt, mode=directory)` -> `meas_eqlt/n_sample`，shape `[100]`，mean `160000.0`。
    - `read_registered_quantity(sign_uneqlt, mode=directory)` -> `meas_uneqlt/sign`，shape `[100]`，mean `2000.0`。
    - `read_registered_quantity(n_sample_uneqlt, mode=directory)` -> `meas_uneqlt/n_sample`，shape `[100]`，mean `2000.0`。
  - [ ] 后续增强：自动从脚本 `--help` 或结构化 spec 生成/校验 adapter schema。

- [ ] 明确其余“眼睛”文件的运行时接入方式。
  - [ ] `code_map.md`：当前不被运行时读取；若要生效，需要人工同步到 `dqmc_tools/scripts/builtin_catalog.py` 或新增生成/索引机制。
  - [ ] `diagnostics_playbook.md`：当前不被运行时读取；若要生效，需要新增只读 resource/tool、结构化 diagnostic registry，或 agent 层检索机制。
  - [ ] `dqmc_tools/scripts/builtin_catalog.py` 等代码：改动后需要重启 MCP server。

- [ ] 记录并测试“手”层边界。
  - [ ] MCP tools 只返回事实、路径、数组摘要、脚本结果和 structured error。
  - [ ] MCP tools 不做 sign quality、warmup 质量、Trotter 误差、物理可靠性判断。
  - [ ] 高层物理解释和诊断建议应在 agent/眼睛层完成。

## P1：SLURM 只读能力增强

- [ ] 增强 `query_slurm` 的分类视图。
  - [ ] 分类显示当前已提交任务：running、pending、held/blocked、other。
  - [ ] 保留当前 filters：user、job_id、state、partition。
  - [ ] 输出 job summary：数量、partition、state、reason、runtime、limit、nodes。
  - [ ] 保持只读：不接入 `sbatch`、`scancel`、`scontrol update`。

- [ ] Sherlock 当前运行状态入口。
  - [ ] agent 层提供“当前我的 Sherlock 任务状态”工作流。
  - [ ] 底层仍调用 MCP `query_slurm`。
  - [ ] 返回面向用户的简洁摘要，同时保留原始 structured rows。

## P1：Agent 层 Slack Bot IM 接入

- [ ] 接入 Slack bot 作为 agent 的 transport adapter。
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

## P1/P2：同步 SLURM 产物到本地

- [ ] 设计 rsync/同步能力。
  - [ ] 先做 dry-run。
  - [ ] 明确远端 allowlist、目标本地 output root、覆盖策略。
  - [ ] 返回同步 manifest：新增文件、更新文件、跳过文件、大小、mtime。
  - [ ] 同步完成后可衔接本地 HDF5/analysis tools。

- [ ] 接入 Sherlock 产物同步工作流。
  - [ ] agent 根据 job/run path 提示同步命令。
  - [ ] 用户审批后执行同步。
  - [ ] 同步结果进入本地 `summarize_run` 或后处理脚本。

## P2：已结束任务状态补全

- [ ] 评估只读邮件接入。
  - 目标：访问已结束任务的成功/失败通知。
  - 依赖：邮箱/IMAP/API 权限、隐私过滤、job id/path 关联规则。
  - 风险：邮件格式不稳定，权限和隐私边界更复杂。

- [ ] 优先评估 SLURM 原生命令是否足够。
  - [ ] `sacct` 只读历史状态可能比邮件更结构化。
  - [ ] 若 `sacct` 可用，应优先接入 `sacct`，邮件作为补充。

## P3：提交 SLURM 任务

- [ ] 设计 `sbatch` 提交能力。
  - 这是高风险能力，应在测试、Slack 审批、只读状态查询、产物同步都稳定后再做。
  - [ ] 必须先 dry-run，展示 job script、命令、cwd、读写路径、资源参数。
  - [ ] 必须逐次用户审批。
  - [ ] 必须记录 provenance：提交人、参数、脚本、git hash、job id、输出路径。
  - [ ] 必须限制资源参数和提交目录。
  - [ ] 第一版不做 cancel；cancel 是单独高风险 backlog。

## 诊断知识接入待决

- [ ] 决定 `diagnostics_playbook.md` 的接入方式。
  - 选项 A：只作为 agent 可读文档，由 agent 在需要时读取或检索。
  - 选项 B：拆成结构化 YAML/JSON diagnostic rules，由工具返回事实、agent 解释规则。
  - 选项 C：新增只读 MCP resource/tool 暴露 playbook sections。
  - 需要保持边界：MCP hands 默认不做物理可靠性结论，除非新增工具明确命名为 diagnostic guidance。

- [ ] 若结构化接入，需要覆盖以下 playbook 内容。
  - [ ] sign problem：平均 sign 小会放大统计误差；sign reweighting 需要 jackknife/bootstrap。
  - [ ] Trotter error：`beta = L * dt`，经验条件 `dt^2 * U * t <= 1/8`。
  - [ ] warmup/sweeps：早期 time series、running mean、前后半段均值差异。
  - [ ] mu tuning：半填充约定、目标 filling、`|n_measured - n_target| <= 0.01`。
  - [ ] compressibility：`dn/dmu` 通常应为正。
  - [ ] MaxEnt binning：典型 bin 数建议 `n_bin = 2L`。

## 文档维护

- [ ] 更新 README，明确三份“眼睛”文件的实际依赖形式。
- [ ] 更新 script adapter 文档，说明 `code_map.md` 变化不会自动改变白名单。
- [ ] 新增 agent/Slack 架构文档，说明 Slack bot 属于 agent transport。
- [ ] 新增操作手册：registry 更新、playbook 更新、dqmc-dev 脚本更新、MCP server 重启条件。
