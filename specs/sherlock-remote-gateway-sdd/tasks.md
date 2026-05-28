# Sherlock Remote Gateway SDD 任务拆解

状态：第一版开发。本地实现和 Sherlock smoke 分开执行。

## Phase G0：规格和边界冻结

- [x] 从 `specs/goals.md`、`specs/backlog.md`、`specs/sherlock-slurm-sdd/sherlock-validation-handoff.md` 复核最新架构方向。
- [x] 新增 `specs/sherlock-remote-gateway-sdd/requirements.md`。
- [x] 新增 `specs/sherlock-remote-gateway-sdd/design.md`。
- [x] 新增 `specs/sherlock-remote-gateway-sdd/tasks.md`。
- [x] 新增 `specs/sherlock-remote-gateway-sdd/verification.md`。

验收：

- [x] 明确本地 Codex 是唯一 agent 大脑。
- [x] 明确 Sherlock 上不长期运行 MCP server。
- [x] 明确第一版不做 `sbatch`、cancel、真实脚本执行或任意 shell。

## Phase G1：远端短命 `remote_call` CLI

- [x] 写 `tests/test_remote_call.py`，覆盖 successful dispatch。
- [x] 写 unknown tool structured error 测试。
- [x] 写 invalid JSON / non-object payload structured error 测试。
- [x] 写 env allowlist 测试，确认只注入允许的 `DQMC_*` env。
- [x] 实现 `dqmc_tools/remote_call.py`。
- [x] 支持 `python -m dqmc_tools.remote_call --cwd /absolute/path/to/DQMC_agent`，进入 repo 后读取 stdin。
- [x] stdout 只打印 JSON。

验收：

- [x] `tests/test_remote_call.py` 通过。
- [x] remote CLI 不调用任意用户命令。

## Phase G2：本地 SSH gateway helper

- [x] 写 `tests/test_remote_gateway.py`，覆盖 config from env。
- [x] 写 command builder test，确认 argv list 为 `ssh host python -m dqmc_tools.remote_call --cwd repo`。
- [x] 写 success test，确认 JSON stdin、JSON stdout、remote provenance。
- [x] 写 host allowlist rejection test。
- [x] 写 missing remote cwd configuration error test。
- [x] 写 ssh unavailable test。
- [x] 写 timeout test。
- [x] 写 nonzero returncode test。
- [x] 写 invalid JSON stdout test。
- [x] 实现 `dqmc_tools/remote_gateway.py`。

验收：

- [x] `tests/test_remote_gateway.py` 通过。
- [x] 不使用 shell string。
- [x] gateway 层错误和远端 tool 错误可区分。

## Phase G3：独立 Sherlock gateway MCP server

- [x] 写 `tests/test_sherlock_gateway_mcp_server.py`，确认 tool set。
- [x] 写 4 个 MCP success contract tests：
  - `sherlock_query_slurm`
  - `sherlock_query_slurm_history`
  - `sherlock_get_slurm_job_detail`
  - `sherlock_summarize_run`
- [x] 写 gateway error contract test。
- [x] 实现 `dqmc_sherlock_gateway_mcp_server.py`。
- [x] 每个 MCP tool 只做薄 adapter，错误使用 `error_dict`。

验收：

- [x] MCP server 暴露 4 个第一版 gateway tools。
- [x] MCP descriptions 明确短 SSH、只读、不提交/取消。

## Phase G4：文档和使用说明

- [x] 更新 `README.md`，说明 `dqmc-sherlock-gateway` MCP 启动和环境变量。
- [x] 更新 `USAGE.md`，说明 Slack -> 本地 Codex -> gateway -> Sherlock 的用户路径。
- [x] 更新 `specs/backlog.md`，标记第一版 SDD 和本地实现进展。
- [x] 更新 `specs/sherlock-remote-gateway-sdd/verification.md`，记录本地测试命令。

验收：

- [x] 文档明确 gateway 和 `dqmc-hands` 的关系。
- [x] 文档明确第一版仍不做真实写入和 `sbatch`。

## Phase G5：本地验证

- [x] 运行 `tests/test_remote_call.py`。
- [x] 运行 `tests/test_remote_gateway.py`。
- [x] 运行 `tests/test_sherlock_gateway_mcp_server.py`。
- [x] 运行现有 MCP server/tool set tests，确认未破坏 `dqmc-hands`。
- [x] 运行全量测试。

验收：

- [x] 本地测试通过。
- [x] `dqmc-hands` 原有 14 个工具面不被 gateway 改动。

## Phase R1：Sherlock smoke

本阶段需要真实 Sherlock 访问，不在本地开发中强制执行。

- [ ] 按 `specs/sherlock-slurm-sdd/sherlock-validation-handoff.md` 完成 Sherlock repo/venv/env 基线。
- [ ] 在 Sherlock 上直接测试 `python -m dqmc_tools.remote_call`。
- [ ] 从本地通过 gateway 调用 `sherlock_query_slurm(filters={"me": true})`。
- [ ] 从本地通过 gateway 调用 `sherlock_query_slurm_history(filters={"me": true, "max_rows": 5})`。
- [ ] 从本地通过 gateway 对一个 allowed run 调用 `sherlock_summarize_run(max_files=1)`。
- [ ] 记录 stdout JSON、source、summary、字段形态和错误。

验收：

- [ ] Gateway 能在 60 秒内返回 JSON。
- [ ] Sherlock 上无常驻进程。
- [ ] 没有 submit/cancel/mutate 命令。

## 推荐执行顺序

1. Phase G0：规格冻结。
2. Phase G1：远端 `remote_call`。
3. Phase G2：本地 SSH gateway。
4. Phase G3：MCP server。
5. Phase G4：文档。
6. Phase G5：本地验证。
7. Phase R1：真实 Sherlock smoke。
