# Sherlock SLURM SDD Handoff

状态：远端 Sherlock Codex 实例执行用规格。Slack bot 相关内容全部排除。

本文档把 Sherlock 上的 SLURM 相关功能拆成 Spec-Driven Development 流程。远端 Codex 实例应按 phase 顺序执行：先补/更新测试，再实现，再在 Sherlock 环境验证，最后记录结果并提交。

## 范围

### In Scope

- 在 Sherlock 上部署并运行当前 DQMC MCP hands 项目。
- 真实验证当前 `query_slurm(filters={"me": true})`。
- 提供非 Slack 的 agent/status 工作流，让用户能询问当前 Sherlock 任务状态。
- 增加只读历史状态查询，优先使用 `sacct`。
- 提供 job id 详情查询，并尽量关联 run/output path。
- 设计并实现可选的 Sherlock 产物同步能力。
- 允许在 Sherlock 上通过现有 `run_script_adapter` 执行受控后处理脚本。
- 后期再设计受限 `sbatch` 提交能力。

### Out of Scope

- Slack Events API、Socket Mode、Slack thread/session 映射、Slack interactive approval。
- `scancel`、`scontrol update` 或任何修改 SLURM 任务状态的能力。
- 第一轮实现中的 `sbatch` 提交。
- 任意 shell 命令执行入口。
- MCP hands 返回 sign quality、warmup 质量、Trotter 误差等物理可靠性结论。

## 架构原则

- MCP hands 必须跑在能访问 `squeue`、后续 `sacct`、Sherlock 文件系统和 DQMC run/output path 的环境中。
- agent 编排层可以和 MCP hands 跑在同一台 Sherlock 登录节点上；第一版不要求公网服务或入站端口。
- 当前仓库只负责第 2/3 层：MCP hands 与面向 agent 的工具契约。第 1/4 层通用 coding agent 部署只消费这些工具和文档，不把 Slack transport 放入本仓库。
- 所有 SLURM 状态工具默认只读。同步、脚本执行、未来提交任务都必须先 dry-run，再由用户逐次审批。
- 路径必须 fail closed：原始 run/HDF5 读取受 `DQMC_ALLOWED_ROOTS` 限制；输出写入受 `DQMC_OUTPUT_ROOT` 限制。
- 子进程调用必须使用 argv list，不使用 shell string。

## SDD 执行规则

每个 phase 都按同一节奏推进：

1. 更新或新增需求/任务记录，确认本 phase 的 in/out scope。
2. 先写测试或 smoke 验证脚本，覆盖成功路径和结构化错误路径。
3. 实现最小功能，不顺手重构无关模块。
4. 运行本地测试：`.venv/bin/python -m pytest`。
5. 在 Sherlock 上运行本 phase 的真实 smoke 命令。
6. 把验证结果记录到 `specs/` 或 `docs/` 的对应文档。
7. 只提交本 phase 相关改动。

## Phase 0：远端环境基线

目标：确认远端 Codex 实例能在 Sherlock 上安装、测试并启动 MCP hands。

实现步骤：

- 克隆或同步当前仓库到 Sherlock。
- 创建 `.venv`，安装 `.[mcp,test]`。
- 在 Sherlock 的 Codex 用户级 `~/.codex/config.toml` 中为 `dqmc-hands` MCP server 设置 `DQMC_DEV_ROOT`。
- 如果 `DQMC_DEV_ROOT` 缺失、为空或路径不存在，先修复配置，不要启动 MCP server。
- 配置：
  - `DQMC_ALLOWED_ROOTS`：Sherlock 上允许读取的 run/output 根目录。
  - `DQMC_OUTPUT_ROOT`：Sherlock 上允许写入的 agent output 根目录。
  - `DQMC_REGISTRY_PATH`：当前仓库的 `registry.yaml`，除非有明确覆盖需求。
- 运行完整测试。
- 启动 `dqmc_mcp_server.py`，确认 MCP tools 可枚举。

验收：

- `.venv/bin/python -m pytest` 通过。
- `dqmc_tools` 可 import。
- MCP server 暴露现有 10 个 tools。
- 未配置 allowed roots 时，原始数据读取继续 fail closed。

## Phase 1：真实 `squeue --me` 验证

目标：在 Sherlock 上验证现有只读队列查询。

当前已有能力：

- `dqmc_tools.slurm.query_slurm`
- MCP tool：`query_slurm`
- 支持 filters：`me`、`user`、`job_id`、`state`、`partition`
- 优先 `squeue --json`
- fallback 到 delimited `squeue --noheader --format=...`
- 返回 `summary`、`groups.by_job_name` 和原始 `jobs`

实现步骤：

- 在 Sherlock 上直接运行 `squeue --me`，记录输出形态。
- 运行 `query_slurm(filters={"me": true})`。
- 判断 Sherlock 是否支持 `squeue --json`。
- 如果 `--json` 不可用，确认 fallback parser 的字段足够。
- 补充 Sherlock-specific smoke test 说明，不把真实集群状态写死进单元测试。

验收：

- `query_slurm(filters={"me": true})` 返回 `ok=true`。
- 返回包含 `summary.total_jobs`、`summary.state_counts`、`summary.category_counts`。
- 对 array job，`groups.by_job_name[*].array_jobs` 能分组。
- 没有任何 submit/cancel/mutate 命令。

## Phase 2：非 Slack 的“我的任务状态”工作流

目标：提供 agent 层可复用的状态摘要流程，但不接 Slack。

实现选择：

- 推荐先做轻量 Python helper 或文档化 agent workflow，不新增复杂服务。
- 输入是自然语言或显式命令，例如“查看我的 Sherlock 任务”。
- agent 调用 MCP：`query_slurm(filters={"me": true})`。
- agent 把 MCP facts 整理为简洁摘要：
  - 总任务数
  - running/pending/held_blocked/other 数量
  - 主要 job name 分组
  - pending reason 或节点信息
  - array job 汇总

实现步骤：

- 明确 summary schema，避免 agent 自由拼接时依赖易变字段。
- 如果需要代码，新增一个小的 presenter 层，输入为 `query_slurm` 返回 dict，输出为纯文本摘要。
- 为 presenter 写 fixture-based 单元测试。
- MCP hands 仍只返回事实，不把“是否正常”等判断写进工具。

验收：

- 空队列能输出明确的“当前没有任务”。
- running/pending/held_blocked 都有稳定文本输出。
- array job 不逐条刷屏，默认先汇总。
- 原始 rows 仍可供 agent 展开查看。

## Phase 3：历史任务查询 `sacct`

目标：补齐已经离开 `squeue` 的 completed/failed/timeout/OOM 等历史状态。

建议设计：

- 新增只读函数：`query_slurm_history`。
- 新增 MCP tool：`query_slurm_history`，不要塞进当前 `query_slurm`。
- 底层优先使用 `sacct`。
- 支持 filters：
  - `me`
  - `user`
  - `job_id`
  - `state`
  - `start`
  - `end`
  - `partition`
  - `max_rows`
- 返回结构：
  - `ok`
  - `source`
  - `command`
  - `jobs`
  - `summary.state_counts`
  - `summary.exit_code_counts`
  - `warnings`

实现步骤：

- 先在 Sherlock 上确认 `sacct` 可用性、默认时间窗口和字段格式。
- 使用 `sacct --parsable2 --noheader` 作为稳定 parse 格式。
- 明确字段白名单，例如 `JobID,JobName,User,State,ExitCode,Elapsed,Timelimit,Submit,Start,End,Partition,NodeList,WorkDir`.
- 如果某些字段在 Sherlock 不开放，返回 warning，不让工具失败。
- 添加 unavailable、timeout、bad filter、parse fallback 测试。

验收：

- 查询最近 N 天当前用户任务可成功。
- 对 failed/timeout/completed 任务能返回 state 和 exit code。
- `sacct` 不可用时返回 structured `tool_unavailable`。
- 不调用任何修改任务状态的 SLURM 命令。

## Phase 4：Job 详情入口

目标：用户给 job id 后，能得到当前或历史详情。

建议设计：

- 新增工具：`get_slurm_job_detail`。
- 输入：`job_id`，可选 `include_history=true`。
- 查询顺序：
  - 先用 `squeue` 查当前队列。
  - 如果没有结果且 `include_history=true`，用 `sacct` 查历史。
- 返回：
  - job id
  - job name
  - state
  - category
  - partition
  - elapsed/time limit
  - node/reason
  - submit/start/end
  - work dir，如果 `sacct` 暴露
  - stdout/stderr path，如果能从 SLURM 字段或脚本约定推断
  - raw rows

实现步骤：

- 先复用 `query_slurm` 和 `query_slurm_history` 的 parser，不复制 parsing 逻辑。
- 对 array job 支持 `12345` 和 `12345_7` 两种输入。
- 对多个 matching rows 返回 candidates，不猜。

验收：

- running job 从 `squeue` 返回详情。
- completed/failed job 从 `sacct` 返回详情。
- array parent 和 task id 行为明确。
- 查不到 job 时返回 `ok=false` 或空 candidates 的稳定结构。

## Phase 5：Job 到 run/output path 关联

目标：让 agent 能从 job 状态跳到 DQMC run 摘要或后处理。

候选信息源：

- `sacct WorkDir`
- job name
- stdout/stderr 文件路径
- submit cwd
- DQMC `.h5.log`
- 后续脚本执行 provenance
- 用户显式提供的 run path

建议设计：

- 第一版不要自动扫描大目录。
- 新增纯推断 helper：输入 job detail 和可选 allowed roots，输出候选 path 与 evidence。
- evidence 必须说明来源，例如 `sacct.WorkDir`、`stdout_path_parent`、`user_provided_path`。
- 如果候选不唯一，返回 candidates，让 agent 询问用户。

实现步骤：

- 定义 `path_candidates` schema。
- 只检查 allowed roots 内的候选路径。
- 对候选 run path 可调用现有 `summarize_run` 做 bounded 验证。

验收：

- 明确 work dir 时能给出一个 high-confidence candidate。
- 多个候选时不猜。
- 越过 allowed roots 的路径被拒绝或标记不可访问。
- 成功关联后可衔接 `summarize_run`。

## Phase 6：Sherlock 产物同步

目标：只在需要本地分析时，把 Sherlock 产物同步到受控本地 output root。

决策点：

- 如果 agent 和 MCP hands 都跑在 Sherlock，第一版可以不做同步，直接读远端文件。
- 如果本地 agent 需要读取远端产物，则需要 rsync 同步能力。

建议设计：

- 新增同步工具前，先写 design doc。
- 所有同步先 dry-run。
- 远端路径必须在 allowlist 内。
- 本地目标必须在 output root 内。
- 返回 manifest：
  - added files
  - updated files
  - skipped files
  - size
  - mtime
  - command
  - source
  - destination
- 真实同步必须有用户逐次审批。

验收：

- dry-run 不写文件。
- output root 外目标被拒绝。
- allowlist 外远端路径被拒绝。
- 真实同步返回 manifest。
- 同步后可调用 `summarize_run` 或 HDF5 工具。

## Phase 7：Sherlock 上的后处理脚本执行

目标：在 Sherlock 上复用现有 `run_script_adapter` 处理远端 run/output。

实现步骤：

- 确认 `DQMC_DEV_ROOT` 在 Sherlock 上指向正确的 `dqmc-dev` checkout。
- 运行 `scripts/audit_script_adapters.py`，确认白名单脚本存在且 argparse schema 可同步。
- 对需要派生产物的脚本，先用 `describe_script_adapter` 和 dry-run 检查 preflight。
- 对真实执行，必须传入 `user_confirmation={"approved": true, "text": "..."}`。

验收：

- `run_script_adapter(..., dry_run=true)` 能显示 command、cwd、required inputs、output root。
- 缺少输入时 preflight fail，不启动脚本。
- 没有用户同意时真实执行被拒绝。
- 有用户同意时输出写入 Sherlock 上的 `DQMC_OUTPUT_ROOT`。

## Phase 8：周期性状态查询

目标：支持用户临时观察任务变化，但不在 MCP hands 内做 daemon。

建议设计：

- MCP hands 保持无状态，一次调用返回一个 snapshot。
- agent 层按用户指定 interval 重复调用 `query_slurm(filters={"me": true})`。
- agent 比较前后 snapshot，报告新增、消失、state 改变的 jobs。

验收：

- 用户可以指定轮询次数和间隔。
- Ctrl-C 或 agent 中断不会留下后台进程。
- MCP hands 不维护 watcher 状态。

## Phase 9：受限 `sbatch` 提交设计

目标：最后再做提交能力，只支持受控模板。

前置条件：

- `squeue --me` 真实验证稳定。
- `sacct` 历史查询稳定。
- job detail 稳定。
- job 到 run/output path 关联稳定。
- dry-run、审批、provenance 流程稳定。

第一版原则：

- 不支持任意 shell。
- 不支持任意资源参数。
- 只允许白名单 job templates。
- 必须先 dry-run，展示 job script、cwd、资源参数、读写路径。
- 必须用户逐次审批。
- 必须记录 provenance：
  - 用户意图
  - 参数
  - job script
  - git hash
  - submit cwd
  - job id
  - output path

验收：

- 没有 dry-run 和审批不能提交。
- 提交结果能被 `query_slurm` 和 `get_slurm_job_detail` 查询。
- 失败提交返回 structured error。
- 不实现 cancel；cancel 是未来单独高风险 spec。

## 推荐远端执行顺序

1. Phase 0：部署并跑通测试。
2. Phase 1：真实验证 `query_slurm(filters={"me": true})`。
3. Phase 2：做非 Slack 的状态摘要工作流。
4. Phase 3：新增 `sacct` 历史查询。
5. Phase 4：新增 job 详情入口。
6. Phase 5：建立 job 到 run/output path 的候选关联。
7. Phase 7：验证 Sherlock 上的后处理脚本 adapter。
8. Phase 6：只有确实需要本地读取远端产物时再做同步。
9. Phase 8：按需做短期轮询。
10. Phase 9：最后单独设计和实现受限 `sbatch`。

## 远端 Codex 开始前检查清单

- [ ] 确认本仓库分支和 commit。
- [ ] 确认 Sherlock 上 Python 版本和虚拟环境。
- [ ] 确认 `squeue` 可用。
- [ ] 确认 `sacct` 是否可用。
- [ ] 确认 Sherlock 上 `dqmc-dev` 路径。
- [ ] 确认 run/output allowlist。
- [ ] 确认是否需要本地同步；如果 agent 全部跑在 Sherlock，先跳过同步。
- [ ] 确认本轮不做 Slack。
- [ ] 确认本轮不做 `sbatch`，除非前置 phase 已全部完成并另写 spec。
