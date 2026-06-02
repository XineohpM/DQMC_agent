# DQMC Agent 使用手册

本文档从用户视角说明这个 DQMC agent 能怎样被使用。它不描述内部实现细节，也不替代
`README.md` 的安装配置说明；它回答的是：用户在本地 Codex 或 Slack 里可以问什么、
做什么，以及哪些动作会进入确认流程。

## 使用入口

### 本地 Codex

用户可以直接在当前工作区启动 Codex，并让它调用 `dqmc-hands` MCP 工具。适合开发、
调试、检查测试、读写项目文档，以及对本地数据目录做分析。

常见用法：

```text
总结 /Users/.../data/T_0.1 这个 run 目录。
读取 density，并给出 mean/error。
列出当前白名单脚本，说明哪个能提取 per-bin JNJN。
先 dry-run check_h5_completion.py，告诉我会读写哪些路径。
```

### Slack/OpenACP

用户也可以在 Slack 里像发消息一样使用这个 agent。先启动本机 OpenACP 后端：

```bash
start-slackbot-backend
stop-slackbot-backend
```

后端启动后，在 Slack 里找到配置好的那个独立 Slack app，直接给它发一条私信。它会为这次
对话创建一个新的 Slack channel，并邀请你加入。进入这个新 channel 后，你就可以在里面和
一个本地 Codex 实例开启一段连续对话。

这个 channel 就像这次研究任务的工作间：你可以一路追问、补充路径、让 agent 继续上一条结果
往下查，也可以让它先 dry-run 一个会写文件的动作。agent 的回复会回到同一个 channel 里，
上下文也会围绕这段对话持续保留。

在 Slack 里你可以做这些事：

- 问当前 run 目录里有什么数据、log 是否完成、某个 observable 怎么读。
- 贴一个 HDF5/run 目录，让 agent 总结 metadata、sign、n_sample 或 density。
- 让 agent 解释白名单脚本，例如哪个脚本负责 warmup 检查，哪个脚本提取 per-bin current-current。
- 让 agent 对脚本执行或 Sherlock 同步先做 dry-run，看看 command、输入、输出和风险点。
- 在确认信息看清楚后，继续在 Slack 里明确回复同意，让 agent 执行真实动作。
- 查询 SLURM/Sherlock job 状态，继续追问某个 job id 对应的输出路径。
- 基于结果继续做诊断，比如 sign 是否值得信任、Trotter 条件是否合理、warmup 是否足够。

如果你想开一个全新的上下文，就重新给这个 Slack app 发起一段新对话；它会再创建一个新的
channel。一个 channel 对应一段连续 session，这样不同任务不会混在一起。

## 可以问什么

### 数据和 run 摘要

用户可以给出一个明确的 run 目录，让 agent 总结其中的 HDF5 文件、metadata、log
completion facts，以及 registry 中有哪些量能在该 run 中读取。

示例：

```text
总结 /Users/phoenixm/Desktop/DQMC_agent/data/T_0.1/ 这个 run。
这个目录里有哪些 HDF5 文件？log 显示是否完成？
读取 equal-time sign 和 n_sample。
```

注意：agent 不会自己扫描父目录寻找 run。请在请求里明确给出 run 目录。

### Observable 和 parameter 查询

用户可以用 registry 中的 id、alias、HDF5 dataset key 或 dataset tail 查询量的定义。
agent 会说明它对应的 registry entry、dataset key，以及后续可以用哪个读取流程。

示例：

```text
density 在 registry 里怎么定义？
mu 对应哪个 parameter？
EqLt density 的 HDF5 dataset key 是什么？
```

### HDF5 读取和误差估计

直接读取单个文件或目录中的 dataset 时，agent 只返回事实性数组摘要，不把单次读取伪装成
误差估计。想要 mean/error 时，可以让 agent 对一组 HDF5 文件做 registered observable
估计。

示例：

```text
读取这个 run 的 density，并报告 mean/error。
读取 sign 的原始 dataset summary。
用 jackknife_noniid 估计 density。
```

### 白名单脚本

agent 可以列出和解释当前接入的 dqmc-dev 脚本 adapter。用户可以先让 agent 描述脚本，
再 dry-run，确认命令、cwd、输入、输出和 preflight 结果。

常见脚本能力包括：

- input generation：beta scan、beta-mu scan。
- 诊断：HDF5 completion、warmup。
- 后处理：energy、specific heat、local moment、local Green function、per-bin current-current。
- MaxEnt 和图像输出：DOS、conductivity、resistivity、double occupancy、charge order。
- workflow 文件操作：stack owner/worker、multi-dir push stack。

示例：

```text
哪个脚本能提取 per-bin current-current 数据？
描述 plot_JNJN 的输入要求。
dry-run check_warm，告诉我缺不缺输入。
```

真实运行白名单脚本前，agent 会先展示 dry-run 信息，并等待你本次明确同意。

### SLURM 和 Sherlock 状态

agent 可以查询当前 SLURM 队列、近期历史、单个 job id 的详情，并从 job facts 推断可能的
run/output path。它只做只读查询，不提交、不取消、不修改任务。

示例：

```text
查询我当前的 Sherlock/SLURM 任务状态。
这个 job id 是 running、pending 还是 failed？
帮我根据 job detail 推断可能的 output path。
每隔一段时间查一次状态，有变化时告诉我。
```

当前状态查询依赖本机或 Sherlock 环境中的 `squeue` / `sacct` 可用性。真实 Sherlock
字段形态后续会在集群上继续验证，并补充到测试 fixture 中。

如果你是在 Slack 里和本地 Codex 聊天，推荐的 Sherlock 查询路径是本地
`dqmc-sherlock-gateway` MCP：本地 agent 收到请求后，通过短命 SSH 到 Sherlock
执行一次白名单 `dqmc_tools.remote_call`，拿到 JSON 后断开。这样 Sherlock 上不需要
长期挂 Codex 或 MCP server。

2026-05-28 当前状态：本地 Codex/OpenACP 实际配置已经注册 `dqmc-sherlock-gateway`
status-only profile；Slack/OpenACP 新会话已确认可以查询 Sherlock SLURM 状态。为了确保
加载最新 MCP 配置，建议从 Slack app 发起一个新的 top-level 对话，而不是继续使用配置变更前
已有的旧 session/thread。

默认 gateway profile 是 status-only/path-redacted，支持：

- 查询当前 Sherlock SLURM 队列。
- 查询近期 Sherlock SLURM 历史任务。
- 查询某个 Sherlock job id 的详情。

默认 profile 不向远端注入 `DQMC_DEV_ROOT`、`DQMC_ALLOWED_ROOTS`、
`DQMC_OUTPUT_ROOT` 或 `DQMC_REGISTRY_PATH`，返回结果也不会暴露 Sherlock
`WorkDir`、stdout/stderr path、run/output path 或远端 repo cwd。对明确给出的
Sherlock run path 做 bounded summary 的能力已实现，但只属于非默认
`data-reading` profile，启用前需要单独审批和重新审查 allowed roots。

它仍然只读，不提交、不取消、不修改任务。

本地 Sherlock SSH 认证由用户完成，agent 不接触密码或 Duo。`dqmc-sherlock-gateway`
启动时会在后台立即做一次非交互 preflight，并按 `DQMC_SHERLOCK_KEEPALIVE_SECONDS`
定期 keepalive；这不会阻塞 MCP server startup：

```bash
ssh -o BatchMode=yes -o ConnectTimeout=8 sherlock true
```

如果失败，恢复步骤是在本机 terminal 中重新完成交互认证：

```bash
kinit <sunetid>@stanford.edu
ssh sherlock hostname
```

`start-slackbot-backend` 也会在启动 OpenACP 前运行 preflight。默认
`DQMC_SHERLOCK_PREFLIGHT=warn`，失败只提示；设为 `require` 时失败会阻止 backend 启动。
`DQMC_SHERLOCK_KEEPALIVE_SECONDS=0` 可关闭 gateway 运行中的 keepalive。

### 产物同步

agent 可以把 allowlist 内的 Sherlock 产物通过受限 rsync 同步到本地 output root。同步默认
会先 dry-run；真实同步会等待你本次明确同意。

示例：

```text
先 dry-run 同步这个 Sherlock output 目录。
同步后帮我 summarize 本地结果。
只同步 h5 和 log 文件。
```

同步流程会返回 command、远端路径、本地目标和 manifest，方便后续进入本地 HDF5 分析。

### 诊断建议

用户可以询问 sign problem、Trotter error、warmup、mu tuning、compressibility、
MaxEnt binning 等诊断问题。agent 会先收集工具事实，再引用 `diagnostics_playbook.md`
中的规则，最后给出推断。

回答会区分：

- 工具事实：来自 HDF5、registry、SLURM 或脚本输出。
- 项目约定：来自 registry、code map 或 dqmc-dev 实现。
- playbook 规则：来自 diagnostics playbook。
- agent 推断：基于以上信息的建议。

示例：

```text
这个 run 的 sign 健康吗？
dt 和 U 是否满足 Trotter error 的经验条件？
这个 warmup 看起来够不够？
这个 mu 是否调到了目标 filling？
```

## 安全确认流程

凡是会写文件、同步文件、生成输入、修改 workflow 文件或运行后处理脚本的动作，都会先进入
确认流程：

1. 用户提出要执行的动作。
2. agent 解析意图，并选择相应的脚本入口或同步工具。
3. agent 先 dry-run。
4. agent 展示 command、cwd、输入路径、输出路径、preflight 和风险点。
5. 用户本次明确同意。
6. agent 执行真实动作，并返回结果、manifest、stdout/stderr tail 或 structured error。

没有本次明确同意时，agent 不会继续真实执行。

## 重要边界

有几件事值得提前知道：

- 底层工具负责把事实查清楚：路径、数组摘要、脚本结果、SLURM 状态和错误信息。
- 物理判断会由 agent 结合 facts 和 diagnostics playbook 给出，而不是直接塞进底层工具结果里。
- `code_map.md` 和 `diagnostics_playbook.md` 会在解释和诊断问题时被 agent 读取，用来补充背景和经验规则。
- agent 不会自动扫描 scratch 目录帮你猜 run 在哪里。你给出明确路径后，它会围绕这个路径继续工作。
- 现在可以查询 SLURM 状态，但还不会替你提交或取消 SLURM job。
- `.openacp/` 是本机运行状态目录，里面有 token、session、history 和插件安装物；它只留在本机，不会提交到 git。

## 用户提供信息的原则

为了让 agent 稳定工作，用户请求里最好明确给出：

- run 目录或 HDF5 文件的绝对路径。
- observable / parameter 名称，或明确 dataset key。
- 想做直接读取、误差估计、脚本 dry-run、真实执行还是诊断解释。
- SLURM job id 或想查询的时间范围。
- 同步远端产物时的 remote host、remote path 和允许同步范围。

路径和执行范围越明确，agent 越能给出可审计、可复现的结果。
