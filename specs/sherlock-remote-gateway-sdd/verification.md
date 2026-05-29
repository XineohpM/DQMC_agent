# Sherlock Remote Gateway SDD 验证记录

状态：本地测试和默认 status-only Sherlock/Slack smoke 已完成。本文记录验证命令、真实 smoke 结果和后续非默认 profile 的边界。

## 本地验证计划

### Phase G1 Remote Call

命令：

```bash
.venv/bin/python -m pytest tests/test_remote_call.py -q
```

期望：

- remote CLI dispatcher 能调用白名单函数。
- unknown tool 返回 `invalid_argument`。
- invalid JSON 返回 structured error。
- env 注入只允许 `DQMC_ALLOWED_ROOTS`、`DQMC_OUTPUT_ROOT`、`DQMC_REGISTRY_PATH`、`DQMC_DEV_ROOT`、`DQMC_SCRIPT_TIMEOUT_SECONDS`。
- 默认 status-only profile 不应注入这些数据/脚本环境变量；allowlist 仅用于非默认 profile 和兼容测试。
- stdout 只输出 JSON。

结果：

- `5 passed`

### Phase G2 Remote Gateway

命令：

```bash
.venv/bin/python -m pytest tests/test_remote_gateway.py -q
```

期望：

- config 能从 env 读取。
- SSH command builder 使用 argv list。
- success path 通过 stdin 发送 JSON payload，并包装 remote provenance。
- host allowlist、missing cwd、ssh unavailable、timeout、nonzero returncode、invalid JSON stdout 都返回 structured error。

结果：

- `12 passed`

### Phase G3 Gateway MCP Server

命令：

```bash
.venv/bin/python -m pytest tests/test_sherlock_gateway_mcp_server.py -q
```

期望：

- 默认 MCP server 暴露：
  - `sherlock_query_slurm`
  - `sherlock_query_slurm_history`
  - `sherlock_get_slurm_job_detail`
- `data-reading` profile 额外暴露：
  - `sherlock_summarize_run`
- success contract 返回 `ok`、`remote`、`result`。
- gateway error contract 返回 JSON-safe structured error。
- 默认 status-only profile contract 验证只暴露前三个 status tools，并验证 path redaction。

结果：

- `7 passed`

2026-05-28 追加 job detail formatter 覆盖：

```bash
.venv/bin/python -m pytest tests/test_slurm_presenter.py \
  tests/test_remote_gateway.py::test_call_sherlock_tool_adds_formatted_detail_after_redaction_without_extra_ssh \
  tests/test_sherlock_gateway_mcp_server.py::test_sherlock_get_slurm_job_detail_description_requires_formatted_detail \
  tests/test_sherlock_gateway_mcp_server.py::test_sherlock_get_slurm_job_detail_mcp_contract -q
```

结果：

- `13 passed`

覆盖：

- `sherlock_get_slurm_job_detail` gateway wrapper 返回顶层 `formatted_detail`。
- formatter 覆盖 array parent 多候选、具体 array task、completed task step group、查无结果和错误消息。
- path redaction 先于 `formatted_detail` 生成；测试确认格式化输出不包含 `/scratch` path。
- 大型 array parent detail 只使用 gateway structured payload 压缩展示，不触发额外 direct SSH、定制 `squeue` 或 `awk` pipeline。

### Regression

命令：

```bash
DQMC_DEV_ROOT=/Users/phoenixm/Desktop/dqmc-dev \
  .venv/bin/python -m pytest tests/test_mcp_server.py tests/test_mcp_contracts.py tests/test_remote_call.py tests/test_remote_gateway.py tests/test_sherlock_gateway_mcp_server.py -q
```

期望：

- 原 `dqmc-hands` 14 个 tool 不变。
- 新 gateway MCP server 是独立入口，不污染 `dqmc_mcp_server.py`。
- `DQMC_DEV_ROOT` 只在本地完整工具测试环境中设置，不属于 Sherlock status-only profile。

结果：

- `45 passed`

### Full Suite

命令：

```bash
DQMC_DEV_ROOT=/Users/phoenixm/Desktop/dqmc-dev .venv/bin/python -m pytest
```

结果：

- `140 passed in 13.30s`

## Sherlock Smoke 模板

本阶段需要真实 Sherlock 访问。执行前必须先完成 `specs/sherlock-slurm-sdd/sherlock-validation-handoff.md` 中的安全检查。

### Sherlock Repo Baseline

记录项：

- Sherlock repo path：
- commit：
- Python：
- `.venv`：
- status-only remote env：应为空或不包含 `DQMC_DEV_ROOT`、`DQMC_ALLOWED_ROOTS`、`DQMC_OUTPUT_ROOT`、`DQMC_REGISTRY_PATH`

命令：

```bash
pwd
git status --short --branch
git log --oneline -5
.venv/bin/python -m pytest tests/test_remote_call.py tests/test_slurm.py -q
```

结果：

- 未执行：需要真实 Sherlock 访问。

### Direct Remote Call On Sherlock

在 Sherlock repo 内直接运行：

```bash
printf '%s\n' '{"tool":"query_slurm","args":{"filters":{"me":true}},"env":{}}' \
  | .venv/bin/python -m dqmc_tools.remote_call --cwd "$PWD"
```

记录：

- returncode：
- stdout JSON parse：
- `ok`：
- `source`：
- `summary.total_jobs`：
- stderr：

### Local Gateway To Sherlock

本地配置示例：

```bash
export DQMC_SHERLOCK_REMOTE_HOST="sherlock"
export DQMC_SHERLOCK_ALLOWED_HOSTS="sherlock"
export DQMC_SHERLOCK_REMOTE_PYTHON="<REDACTED_DQMC_AGENT_ON_SHERLOCK>/.venv/bin/python"
export DQMC_SHERLOCK_REMOTE_CWD="<REDACTED_DQMC_AGENT_ON_SHERLOCK>"
export DQMC_SHERLOCK_TIMEOUT_SECONDS="60"
export DQMC_SHERLOCK_REMOTE_ENV_JSON='{}'
```

2026-05-28 smoke 发现：`DQMC_SHERLOCK_REMOTE_PYTHON` 必须使用远端 venv Python 的绝对路径。相对 `.venv/bin/python` 会在远端 `--cwd` 生效前解析，可能导致 gateway SSH 子进程失败。

2026-05-28 本地 Codex/OpenACP 实际配置状态：

- `dqmc-sherlock-gateway` 已写入本地用户级 Codex 配置。
- profile 为 `status-only`。
- Sherlock 端 Python 使用已验证的绝对路径；真实路径不写入 repo 文档。
- `DQMC_SHERLOCK_REMOTE_ENV_JSON` 为 `{}`。
- 未设置 `DQMC_DEV_ROOT`、`DQMC_ALLOWED_ROOTS`、`DQMC_OUTPUT_ROOT`、`DQMC_REGISTRY_PATH` 等数据读取或脚本执行 env。
- 默认工具面枚举结果为 `sherlock_query_slurm`、`sherlock_query_slurm_history`、`sherlock_get_slurm_job_detail`。

MCP smoke：

```python
sherlock_query_slurm(filters={"me": True})
sherlock_query_slurm_history(filters={"me": True, "max_rows": 5})
sherlock_get_slurm_job_detail(job_id="REDACTED_JOB_ID")
```

记录：

- 每次调用是否 60 秒内完成：是。
- gateway `ok`：true。
- remote tool `result.ok`：true。
- stdout/stderr tail：
- 字段形态是否需要补 fixture：`squeue --json` wrapped fields 已记录；fixture 回流可后续补充。
- response 是否不含 `work_dir`、stdout/stderr path、真实 run path、output path 或 raw path fields：是，三个默认 status tools 的 path redaction check 均通过。
- gateway provenance 是否不暴露 Sherlock remote cwd：是，只包含 host/tool。

真实结果摘录：

- `sherlock_query_slurm(filters={"me": true})`：`ok=true`、`source=squeue_json`；队列是 live 状态，连续调用时 total/running/pending 数量会变化。
- `sherlock_query_slurm_history(filters={"me": true, "max_rows": 5})`：`ok=true`、`source=sacct_parsable2`，返回 5 条 completed rows。
- `sherlock_get_slurm_job_detail(job_id="<REDACTED_JOB_ID>")`：`ok=true`，一个当前队列 job 返回单个 candidate。
- 2026-05-28 补充 job detail smoke：
  - running array parent id：`ok=true`，返回多候选；running `parent_task` id：经 `squeue` 收敛到单个 `RUNNING` candidate。
  - completed array parent id：先记录 `squeue` job-specific lookup failure，再 fallback 到 `sacct`，返回 completed 多候选。
  - completed `parent_task` id：fallback 到 `sacct` 后返回该 task 的 step group，包括 task 本体和 `.batch`/`.extern`/`.0` rows，state 为 `COMPLETED`、exit code 为 `0:0`。
  - 补充 smoke 的 status-only response path check 均通过：无 sensitive path keys，无 path-like values。

### Slack/OpenACP End-to-End Smoke

2026-05-28：

- OpenACP backend 已用本地私密 Slack/OpenACP env 启动。
- 本地 API 监听验证通过；Slack adapter 启动。
- Slack 新 session 能加载 Codex 的本地 MCP 配置。
- 用户确认通过 Slack/OpenACP 可正常查询 Sherlock SLURM 任务。
- 端到端链路为 `Slack -> OpenACP -> 本地 Codex -> dqmc-sherlock-gateway -> 短 SSH -> Sherlock remote_call -> SLURM`。
- Sherlock 上没有常驻 agent；查询只产生短命 SSH/remote Python 进程。
- 此前 job detail 展示存在缺口：用户请求两个 array parent job 的详细信息时，agent 先尝试 gateway MCP tool，但在面对较大 detail payload 时又尝试 direct SSH + 定制 `squeue`。这是验证中发现的非目标 fallback；本地已通过 `sherlock_get_slurm_job_detail` 的固定 `formatted_detail` 展示契约修复，仍需 Sherlock/Slack smoke 验证。
- 后续 Slack/OpenACP job detail smoke 应验证：不出现 direct SSH approval request，不出现自定义 `squeue`/`awk` pipeline，用户回复直接来自 path-redacted gateway formatter。

`sherlock_summarize_run` 不属于默认 status-only smoke。如需验证，必须作为单独
data-reading profile，先明确 allowed roots、审批文本和响应脱敏策略。

## 安全审计清单

- 本地代码审计：已执行。

- [x] 没有 `shell=True`。
- [x] 没有 `bash -lc`。
- [x] 没有用户可控 remote command。
- [x] 没有 `sbatch`、`scancel`、`scontrol update`。
- [x] 没有 `/scratch` 大目录扫描。
- [x] 没有真实写入动作。
- [x] 远端 env 只允许明确白名单变量。
- [x] 默认 status-only profile 不注入数据/脚本 env。
- [x] 默认 status-only response 做 path redaction。
- [x] 本地 Codex/OpenACP 实际配置使用 status-only profile 和空远端 env JSON。
- [x] Slack/OpenACP 端到端 status 查询已通过，且不改变 MCP hands 的边界。
- [ ] Slack/OpenACP job detail 查询只使用 gateway formatter，不触发 direct SSH 或任意 shell fallback。
