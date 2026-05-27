# DQMC Agent Goals

本文档描述 DQMC agent 项目的最终远景和要完成的目标。具体执行 todo list 放在 `specs/backlog.md`。

## 总体愿景

DQMC agent 的最终目标是成为一个面向 DQMC 工作流的可靠研究助手：它能理解项目知识，安全调用本地和集群工具，帮助用户查询、生成、同步、分析和诊断 DQMC 产物，同时对高风险动作保持清晰审批和可追溯记录。

最终系统采用分层架构：

- “眼睛”层负责知识和上下文：`registry.yaml`、`code_map.md`、`diagnostics_playbook.md`、dqmc-dev 代码地图、语义索引、运行经验。
- “手”层负责安全、可测试的动作：HDF5 读取、registry resolve、script adapter、SLURM 队列状态查询、产物同步、未来提交任务。
- agent 编排层负责理解用户意图、选择工具、组织回复、执行审批流程、维护会话上下文。
- Slack bot 作为 agent 的入口和交互 transport 接入。

## 分层目标

### MCP Hands

MCP hands 要提供稳定、低层、事实型能力：

- 读取明确路径下的 DQMC run/HDF5 数据。
- 根据 `registry.yaml` 解析 observable/parameter。
- 调用 dqmc-dev 已有 util 和 scripts。
- 做路径安全、preflight、dry-run、输出 manifest、structured error。
- 查询 SLURM 当前队列和近期历史任务事实。
- 为 agent 层提供稳定的工具契约和可测试返回结构。

### Eyes / Knowledge

知识层的目标是让 agent 能回答“为什么”和“应该看什么”，但需要区分事实来源：

- `registry.yaml`：observable/parameter 的事实源，包括 id、alias、HDF5 dataset key、measurement/generation 信息、normalization、requirements。
- `code_map.md`：dqmc-dev 数据流、脚本能力、核心文件职责的人工地图。
- `diagnostics_playbook.md`：sign、Trotter、warmup、mu tuning、MaxEnt binning 等经验规则和诊断建议。

长期目标是让这些知识可更新、可审计、可引用。

### Agent Orchestration

agent 层的目标是把用户请求转化成安全工作流：

- 判断什么时候读 registry，什么时候读 HDF5，什么时候调用脚本。
- 在执行高风险动作前先 dry-run。
- 向用户展示命令、cwd、输入、输出、preflight。
- 获取明确审批后再执行真实动作。
- 把工具事实和诊断知识合并成清晰回复，并标注哪些是代码事实、哪些是经验判断。

### Slack Bot

Slack bot 是 agent 的交互入口：

- 接收 Slack IM/thread 消息。
- 维护 Slack thread 与 agent session 的映射。
- 把 agent 回复发送回 Slack。
- 用 Slack interactive UI 承载审批流程。
- 将 Slack 用户、频道、thread、审批记录传递给 agent 编排层。

## 最终能力目标

### 状态和数据查询

最终 agent 应能稳定回答：

- 当前和近期历史 Sherlock/SLURM 中我的任务有哪些。
- 哪些任务 running、pending、held、failed、completed。
- 某个 job id 的当前或历史详情，以及它可能对应的 run/output path。
- 某个 run 目录有哪些 HDF5 文件、metadata、log completion facts。
- 某个 observable/parameter 在 registry 里如何定义，HDF5 dataset key 是什么。
- 某组 HDF5 文件的 observable mean/error 是多少。

### 安全执行

最终 agent 应能完成带审批的执行工作流：

- 输入生成：beta scan、beta-mu scan、one-band Hubbard input generation。
- 诊断脚本：completion、warmup 等。
- 后处理脚本：energy、local moment、local G、per-bin current-current、bootstrap、MaxEnt、plot。
- 产物同步：从 Sherlock rsync 到本地 output root。
- 未来的 SLURM job submission。

所有真实执行都应可追溯：

- 用户意图。
- 工具名和参数。
- dry-run/preflight。
- 审批记录。
- 命令、cwd、环境。
- 输入路径、输出路径。
- 产物 manifest。
- job id 或同步 manifest。

### 诊断辅助

最终 agent 应能基于事实和 playbook 给出诊断建议，但必须区分层次：

- 工具事实：来自 HDF5、registry、SLURM、脚本输出。
- 项目约定：来自 `registry.yaml`、`code_map.md`、dqmc-dev 实现。
- 经验规则：来自 `diagnostics_playbook.md`。
- agent 推断：基于上述信息的建议，并明确标注推断来源。

诊断辅助应覆盖：

- sign problem 风险提示。
- Trotter discretization 检查。
- warmup/sweep 诊断入口。
- mu tuning 和 filling 目标检查。
- MaxEnt binning 和 covariance 风险提示。

## 更新目标

项目应支持明确的更新流程：

- 更新 `registry.yaml` 后，registry 相关工具应在下一次调用时看到变化，并通过测试确认 schema 和 resolve 行为。
- 更新 `code_map.md` 后，agent 应能重新索引或提示需要同步脚本白名单。
- 更新 `diagnostics_playbook.md` 后，agent 应能在诊断建议中使用新知识。
- 更新 dqmc-dev 脚本后，应有 adapter contract tests 检查 CLI、preflight 和输出 parser 是否仍匹配。
- 更新 MCP hands 代码后，应重启 MCP server，并运行完整测试。

## 成功标准

这个项目达到目标时，应满足：

- 用户可以从 Slack 或本地 agent 发起常见 DQMC 工作流。
- 用户可以通过 agent 完成集群状态查询。
- 同步远端产物后，可以直接进入本地分析工具链。
- 高风险动作全部经过明确审批。
- 工具层稳定、可测试、可审计。
- agent 回复能清楚区分事实、规则和推断。
- 更新 registry、code map、diagnostic playbook 或 dqmc-dev 脚本时，有明确的测试和刷新流程。
