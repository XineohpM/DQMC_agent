# SLURM Polling Workflow

状态：本地 agent workflow 说明。MCP hands 不实现 daemon，也不保存轮询状态。

## 目标

让 agent 能按用户指定的 interval 观察 Sherlock/SLURM 状态变化，同时保持 MCP tools 无状态。每次状态读取仍然是一次普通 `query_slurm(filters={"me": true})` 调用。

## 工作流

1. 用户提出轮询请求，例如“每 5 分钟看一下我的任务状态，持续 30 分钟”。
2. agent 校验 interval、总时长或最大次数，避免无限轮询。
3. agent 调用 `query_slurm(filters={"me": true})` 获取初始 snapshot。
4. 每次 sleep 到 interval 后，再调用一次 `query_slurm(filters={"me": true})`。
5. agent 用 `diff_slurm_snapshots(previous, current)` 比较新增、消失和 state 改变。
6. agent 用 `format_slurm_snapshot_diff(diff)` 生成短摘要。
7. agent 将 current 作为下一轮 previous。
8. 用户中断、达到最大次数或达到总时长后，agent 停止循环。

## 中断行为

轮询循环只存在于 agent 会话内，不在 MCP hands 中创建后台进程。中断时 agent 停止下一次 sleep/call 即可；MCP server 不需要 cancel、cleanup 或恢复状态。

## 输出建议

每轮只报告变化：

- 新增 jobs。
- 消失 jobs。
- state 改变 jobs。

如果没有变化，输出“没有任务状态变化。”，避免重复刷完整队列。用户需要完整状态时，agent 可再次调用 `query_slurm` 并使用 presenter 展开当前 snapshot。

## 边界

- 不自动调用 `scancel`、`scontrol` 或任何 mutating command。
- 不在 MCP hands 内保存 previous snapshot。
- 不在 MCP hands 内启动线程、定时器或后台循环。
- 不保证 agent 进程退出后还能继续监控。
