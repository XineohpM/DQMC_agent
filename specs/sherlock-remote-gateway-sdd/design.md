# Sherlock Remote Gateway SDD 技术设计

状态：第一版默认 status-only 设计已实现并通过本地测试、真实 Sherlock smoke 和 Slack/OpenACP 端到端 smoke。非默认 data-reading、path-discovery、script 和 sync profile 仍需单独设计/审批。

## 设计原则

1. 本地 Codex 是唯一 agent 大脑；Sherlock 上不启动第二个 Codex。
2. Sherlock 上不常驻 MCP server；每次远端工具调用都是短命 SSH + Python。
3. 本地 gateway 和远端 entrypoint 都只提供白名单函数，不提供任意 shell。
4. 远端 stdin/stdout 协议只传 JSON；stdout 不允许混入 banner、debug log 或 traceback。
5. 默认 profile 是 status-only/path-redacted：只查 SLURM 状态，不返回 Sherlock 上的真实 run/data path。
6. `DQMC_DEV_ROOT`、`DQMC_ALLOWED_ROOTS`、`DQMC_OUTPUT_ROOT`、`DQMC_REGISTRY_PATH` 不注入默认 status-only profile；只在单独 data/script profile 中使用。
7. 第一版只读，避免把远端执行和 `sbatch`、sync、真实脚本执行混在一起。

## 总体架构

```text
Slack / OpenACP
  -> 本地 Codex session
  -> 本地 MCP: dqmc-sherlock-gateway
  -> dqmc_tools.remote_gateway.call_sherlock_tool(...)
  -> ssh argv list
  -> Sherlock: python -m dqmc_tools.remote_call --cwd /absolute/path/to/DQMC_agent
  -> remote_call 调用白名单 dqmc_tools 函数
  -> JSON stdout
  -> 本地 gateway 包装 redacted remote provenance
  -> Codex 回复 Slack
```

2026-05-28 实际验证：本地 Codex/OpenACP 配置已注册 `dqmc-sherlock-gateway`
status-only profile，Slack 新 session 可以通过该链路查询 Sherlock SLURM 状态。Sherlock
端没有常驻 agent；每次查询只产生短 SSH 和短命远端 Python 调用。

这条链路和 `dqmc-hands` 的关系：

- `dqmc-hands`：本地直接操作本机文件、registry、dqmc-dev、SLURM 环境。
- `dqmc-sherlock-gateway`：本地 MCP，但每个工具通过 SSH 调 Sherlock 上的 `dqmc_tools`。
- 二者共享同一套底层 Python 包和错误模型。

## 模块边界

新增文件：

- `dqmc_tools/remote_call.py`
  - 远端短命 CLI。
  - 读取 stdin JSON。
  - 校验白名单 tool。
  - 设置允许的 env。
  - 调用已有 Python 函数。
  - stdout 打印 JSON。

- `dqmc_tools/remote_gateway.py`
  - 本地 SSH gateway helper。
  - 读取/校验 gateway 配置。
  - 构造 SSH argv list。
  - 调用 subprocess。
  - 解析 JSON 输出。
  - 包装 provenance。

- `dqmc_sherlock_gateway_mcp_server.py`
  - 独立 MCP server。
  - 注册 `sherlock_*` tools。
  - 每个 tool 只转发到 `remote_gateway.call_sherlock_tool`。

新增测试：

- `tests/test_remote_call.py`
  - 覆盖 remote CLI 和 dispatcher。

- `tests/test_remote_gateway.py`
  - 覆盖 config、command builder、subprocess success/error。

- `tests/test_sherlock_gateway_mcp_server.py`
  - 覆盖 MCP tool set 和 contract。

新增 SDD 文档：

- `specs/sherlock-remote-gateway-sdd/requirements.md`
- `specs/sherlock-remote-gateway-sdd/design.md`
- `specs/sherlock-remote-gateway-sdd/tasks.md`
- `specs/sherlock-remote-gateway-sdd/verification.md`

## Remote JSON 协议

本地 gateway 发送到远端 stdin：

```json
{
  "tool": "query_slurm",
  "args": {
    "filters": {"me": true}
  },
  "env": {}
}
```

默认 status-only profile 的 `env` 必须为空或只包含非数据读取所需的安全变量。不得注入
`DQMC_DEV_ROOT`、`DQMC_ALLOWED_ROOTS`、`DQMC_OUTPUT_ROOT`、`DQMC_REGISTRY_PATH`。
这些变量只允许出现在单独审批的 data-reading/script profile 中。

远端 stdout：

```json
{
  "ok": true,
  "source": "squeue_json",
  "command": ["squeue", "--json", "--me"],
  "jobs": [],
  "summary": {...}
}
```

远端错误仍沿用 `error_dict`：

```json
{
  "ok": false,
  "error_type": "invalid_argument",
  "message": "...",
  "details": {...}
}
```

本地 MCP gateway 成功包装：

```json
{
  "ok": true,
  "remote": {
    "host": "sherlock",
    "tool": "query_slurm"
  },
  "result": {
    "ok": true,
    "source": "squeue_json"
  }
}
```

默认 agent 可见响应不包含 Sherlock 远端 repo cwd。需要调试 cwd 时，使用 redacted
value 或本地私有日志。

如果 SSH/gateway 层失败，直接返回 gateway error，不伪装成远端 tool result。

## 配置设计

`dqmc_tools.remote_gateway.SherlockGatewayConfig` 使用环境或显式参数构造：

```python
SherlockGatewayConfig(
    remote_host="sherlock",
    allowed_hosts=["sherlock"],
    remote_python="<REDACTED_DQMC_AGENT_ON_SHERLOCK>/.venv/bin/python",
    remote_cwd="/home/user/DQMC_agent",
    timeout_seconds=60,
    remote_env={},
)
```

环境变量：

- `DQMC_SHERLOCK_REMOTE_HOST`
- `DQMC_SHERLOCK_ALLOWED_HOSTS`
- `DQMC_SHERLOCK_REMOTE_PYTHON`
- `DQMC_SHERLOCK_REMOTE_CWD`
- `DQMC_SHERLOCK_TIMEOUT_SECONDS`
- `DQMC_SHERLOCK_REMOTE_ENV_JSON`

默认值只允许非危险默认：

- host 默认 `sherlock`。
- allowed hosts 默认只包含 host。
- remote python 在真实 Sherlock gateway 配置中使用绝对路径；不要依赖相对 `.venv/bin/python`。
- timeout 默认 60。
- remote cwd 必须显式配置；缺失返回 `configuration_error`。
- remote env 默认空；数据读取、script adapter、artifact sync 相关 env 不属于 status-only profile。

## SSH 命令设计

命令 argv：

```python
[
    "/usr/bin/ssh",
    "sherlock",
    "<REDACTED_DQMC_AGENT_ON_SHERLOCK>/.venv/bin/python",
    "-m",
    "dqmc_tools.remote_call",
    "--cwd",
    "/home/user/DQMC_agent",
]
```

不使用：

- `shell=True`
- `bash -lc`
- 用户传入的 raw SSH args
- 用户传入的 remote command

第一版不强制 `BatchMode=yes`，因为不同 Sherlock SSH 配置可能不同；如需要可在后续 spec 中增加固定安全 SSH options。当前调用必须用 timeout 防止阻塞。

## Tool Mapping

本地 MCP tool 到远端 tool 映射：

| MCP tool | Remote tool | 说明 |
| --- | --- | --- |
| `sherlock_query_slurm` | `query_slurm` | 当前队列，只读；gateway wrapper 增加 `formatted_summary` 作为默认用户展示文本 |
| `sherlock_query_slurm_history` | `query_slurm_history` | 历史队列，只读 |
| `sherlock_get_slurm_job_detail` | `get_slurm_job_detail` | job detail，只读；应增加 `formatted_detail` 作为默认用户展示文本 |
| `sherlock_summarize_run` | `summarize_run` | 已实现，非默认 data-reading profile |

默认 status-only profile 只暴露前三个 status tools。`sherlock_summarize_run` 已经实现，
但不作为默认 Sherlock/Slack status profile 暴露。

`infer_slurm_path_candidates` 第一版暂不暴露成 remote MCP tool。它会处理并返回 Sherlock
真实路径候选，因此只能放入单独 path-discovery profile；默认 status 查询不启用。

## Path Redaction

默认 gateway status response 必须移除或脱敏以下字段，无论它们位于顶层 row、
detail candidate 还是 `raw` 中：

- `work_dir`
- `stdout_path`
- `stderr_path`
- `standard_output`
- `standard_error`
- `standard_input`
- `current_working_directory`
- `std_out`
- `std_err`
- `submit_line`
- raw SLURM `command` / batch script fields that may carry submit script paths
- `WorkDir`
- 任何明显的 stdout/stderr/run/output path 等同字段

redaction 后的 payload 仍应保留 job id、job name、state、partition、elapsed、time limit、
node/reason、summary 和 grouping，足够回答 Slack 中的状态问题。

## User-Facing Formatting

`sherlock_query_slurm` 已返回顶层 `formatted_summary`，Slack/OpenACP 默认应直接展示该字段。
同样，`sherlock_get_slurm_job_detail` 需要提供顶层 `formatted_detail` 或等价字段，避免
agent 在面对大型 array parent detail 时自行追加 direct SSH 或定制 `squeue` 命令。

detail formatter 的输入只能是已经 path-redacted 的 structured candidates；输出保持英文，
并覆盖：

- array parent 多候选：显示 parent id、job name、候选/子任务数量、状态计数和必要的样例 task id。
- 具体 `parent_task`：显示 job/task id、job name、state/category、partition、elapsed、time limit、nodes 或 reason。
- completed task step group：说明返回的是 task-level step group，列出 step 数量、states 和 exit codes，不猜唯一 step row。
- 查无结果或远端错误：输出稳定英文错误/空结果消息。

如果 formatter 缺少字段，修复位置是 gateway formatter 或远端 structured result，不是
Slack/OpenACP agent 侧的任意 shell fallback。

## 错误模型

Gateway 层 structured errors：

- `configuration_error`
  - 缺少 remote cwd、remote env JSON 非 object、timeout 无效。
- `invalid_argument`
  - host 不在 allowlist、tool 不在 gateway allowlist、remote cwd 不是绝对 POSIX 路径。
- `tool_unavailable`
  - 本地 `ssh` 不存在、SSH OSError、timeout。
- `script_registry_error`
  - SSH returncode 非 0、stdout 不是 JSON、远端 stdout JSON 不是 object。

远端 tool 自身错误直接作为 `result` 返回，保留远端 tool 的 `ok=false`。例如 Sherlock 上没有 `sacct` 时：

```json
{
  "ok": true,
  "remote": {...},
  "result": {
    "ok": false,
    "error_type": "tool_unavailable",
    "details": {"command": "sacct"}
  }
}
```

这样 agent 能区分“SSH/gateway 坏了”和“远端工具正常返回了业务错误”。

## Testing Strategy

本地测试不依赖真实 SSH：

- monkeypatch `shutil.which("ssh")`。
- monkeypatch `subprocess.run` 返回 fixed stdout/stderr/returncode。
- monkeypatch remote_call dispatcher 内部函数，避免调用真实 `squeue`。
- MCP tests monkeypatch `dqmc_tools.remote_gateway.call_sherlock_tool`。

真实 Sherlock smoke 只在本地测试通过后做：

1. 按 handoff 配置 Sherlock repo 和 `.venv`。
2. 直接在 Sherlock 上运行 `python -m dqmc_tools.remote_call` 的 stdin JSON smoke。
3. 从本地 gateway 调 `sherlock_query_slurm(filters={"me": true})`。
4. 调 `sherlock_query_slurm_history` 和 `sherlock_get_slurm_job_detail`。
5. 确认返回结果 path-redacted，不包含 `WorkDir`、stdout/stderr path、真实 run path 或 raw path fields。
6. 记录 source、summary、字段形态和错误；所有真实路径、用户名、project 名称必须先脱敏。

2026-05-28 默认 status-only smoke 已完成：

- 手写 SSH + `remote_call` 的 `query_slurm(filters={"me": true})` 返回 `ok=true`。
- 本地 gateway 的 `sherlock_query_slurm`、`sherlock_query_slurm_history`、`sherlock_get_slurm_job_detail` 均可在 60 秒内返回 JSON。
- 三个默认 status tools 的 response path redaction check 通过。
- 本地 Codex/OpenACP 实际配置使用 status-only profile 和空远端 env JSON。
- Slack/OpenACP 新会话可查询 Sherlock SLURM 状态。

## Future Work

后续可以单独扩展：

- `sherlock_healthcheck`：返回 remote commit、Python、env、tool version。
- `sherlock_infer_path_candidates`：仅在单独 path-discovery profile 中判断路径可访问性。
- `sherlock_describe_script_adapter`：远端 dry-run 前查看 script schema。
- `sherlock_run_script_adapter_dry_run`：只做 dry-run/preflight。
- `sherlock_summarize_run` data-reading profile：默认关闭，必须单独审批和记录。
- 真实远端 script execution：必须另起 SDD，带审批和 provenance。
- 受限 `sbatch`：必须另起高风险 SDD。
