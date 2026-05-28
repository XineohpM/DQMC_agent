# Sherlock Remote Gateway SDD 验证记录

状态：本地开发中。本文记录本地验证命令和 Sherlock smoke 模板。

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

- `10 passed`

### Phase G3 Gateway MCP Server

命令：

```bash
.venv/bin/python -m pytest tests/test_sherlock_gateway_mcp_server.py -q
```

期望：

- MCP server 暴露：
  - `sherlock_query_slurm`
  - `sherlock_query_slurm_history`
  - `sherlock_get_slurm_job_detail`
  - `sherlock_summarize_run`
- success contract 返回 `ok`、`remote`、`result`。
- gateway error contract 返回 JSON-safe structured error。

结果：

- `6 passed`

### Regression

命令：

```bash
.venv/bin/python -m pytest tests/test_mcp_server.py tests/test_mcp_contracts.py tests/test_remote_call.py tests/test_remote_gateway.py tests/test_sherlock_gateway_mcp_server.py -q
```

期望：

- 原 `dqmc-hands` 14 个 tool 不变。
- 新 gateway MCP server 是独立入口，不污染 `dqmc_mcp_server.py`。

结果：

- `42 passed`

### Full Suite

命令：

```bash
.venv/bin/python -m pytest
```

结果：

- `137 passed in 13.18s`

## Sherlock Smoke 模板

本阶段需要真实 Sherlock 访问。执行前必须先完成 `specs/sherlock-slurm-sdd/sherlock-validation-handoff.md` 中的安全检查。

### Sherlock Repo Baseline

记录项：

- Sherlock repo path：
- commit：
- Python：
- `.venv`：
- `DQMC_DEV_ROOT`：
- `DQMC_ALLOWED_ROOTS`：
- `DQMC_OUTPUT_ROOT`：
- `DQMC_REGISTRY_PATH`：

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
export DQMC_SHERLOCK_REMOTE_PYTHON=".venv/bin/python"
export DQMC_SHERLOCK_REMOTE_CWD="/absolute/path/to/DQMC_agent"
export DQMC_SHERLOCK_TIMEOUT_SECONDS="60"
export DQMC_SHERLOCK_REMOTE_ENV_JSON='{
  "DQMC_ALLOWED_ROOTS": "/one/explicit/allowed/run/root",
  "DQMC_OUTPUT_ROOT": "/absolute/path/to/DQMC_agent/outputs/sherlock-gateway",
  "DQMC_REGISTRY_PATH": "/absolute/path/to/DQMC_agent/registry.yaml",
  "DQMC_DEV_ROOT": "/absolute/path/to/dqmc-dev"
}'
```

MCP smoke：

```python
sherlock_query_slurm(filters={"me": True})
sherlock_query_slurm_history(filters={"me": True, "max_rows": 5})
sherlock_summarize_run(path="/allowed/run", max_files=1)
```

记录：

- 每次调用是否 60 秒内完成：
- gateway `ok`：
- remote tool `result.ok`：
- stdout/stderr tail：
- 字段形态是否需要补 fixture：

## 安全审计清单

- 本地代码审计：已执行。

- [x] 没有 `shell=True`。
- [x] 没有 `bash -lc`。
- [x] 没有用户可控 remote command。
- [x] 没有 `sbatch`、`scancel`、`scontrol update`。
- [x] 没有 `/scratch` 大目录扫描。
- [x] 没有真实写入动作。
- [x] 远端 env 只允许明确白名单变量。
