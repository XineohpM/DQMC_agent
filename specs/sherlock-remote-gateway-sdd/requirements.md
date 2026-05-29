# Sherlock Remote Gateway SDD 需求规格

状态：第一版默认 status-only 路径已实现并完成真实 Sherlock/Slack smoke。目标是把本地 Slack/OpenACP -> 本地 Codex 链路安全接到 Sherlock 真实环境，同时避免 Sherlock login node 上长期运行 Codex 或长连接 MCP server。默认产品 profile 已收紧为 status-only/path-redacted：只查询 SLURM 状态，不让 agent 接触 Sherlock 上的真实 run/data path。

## 背景

当前项目已经有两条基础能力：

- 本地 Slack/OpenACP 后端可以把 Slack 对话接到本地 Codex session。
- `dqmc-hands` 已经提供本地 MCP tools，包括 SLURM 查询、历史查询、job detail、path candidates、run summary 和受限 artifact sync。

缺口是：当本地 Codex 需要查询 Sherlock 真实 `squeue` / `sacct` 时，目前要么需要用户手工登录 Sherlock，要么需要在 Sherlock 上启动长期 MCP/Codex。最新目标形态是不采用长期远端进程，而是在本地新增一个 Sherlock gateway MCP：每次远端工具调用通过 SSH 启动一个短命 Python entrypoint，执行白名单 `dqmc_tools` 函数，输出 JSON 后立即退出。

默认 gateway 不负责读取 Sherlock run summary、推断 run/output path、同步产物或执行脚本。这些能力如果后续需要，必须进入单独 data-reading/path-discovery profile，并重新审查审批、脱敏和路径边界。

2026-05-28 当前进展：本地用户级 Codex 配置已注册 `dqmc-sherlock-gateway`，使用 status-only profile、Sherlock 端绝对 Python 路径和空远端 env JSON；OpenACP 新 Slack session 已确认可通过该 gateway 查询 Sherlock SLURM 状态。

## 总目标

- 本地实现一个可测试、受限的 Sherlock remote gateway。
- Gateway 默认暴露少量 path-redacted `sherlock_*` status tools，供本地 Codex 按需调用。
- 每个 gateway tool 使用 argv list 调用 `ssh`，不拼 shell string。
- SSH 远端只执行固定 Python module：`python -m dqmc_tools.remote_call`。
- 工具名和参数通过 JSON stdin 传给远端 entrypoint。
- 远端 entrypoint 只允许白名单工具，返回 JSON-safe result 或 structured error。
- 每次调用有硬 timeout，默认 60 秒。
- 默认第一版只做只读 SLURM status 查询，不做 run summary、path discovery、真实写入、`sbatch` 或远端 Codex。

## In Scope

- 新增 `dqmc_tools.remote_call`：短命远端 CLI，读取 stdin JSON，调用白名单本地 Python 函数，stdout 只打印 JSON。
- 新增本地 gateway helper：校验 Sherlock host allowlist、远端 repo/python 路径、timeout、JSON 输出和错误模型。
- 新增独立 MCP server：`dqmc_sherlock_gateway_mcp_server.py`。
- 默认 status-only MCP tools：
  - `sherlock_query_slurm`
  - `sherlock_query_slurm_history`
  - `sherlock_get_slurm_job_detail`
- 已实现但不默认暴露的 data-reading tool：
  - `sherlock_summarize_run`
- 本地测试覆盖 remote CLI、SSH command builder、gateway 错误路径和 MCP contract。
- 文档记录 Sherlock smoke 步骤，但本地开发不依赖真实 Sherlock 网络。

## Out of Scope

- 不启动 Sherlock 上的长期 MCP server。
- 不启动 Sherlock 上的第二个 Codex agent。
- 不实现 MCP-over-SSH 长连接。
- 不暴露任意 shell、任意 SSH 命令或用户自定义远端命令。
- 第一版不实现 `sbatch`、`scancel`、`scontrol update`。
- 第一版不执行真实远端 `run_script_adapter(dry_run=false)`。
- 第一版不执行真实远端 artifact sync。
- 第一版不自动扫描 `/scratch` 或 Sherlock 大目录。
- 第一版不把 Slack user/channel/thread 传进 MCP hands。
- 默认 profile 不暴露 Sherlock run/output path，不返回 `WorkDir`、stdout/stderr path 或 raw path fields。
- 默认 profile 不注入 `DQMC_DEV_ROOT`、`DQMC_ALLOWED_ROOTS`、`DQMC_OUTPUT_ROOT`、`DQMC_REGISTRY_PATH`。

## 功能需求

### R1 配置

本地 gateway 使用环境变量配置远端执行环境：

- `DQMC_SHERLOCK_REMOTE_HOST`：默认远端 host，例如 `sherlock`。
- `DQMC_SHERLOCK_ALLOWED_HOSTS`：允许的 SSH host allowlist，path separator 分隔。
- `DQMC_SHERLOCK_REMOTE_PYTHON`：远端 Python 可执行文件。真实 Sherlock gateway 配置应使用绝对路径，例如 `<REDACTED_DQMC_AGENT_ON_SHERLOCK>/.venv/bin/python`；相对 `.venv/bin/python` 会在远端 `--cwd` 生效前解析，不能作为可靠配置。
- `DQMC_SHERLOCK_REMOTE_CWD`：远端 repo 工作目录，必须是绝对 POSIX 路径。
- `DQMC_SHERLOCK_TIMEOUT_SECONDS`：每次 SSH 调用 timeout，默认 60。
- `DQMC_SHERLOCK_REMOTE_ENV_JSON`：可选 JSON object，注入远端 entrypoint 环境。默认 status-only profile 应为空或省略；`DQMC_ALLOWED_ROOTS`、`DQMC_OUTPUT_ROOT`、`DQMC_DEV_ROOT`、`DQMC_REGISTRY_PATH` 只允许在单独 data/script profile 中使用。

配置错误必须返回 structured `configuration_error` 或 `invalid_argument`，不能退化为任意 shell 拼接。

### R2 本地 SSH gateway

Gateway helper 必须：

- 使用 `shutil.which("ssh")` 找到 SSH。
- 只允许 allowlist 内的 host。
- 只接受绝对 POSIX `remote_cwd`。
- 拒绝空 host、空 cwd、空 remote python、timeout 小于 1。
- 构造 argv list，不使用 `shell=True`。
- 使用 `ssh <host> <remote_python> -m dqmc_tools.remote_call --cwd <remote_cwd>` 形式。
- 通过 stdin 传 JSON payload。
- 使用 `subprocess.run(..., input=json_payload, timeout=timeout, capture_output=True, text=True, check=False)`。
- 解析 stdout 为 JSON；如果 stdout 不是 JSON，返回 structured error 并带 stdout/stderr tail。
- 非零 return code 返回 structured error。

### R3 远端 `remote_call` entrypoint

`dqmc_tools.remote_call` 必须：

- 从 stdin 读取一个 JSON object。
- payload schema：`{"tool": "...", "args": {...}, "env": {...}}`。
- 只允许白名单 tool：
  - `query_slurm`
  - `query_slurm_history`
  - `get_slurm_job_detail`
  - `summarize_run`
- 在调用前把 `env` 中允许的环境变量设置到当前进程，只允许 `DQMC_ALLOWED_ROOTS`、`DQMC_OUTPUT_ROOT`、`DQMC_REGISTRY_PATH`、`DQMC_DEV_ROOT`、`DQMC_SCRIPT_TIMEOUT_SECONDS`。
- 默认 status-only payload 不应携带这些数据/脚本环境变量；env allowlist 只是为了已实现的非默认 profile 和兼容测试保留。
- 调用现有 `dqmc_tools` 普通 Python 函数。
- 捕获 expected/unexpected exception，通过 `error_dict` 输出 JSON-safe structured error。
- stdout 只输出一段 JSON。

### R4 MCP tools

独立 MCP server `dqmc_sherlock_gateway_mcp_server.py` 默认 status-only profile 暴露：

- `sherlock_query_slurm(filters=None)`
  - 远端调用 `query_slurm`。
  - 用于查询 Sherlock 当前队列。
  - 返回结果必须移除或脱敏真实 path fields。
  - gateway wrapper 必须返回顶层 `formatted_summary`，由 `format_slurm_status_summary(result)` 生成。Slack/OpenACP 面向用户回复当前状态时必须直接输出该字段，不再自行重写摘要或运行 shell/SSH 压缩命令。

- `sherlock_query_slurm_history(filters=None)`
  - 远端调用 `query_slurm_history`。
  - 用于查询 Sherlock 历史任务。
  - 返回结果必须移除或脱敏 `work_dir` 和 `raw` 中的路径字段。

- `sherlock_get_slurm_job_detail(job_id, include_history=True)`
  - 远端调用 `get_slurm_job_detail`。
  - 用于查询 Sherlock job detail。
  - 返回结果必须移除或脱敏 `work_dir`、`stdout_path`、`stderr_path`、`standard_output`、`standard_error` 和 `raw` 中的同类字段。
  - 应提供顶层 `formatted_detail` 或等价字段，作为 Slack/OpenACP 默认 job detail 展示契约。
  - formatter 应基于 path-redacted structured candidates 生成英文摘要，覆盖 array parent 多候选、具体 array task、completed task step group 和查无结果。
  - Slack/OpenACP 不得为了补齐 compact detail 字段而运行 direct SSH、定制 `squeue`、`awk` pipeline 或其它 shell 命令；缺口应回到 gateway formatter/structured result 中修复。

- `sherlock_summarize_run(path, max_files=5, max_registry_entries=50, max_log_chars=1000, allowed_roots=None, registry_path=None)` 非默认 data-reading profile
  - 远端调用 `summarize_run`。
  - 已实现 bounded summary，但不属于默认 Sherlock/Slack status profile。
  - 启用前必须单独审批，并重新审查 allowed roots、响应脱敏和用户确认边界。

每个 MCP tool 返回远端 JSON result，并附带 gateway provenance：

```python
{
    "ok": True,
    "remote": {"host": "...", "tool": "..."},
    "result": {...},
}
```

默认 status-only profile 不应在 agent 可见响应中暴露 Sherlock 远端 repo cwd。调试需要 cwd 时，应使用本地私有日志或 redacted value。

如果 gateway 层失败，则返回：

```python
{
    "ok": False,
    "error_type": "...",
    "message": "...",
    "details": {...},
}
```

### R5 安全边界

- 不把用户输入拼进 shell string。
- 不允许用户选择任意 SSH host；host 必须 allowlist。
- 不允许用户传入远端命令。
- 默认 profile 不做远端 path 读取。
- 非默认 data-reading profile 的远端 path 读取必须继续受 `DQMC_ALLOWED_ROOTS` 或更严格的本地配置限制，并且不得由用户消息临时扩大。
- Gateway 不对 `/scratch` 做扫描、写入、删除、移动。
- Gateway 不运行 `sbatch`、`scancel`、`scontrol`。
- 第一版 gateway 不做真实写入动作。
- Gateway status responses 必须 path-redacted：不得返回 Sherlock `WorkDir`、stdout/stderr path、真实 run path、output path 或 raw path fields。

### R6 更新和部署边界

- 本地 gateway 和 Sherlock repo 上的 `dqmc_tools.remote_call` 必须版本兼容。
- Sherlock status-only smoke 前只需要完成 repo、venv、SSH、`squeue`、`sacct` 基线。`DQMC_DEV_ROOT`、`DQMC_ALLOWED_ROOTS`、`DQMC_OUTPUT_ROOT`、`DQMC_REGISTRY_PATH` 只属于非默认 data/script profile。
- 后续可以新增 `sherlock_healthcheck` 查询远端 commit/env，但第一版不要求。

## 验收标准

- [x] 本地测试能验证 remote CLI 白名单、JSON stdin/stdout、structured error。
- [x] 本地测试能验证 SSH argv builder 不使用 shell string。
- [x] 本地测试能验证 SSH unavailable、timeout、nonzero exit、invalid JSON 输出。
- [x] MCP contract tests 覆盖默认 status tools，并保留已实现 `sherlock_summarize_run` 的非默认 contract。
- [x] Sherlock smoke 验证 status tools 返回 JSON 且不暴露真实 path fields。
- [x] README 或 usage 文档说明 gateway 与 Slack/OpenACP、本地 `dqmc-hands`、Sherlock handoff 的关系。
- [x] 不新增任何 submit/cancel/mutate SLURM 能力。
- [x] Slack/OpenACP 新 session 端到端查询 Sherlock SLURM 状态通过。
