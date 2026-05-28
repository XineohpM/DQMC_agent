# Sherlock SLURM SDD 验证记录

状态：待执行。本文件记录本地验证命令、Sherlock smoke 命令和真实输出字段发现。

## 本地验证

### 基线命令

```bash
.venv/bin/python -m pytest tests/test_slurm.py
```

期望：

- `query_slurm` unavailable、bad filter、JSON path、fallback path、`me` filter、array grouping、wrapped JSON fields 测试通过。

### MCP contract

```bash
.venv/bin/python -m pytest \
  tests/test_mcp_contracts.py::test_query_slurm_mcp_success_contract \
  tests/test_mcp_contracts.py::test_query_slurm_mcp_error_contract \
  tests/test_mcp_server.py::test_mcp_tool_set_has_current_hands_surface \
  tests/test_mcp_server.py::test_mcp_descriptions_match_current_registry_and_run_rules
```

期望：

- MCP tool set 包含 `query_slurm`。
- success contract 返回 `ok`、`source`、`command`、`commands_attempted`、`jobs`、`summary`、`groups`。
- error contract 对缺少 `squeue` 返回 structured `tool_unavailable`。

### 共享契约变更后

本节是本地完整工具环境验证记录，不代表 Sherlock status-only profile 需要设置
`DQMC_DEV_ROOT`。

```bash
DQMC_DEV_ROOT=/Users/phoenixm/Desktop/dqmc-dev .venv/bin/python -m pytest
```

结果：

- `116 passed in 13.13s`

## Phase L1 本地 Presenter

命令：

```bash
.venv/bin/python -m pytest tests/test_slurm_presenter.py -q
.venv/bin/python -m pytest tests/test_slurm_presenter.py tests/test_package_import.py tests/test_slurm.py tests/test_mcp_contracts.py::test_query_slurm_mcp_success_contract tests/test_mcp_contracts.py::test_query_slurm_mcp_error_contract tests/test_mcp_server.py::test_mcp_tool_set_has_current_hands_surface tests/test_mcp_server.py::test_mcp_descriptions_match_current_registry_and_run_rules -q
```

结果：

- `tests/test_slurm_presenter.py -q`：`3 passed`
- presenter/import/SLURM/MCP targeted suite：`15 passed`

覆盖：

- 空队列输出 `当前没有任务。`
- running/pending/held_blocked/other 计数。
- array job 汇总保持紧凑，不逐条刷屏。
- pending reason 或 node 信息保留在示例行。
- 不新增 Slack 依赖。

## Phase L2 本地 `sacct` 历史查询

命令：

```bash
.venv/bin/python -m pytest tests/test_slurm.py::test_query_slurm_history_unavailable tests/test_slurm.py::test_query_slurm_history_rejects_unknown_filter tests/test_slurm.py::test_query_slurm_history_timeout tests/test_slurm.py::test_query_slurm_history_builds_sacct_command_and_parses_rows tests/test_slurm.py::test_query_slurm_history_applies_job_filter_and_max_rows tests/test_slurm.py::test_query_slurm_history_warns_on_short_rows tests/test_mcp_contracts.py::test_query_slurm_history_mcp_success_contract tests/test_mcp_contracts.py::test_query_slurm_history_mcp_error_contract tests/test_mcp_server.py::test_mcp_tool_set_has_current_hands_surface tests/test_mcp_server.py::test_mcp_descriptions_match_current_registry_and_run_rules -q
```

结果：

- `10 passed`

覆盖：

- `sacct --parsable2 --noheader` command builder 和字段白名单。
- filters：`me`、`job_id`、`state`、`start`、`end`、`partition`、`max_rows`。
- unknown filter structured error。
- `sacct` unavailable structured `tool_unavailable`。
- timeout structured error。
- completed/failed/timeout/OOM parsable2 fixture。
- short rows warning。
- MCP tool set 和 success/error contract。

## Phase L3 本地 Job 详情入口

命令：

```bash
.venv/bin/python -m pytest tests/test_slurm.py::test_get_slurm_job_detail_prefers_current_queue tests/test_slurm.py::test_get_slurm_job_detail_uses_history_when_current_queue_is_empty tests/test_slurm.py::test_get_slurm_job_detail_preserves_failed_history_candidate tests/test_slurm.py::test_get_slurm_job_detail_returns_stable_empty_result_without_history tests/test_slurm.py::test_get_slurm_job_detail_returns_array_candidates_without_guessing tests/test_slurm.py::test_get_slurm_job_detail_filters_specific_array_task tests/test_slurm.py::test_get_slurm_job_detail_rejects_empty_job_id tests/test_mcp_contracts.py::test_get_slurm_job_detail_mcp_success_contract tests/test_mcp_contracts.py::test_get_slurm_job_detail_mcp_error_contract tests/test_mcp_server.py::test_mcp_tool_set_has_current_hands_surface tests/test_mcp_server.py::test_mcp_descriptions_match_current_registry_and_run_rules -q
```

结果：

- `11 passed`

覆盖：

- `get_slurm_job_detail(job_id, include_history=True)` public API。
- 当前队列 `squeue` 命中时不查历史。
- 当前队列为空时查 `sacct` 历史，覆盖 completed 和 failed 状态。
- `include_history=false` 时返回稳定空结果。
- array parent 返回多个 candidates，具体 task id 只返回对应 candidate。
- 空 job id structured error。
- MCP tool set 和 success/error contract。

## Phase L4 本地 Path Candidates

命令：

```bash
.venv/bin/python -m pytest tests/test_slurm_paths.py tests/test_mcp_contracts.py::test_infer_slurm_path_candidates_mcp_success_contract tests/test_mcp_server.py::test_mcp_tool_set_has_current_hands_surface tests/test_mcp_server.py::test_mcp_descriptions_match_current_registry_and_run_rules -q
```

结果：

- `9 passed`

覆盖：

- `sacct.WorkDir` 生成 high-confidence candidate。
- stdout/stderr parent 分别生成 medium-confidence candidate，不做唯一猜测。
- allowed roots 外路径标记为 inaccessible 和 `outside_allowed_roots`。
- 同一路径去重并保留更高 confidence evidence。
- 用户显式 path 作为 high-confidence candidate。
- accessible candidate 可作为 `summarize_run(max_files=1)` 输入做 bounded 验证。
- MCP tool set 和 success contract。

## Phase L5/R5 Artifact Sync Design

文档：

- `specs/sherlock-slurm-sdd/artifact-sync-design.md`

覆盖：

- sync 仅用于用户明确要求读取 Sherlock 远端产物的非默认 data-transfer profile。
- 默认 Sherlock/Slack status profile 不进入同步，也不主动提示真实 run/output path。
- 已实现 `sync_sherlock_artifacts`，但不属于默认 status workflow。
- 明确 remote host/path allowlist、本地 output root、dry-run、审批、manifest schema 和错误模型。
- 明确实现前测试计划，真实 Sherlock 验证必须先 dry-run 小目录。

## Phase L5 本地 Artifact Sync

命令：

```bash
.venv/bin/python -m pytest tests/test_sync.py tests/test_mcp_contracts.py::test_sync_sherlock_artifacts_mcp_success_contract tests/test_mcp_contracts.py::test_sync_sherlock_artifacts_mcp_approval_error_contract tests/test_mcp_server.py::test_mcp_tool_set_has_current_hands_surface tests/test_mcp_server.py::test_mcp_descriptions_match_current_registry_and_run_rules -q
```

结果：

- `12 passed`

覆盖：

- dry-run command builder 使用 argv list，并包含 `--dry-run`。
- remote host allowlist、remote path allowlist 和 unsafe remote path rejection。
- local destination 必须在 output root 内。
- `dry_run=false` 无审批返回 `user_approval_required`。
- 已审批同步命令不带 `--dry-run`，并返回 manifest。
- `rsync` unavailable 返回 structured `tool_unavailable`。
- MCP success/error contract 和 tool set。

## Phase L6 本地 Polling Workflow

命令：

```bash
.venv/bin/python -m pytest tests/test_slurm_monitor.py -q
```

结果：

- `3 passed`

覆盖：

- 固定 snapshots diff：新增、消失、state 改变和 unchanged count。
- snapshot diff 文本摘要。
- 无变化时输出稳定摘要。
- workflow 文档：`polling-workflow.md`，说明轮询由 agent 层驱动，MCP hands 不启动后台进程。

## Sherlock 环境基线

记录项：

- 仓库分支：
- commit：
- Python 版本：
- `.venv` 路径：
- status-only env：确认未设置 `DQMC_DEV_ROOT`、`DQMC_ALLOWED_ROOTS`、`DQMC_OUTPUT_ROOT`、`DQMC_REGISTRY_PATH`

命令：

```bash
.venv/bin/python -m pytest tests/test_package_import.py tests/test_slurm.py tests/test_slurm_presenter.py tests/test_slurm_monitor.py -q
.venv/bin/python -c "import dqmc_tools; print(dqmc_tools.__version__)"
```

结果：

- 待记录。

## Sherlock `squeue --me` smoke

命令：

```bash
squeue --me
```

记录：

- 是否成功：
- 输出是否包含 array jobs：
- pending reason 字段形态：
- node/reason 字段形态：

MCP smoke：

```python
query_slurm(filters={"me": True})
```

记录：

- `ok`：
- `source`：`squeue_json` 或 `squeue_fallback`
- `summary.total_jobs`：
- `summary.state_counts`：
- `summary.category_counts`：
- `groups.by_job_name` 是否可读：

验收：

- `ok=true`。
- summary 包含 total/state/category counts。
- array jobs 可分组。
- 无 submit/cancel/mutate 命令。

## Sherlock `squeue --json` 字段形态

如果 Sherlock 支持 `squeue --json`，记录脱敏后的最小字段样本。

重点字段：

- `job_id`：
- `name` / `job_name`：
- `job_state`：scalar/list/dict
- `state_reason` / `reason`：
- `array_job_id`：scalar/list/dict
- `array_task_id`：scalar/list/dict
- `nodes`：

已知需要覆盖的 wrapped forms：

```json
{
  "job_state": ["PENDING"],
  "array_job_id": {"set": true, "infinite": false, "number": 24884301},
  "array_task_id": {"set": false, "infinite": false, "number": 0}
}
```

处理要求：

- 脱敏后补入本地 fixture。
- 本地 wrapped fields 测试必须覆盖新形态。
- summary/grouping 必须使用 normalized facts。

## Sherlock `sacct` 可用性

命令：

```bash
which sacct
sacct --parsable2 --noheader --format=JobID,JobName,User,State,ExitCode,Elapsed,Timelimit,Submit,Start,End,Partition,NodeList
```

记录：

- `sacct` 是否存在：
- 默认时间窗口是否足够：
- 是否需要显式 `--starttime`：
- `WorkDir` 是否开放：仅在 path-discovery profile 中记录，status-only profile 不返回该字段
- `JobID` 对 array parent/task 的格式：
- `State` 和 `ExitCode` 对 completed/failed/timeout/OOM 的实际形态：
- 字段是否全部为 scalar：

验收：

- 可查询最近 N 天当前用户任务，或返回明确 unavailable/error。
- completed/failed/timeout/OOM 能返回 state 和 exit code。
- 缺失可选字段只产生 warning，不让工具整体失败。

## Job Detail Smoke

当前队列 job：

- job id：
- command/source：
- candidate count：
- state：
- partition：
- node/reason：

历史 job：

- job id：
- command/source：
- candidate count：
- state：
- exit code：
- start/end：
- work dir：默认响应应脱敏或不返回

验收：

- running job 从 `squeue` 返回详情。
- completed/failed job 从 `sacct` 返回详情。
- array parent 和 task id 行为明确。
- 查不到 job 时返回稳定空结构。
- 默认 Sherlock gateway/status response 不含 `work_dir`、stdout/stderr path 或 raw path fields。

## Path Association Smoke

本节不属于默认 Sherlock/Slack status profile。只有用户明确批准 path-discovery profile 时执行。

记录：

- `sacct WorkDir` 是否指向 run/output：
- stdout/stderr path 是否可推断：
- allowed roots 是否覆盖目标路径：
- 越界路径是否被拒绝或标记不可访问：

验收：

- 不做大目录扫描。
- high-confidence candidate 有明确 evidence。
- 多候选时不猜。

## 后处理脚本 Smoke

本节不属于默认 Sherlock/Slack status profile。只有用户明确批准 script profile 时执行。

命令：

```python
describe_script_adapter(script_id)
run_script_adapter(script_id, params, dry_run=True)
```

记录：

- `DQMC_DEV_ROOT`：
- script id：
- dry-run command：
- cwd：
- required inputs：
- output root：
- preflight result：

验收：

- dry-run 显示 command、cwd、required inputs、output root。
- 缺少输入时 preflight fail。
- 没有用户同意时真实执行被拒绝。
- 有用户同意时输出写入 Sherlock 上的 `DQMC_OUTPUT_ROOT`。

## 不启用能力

除非后续单独 spec 明确引入，否则以下能力保持未启用：

- Slack transport。
- `sbatch` 提交。
- `scancel` / `scontrol update`。
- 任意 shell 命令执行。
- MCP hands 内部 daemon/watchers。
