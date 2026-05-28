# Sherlock SLURM SDD 技术设计

状态：默认 status-only 查询链路已实现并通过真实 gateway/Slack smoke；后续仍需 fixture 回流和非默认 profile 验证。

## 设计原则

1. MCP hands 返回事实、schema 和 provenance；状态解释由 agent 层完成。
2. 代码开发不依赖 Sherlock；真实环境只用于 smoke、字段确认和 fixture 回流。
3. 所有 SLURM 命令默认只读，子进程调用使用 argv list。
4. parser 先 normalize SLURM 输出为稳定 facts，再生成 summary、detail 和 presenter 文本。
5. 默认 Sherlock/Slack status profile 必须 path-redacted：不返回真实 `WorkDir`、stdout/stderr path、run path、output path 或 raw path fields。
6. 数据读取、path discovery、artifact sync 和 script adapter 不属于默认 status profile；如需启用必须单独审批。

## 两条执行轨道

### 本地开发轨道

本地负责：

- public API、MCP tool name、filters、返回 schema 和 structured error。
- command builder、parser、normalization helper。
- fixture-based unit tests。
- MCP contract tests。
- agent/status presenter pure function；默认给用户的 SLURM 状态摘要必须使用英文固定表格格式。

每次真实 Sherlock 输出暴露新字段形态时，先脱敏保存成 fixture，再补本地测试和 parser 兼容。

### Sherlock 验证轨道

Sherlock 负责：

- 确认远端仓库分支和 commit 与本地一致。
- 运行真实 `squeue`、`sacct` 或 MCP smoke。
- 记录字段形态、missing/extra fields、array job 表达方式。
- 默认 status-only 验证不设置 `DQMC_DEV_ROOT`、`DQMC_ALLOWED_ROOTS`、`DQMC_OUTPUT_ROOT`、`DQMC_REGISTRY_PATH`。
- 路径可用性、数据读取和脚本环境验证只在单独 profile 中进行。
- 对真实输出脱敏后回流为本地 fixture。
- 本地 gateway 配置中，`DQMC_SHERLOCK_REMOTE_PYTHON` 使用 Sherlock 上 venv Python 的绝对路径；`DQMC_SHERLOCK_REMOTE_CWD` 只作为本地私有配置，不出现在 agent 可见响应中。
- 2026-05-28 status-only gateway smoke 已验证：`query_slurm`、`query_slurm_history`、`get_slurm_job_detail` 均可通过短 SSH 返回 JSON，且返回 payload 不含敏感路径字段。
- 2026-05-28 Slack/OpenACP 新 session 已验证可通过本地 gateway 查询 Sherlock SLURM 状态；这是 transport 层端到端验证，不改变 MCP hands 的模块边界。

## 模块边界

现有实现：

- `dqmc_tools/slurm.py`：当前只读 `squeue` 查询、fallback parser、summary/grouping、SLURM wrapped field normalization。
- `dqmc_mcp_server.py`：薄 MCP adapter，注册 `query_slurm` 并转发。
- `tests/test_slurm.py`：本地 parser、command builder、fallback、wrapped field fixture。

后续建议新增或扩展：

- `dqmc_tools/slurm.py`：继续承载 `query_slurm_history`、共享 normalization/fact helper、`get_slurm_job_detail` 的底层逻辑，直到文件明显过大再拆。
- `dqmc_tools/slurm_presenter.py`：纯 presenter，输入 normalized `query_slurm` payload，输出英文固定表格摘要。表格列为 `Job Name`、`Array Job ID`、`Total`、`Pending`、`Running`；非 array job 的 `Array Job ID` 显示其自身 job id。
- `tests/test_slurm_history.py` 或继续扩展 `tests/test_slurm.py`：覆盖 `sacct` command builder、parser、unavailable、timeout、bad filter。
- `tests/test_slurm_presenter.py`：覆盖空队列、error、running/pending/held_blocked、array summary，以及 `CG`/`CF` 计入 `Running`。
- `tests/test_mcp_contracts.py`：新增 MCP success/error contract。

## SLURM 字段 normalization

真实 `squeue --json` 可能返回 wrapped fields：

- list：`job_state: ["PENDING"]`
- dict：`array_job_id: {"set": true, "infinite": false, "number": 24884301}`
- unset dict：`array_task_id: {"set": false, ...}`

当前 `query_slurm` 使用这些 helper：

- `_slurm_scalar(value)`：从 list/dict/scalar 中提取可用 scalar。
- `_slurm_text(value)`：提取 scalar 后转成 stripped string。
- `_has_slurm_value(value)`：过滤 `None`、空字符串、`N/A`、`NONE`。

后续设计要求：

- `query_slurm_history` 如果遇到 wrapped 或 multi-value 字段，也必须先 normalize。
- `get_slurm_job_detail` 基于 normalized facts 构造 candidates。
- presenter 不直接解释 raw rows；raw rows 只作为 provenance。
- 不在多个位置重复 `str(value)` 解析 SLURM 字段。
- 用户可见 SLURM presenter/monitor 文本保持英文，避免 Slack/OpenACP 真实用户场景里返回中文状态消息。

## `query_slurm_history`

命令：

- 优先 `sacct --parsable2 --noheader`。
- 字段白名单建议：默认 status profile 使用不含 `WorkDir` 的字段；path-discovery profile 才允许查询 `WorkDir`。
- filters 映射为 argv list，不使用 shell string。

返回结构：

```python
{
    "ok": True,
    "source": "sacct_parsable2",
    "command": [...],
    "jobs": [...],
    "summary": {
        "state_counts": {...},
        "exit_code_counts": {...},
    },
    "warnings": [...],
}
```

错误：

- `sacct` 不存在：`tool_unavailable`。
- bad filter：`invalid_argument`。
- timeout：structured timeout error。
- 某些字段不可用：warning，不让工具失败。

## `get_slurm_job_detail`

查询顺序：

1. `query_slurm({"job_id": job_id})`
2. 如果没有当前队列结果且 `include_history=true`，调用 `query_slurm_history({"job_id": job_id})`

candidate schema：

```python
{
    "job_id": "...",
    "job_name": "...",
    "state": "...",
    "category": "...",
    "partition": "...",
    "elapsed": "...",
    "time_limit": "...",
    "node_or_reason": "...",
    "submit": "...",
    "start": "...",
    "end": "...",
    "work_dir": "...",
    "stdout_path": "...",
    "stderr_path": "...",
    "raw": {...},
}
```

多个候选必须返回 candidates，不猜。查不到 job 时返回稳定空结构。

默认 Sherlock gateway/status profile 应返回 redacted candidate schema，移除或脱敏：

- `work_dir`
- `stdout_path`
- `stderr_path`
- `standard_output`
- `standard_error`
- `raw` 中同类 path fields

## Job 到 run/output path 关联

该能力不属于默认 Sherlock/Slack status profile。第一版只做候选推断，不做大目录扫描。

候选信息源：

- `sacct WorkDir`
- stdout/stderr 文件路径的 parent
- submit cwd
- job name
- 后续脚本执行 provenance
- 用户显式提供的 run path

返回每个 candidate 时必须包含 evidence：

```python
{
    "path": "...",
    "confidence": "high" | "medium" | "low",
    "evidence": "sacct.WorkDir",
    "accessible": True,
}
```

路径必须通过 allowed roots 检查。越界路径拒绝或标记不可访问。

在 Sherlock 场景中，`infer_slurm_path_candidates` 只能放入单独 path-discovery profile。
普通 status 查询不得主动调用它，也不得把候选 path 返回给 agent。

## 产物同步

同步能力需要单独 design doc 后再实现。当前设计文档：

- `artifact-sync-design.md`

原则：

- 先 dry-run。
- 远端 source 必须在 allowlist 内。
- 本地 destination 必须在 output root 内。
- 真实同步必须逐次审批。
- 返回 manifest，包含新增/更新/跳过文件、大小、mtime、命令和源/目标。

同步不属于默认 Sherlock/Slack status profile。如果 agent 和 MCP hands 都跑在 Sherlock，
也不应默认直接用远端文件工具；只有用户明确要求读取数据时才进入 data-reading profile。

## 后处理脚本执行

Sherlock 上复用现有 `run_script_adapter`：

- `DQMC_DEV_ROOT` 指向 Sherlock 上的 `dqmc-dev` checkout。
- `describe_script_adapter` 和 dry-run 用于 preflight。
- 真实执行必须传入 `user_confirmation`。
- 输出写入 Sherlock 上的 `DQMC_OUTPUT_ROOT`。

该能力不属于默认 Sherlock/Slack status profile。默认 status 环境不设置 `DQMC_DEV_ROOT`
或 `DQMC_OUTPUT_ROOT`。

## 周期性状态查询

周期性查询由 agent 层实现，不在 MCP hands 中做 daemon。当前 workflow 文档：

- `polling-workflow.md`

MCP hands 只提供单次 `query_slurm` snapshot；agent 保存 previous/current snapshots，并使用纯 helper 比较新增、消失和 state 改变。

## 受限 `sbatch`

`sbatch` 不在第一轮实现中。后续单独设计时必须满足：

- 只允许白名单模板。
- 不支持任意 shell。
- 不支持任意资源参数。
- dry-run 展示 job script、cwd、资源参数、读写路径。
- 用户逐次审批。
- 记录 provenance：用户意图、参数、job script、git hash、submit cwd、job id、output path。
- 不实现 cancel。
