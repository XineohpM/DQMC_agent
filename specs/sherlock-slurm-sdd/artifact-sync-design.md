# Sherlock Artifact Sync Design

状态：设计草案。本文只定义后续实现边界，不表示已经实现同步能力。

## 目标

在本地 agent 需要读取 Sherlock 上的 run/output 产物时，提供一个受限同步能力，把用户明确指定的远端路径同步到本地 `DQMC_OUTPUT_ROOT` 下，并返回 dry-run 或真实同步 manifest。

本设计不属于默认 Sherlock/Slack status profile。默认 status 查询只返回 path-redacted SLURM 状态，不主动发现、展示或同步 Sherlock 实际 run/output path。只有用户明确要求处理具体远端产物时，才进入本 data-transfer profile。

## 非目标

- 不提供任意 shell 命令入口。
- 不支持 `rsync --delete`、远端通配符、远端命令拼接或任意 rsync 参数。
- 不自动扫描 Sherlock 大目录寻找候选 run。
- 不绕过 `infer_slurm_path_candidates`、用户显式路径或 allowed roots 边界。
- 不把同步和 `sbatch` 提交混在同一个工具里。
- 不作为 `dqmc status` / `dqmc jobs` / 默认 Sherlock job detail 的自动后续动作。
- 不把真实 remote path 写入 agent 可见长期记录；需要记录时先脱敏。

## 工具边界

建议新增 MCP tool：`sync_sherlock_artifacts`。

建议 Python API：

```python
def sync_sherlock_artifacts(
    *,
    remote_host: str,
    remote_path: str,
    remote_allowed_hosts: list[str],
    remote_allowed_roots: list[str],
    local_subdir: str | None = None,
    output_root: str | None = None,
    dry_run: bool = True,
    user_confirmation: dict[str, Any] | None = None,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    ...
```

参数约束：

- `remote_host` 必须是 `remote_allowed_hosts` 中的 exact allowlist value；第一版不从用户输入拼接 SSH options。
- `remote_path` 是远端 POSIX 绝对路径，必须落在 `remote_allowed_roots` 之一下面。
- `remote_path` 和 `remote_allowed_roots` 用 `PurePosixPath` 做 lexical normalization；拒绝空路径、相对路径、`..` segment、NUL 字符和明显 shell metacharacter。
- `local_subdir` 是相对路径；最终 destination 必须在 `output_root` 内。
- `output_root` 默认复用现有 `DQMC_OUTPUT_ROOT`。
- `dry_run=False` 必须有 `user_confirmation={"approved": true, "text": "..."}`。

## 命令构造

第一版底层使用 `rsync`，只生成 argv list，不使用 shell string。

dry-run 命令形态：

```python
[
    "rsync",
    "--archive",
    "--itemize-changes",
    "--human-readable",
    "--dry-run",
    "--protect-args",
    f"{remote_host}:{remote_path.rstrip('/')}/",
    str(destination),
]
```

真实同步移除 `--dry-run`，其余参数保持一致。第一版不支持用户传入 raw rsync args。`include_patterns` 和 `exclude_patterns` 后续若实现，只允许普通相对 glob fragment，不允许以 `/` 开头、不允许 `..`，并转换为成对的 `--include` / `--exclude` argv 元素。

## Manifest Schema

返回结构：

```python
{
    "ok": True,
    "dry_run": True,
    "command": [...],
    "remote": {
        "host": "...",
        "path": "/oak/...",
    },
    "destination": "/local/output/...",
    "user_confirmation": {
        "approved": False,
        "text": "",
    },
    "manifest": {
        "created": [...],
        "updated": [...],
        "deleted": [],
        "skipped": [...],
        "unknown": [...],
        "total_items": 0,
    },
    "stdout_tail": "...",
    "stderr_tail": "...",
    "warnings": [],
}
```

Manifest items：

```python
{
    "path": "relative/path/from/destination",
    "change": "created" | "updated" | "skipped" | "unknown",
    "itemize": ">f+++++++++",
}
```

`deleted` 第一版固定为空，因为不支持 `--delete`。如果 rsync itemize 行无法稳定解析，放入 `unknown`，不让 parser 猜测。

## 错误模型

- remote host 不在 allowlist：`invalid_argument`。
- remote path 不在 allowlist：`path_not_allowed` 或 `invalid_argument`；实现时应保持 JSON-safe details。
- local destination 越过 output root：`path_not_allowed`。
- `rsync` 不存在：`tool_unavailable`。
- `dry_run=False` 且无审批：`user_approval_required`。
- rsync nonzero exit：structured tool error，包含 command、returncode、stdout_tail、stderr_tail。
- timeout：structured timeout error。

## 与现有 SLURM 工具的关系

推荐 agent workflow：

1. 用户询问 job 或 run 产物。
2. 如果用户只问任务状态，停留在 path-redacted status workflow，不进入同步。
3. 如果用户明确要求处理具体产物，可在单独 path-discovery/data-transfer profile 中调用 `get_slurm_job_detail(job_id)` 获取 candidates。
4. 在用户批准 path discovery 后，调用 `infer_slurm_path_candidates(job_detail, allowed_roots=...)` 推断远端 run/output path candidates。
5. 用户确认具体远端路径后，先调用 `sync_sherlock_artifacts(..., dry_run=True)`。
6. 展示 dry-run manifest，用户逐次审批。
7. 审批后调用真实同步。
8. 对本地 destination 调用 `summarize_run` 或 HDF5 tools。

## 测试计划

实现前先补以下测试：

- remote path lexical normalization：接受 allowlist 内绝对路径，拒绝相对路径、`..`、空路径。
- remote allowlist：allowlist 外路径返回 structured error。
- local destination：output root 内通过，output root 外拒绝。
- approval：`dry_run=False` 无审批返回 `user_approval_required`。
- rsync unavailable：返回 `tool_unavailable`。
- command builder：dry-run 包含 `--dry-run`，真实执行不包含。
- manifest parser：覆盖 created、updated、skipped、unknown itemize lines。
- MCP contract：固定 success/error JSON schema。
- small fixture dry-run：用 monkeypatched subprocess 输出，不依赖真实 Sherlock 网络。

真实 Sherlock 验证只在本地测试通过、用户明确进入 data-transfer profile 后做，并且只对小目录先 dry-run。
