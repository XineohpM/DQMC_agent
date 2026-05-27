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

```bash
DQMC_DEV_ROOT=/Users/phoenixm/Desktop/dqmc-dev .venv/bin/python -m pytest
```

结果：

- `79 passed in 8.50s`

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

## Sherlock 环境基线

记录项：

- 仓库分支：
- commit：
- Python 版本：
- `.venv` 路径：
- `DQMC_DEV_ROOT`：
- `DQMC_ALLOWED_ROOTS`：
- `DQMC_OUTPUT_ROOT`：
- `DQMC_REGISTRY_PATH`：

命令：

```bash
.venv/bin/python -m pytest
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
sacct --parsable2 --noheader --format=JobID,JobName,User,State,ExitCode,Elapsed,Timelimit,Submit,Start,End,Partition,NodeList,WorkDir
```

记录：

- `sacct` 是否存在：
- 默认时间窗口是否足够：
- 是否需要显式 `--starttime`：
- `WorkDir` 是否开放：
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
- work dir：

验收：

- running job 从 `squeue` 返回详情。
- completed/failed job 从 `sacct` 返回详情。
- array parent 和 task id 行为明确。
- 查不到 job 时返回稳定空结构。

## Path Association Smoke

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
