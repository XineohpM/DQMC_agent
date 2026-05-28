# Sherlock Remote Gateway SDD 技术设计

状态：第一版设计。本地优先开发，真实 Sherlock 只做 smoke 和字段确认。

## 设计原则

1. 本地 Codex 是唯一 agent 大脑；Sherlock 上不启动第二个 Codex。
2. Sherlock 上不常驻 MCP server；每次远端工具调用都是短命 SSH + Python。
3. 本地 gateway 和远端 entrypoint 都只提供白名单函数，不提供任意 shell。
4. 远端 stdin/stdout 协议只传 JSON；stdout 不允许混入 banner、debug log 或 traceback。
5. 所有路径边界继续复用现有 `dqmc_tools` 的 allowed roots / output root 机制。
6. 第一版只读，避免把远端执行和 `sbatch`、sync、真实脚本执行混在一起。

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
  -> 本地 gateway 包装 remote provenance
  -> Codex 回复 Slack
```

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
  "env": {
    "DQMC_ALLOWED_ROOTS": "/oak/users/example/run",
    "DQMC_OUTPUT_ROOT": "/home/example/DQMC_agent/outputs/sherlock-gateway",
    "DQMC_REGISTRY_PATH": "/home/example/DQMC_agent/registry.yaml",
    "DQMC_DEV_ROOT": "/home/example/dqmc-dev"
  }
}
```

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
    "cwd": "/home/example/DQMC_agent",
    "tool": "query_slurm"
  },
  "result": {
    "ok": true,
    "source": "squeue_json"
  }
}
```

如果 SSH/gateway 层失败，直接返回 gateway error，不伪装成远端 tool result。

## 配置设计

`dqmc_tools.remote_gateway.SherlockGatewayConfig` 使用环境或显式参数构造：

```python
SherlockGatewayConfig(
    remote_host="sherlock",
    allowed_hosts=["sherlock"],
    remote_python=".venv/bin/python",
    remote_cwd="/home/user/DQMC_agent",
    timeout_seconds=60,
    remote_env={
        "DQMC_ALLOWED_ROOTS": "/oak/user/run",
        "DQMC_OUTPUT_ROOT": "/home/user/DQMC_agent/outputs/sherlock-gateway",
        "DQMC_REGISTRY_PATH": "/home/user/DQMC_agent/registry.yaml",
        "DQMC_DEV_ROOT": "/home/user/dqmc-dev",
    },
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
- remote python 默认 `.venv/bin/python`。
- timeout 默认 60。
- remote cwd 必须显式配置；缺失返回 `configuration_error`。

## SSH 命令设计

命令 argv：

```python
[
    "/usr/bin/ssh",
    "sherlock",
    ".venv/bin/python",
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
| `sherlock_query_slurm` | `query_slurm` | 当前队列，只读 |
| `sherlock_query_slurm_history` | `query_slurm_history` | 历史队列，只读 |
| `sherlock_get_slurm_job_detail` | `get_slurm_job_detail` | job detail，只读 |
| `sherlock_summarize_run` | `summarize_run` | bounded run summary，只读 |

`infer_slurm_path_candidates` 第一版暂不暴露成 remote MCP tool。原因：它是纯推断函数，本地已有工具可用；如果后续需要远端路径存在性或 allowed roots 语义完全由 Sherlock 判断，再补 `sherlock_infer_path_candidates`。

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
4. 记录 source、summary、字段形态和错误。

## Future Work

后续可以单独扩展：

- `sherlock_healthcheck`：返回 remote commit、Python、env、tool version。
- `sherlock_infer_path_candidates`：在远端判断路径可访问性。
- `sherlock_describe_script_adapter`：远端 dry-run 前查看 script schema。
- `sherlock_run_script_adapter_dry_run`：只做 dry-run/preflight。
- 真实远端 script execution：必须另起 SDD，带审批和 provenance。
- 受限 `sbatch`：必须另起高风险 SDD。
