# Sherlock Validation Handoff

状态：交接/runbook。面向即将在 Sherlock 工作区 repo 中启动的 Codex 实例。

本文目标是给 Sherlock 上的新 Codex 提供足够上下文：项目是什么、已经演进到哪里、哪些能力已经本地实现、Sherlock 最后一公里要完成什么、如何验证、哪些安全边界绝不能越过、遇到常见错误时如何处理。

## Architecture Update：这份文档现在的定位

最新产品方向已经从“长期在 Sherlock 上挂一个远端 MCP server”调整为：

```text
Slack / OpenACP
  -> 本地 Codex
  -> 本地 Sherlock gateway MCP
  -> 按需 SSH 到 Sherlock
  -> 远端短命 Python 调用 dqmc_tools
  -> 返回 JSON 后立即断开
```

也就是说，最终更推荐的产品形态不是让 Sherlock login node 长期运行 `dqmc_mcp_server.py`，也不是让本地 Codex 把消息转发给 Sherlock 上另一个 Codex。最终方向是：本地只有一个 agent 大脑；Sherlock 只在需要时通过短 SSH 会话执行受控工具函数。

因此本文档的定位也随之调整：

- 它仍然有用，但不再是“最终长连接 Sherlock MCP 部署说明”。
- 它现在是 Sherlock 环境验收、真实字段观察、远端短命调用前置验证的 runbook。
- 文中提到的“在 Sherlock 上启动 Codex/MCP”只作为人工验证形态。默认验证只确认 repo、`.venv`、`squeue`、`sacct` 和 status-only 工具面可用。
- 产品化落地应另写 `sherlock-remote-gateway` spec：本地 MCP gateway 按需 SSH，远端进程必须短命、受 timeout 限制、只执行白名单 Python entrypoint。

后续 Sherlock 验证仍应按本文的安全规则执行。默认 Sherlock/Slack profile 是
status-only/path-redacted：只查询 SLURM 状态，不让 agent 接触 Sherlock 上的真实
run/data path。`DQMC_DEV_ROOT`、`DQMC_ALLOWED_ROOTS`、`DQMC_OUTPUT_ROOT`、
`DQMC_REGISTRY_PATH` 默认不在 Sherlock status-only profile 中设置；只有进入单独
data-reading/path-discovery/script profile 时才允许配置。

## 最重要的安全要求

Sherlock 上的文件可能包含重要模拟产物。尤其是任何 `/scratch` 路径下的文件和目录，都必须默认视为重要且不可破坏。

严格遵守：

- 不运行 `rm -rf`、`git reset --hard`、`git clean -fdx`、`find ... -delete`、`rsync --delete`、`mv` 覆盖目录、批量 chmod/chown 等破坏性命令。
- 不对 `/scratch` 下的任何现有目录做删除、移动、覆盖、清空或递归写入。
- 默认 status-only profile 不设置 `DQMC_OUTPUT_ROOT` 或 `DQMC_ALLOWED_ROOTS`。
- 如果用户明确批准进入 data-reading/path-discovery/script profile，不把 `DQMC_OUTPUT_ROOT` 指向已有的重要 run/output 目录。需要写文件时，只使用新建的、明确命名的专用目录，例如 repo 内 `outputs/sherlock-validation/`，或用户明确批准的新目录。
- 如果用户明确批准进入 data-reading/path-discovery profile，不把 `DQMC_ALLOWED_ROOTS` 粗暴设成整个 `/scratch`。只允许设成当前要验证的少数明确 run/output 根目录。
- 不运行 `scancel`、`scontrol update`、`sbatch` 或任何会改变 SLURM 状态的命令。本轮只读验证为主。
- 不运行任意 shell 拼接命令。项目代码中所有 SLURM/rsync 调用都应使用 argv list。
- `sync_sherlock_artifacts` 不属于默认 status-only profile；真实同步前必须 dry-run，并需要明确 `user_confirmation`。
- 任何测试或 smoke 如果会写输出，必须先确认已经进入对应非默认 profile，且输出位置在专用 output root 内。
- 默认 status 响应必须 path-redacted：不得返回真实 `WorkDir`、stdout/stderr path、run path、output path 或 raw path fields。
- 如果 git 工作区有用户改动，不要还原；先读 diff，无法判断时停下来问用户。

## 项目全局功能总览

本 repo 是 DQMC agent 的“手”层实现：`dqmc_tools/` 是普通 Python 包，`dqmc_mcp_server.py` 是薄 MCP adapter。工具层只返回事实、路径、schema、provenance 和 structured errors，不做物理可靠性判断，不替用户修改集群任务。

完整本地 `dqmc-hands` MCP tool 面：

- `summarize_run`
- `inspect_hdf5`
- `read_dataset`
- `resolve_registry_entry`
- `read_registered_quantity`
- `estimate_registered_observable`
- `list_script_adapters`
- `describe_script_adapter`
- `run_script_adapter`
- `query_slurm`
- `query_slurm_history`
- `get_slurm_job_detail`
- `infer_slurm_path_candidates`
- `sync_sherlock_artifacts`

核心能力：

- 明确路径的 DQMC run/HDF5 摘要与 dataset 读取。
- 通过 `registry.yaml` 解析 observable/parameter。
- 复用 `DQMC_DEV_ROOT/scripts/` 下 dqmc-dev 脚本，通过 adapter 做 dry-run、preflight、审批执行。
- 当前 SLURM 队列查询：`squeue`，支持 `--json` 和 fallback delimited output。
- 历史 SLURM 查询：`sacct --parsable2 --noheader`。
- Job detail：当前队列优先，必要时查历史，多个候选不猜唯一结果。
- Job 到 run/output path 候选：基于 `sacct.WorkDir`、stdout/stderr parent、用户显式 path，不做大目录扫描。
- 受限 artifact sync：默认 dry-run，remote host/path allowlist，本地 output root 限制，真实同步逐次审批。
- Agent 层轮询 helper：比较两个 `query_slurm` snapshots 的新增、消失、状态变化；MCP hands 不做 daemon。

## 代码演进和历史 commit 回顾

当前这条开发线的关键 commit：

- `78c1ab8 Update slurm.py and corresponding tests`
  修复真实 `squeue --json` wrapped fields：例如 `job_state` 可能是 list，`array_job_id` / `array_task_id` 可能是 dict。后续所有 SLURM 解析都要尊重这个经验，不能假设字段都是普通字符串。

- `0f6b7e6 docs: split Sherlock SLURM SDD`
  将单个 SDD 拆为 `requirements.md`、`design.md`、`tasks.md`、`verification.md`。

- `187fe65 feat: add SLURM status presenter`
  增加 `dqmc_tools/slurm_presenter.py`，把 `query_slurm` payload 转成人可读摘要。

- `e8b1f2a feat: add SLURM history query`
  实现 `query_slurm_history`，使用本地 `sacct` 查询历史任务，返回 jobs、state counts、exit code counts、warnings。

- `d38715f feat: add SLURM job detail query`
  实现 `get_slurm_job_detail(job_id, include_history=True)`，先查 `query_slurm`，没有当前队列结果时查 `query_slurm_history`。

- `a614b02 feat: infer SLURM path candidates`
  新增 `dqmc_tools/slurm_paths.py` 和 MCP tool `infer_slurm_path_candidates`，推断 run/output path candidates。

- `897496e test: verify SLURM path candidates feed run summary`
  验证 path candidate 可以 bounded 地衔接 `summarize_run(max_files=1)`。

- `9afbe36 docs: design Sherlock artifact sync`
  落地 `artifact-sync-design.md`，定义受限 rsync 同步设计。

- `4a38496 feat: add restricted Sherlock artifact sync`
  实现 `sync_sherlock_artifacts`，默认 dry-run，真实同步需要审批，返回 manifest。

- `5298cbe feat: add SLURM snapshot polling helpers`
  新增 `dqmc_tools/slurm_monitor.py` 和 `polling-workflow.md`，定义 agent 层状态轮询。

- `2ee2509 chore: add OpenACP backend helper scripts`
  增加 Slack/OpenACP backend 启停脚本和 README 说明。这是 transport 辅助，不改变 MCP hands 的安全边界。

## 关键文件地图

- `dqmc_mcp_server.py`
  MCP tool 注册和错误包装。应保持薄 adapter。

- `dqmc_tools/slurm.py`
  `query_slurm`、`query_slurm_history`、`get_slurm_job_detail`、SLURM field normalization。

- `dqmc_tools/slurm_presenter.py`
  纯文本状态摘要。

- `dqmc_tools/slurm_paths.py`
  从 job detail 推断 path candidates。

- `dqmc_tools/sync.py`
  受限 artifact sync，底层 `rsync`，默认 dry-run。

- `dqmc_tools/slurm_monitor.py`
  Agent 层 snapshot diff helper。不启动进程、不保存状态。

- `dqmc_tools/scripts/`
  dqmc-dev script adapter registry、argparse sync、runner、preflight、output parser。

- `specs/sherlock-slurm-sdd/tasks.md`
  当前 SDD task checklist。Sherlock 上要优先完成 R0/R1、L2-L4 Sherlock 验证、R6 验证。

- `specs/sherlock-slurm-sdd/verification.md`
  本地验证记录和 Sherlock 验证模板。

- `specs/sherlock-slurm-sdd/artifact-sync-design.md`
  远端产物同步设计。

- `specs/sherlock-slurm-sdd/polling-workflow.md`
  agent 层轮询说明。

## Sherlock Codex 的使命

Sherlock 上的 Codex 实例不是从零开发，而是完成真实环境验证和小范围兼容修正。

主要使命：

1. 拉取当前 repo 最新 commit，确认工作区干净或只包含可解释的本地改动。
2. 配好 Sherlock 上的 Python 环境；默认 status-only profile 不设置数据/脚本环境变量。
3. 跑 status 相关测试，确认本地 fixture 测试在 Sherlock 也能通过。
4. 对真实 `squeue` / `sacct` 输出做只读 smoke。
5. 验证默认 status tools：`query_slurm`、`query_slurm_history`、`get_slurm_job_detail`。
6. 如果真实输出和本地 fixture 假设不同，脱敏保存最小 fixture，补本地 parser 测试，再做小修。
7. 验证默认响应不包含真实路径字段。
8. 只在用户明确批准时，才进入 path-discovery、data-reading、script 或 sync profile；默认不做。
9. 更新 `verification.md` 或新增 Sherlock observation 文档，记录命令、结果、字段形态、兼容修正。

不属于本轮使命：

- 不实现 `sbatch` 提交。
- 不提交或取消 SLURM jobs。
- 不做大目录扫描。
- 不对 `/scratch` 现有目录做清理或重排。
- 不把 Slack/OpenACP 强行接进 MCP tools。
- 不在默认 status-only profile 中设置 `DQMC_DEV_ROOT`、`DQMC_ALLOWED_ROOTS`、`DQMC_OUTPUT_ROOT`、`DQMC_REGISTRY_PATH`。
- 不在默认 status 查询中调用 `infer_slurm_path_candidates`、`summarize_run`、script adapter 或 artifact sync。

## 推荐执行计划

### 0. 进入 Sherlock repo 后先做只读状态检查

```bash
pwd
git status --short --branch
git log --oneline -5
```

如果有本地改动：

- 不要 reset。
- 先 `git diff --stat` 和 `git diff` 了解改动。
- 如果改动和验证无关，尽量不碰。
- 如果改动影响验证，先问用户。

### 1. 同步代码

优先使用 fast-forward：

```bash
git pull --ff-only
```

如果失败：

- `fatal: Not possible to fast-forward`：说明 Sherlock repo 有本地 commit 或分叉。不要强推/重置；先汇报。
- `Your local changes would be overwritten`：不要 stash/drop；先看 `git status`，让用户决定。
- 网络或认证失败：确认 remote、SSH key、GitHub 权限。

### 2. 建立 Python 环境

推荐在 repo 内使用 `.venv`，或使用用户明确指定的安全 venv 路径。不要把 venv 建在已有重要 run 目录里。

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[mcp,test]"
```

如果 Sherlock 默认 Python 太旧或缺模块：

```bash
python --version
module avail python
module load python/<合适版本>
python -m venv .venv
```

不要随意修改系统 Python 或共享 module。

### 3. 配置环境变量

默认 status-only profile 不设置数据/脚本相关环境变量。不要在默认 Sherlock/Codex MCP
配置中设置：

- `DQMC_DEV_ROOT`
- `DQMC_ALLOWED_ROOTS`
- `DQMC_OUTPUT_ROOT`
- `DQMC_REGISTRY_PATH`

只有在用户明确批准进入 script 或 data-reading profile 后，才配置这些变量。

非默认 script profile 中，`DQMC_DEV_ROOT` 必须指向 Sherlock 上的 `dqmc-dev` checkout：

```bash
export DQMC_DEV_ROOT="/path/to/dqmc-dev"
export DQMC_REGISTRY_PATH="$PWD/registry.yaml"
export DQMC_OUTPUT_ROOT="$PWD/outputs/sherlock-validation"
```

非默认 data-reading/path-discovery profile 中，`DQMC_ALLOWED_ROOTS` 要尽量窄。示例：

```bash
export DQMC_ALLOWED_ROOTS="/path/to/one/safe/run/root:/path/to/another/safe/root"
```

安全建议：

- 没有明确目标 run/root 前，可以先不设置 `DQMC_ALLOWED_ROOTS`，确认 fail-closed 行为。
- 不要设置成 `/scratch`。
- 不要设置成用户整个 home 或整个 group scratch。
- 如果只验证某个 run，就只设置到该 run 或该 run 的直接父目录。

默认 status-only Codex MCP server 配置应指向 SLURM-only server 或 gateway profile，
不要指向完整 `dqmc_mcp_server.py`。如果当前还没有 SLURM-only server，只做 Python API
smoke，不把完整 MCP server 作为默认产品形态。

如果使用本地 `dqmc-sherlock-gateway` 访问 Sherlock，gateway 相关 `DQMC_SHERLOCK_*`
变量只在本地配置。`DQMC_SHERLOCK_REMOTE_CWD` 指 Sherlock 上的 `DQMC_agent`
checkout；真实值不得写入 agent 可见响应或长期记录。`DQMC_SHERLOCK_REMOTE_PYTHON`
应使用该 checkout 下 venv Python 的绝对路径，例如：

```bash
export DQMC_SHERLOCK_REMOTE_HOST="sherlock"
export DQMC_SHERLOCK_ALLOWED_HOSTS="sherlock"
export DQMC_SHERLOCK_REMOTE_PYTHON="<REDACTED_DQMC_AGENT_ON_SHERLOCK>/.venv/bin/python"
export DQMC_SHERLOCK_REMOTE_CWD="<REDACTED_DQMC_AGENT_ON_SHERLOCK>"
export DQMC_SHERLOCK_TIMEOUT_SECONDS="60"
export DQMC_SHERLOCK_GATEWAY_PROFILE="status-only"
export DQMC_SHERLOCK_REMOTE_ENV_JSON="{}"
```

不要把 `DQMC_SHERLOCK_REMOTE_PYTHON` 配成相对 `.venv/bin/python`。gateway 会先启动
远端 Python，再把 `--cwd` 传给 `remote_call`，所以相对 Python 路径会在远端 cwd
切换前解析，容易失败。

非默认完整 MCP server 配置位置通常是 `~/.codex/config.toml`：

```toml
[mcp_servers.dqmc-hands]
command = "/absolute/path/to/repo/.venv/bin/python"
args = ["/absolute/path/to/repo/dqmc_mcp_server.py"]

[mcp_servers.dqmc-hands.env]
DQMC_DEV_ROOT = "/path/to/dqmc-dev"
DQMC_ALLOWED_ROOTS = "/path/to/safe/run/root"
DQMC_OUTPUT_ROOT = "/absolute/path/to/repo/outputs/sherlock-validation"
DQMC_REGISTRY_PATH = "/absolute/path/to/repo/registry.yaml"
```

### 4. 跑测试

先跑基础 import 和 status 目标测试：

```bash
.venv/bin/python -m pytest tests/test_package_import.py tests/test_slurm.py tests/test_slurm_presenter.py tests/test_slurm_monitor.py -q
```

全量测试会涉及 HDF5/script/sync 等非默认能力，只在本地完整工具环境或单独 profile 中运行：

```bash
DQMC_DEV_ROOT="$DQMC_DEV_ROOT" .venv/bin/python -m pytest
```

本地最近通过记录是：

```text
140 passed in 13.14s
```

Sherlock 上时间可能不同。关键是 0 failures。

### 5. MCP tool 面 smoke

```bash
.venv/bin/python - <<'PY'
from dqmc_mcp_server import build_server
import asyncio

async def main():
    server = build_server()
    tools = await server.list_tools()
    print(len(tools))
    for tool in tools:
        print(tool.name)

asyncio.run(main())
PY
```

完整 `dqmc_mcp_server.py` 会看到 14 个工具；这不是默认 Sherlock status profile。
默认 Sherlock status profile 应只暴露 path-redacted SLURM status tools：

- `query_slurm`
- `query_slurm_history`
- `get_slurm_job_detail`

不要在默认 profile 中暴露 `infer_slurm_path_candidates`、HDF5/read tools、script adapters、
`sync_sherlock_artifacts` 或 run summary。

### 6. 只读 SLURM 命令基线

只运行只读命令：

```bash
which squeue
which sacct
squeue --me
squeue --me --json
```

如果 `squeue --json` 失败，不一定是错误；代码会 fallback 到 delimited output。需要记录 Sherlock 是否支持 JSON。

历史查询示例，选择较短窗口。建议手动设置日期，避免误查过大范围：

```bash
sacct --parsable2 --noheader --user "$USER" --starttime YYYY-MM-DD --format=JobID,JobName,User,State,ExitCode,Elapsed,Timelimit,Submit,Start,End,Partition,NodeList
```

注意：

- 不要提交新 job 只为了制造数据。
- 如果当前没有 jobs，`query_slurm` 返回空队列也可以接受。
- 如果历史没有失败/timeout/OOM 样本，可先验证 completed 或已有状态，不要制造失败任务。

### 7. Python API smoke

当前队列：

```bash
.venv/bin/python - <<'PY'
from dqmc_tools.slurm import query_slurm
from dqmc_tools.slurm_presenter import format_slurm_status_summary

payload = query_slurm({"me": True})
print(payload["ok"], payload["source"])
print(payload["summary"])
print(format_slurm_status_summary(payload))
PY
```

历史任务：

```bash
.venv/bin/python - <<'PY'
from dqmc_tools.slurm import query_slurm_history

payload = query_slurm_history({"me": True, "max_rows": 10})
print(payload["ok"], payload["source"])
print(payload["summary"])
print(payload["warnings"])
for row in payload["jobs"][:3]:
    print(row)
PY
```

Job detail，优先用已有真实 job id：

```bash
.venv/bin/python - <<'PY'
from dqmc_tools.slurm import get_slurm_job_detail

job_id = "REPLACE_WITH_REAL_JOB_ID"
payload = get_slurm_job_detail(job_id)
print(payload["ok"])
print(payload["match_count"], payload["multiple_matches"])
for candidate in payload["candidates"]:
    print(candidate)
PY
```

默认 status smoke 到此为止。返回 payload 如果包含 `work_dir`、stdout/stderr path 或
`raw` 中的真实 path，需要先修 redaction，再接 Slack/gateway。

Path candidates 不属于默认 status profile。只有进入单独 path-discovery profile 时才运行：

```bash
.venv/bin/python - <<'PY'
from dqmc_tools.slurm import get_slurm_job_detail
from dqmc_tools.slurm_paths import infer_slurm_path_candidates

job_id = "REPLACE_WITH_REAL_JOB_ID"
detail = get_slurm_job_detail(job_id)
paths = infer_slurm_path_candidates(detail, allowed_roots=["/path/to/safe/root"])
print(paths)
PY
```

bounded run read 不属于默认 status profile。只有进入单独 data-reading profile 且用户明确
批准后，才可对 allowed roots 内的 DQMC run 做 bounded read：

```bash
.venv/bin/python - <<'PY'
from dqmc_tools.runs import summarize_run

path = "/path/to/one/safe/run"
payload = summarize_run(path, allowed_roots=[path], max_files=1, max_registry_entries=8, max_log_chars=200)
print(payload["ok"])
print(payload["path"])
print(payload["reported_hdf5_file_count"])
PY
```

### 8. Script adapter Sherlock 验证

本节不属于默认 status-only profile。只有进入单独 script profile 后才执行。先只做 audit 和 dry-run：

```bash
.venv/bin/python scripts/audit_script_adapters.py
```

然后：

```bash
.venv/bin/python - <<'PY'
from dqmc_tools.scripts import list_script_adapters, describe_script_adapter

print(len(list_script_adapters()))
print(describe_script_adapter("check_h5_completion"))
PY
```

对真实脚本只先 dry-run。示例：

```bash
.venv/bin/python - <<'PY'
from dqmc_tools.scripts import run_script_adapter

payload = run_script_adapter(
    "check_h5_completion",
    {"root": "/path/to/safe/run", "glob": "*.h5"},
    cwd=".",
    allowed_roots=["/path/to/safe/run"],
    output_root="outputs/sherlock-validation",
    dry_run=True,
)
print(payload)
PY
```

不要在没有用户审批时真实执行。真实执行会写文件，必须确认 output location。

### 9. Artifact sync 验证

本节不属于默认 status-only profile。只有本地 agent 需要把用户明确指定的 Sherlock 产物拉到本地时，才使用 `sync_sherlock_artifacts`。第一步永远 dry-run：

```python
sync_sherlock_artifacts(
    remote_host="sherlock",
    remote_path="/remote/safe/run",
    remote_allowed_hosts=["sherlock"],
    remote_allowed_roots=["/remote/safe"],
    local_subdir="sherlock/run",
    output_root="/local/output/root",
    dry_run=True,
)
```

真实同步必须逐次审批：

```python
user_confirmation={"approved": True, "text": "I approve syncing this specific run after reviewing dry-run manifest"}
```

禁止：

- `rsync --delete`
- remote path 通配符
- output root 指向已有重要目录
- 未看 dry-run manifest 就真实同步

## 需要记录和回流的 Sherlock 观察结果

建议在 `specs/sherlock-slurm-sdd/verification.md` 追加 Sherlock 小节，或新增 `sherlock-observations-YYYY-MM-DD.md`。记录：

- Sherlock hostname、repo commit hash、Python 版本。
- status-only profile 是否未设置 `DQMC_DEV_ROOT`、`DQMC_ALLOWED_ROOTS`、`DQMC_OUTPUT_ROOT`、`DQMC_REGISTRY_PATH`。
- `squeue --me` 是否可用。
- `squeue --json` 是否可用。
- `squeue --json` 真实字段形态：`job_state`、`state_reason`、`array_job_id`、`array_task_id`、`nodes`。
- `sacct` 是否可用。
- array parent/task id 在 `sacct` 中的实际格式。
- `State` 和 `ExitCode` 的真实样例。
- status response 是否不含 `WorkDir`、stdout/stderr path、run path、output path 或 raw path fields。
- 非默认 profile 如已单独审批：`infer_slurm_path_candidates`、`summarize_run(max_files=1)`、script adapter audit 的结果。

所有真实 job id、路径、用户名、project 名称如果敏感，应脱敏后再提交 fixture。

## 常见错误和处理

### `configuration_error: DQMC_DEV_ROOT must be set`

原因：调用了 script adapter 或依赖 dqmc-dev 的非默认 profile，但没有设置 `DQMC_DEV_ROOT`，或 Codex MCP config 没把 env 传给 server。默认 status-only profile 不应需要该变量。

处理：

- 确认 Sherlock 上 dqmc-dev checkout 路径。
- 设置 shell env 或 `~/.codex/config.toml` 的 `[mcp_servers.dqmc-hands.env]`。
- 路径必须存在。

### `path_not_allowed`

原因：进入了 data-reading/path-discovery profile，目标路径不在 `DQMC_ALLOWED_ROOTS` 内，或 allowed root 未设置。默认 status-only profile 不应读取路径。

处理：

- 不要直接把 allowed roots 放宽到 `/scratch`。
- 找到要读的最小安全根目录。
- 用该 run 或其直接父目录作为 allowed root。

### `squeue --json` 失败

原因：Sherlock SLURM 版本可能不支持 JSON，或命令输出非 JSON。

处理：

- 这不一定阻塞；`query_slurm` 会 fallback。
- 记录 stderr 和 fallback 输出字段是否足够。
- 如果 fallback 字段不足，补最小 parser fixture。

### `sacct` 不存在或失败

原因：命令不可用、accounting 限制、时间窗口不对、集群配置限制。

处理：

- 先 `which sacct`。
- 尝试小时间窗口和 `--user "$USER"`。
- 如果不可用，工具应返回 structured `tool_unavailable`；记录现象，不要改用危险命令。

### `sacct WorkDir` 为空

原因：集群 accounting 未记录 WorkDir，或权限限制。

处理：

- 记录字段为空。
- 只有在 path-discovery profile 中，才尝试使用 stdout/stderr parent 或用户显式 path。
- 不扫描大目录猜测。

### full pytest 中 HDF5/script adapter 失败

可能原因：

- `DQMC_DEV_ROOT` 错误。
- Sherlock Python/numpy/h5py 环境不一致。
- dqmc-dev 脚本版本和 adapter registry 不匹配。

处理：

- 先跑 `scripts/audit_script_adapters.py`。
- 确认 `.venv` 安装完整。
- 如果是 dqmc-dev CLI 参数变化，更新 adapter/fixture，补测试。

### `rsync` unavailable

原因：Sherlock 或本地环境没有 `rsync`。

处理：

- `sync_sherlock_artifacts` 应返回 `tool_unavailable`。
- 不要退回到任意 shell/scp 拼接。

### Permission denied on `/scratch`

处理：

- 不要 chmod/chown。
- 不要尝试删除或移动。
- 确认路径是否属于当前用户或 group。
- 只读验证失败就记录，换用户明确授权的路径。

### Git pull 冲突或本地改动

处理：

- 不要 reset。
- 读 `git status` 和 `git diff`。
- 如果是 Sherlock 本地观察文档，保留并协调。
- 如果不清楚，问用户。

## 最终验收标准

Sherlock 最后一公里完成时，应满足：

- Sherlock repo 在明确 commit 上。
- status 相关 pytest 通过，或失败项有清楚 root cause 和非破坏性处理建议。
- 默认 Sherlock status profile 可枚举 path-redacted status tools。
- `query_slurm(filters={"me": true})` 在 Sherlock 上 smoke 成功，包括空队列情况。
- `query_slurm_history({"me": true, "max_rows": N})` smoke 成功，或明确记录 `sacct` 不可用原因。
- 至少一个真实 job id 经过 `get_slurm_job_detail` 验证；如果没有可用 job，则记录无法验证原因。
- 默认 status response 不包含真实 `WorkDir`、stdout/stderr path、run path、output path 或 raw path fields。
- `infer_slurm_path_candidates`、`summarize_run(max_files=1)`、`scripts/audit_script_adapters.py` 只在单独 profile 中验收。
- 所有真实输出脱敏后写入 verification/observation 文档。
- 没有任何 `/scratch` 重要目录被删除、移动、覆盖或递归写入。

2026-05-28 已完成的 status-only gateway smoke：

- 本机 `ssh -o BatchMode=yes sherlock hostname` 可非交互返回。
- Sherlock 端 repo 同步后，远端 `.venv` 可 `import dqmc_tools.remote_call`。
- 手写 SSH + `remote_call` 的 `query_slurm(filters={"me": true})` 返回 `ok=true`、`source=squeue_json`。
- 本地 gateway 调 `sherlock_query_slurm` 返回 `ok=true`、`source=squeue_json`。
- 本地 gateway 调 `sherlock_query_slurm_history(filters={"me": true, "max_rows": 5})` 返回 `ok=true`、`source=sacct_parsable2`。
- 本地 gateway 调 `sherlock_get_slurm_job_detail` 查询一个临时 job id，返回 `match_count=1`、`multiple_matches=false`。
- 三个 gateway status tools 的 path redaction check 均为 false；provenance 只含 host/tool，不含 remote cwd。
- 未默认调用 `sherlock_summarize_run`、`infer_slurm_path_candidates`、script adapter 或 sync。

## 给 Sherlock Codex 的建议开场提示

可以在 Sherlock 上启动 Codex 后，把下面这段作为第一条任务：

```text
请阅读 specs/sherlock-slurm-sdd/sherlock-validation-handoff.md、tasks.md、verification.md。
你的任务是完成 Sherlock 真实环境验证，不要实现 sbatch，不要运行任何破坏性命令，
不要修改或删除 /scratch 下任何现有文件或目录。默认只做 status-only/path-redacted
验证，不设置 DQMC_DEV_ROOT、DQMC_ALLOWED_ROOTS、DQMC_OUTPUT_ROOT、DQMC_REGISTRY_PATH。
先做 git/status/env/test 基线，然后按 handoff 的 R0/R1/L2/L3 顺序做只读 smoke。
不要调用 infer_slurm_path_candidates、summarize_run、script adapter 或 sync，除非用户明确
批准进入单独 profile。所有真实输出要脱敏记录；
如果遇到不确定或需要写入 /scratch 的操作，先停止并询问。
```
