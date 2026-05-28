# Sherlock SLURM SDD 任务拆解

状态：进行中。默认 status-only Sherlock 查询链路已通过真实 gateway、Slack/OpenACP smoke 和 Sherlock status-only pytest；fixture 回流和非默认 profile 验证仍分开执行。

## Phase L0：本地基线和契约冻结

- [x] 运行 `tests/test_slurm.py`。
- [x] 运行 `query_slurm` MCP success/error contract tests。
- [x] 运行 MCP tool set test，确认当前完整 `dqmc-hands` 暴露 14 个 tools；默认 Sherlock status profile 只暴露 3 个 path-redacted status tools。
- [x] 运行 wrapped SLURM JSON fields 测试，确认 `job_state` list、`array_job_id` dict、`array_task_id set=false` 都被正确 normalize。
- [x] 记录 `query_slurm` 当前 schema：`ok`、`source`、`command`、`commands_attempted`、`jobs`、`summary`、`groups`、JSON path 的 `raw`。

验收：

- [x] `query_slurm` 本地测试通过。
- [x] MCP contract tests 通过。
- [x] wrapped SLURM JSON fields 不会破坏 state/category 计数或 array job 分组。
- [x] `requirements.md` 的“当前已实现能力”没有描述不存在的代码。

## Phase R0：Sherlock 环境基线

- [x] 克隆或同步当前仓库到 Sherlock。
- [x] 创建 `.venv`，并确认可 import `dqmc_tools.remote_call`。
- [x] 默认 status-only 验证不设置 `DQMC_DEV_ROOT`、`DQMC_ALLOWED_ROOTS`、`DQMC_OUTPUT_ROOT`、`DQMC_REGISTRY_PATH`。
- [x] 运行 SLURM/status 相关测试；完整 HDF5/script 测试只在本地或单独 data/script profile 中运行。
  - 2026-05-28：Sherlock 上运行 status-only pytest，`27 passed`；命令禁用 bytecode 写入和 pytest cache。
- [x] 调用 path-redacted gateway status-only tool surface，确认默认只暴露 status 查询相关工具。

验收：

- [x] `.venv/bin/python -m pytest tests/test_package_import.py tests/test_slurm.py tests/test_slurm_presenter.py tests/test_slurm_monitor.py -q` 通过。
- [x] `dqmc_tools` 可 import。
- [x] 默认 status-only tool surface 不暴露 HDF5、script adapter、sync、run summary 或 path discovery。
- [ ] 未配置 allowed roots 时，原始数据读取继续 fail closed。

## Phase R1：真实 `squeue --me` 验证

- [x] 直接或经 `remote_call` 运行 `squeue --me` 路径，记录输出形态。
- [x] 运行 `query_slurm(filters={"me": true})`。
- [x] 判断 Sherlock 是否支持 `squeue --json`。
- [ ] 如果 `--json` 不可用，确认 fallback parser 的字段足够。
- [ ] 确认 array job 的 `job_id`、`array_job_id`、`array_task_id` 形态。
- [ ] 如果 `squeue --json` 可用，记录 `job_state`、`state_reason`、`array_job_id`、`array_task_id`、`nodes` 等字段是否为 list/dict/scalar。
- [ ] 对 list/dict wrapped fields 脱敏保存一份最小 fixture。
- [x] 补充 Sherlock-specific smoke 说明，不把真实集群状态写死进单元测试。
  - 2026-05-28：gateway 和 Slack/OpenACP smoke 已记录在 `verification.md`；真实队列数量只作为观察记录，不写入单元测试断言。

验收：

- [x] `query_slurm(filters={"me": true})` 返回 `ok=true`。
- [x] 返回包含 `summary.total_jobs`、`summary.state_counts`、`summary.category_counts`。
- [x] 对 array job，`groups.by_job_name[*].array_jobs` 能分组。
- [x] wrapped JSON fields 被 normalize 后再进入 `summary` 和 `groups`。
- [x] 没有任何 submit/cancel/mutate 命令。

## Phase L1：非 Slack 的“我的任务状态”presenter

- [x] 明确 presenter 输入为 `query_slurm` 返回 dict。
- [x] 明确 presenter 输出为英文固定表格摘要。
- [x] 将 presenter 接入 `dqmc-sherlock-gateway` 当前状态查询 wrapper，作为顶层 `formatted_summary` 返回。
- [x] 明确 Slack/OpenACP 默认用户展示契约：直接输出 `formatted_summary`，不自行重写表格、不运行 direct SSH/shell 命令。
- [x] 写空队列 fixture test。
- [x] 写 running/pending/held_blocked/other fixture test。
- [x] 写 array job 汇总 fixture test，默认以每个 top-level array job id 汇总。
- [x] 写 `CG`/`CF`/`COMPLETING`/`CONFIGURING` 计入 `Running` 的 fixture test。
- [x] 写 SLURM presenter/monitor 用户可见消息保持英文的 fixture test。
- [x] 实现 pure function，不新增服务。
- [x] 保证原始 rows 仍可供 agent 展开查看。

验收：

- [x] presenter fixture tests 通过。
- [x] 真实 Sherlock payload 能生成可读摘要。
  - 2026-05-28：Slack/OpenACP 新会话已能基于 status-only gateway 查询并回复 Sherlock SLURM 状态；Slack transport 本身仍不属于本 SDD 的 MCP hands。
- [x] 不新增 Slack 依赖。

## Phase L2：`sacct` 历史查询工具

- [x] 设计 `query_slurm_history(filters=None)` public API。
- [x] 设计 MCP tool `query_slurm_history`。
- [x] 写 command builder test：生成 `sacct --parsable2 --noheader` 和白名单字段。
- [x] 写 filter tests：`me`、`user`、`job_id`、`state`、`start`、`end`、`partition`、`max_rows`。
- [x] 写 unknown filter structured `invalid_argument` test。
- [x] 写 `sacct` unavailable structured `tool_unavailable` test。
- [x] 写 timeout structured error test。
- [x] 写 parsable2 fixture test：completed、failed、timeout、OOM。
- [x] 写缺失可选字段 warning test。
- [ ] 如 Sherlock 的 `sacct` 输出嵌入 wrapped 或 multi-value 字段，新增脱敏 fixture 并覆盖 normalization。
- [x] 实现 command builder、parser、summary 和 warnings。
- [x] 注册 MCP tool，并补 MCP contract tests。

验收：

- [x] 查询最近 N 天当前用户任务可成功。
- [x] 对 failed/timeout/completed 任务能返回 state 和 exit code。
- [x] `sacct` 不可用时返回 structured `tool_unavailable`。
- [x] 不调用任何修改任务状态的 SLURM 命令。

## Phase L2 的 Sherlock 验证步骤

- [x] 运行 `sacct` 路径的最近任务查询，确认可返回当前用户历史任务。
- [ ] 确认默认时间窗口；当前 smoke 使用 `max_rows` 限制，没有把默认窗口写死。
- [x] 默认 gateway/status 查询不返回 `WorkDir`。
- [ ] 如需验证 `WorkDir`，必须进入单独 path-discovery profile，并脱敏记录。
- [x] 验证 `JobID` 对 array parent/task 的格式。
- [x] 验证 `State` 和 `ExitCode` 对 completed/failed/timeout/OOM 的实际形态。
  - 2026-05-28：completed array task smoke 中 `sacct` 返回 task 本体及 `.batch`/`.extern`/`.0` step rows，state 为 `COMPLETED`，exit code 为 `0:0`。
- [ ] 验证字段是否全部为 `--parsable2` scalar；如果不是，记录 wrapped/multi-value 形态。
- [ ] 把脱敏后的代表性输出补成本地 fixture。

## Phase L3：Job 详情入口

- [x] 设计 `get_slurm_job_detail(job_id, include_history=True)` public API。
- [x] 写 running job 从 mocked `query_slurm` 返回详情的 test。
- [x] 写 completed/failed job 从 mocked `query_slurm_history` 返回详情的 test。
- [x] 写 array parent 和 task id 行为 test。
- [x] 写多个 matching rows 返回 candidates 的 test。
- [x] 写查不到 job 时返回稳定空结果的 test。
- [x] 实现查询顺序：当前队列优先，必要时查历史。
- [x] 基于 normalized facts 构造 detail candidate。
- [x] raw rows 只作为 provenance 返回。
- [x] 注册 MCP tool，并补 MCP contract tests。

验收：

- [x] running job 从 `squeue` 返回详情。
- [x] completed/failed job 从 `sacct` 返回详情。
- [x] 查不到 job 时返回稳定结构。
- [x] 不猜测多个候选中的唯一结果。

## Phase L3 的 Sherlock 验证步骤

- [x] 用一个当前队列 job id 验证 `squeue` detail path。
- [x] 用一个已结束 job id 验证 `sacct` detail path。
  - 2026-05-28：completed array parent id 先记录 `squeue` lookup failure，再 fallback 到 `sacct`，返回多候选 completed rows。
- [x] 验证 array parent 和具体 task id 的查询行为。
  - running array parent id 返回多候选；running `parent_task` id 经 `squeue` 收敛到单个 task candidate。
  - completed `parent_task` id 经 `sacct` 收敛到该 task 的 step group，不猜测唯一 step row。
- [x] 验证默认 Sherlock gateway/status response 不包含 `work_dir`、stdout/stderr path 或 raw path fields。

## Phase L4：Job 到 run/output path 关联

- [x] 定义 `path_candidates` schema。
- [x] 写 `sacct.WorkDir` high-confidence candidate test。
- [x] 写 stdout/stderr parent candidate test。
- [x] 写多个候选不猜 test。
- [x] 写越过 allowed roots 的路径拒绝或不可访问 test。
- [x] 实现纯推断 helper。
- [x] 对候选 run path 可调用现有 `summarize_run` 做 bounded 验证。
- [x] 标记为非默认 path-discovery profile；普通 Sherlock/Slack status 查询不调用该工具。

验收：

- [x] path candidates schema 稳定。
- [x] 不做大目录扫描。
- [x] 路径边界 fail closed。
- [x] 成功关联后可衔接 `summarize_run`。

## Phase L4 的 Sherlock 验证步骤

- [ ] 仅在用户明确批准 path-discovery profile 时验证 `sacct WorkDir` 是否能直接指向 run/output。
- [ ] 仅在 path-discovery profile 中验证 stdout/stderr 路径是否可从实际 job detail 推断。
- [ ] 仅在 path-discovery profile 中验证 allowed roots 配置能覆盖目标 run/output。
- [ ] 所有真实路径必须脱敏记录；默认 status profile 不执行本阶段 Sherlock path smoke。

## Phase L5/R5：Sherlock 产物同步

- [x] 先写单独 design doc：`artifact-sync-design.md`。
- [ ] 明确该能力不属于默认 Sherlock/Slack status profile。
- [x] 明确远端路径 allowlist。
- [x] 明确本地目标 output root。
- [x] 写 dry-run 不写文件 test。
- [x] 写 output root 外目标拒绝 test。
- [x] 写 allowlist 外远端路径拒绝 test。
- [x] 写 manifest schema test。
- [ ] 对小型测试目录运行 dry-run。
- [x] 写经用户审批后运行同步命令并记录 manifest 的本地 mock test。

验收：

- [x] 本地 mock 同步返回 manifest。
- [ ] 同步后可调用 `summarize_run` 或 HDF5 工具。
- [x] 未审批时不写本地文件。

## Phase R6：Sherlock 上的后处理脚本执行

- [ ] 明确该能力不属于默认 Sherlock/Slack status profile。
- [ ] 确认 `DQMC_DEV_ROOT` 在 Sherlock 上指向正确的 `dqmc-dev` checkout。
- [ ] 运行 `scripts/audit_script_adapters.py`，确认白名单脚本存在且 argparse schema 可同步。
- [ ] 对需要派生产物的脚本，先用 `describe_script_adapter` 和 dry-run 检查 preflight。
- [ ] 对真实执行，必须传入 `user_confirmation={"approved": true, "text": "..."}`。

验收：

- [ ] `run_script_adapter(..., dry_run=true)` 能显示 command、cwd、required inputs、output root。
- [ ] 缺少输入时 preflight fail，不启动脚本。
- [ ] 没有用户同意时真实执行被拒绝。
- [ ] 有用户同意时输出写入 Sherlock 上的 `DQMC_OUTPUT_ROOT`。

## Phase L6：周期性状态查询

- [x] 设计 agent 层轮询流程，不在 MCP hands 内做 daemon。
- [x] 写固定 snapshots 的 diff test：新增、消失、state 改变。
- [x] 写中断不留下后台进程的行为说明或测试。
- [x] 实现或文档化 agent workflow。

验收：

- [x] 轮询由 agent 层驱动。
- [x] MCP hands 无状态。

## Phase L7/R7：受限 `sbatch` 提交设计

- [ ] 确认前置条件已完成：`squeue --me`、`sacct`、job detail、path association、dry-run、审批、provenance。
- [ ] 先写单独 design doc，不直接实现。
- [ ] 明确模板 schema、资源参数 allowlist、路径 allowlist 和审批记录。
- [ ] 写 dry-run-only tests。
- [ ] 只在所有前置条件通过后进行 Sherlock dry-run smoke。
- [ ] 真实提交必须另行确认。

验收：

- [ ] 没有 dry-run 和审批不能提交。
- [ ] 提交结果能被 `query_slurm` 和 `get_slurm_job_detail` 查询。
- [ ] 失败提交返回 structured error。
- [ ] 不实现 cancel。

## 推荐执行顺序

1. Phase L0：本地基线和契约冻结。
2. Phase R0：Sherlock status-only 环境基线。已完成 repo/venv/import/gateway tool-surface smoke 和 Sherlock status-only pytest。
3. Phase R1：真实验证 `query_slurm(filters={"me": true})`，并收集 wrapped JSON fields fixture。已完成 gateway smoke；fixture 回流仍可补充。
4. Phase L1：本地实现非 Slack 的状态摘要 presenter。真实 Sherlock payload 已经通过 gateway/Slack 路径生成用户可读状态回复；纯 presenter fixture 仍是本 SDD 的本地验证基线。
5. Phase L2：本地实现 `sacct` 历史查询，使用 fixture 测试。
6. Phase L2 的 Sherlock 验证步骤：用真实 `sacct` 输出补 fixture 和兼容修正。
7. Phase L3：本地实现 job 详情入口。
8. Phase L4：本地实现 job 到 run/output path 的候选关联；Sherlock 默认不启用。
9. Phase R6：只有明确进入 script profile 时验证 Sherlock 上的后处理脚本 adapter。
10. Phase L5/R5：只有确实需要本地读取远端产物且用户审批时再做同步。
11. Phase L6：按需做短期轮询。
12. Phase L7/R7：最后单独设计和实现受限 `sbatch`。

## 本地开发开始前检查清单

- [ ] 确认当前分支和已有未提交改动。
- [ ] 确认 `.venv/bin/python -m pytest tests/test_slurm.py` 可运行。
- [ ] 确认 MCP contract tests 可运行。
- [ ] 确认本轮不做 Slack。
- [ ] 确认本轮不做 `sbatch`。
- [ ] 对任何新增 SLURM 命令，只生成 argv list，不使用 shell string。
- [ ] 对任何真实执行能力，先 dry-run，再逐次审批。
