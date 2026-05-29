# Sherlock SLURM SDD 验证记录

状态：默认 status-only Sherlock 查询链路已完成真实 smoke；本文件记录本地验证命令、Sherlock smoke 命令、真实输出字段发现和不属于本 SDD 的 transport 观察。

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

- 旧记录：`116 passed in 13.13s`
- 2026-05-28 更新：`140 passed in 13.14s`

## Phase L1 本地 Presenter

命令：

```bash
.venv/bin/python -m pytest tests/test_slurm_presenter.py -q
.venv/bin/python -m pytest tests/test_slurm_presenter.py tests/test_slurm_monitor.py -q
.venv/bin/python -m pytest tests/test_package_import.py tests/test_slurm.py tests/test_slurm_presenter.py tests/test_slurm_monitor.py -q
```

结果：

- `tests/test_slurm_presenter.py -q`：`5 passed`
- presenter/monitor targeted suite：`8 passed`
- package/import/SLURM/presenter/monitor targeted suite：`29 passed`

覆盖：

- 空队列输出 `No current SLURM jobs.`
- error 输出 `SLURM status query failed: ...`
- 按 `Job Name`、`Array Job ID`、`Total`、`Pending`、`Running` 生成英文固定表格。
- 非 array job 的 `Array Job ID` 显示自身 job id。
- `CG`、`CF`、`COMPLETING`、`CONFIGURING` 计入 `Running`。
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
- snapshot diff 文本摘要使用英文。
- 无变化时输出 `No SLURM job status changes.`
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
env -u DQMC_DEV_ROOT -u DQMC_ALLOWED_ROOTS -u DQMC_OUTPUT_ROOT -u DQMC_REGISTRY_PATH \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  .venv/bin/python -m pytest \
    -p no:cacheprovider \
    tests/test_package_import.py \
    tests/test_slurm.py \
    tests/test_slurm_presenter.py \
    tests/test_slurm_monitor.py \
    -q
.venv/bin/python -c "import dqmc_tools; print(dqmc_tools.__version__)"
```

结果：

- 2026-05-28 status-only gateway smoke 前置检查：
  - 本机 `ssh -o BatchMode=yes sherlock hostname` 可非交互返回。
  - Sherlock 端 repo 同步后，远端 `.venv` 可 `import dqmc_tools.remote_call`。
  - 默认 status-only smoke 未向远端注入 `DQMC_DEV_ROOT`、`DQMC_ALLOWED_ROOTS`、`DQMC_OUTPUT_ROOT`、`DQMC_REGISTRY_PATH`。
  - 真实 Sherlock repo 路径不写入本文件；统一记为 `<REDACTED_DQMC_AGENT_ON_SHERLOCK>`。
  - 发现：本地 gateway 的 `DQMC_SHERLOCK_REMOTE_PYTHON` 应配置为 Sherlock 上 venv Python 的绝对路径，例如 `<REDACTED_DQMC_AGENT_ON_SHERLOCK>/.venv/bin/python`。相对 `.venv/bin/python` 会在远端 `--cwd` 生效前解析，可能失败。
- 2026-05-28 Sherlock status-only pytest：
  - 执行前先做本地只读 preflight，确认目标测试文件没有显式写 repo、scratch 或 output root。
  - 命令使用 `PYTHONDONTWRITEBYTECODE=1`、`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` 和 `-p no:cacheprovider`，避免 Python bytecode 和 pytest cache 写入。
  - 运行时显式 unset `DQMC_DEV_ROOT`、`DQMC_ALLOWED_ROOTS`、`DQMC_OUTPUT_ROOT`、`DQMC_REGISTRY_PATH`。
  - 结果：`27 passed`。
  - 未运行 HDF5、script adapter、sync、path-discovery 或 data-reading tests。

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

- 2026-05-28 手写 SSH + `remote_call` smoke：
  - `ok`：true
  - `source`：`squeue_json`
  - `summary.total_jobs`：1077
  - `summary.state_counts`：`PENDING` 和 `RUNNING`
  - `summary.category_counts`：`pending` 和 `running`
  - `groups.by_job_name` 是否可读：是
- 2026-05-28 本地 `dqmc-sherlock-gateway` smoke：
  - `ok`：true
  - `source`：`squeue_json`
  - `summary.total_jobs`：1077
  - 连续调用期间队列实时变化，pending/running counts 有小幅变化。
  - gateway provenance：只包含 `host` 和 `tool`，不包含 remote cwd。
  - path redaction check：`has_sensitive_path_keys=false`
- 2026-05-28 本地 Codex/OpenACP 实际配置 smoke：
  - `dqmc-sherlock-gateway` 已写入本地用户级 Codex 配置。
  - profile：`status-only`
  - 远端 env JSON：`{}`
  - 默认工具面：`sherlock_query_slurm`、`sherlock_query_slurm_history`、`sherlock_get_slurm_job_detail`
  - `sherlock_query_slurm(filters={"me": true})` 返回 `ok=true`、`source=squeue_json`；后续一次配置验证中 `summary.total_jobs` 为 1072，说明队列 live 状态在 smoke 期间正常变化。
  - response path redaction check：`has_sensitive_path_keys=false`

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

2026-05-28 追加字段形态：

- 非 array `sdev` 交互任务可在 `squeue --json` 中返回 `array_job_id=0`。
- `array_job_id=0` 是 non-array sentinel；`query_slurm` 应 fallback 到真实 `job_id`，避免当前状态表格的 `Array Job ID` 显示为 `0`。
- 如果同一 row 也有 `array_task_id=0`，且 `job_id` 本身不是 `parent_task` 形式，该 task id 也应按 sentinel 处理；`array_task_id=0` 对真实 array task 仍可能是有效 task id。

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

- 2026-05-28 本地 gateway `sherlock_query_slurm_history(filters={"me": true, "max_rows": 5})` smoke：
  - `ok`：true
  - `source`：`sacct_parsable2`
  - `job_count`：5
  - `summary.state_counts`：`COMPLETED=5`
  - `summary.exit_code_counts`：`0:0=5`
  - `WorkDir` 是否开放：默认 status-only response 不返回该字段。
  - path redaction check：`has_sensitive_path_keys=false`
- 默认时间窗口是否足够：仍需单独确认；当前 smoke 使用 `max_rows` 限制，没有把默认窗口写死。

验收：

- 可查询最近 N 天当前用户任务，或返回明确 unavailable/error。
- completed/failed/timeout/OOM 能返回 state 和 exit code。
- 缺失可选字段只产生 warning，不让工具整体失败。

## Job Detail Smoke

当前队列 job：

- 2026-05-28 本地 gateway `sherlock_get_slurm_job_detail` smoke：
  - job id：使用临时真实 job id 查询，但不记录。
  - command/source：`squeue`
  - `match_count`：1
  - `multiple_matches`：false
  - candidate count：1
  - state/category：`PENDING` / `pending`
  - warning count：0
  - path redaction check：`has_sensitive_path_keys=false`

array parent/task job：

- 2026-05-28 本地 gateway `sherlock_get_slurm_job_detail` 补充 smoke：
  - running array parent id：返回 `match_count=96`、`multiple_matches=true`，符合 parent id 不猜唯一结果。
  - running `parent_task` id：经 `squeue` 返回 `match_count=1`、`multiple_matches=false`。
  - running task candidate：`source=squeue`，state/category 为 `RUNNING` / `running`。
  - running task response path check：`sensitive_path_keys_present=[]`，`path_like_value_count=0`。

历史 job：

- 2026-05-28 本地 gateway `sherlock_get_slurm_job_detail` completed array parent smoke：
  - command/source：先 `squeue`，job-specific lookup 返回 `tool_unavailable`，随后 fallback 到 `sacct`。
  - `sacct` candidate count：1024。
  - candidate state/category：`COMPLETED` / `completed`。
  - exit code：`0:0`。
  - path redaction check：`sensitive_path_keys_present=[]`，`path_like_value_count=0`。

- 2026-05-28 本地 gateway `sherlock_get_slurm_job_detail` completed `parent_task` smoke：
  - command/source：先 `squeue`，随后 fallback 到 `sacct`。
  - candidate count：4。
  - candidates：task 本体、`.batch`、`.extern`、`.0` step rows。
  - state/category：全部为 `COMPLETED` / `completed`。
  - exit code：全部为 `0:0`。
  - interpretation：已结束 array task 在 `sacct` 中收敛到 task-level step group，不是单条 row；工具继续返回 candidates，不猜唯一 step。
  - path redaction check：`sensitive_path_keys_present=[]`，`path_like_value_count=0`。

验收：

- 当前队列 job 从 `squeue` 返回详情。
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

## Slack/OpenACP Transport Observation

本节记录产品链路观察，不改变本 SDD 的 MCP hands 范围；Slack transport 仍不接进
`dqmc_tools.slurm`。

2026-05-28：

- OpenACP backend 已加载本地 Codex 配置中的 `dqmc-sherlock-gateway`。
- Slack/OpenACP 新会话可正常查询 Sherlock SLURM 任务。
- 端到端链路为 `Slack -> OpenACP -> 本地 Codex -> dqmc-sherlock-gateway -> 短 SSH -> Sherlock remote_call -> SLURM`。
- Sherlock 上没有常驻 agent；查询期间只会出现短命 SSH/remote Python 调用。
- 默认 status-only profile 不向远端注入 `DQMC_DEV_ROOT`、`DQMC_ALLOWED_ROOTS`、`DQMC_OUTPUT_ROOT` 或 `DQMC_REGISTRY_PATH`。
- 观察到一个待修复的 job detail 展示缺口：用户请求两个 array parent job 的详细信息时，agent 先尝试使用 gateway MCP tool，但在压缩大结果时又尝试 direct SSH + 定制 `squeue`。该行为不符合 status-only gateway 展示契约；后续应让 `sherlock_get_slurm_job_detail` 返回固定英文 `formatted_detail`，并要求 Slack/OpenACP 直接使用该字段。
- 该观察不表示可以把 direct SSH 作为 fallback；缺少紧凑字段时应扩展 gateway formatter 或 structured result。

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
