# Sherlock SLURM SDD 需求规格

状态：本地优先开发，Sherlock 真实环境验证。Slack bot 相关内容全部排除。

## 背景

当前 DQMC MCP hands 已经有第一版只读 SLURM 队列查询：`query_slurm`。后续需要围绕 Sherlock 环境补齐更完整的只读任务状态能力，包括当前队列、历史任务、job 详情、job 到 run/output path 的关联，以及可选的远端产物同步。

这个 spec 不要求所有代码都在 Sherlock 上开发。除真实 `squeue`、`sacct`、Sherlock 文件系统和 MCP 环境验证外，代码应优先在本地用 fixture、unit tests 和 MCP contract tests 开发。

## 总目标

- 本地实现可测试、只读、结构化的 SLURM 状态工具。
- 在 Sherlock 上验证真实命令输出和字段形态，并把发现反馈为脱敏 fixture。
- 让 agent 能回答“我当前 Sherlock 任务怎么样”“某个 job 详情是什么”“这个 job 可能对应哪个 run/output path”。
- 保持 MCP hands 的边界：返回事实、schema、provenance，不做物理可靠性判断，不接 Slack transport。

## In Scope

- 本地开发非 Slack 的 agent/status 工作流，让用户能询问当前 Sherlock 任务状态。
- 本地实现只读历史状态查询，优先使用 `sacct`。
- 本地实现 job id 详情查询，并尽量关联 run/output path。
- 在 Sherlock 上真实验证当前 `query_slurm(filters={"me": true})`。
- 在 Sherlock 上验证 `sacct` 可用性、字段格式、job array 形态和路径信息。
- 设计并实现可选的 Sherlock 产物同步能力。
- 允许在 Sherlock 上通过现有 `run_script_adapter` 执行受控后处理脚本。
- 后期再单独设计受限 `sbatch` 提交能力。

## Out of Scope

- Slack Events API、Socket Mode、Slack thread/session 映射、Slack interactive approval。
- `scancel`、`scontrol update` 或任何修改 SLURM 任务状态的能力。
- 第一轮实现中的 `sbatch` 提交。
- 任意 shell 命令执行入口。
- MCP hands 返回 sign quality、warmup 质量、Trotter 误差等物理可靠性结论。

## 当前已实现能力

- `dqmc_tools.slurm.query_slurm`
- MCP tool：`query_slurm`
- 支持 filters：`me`、`user`、`job_id`、`state`、`partition`
- 优先 `squeue --json`
- fallback 到 delimited `squeue --noheader --format=...`
- 返回 `summary`、`groups.by_job_name` 和原始 `jobs`
- `squeue --json` path 会 normalize SLURM wrapped fields，再用于 state/category 计数和 array job 分组。
- 本地测试覆盖 `squeue` unavailable、unknown filter、JSON path、fallback path、`me` filter、array job grouping 和 wrapped JSON fields。

## 重要实现经验：SLURM JSON wrapped fields

`78c1ab8` 修复了真实 `squeue --json` 输出和本地 parser 假设不一致的问题。后续 SLURM 工具不能假设 JSON 字段都是普通字符串或数字。

已观察到的真实形态：

- `job_state` 可能是 list，例如 `["PENDING"]`。
- `array_job_id` / `array_task_id` 可能是 dict，例如 `{"set": true, "infinite": false, "number": 24884301}`。
- `set=false` 的 dict 表示该字段没有有效值，不能把 `number` 当成真实 task id。
- wrapped dict 也可能通过 `name`、`id` 或 `infinite=true` 表示可显示值。

当前 `query_slurm` 通过 `_slurm_scalar`、`_slurm_text`、`_has_slurm_value` 统一提取可用 scalar。后续 `query_slurm_history`、`get_slurm_job_detail` 和 presenter 应消费 normalized facts，不能在各处重复 ad hoc `str(value)`。

## 功能需求

### R1 本地/远端执行边界

- 命令构造、parser、schema、MCP contract、structured error handling 应在本地用 fixture 测试覆盖。
- 真实 SLURM 输出暴露的新字段形态必须先变成脱敏 fixture，再补 parser 兼容。
- Sherlock 只负责真实 `squeue`/`sacct` smoke、字段确认、部署配置和路径验证。

### R2 只读安全边界

- 所有 SLURM 状态工具默认只读。
- 子进程调用必须使用 argv list，不使用 shell string。
- 不接入 `scancel`、`scontrol update` 或任何 mutating SLURM 命令。
- 同步、脚本执行、未来提交任务都必须先 dry-run，再由用户逐次审批。

### R3 `query_slurm` 当前队列查询

- 保留现有 MCP tool `query_slurm`。
- 支持 `filters={"me": true}` 生成 `squeue --me`。
- 返回原始 job rows、`summary`、`groups.by_job_name` 和 array job 分组。
- 对 `squeue --json` wrapped fields 先 normalize，再进入 summary/grouping。
- fallback delimited parser 继续支持 Sherlock 不支持 `--json` 的情况。

### R4 非 Slack 状态摘要

- 提供 agent 层可复用 presenter 或 workflow helper。
- 输入为 `query_slurm` 返回 dict，输出为纯文本摘要。
- 摘要包含总任务数、running/pending/held_blocked/other 数量、主要 job name 分组、pending reason 或节点信息、array job 汇总。
- MCP hands 继续只返回事实，不判断“是否正常”。

### R5 `sacct` 历史任务查询

- 新增只读函数：`query_slurm_history`。
- 新增 MCP tool：`query_slurm_history`，不要塞进当前 `query_slurm`。
- 底层优先使用 `sacct --parsable2 --noheader`。
- 支持 filters：`me`、`user`、`job_id`、`state`、`start`、`end`、`partition`、`max_rows`。
- 返回 `ok`、`source`、`command`、`jobs`、`summary.state_counts`、`summary.exit_code_counts`、`warnings`。
- `sacct` 不可用时返回 structured `tool_unavailable`。

### R6 Job 详情入口

- 新增工具：`get_slurm_job_detail`。
- 输入：`job_id`，可选 `include_history=true`。
- 查询顺序：先查当前 `squeue`，没有结果且允许历史时再查 `sacct`。
- 对 array job 支持 `12345` 和 `12345_7` 两种输入。
- 多个 matching rows 返回 candidates，不猜。
- raw rows 只作为 provenance 返回；展示和摘要应基于 normalized facts。

### R7 Job 到 run/output path 关联

- 第一版不要自动扫描大目录。
- 新增纯推断 helper：输入 job detail 和可选 allowed roots，输出候选 path 与 evidence。
- evidence 必须说明来源，例如 `sacct.WorkDir`、`stdout_path_parent`、`user_provided_path`。
- 只检查 allowed roots 内的候选路径。
- 候选不唯一时返回 candidates，让 agent 询问用户。

### R8 Sherlock 产物同步

- 如果 agent 和 MCP hands 都跑在 Sherlock，第一版可以不做同步，直接读远端文件。
- 如果本地 agent 需要读取远端产物，则需要 rsync 同步能力。
- 所有同步先 dry-run。
- 远端路径必须在 allowlist 内，本地目标必须在 output root 内。
- 真实同步必须有用户逐次审批。
- 返回同步 manifest：新增文件、更新文件、跳过文件、大小、mtime、command、source、destination。

### R9 Sherlock 后处理脚本

- 在 Sherlock 上复用现有 `run_script_adapter`。
- `DQMC_DEV_ROOT` 必须指向 Sherlock 上正确的 `dqmc-dev` checkout。
- 真实执行必须传入 `user_confirmation={"approved": true, "text": "..."}`。
- 缺少输入时 preflight fail，不启动脚本。

### R10 周期性状态查询

- MCP hands 保持无状态，一次调用返回一个 snapshot。
- agent 层按用户指定 interval 重复调用 `query_slurm(filters={"me": true})`。
- agent 比较前后 snapshot，报告新增、消失、state 改变的 jobs。
- 中断后不能留下后台进程。

### R11 受限 `sbatch` 提交

- `sbatch` 是后期单独设计，不属于第一轮实现。
- 前置条件：`squeue --me`、`sacct`、job detail、path association、dry-run、审批、provenance 都稳定。
- 第一版原则：不支持任意 shell，不支持任意资源参数，只允许白名单 job templates。
- 必须先 dry-run，展示 job script、cwd、资源参数、读写路径，并逐次审批。
- 不实现 cancel；cancel 是未来单独高风险 spec。

## 验收标准

- 本地 `query_slurm` 相关测试通过。
- MCP contract tests 通过。
- Sherlock `query_slurm(filters={"me": true})` smoke 返回 `ok=true`。
- `sacct` 可用时能查询 completed/failed/timeout/OOM 任务；不可用时返回 structured `tool_unavailable`。
- wrapped JSON fields 不会破坏 state/category 计数或 array job 分组。
- 任意新增 SLURM 命令都只生成 argv list，不使用 shell string。
- 不存在 submit/cancel/mutate SLURM 工具，除非后续单独 spec 明确引入。
