# Sherlock SLURM SDD 需求规格

状态：默认 status-only Sherlock 查询链路已通过真实 gateway 和 Slack/OpenACP smoke。Slack bot transport 设计仍排除在本 SDD 之外；这里只记录它作为端到端产品验证的观察结果。

## 背景

当前 DQMC MCP hands 已经有第一版只读 SLURM 队列查询：`query_slurm`。后续需要围绕 Sherlock 环境补齐更完整的只读任务状态能力，包括当前队列、历史任务和 job 详情。job 到 run/output path 的关联、远端产物同步和脚本执行属于非默认 profile，不能混入默认 Sherlock/Slack status 查询。

这个 spec 不要求所有代码都在 Sherlock 上开发。除真实 `squeue`、`sacct`、Sherlock 文件系统和 MCP 环境验证外，代码应优先在本地用 fixture、unit tests 和 MCP contract tests 开发。

## 总目标

- 本地实现可测试、只读、结构化的 SLURM 状态工具。
- 在 Sherlock 上验证真实命令输出和字段形态，并把发现反馈为脱敏 fixture。
- 让 agent 能回答“我当前 Sherlock 任务怎么样”“某个 job 详情是什么”，且默认不暴露 Sherlock 实际 run/data path。
- 保持 MCP hands 的边界：返回事实、schema、provenance，不做物理可靠性判断，不接 Slack transport。

## In Scope

- 本地开发非 Slack 的 agent/status 工作流，让用户能询问当前 Sherlock 任务状态。
- 本地实现只读历史状态查询，优先使用 `sacct`。
- 本地实现 job id 详情查询。
- 本地保留 job 到 run/output path 候选关联能力，但它不属于默认 Sherlock/Slack status profile。
- 在 Sherlock 上真实验证当前 `query_slurm(filters={"me": true})`。
- 在 Sherlock 上验证 `sacct` 可用性、字段格式和 job array 形态；真实路径信息只允许脱敏记录。
- 设计并实现可选的 Sherlock 产物同步能力，但只作为单独 data-transfer profile。
- 允许在 Sherlock 上通过现有 `run_script_adapter` 执行受控后处理脚本，但只作为单独 script profile。
- 后期再单独设计受限 `sbatch` 提交能力。

## Out of Scope

- Slack Events API、Socket Mode、Slack thread/session 映射、Slack interactive approval。
- `scancel`、`scontrol update` 或任何修改 SLURM 任务状态的能力。
- 第一轮实现中的 `sbatch` 提交。
- 任意 shell 命令执行入口。
- MCP hands 返回 sign quality、warmup 质量、Trotter 误差等物理可靠性结论。
- 默认 Sherlock/Slack status profile 中的 path discovery、run summary、artifact sync 和 script adapter。
- 默认 status response 中的真实 `WorkDir`、stdout/stderr path、run path、output path 或 raw path fields。

## 当前已实现能力

- `dqmc_tools.slurm.query_slurm`
- MCP tool：`query_slurm`
- 支持 filters：`me`、`user`、`job_id`、`state`、`partition`
- 优先 `squeue --json`
- fallback 到 delimited `squeue --noheader --format=...`
- 返回 `summary`、`groups.by_job_name` 和原始 `jobs`
- `squeue --json` path 会 normalize SLURM wrapped fields，再用于 state/category 计数和 array job 分组。
- 本地测试覆盖 `squeue` unavailable、unknown filter、JSON path、fallback path、`me` filter、array job grouping 和 wrapped JSON fields。
- 本地 `dqmc-sherlock-gateway` status-only profile 已通过真实 Sherlock smoke：默认只暴露 `sherlock_query_slurm`、`sherlock_query_slurm_history`、`sherlock_get_slurm_job_detail`，返回 path-redacted payload。
- `sherlock_query_slurm` gateway wrapper 返回顶层 `formatted_summary`，这是 Slack/OpenACP 默认用户展示契约；agent 不应自行重写当前状态摘要或运行 direct SSH/shell 命令压缩输出。
- `sherlock_get_slurm_job_detail` 已能返回 path-redacted structured candidates，但尚缺少与当前状态查询同等级的默认 detail 展示契约；Slack/OpenACP 查询 job detail 时不应追加 direct SSH 或自定义 `squeue`，缺少字段时应扩展 gateway/detail formatter。
- 真实 gateway smoke 确认 `query_slurm` 使用 `squeue_json`、`query_slurm_history` 使用 `sacct_parsable2`、`get_slurm_job_detail` 可从当前队列返回单个 candidate。
- 2026-05-28 补充 smoke 确认：running `parent_task` id 可经 `squeue` 收敛到单个 candidate；completed parent/task id 可经 `sacct` 返回历史 detail，其中 completed task 返回 task-level step group，工具不猜唯一 step row。
- Slack/OpenACP 新 session 已确认可通过本地 `dqmc-sherlock-gateway` 查询 Sherlock SLURM 状态；该事实验证部署链路，不把 Slack transport 逻辑纳入 MCP hands。

## 重要实现经验：SLURM JSON wrapped fields

`78c1ab8` 修复了真实 `squeue --json` 输出和本地 parser 假设不一致的问题。后续 SLURM 工具不能假设 JSON 字段都是普通字符串或数字。

已观察到的真实形态：

- `job_state` 可能是 list，例如 `["PENDING"]`。
- `array_job_id` / `array_task_id` 可能是 dict，例如 `{"set": true, "infinite": false, "number": 24884301}`。
- `set=false` 的 dict 表示该字段没有有效值，不能把 `number` 当成真实 task id。
- `array_job_id=0` 在 Sherlock `squeue --json` 中可表示非 array job 的 sentinel；不能把 `0` 当成 top-level array id，必须 fallback 到真实 `job_id`。当同一 row 也有 `array_task_id=0` 且 job id 本身不是 `parent_task` 形式时，该 task id 也应按 sentinel 处理。
- wrapped dict 也可能通过 `name`、`id` 或 `infinite=true` 表示可显示值。

当前 `query_slurm` 通过 `_slurm_scalar`、`_slurm_text`、`_has_slurm_value` 统一提取可用 scalar。后续 `query_slurm_history`、`get_slurm_job_detail` 和 presenter 应消费 normalized facts，不能在各处重复 ad hoc `str(value)`。

## 功能需求

### R1 本地/远端执行边界

- 命令构造、parser、schema、MCP contract、structured error handling 应在本地用 fixture 测试覆盖。
- 真实 SLURM 输出暴露的新字段形态必须先变成脱敏 fixture，再补 parser 兼容。
- Sherlock 默认只负责真实 `squeue`/`sacct` smoke、字段确认和 status-only 部署验证。
- 任何路径验证、数据读取、同步或脚本执行都必须作为单独 profile，并先确认脱敏和审批边界。
- 本地 gateway 连接 Sherlock 时，`DQMC_SHERLOCK_REMOTE_PYTHON` 应使用 Sherlock 上 venv Python 的绝对路径。相对 `.venv/bin/python` 会在远端 `--cwd` 生效前解析，不作为可靠配置。

### R2 只读安全边界

- 所有 SLURM 状态工具默认只读。
- 子进程调用必须使用 argv list，不使用 shell string。
- 不接入 `scancel`、`scontrol update` 或任何 mutating SLURM 命令。
- 同步、脚本执行、未来提交任务都必须先 dry-run，再由用户逐次审批。
- 默认 Sherlock status 工具不得返回真实 path。`work_dir`、`stdout_path`、`stderr_path`、`standard_output`、`standard_error` 和 `raw` 中同类字段必须移除或脱敏。
- 默认 Sherlock status 环境不设置 `DQMC_DEV_ROOT`、`DQMC_ALLOWED_ROOTS`、`DQMC_OUTPUT_ROOT`、`DQMC_REGISTRY_PATH`。

### R3 `query_slurm` 当前队列查询

- 保留现有 MCP tool `query_slurm`。
- 支持 `filters={"me": true}` 生成 `squeue --me`。
- 返回原始 job rows、`summary`、`groups.by_job_name` 和 array job 分组。
- 对 `squeue --json` wrapped fields 先 normalize，再进入 summary/grouping。
- fallback delimited parser 继续支持 Sherlock 不支持 `--json` 的情况。

### R4 非 Slack 状态摘要

- 提供 agent 层可复用 presenter 或 workflow helper。
- 输入为 `query_slurm` 返回 dict，输出为英文纯文本摘要。
- 完整队列摘要使用固定表格：`Job Name`、`Array Job ID`、`Total`、`Pending`、`Running`。
- `Array Job ID` 对 array job 显示 top-level array job id；非 array job 显示自身 job id。
- 表格后输出 `Total jobs`、`Pending`、`Running` 汇总；`CG`、`CF`、`COMPLETING`、`CONFIGURING` 计入 `Running`。
- MCP hands 继续只返回事实，不判断“是否正常”。

### R5 `sacct` 历史任务查询

- 新增只读函数：`query_slurm_history`。
- 新增 MCP tool：`query_slurm_history`，不要塞进当前 `query_slurm`。
- 底层优先使用 `sacct --parsable2 --noheader`。
- 支持 filters：`me`、`user`、`job_id`、`state`、`start`、`end`、`partition`、`max_rows`。
- 返回 `ok`、`source`、`command`、`jobs`、`summary.state_counts`、`summary.exit_code_counts`、`warnings`。
- `sacct` 不可用时返回 structured `tool_unavailable`。
- 默认 Sherlock gateway/status profile 必须从返回 rows 和 `raw` 中移除或脱敏 `WorkDir`/`work_dir`。

### R6 Job 详情入口

- 新增工具：`get_slurm_job_detail`。
- 输入：`job_id`，可选 `include_history=true`。
- 查询顺序：先查当前 `squeue`，没有结果且允许历史时再查 `sacct`。
- 对 array job 支持 `12345` 和 `12345_7` 两种输入。
- 多个 matching rows 返回 candidates，不猜。
- raw rows 只作为 provenance 返回；展示和摘要应基于 normalized facts。
- 默认 Sherlock gateway/status profile 必须从 candidates 和 `raw` 中移除或脱敏 path fields。
- Slack/OpenACP 默认 job detail 回复必须只使用 `sherlock_get_slurm_job_detail` 的 path-redacted structured result 和固定 detail formatter；不得在 formatter 缺字段时退回 direct SSH、定制 `squeue` 或其它任意 shell 命令。
- detail formatter 应覆盖 array parent 多候选、具体 `parent_task` 单候选、completed task step group 和查无结果四类情况，并用英文输出。

### R7 Job 到 run/output path 关联

- 该能力不属于默认 Sherlock/Slack status profile，只能作为单独 path-discovery profile。
- 第一版不要自动扫描大目录。
- 新增纯推断 helper：输入 job detail 和可选 allowed roots，输出候选 path 与 evidence。
- evidence 必须说明来源，例如 `sacct.WorkDir`、`stdout_path_parent`、`user_provided_path`。
- 只检查 allowed roots 内的候选路径。
- 候选不唯一时返回 candidates，让 agent 询问用户。
- 在 Sherlock 场景启用前必须逐次审批，并确保 agent 不在普通 status 查询中看到实际路径。

### R8 Sherlock 产物同步

- 不属于默认 Sherlock/Slack status profile。
- 如果 agent 和 MCP hands 都跑在 Sherlock，第一版也不应默认直接读远端文件；只有用户明确要求数据读取时才进入 data-reading profile。
- 如果本地 agent 需要读取远端产物，则需要 rsync 同步能力。
- 所有同步先 dry-run。
- 远端路径必须在 allowlist 内，本地目标必须在 output root 内。
- 真实同步必须有用户逐次审批。
- 返回同步 manifest：新增文件、更新文件、跳过文件、大小、mtime、command、source、destination。

### R9 Sherlock 后处理脚本

- 不属于默认 Sherlock/Slack status profile。
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
- Sherlock `query_slurm(filters={"me": true})` smoke 返回 `ok=true`。2026-05-28 已通过本地 gateway smoke。
- `sacct` 可用时能查询 completed/failed/timeout/OOM 任务；不可用时返回 structured `tool_unavailable`。2026-05-28 已通过 completed rows 的 gateway smoke。
- wrapped JSON fields 不会破坏 state/category 计数或 array job 分组。
- 任意新增 SLURM 命令都只生成 argv list，不使用 shell string。
- 不存在 submit/cancel/mutate SLURM 工具，除非后续单独 spec 明确引入。
- 默认 Sherlock gateway/status response 不包含真实 `WorkDir`、stdout/stderr path、run/output path、remote repo cwd 或 raw path fields。2026-05-28 gateway smoke 中三个 status tools 的 path redaction check 均通过。
