# Update Mechanism

本文档说明 DQMC agent 的“眼睛”和底层脚本更新后，当前 hands/agent 应如何感知变化、如何验证、何时需要重启。

## `registry.yaml`

`registry.yaml` 是 hands 层的运行时事实源。当前实现中，`dqmc_tools.registry.load_registry()` 每次调用都会从磁盘读取 registry 文件；没有 registry 缓存。

默认路径：

```bash
registry.yaml
```

覆盖方式：

```bash
export DQMC_REGISTRY_PATH=/path/to/registry.yaml
```

或者在 MCP/tool 调用参数中传入 `registry_path`。

更新流程：

1. 编辑 `registry.yaml`。
2. 运行 registry 相关测试。
3. 如果只是 registry 内容更新，下一次 `resolve_registry_entry()`、`read_registered_quantity()`、`estimate_registered_observable()` 或 `summarize_run()` 调用会读取新文件内容。
4. 如果 registry schema 改变，同步更新 `dqmc_tools/registry.py`、HDF5 读取逻辑和测试。

推荐验证：

```bash
.venv/bin/python -m pytest tests/test_registry.py tests/test_mcp_server.py
```

当前测试覆盖：

- 显式 `registry_path` 文件修改后，下一次 resolve 读取新内容。
- `DQMC_REGISTRY_PATH` 环境变量覆盖路径后，文件修改会被下一次调用读取。
- MCP server 在同一个 server 实例内通过 `registry_path` 读取更新后的 registry。

## `dqmc-dev` 脚本

`dqmc-dev` 根目录由 Codex 用户级 `~/.codex/config.toml` 中的 MCP env 决定：

```toml
[mcp_servers.dqmc-hands.env]
DQMC_DEV_ROOT = "/Users/phoenixm/Desktop/dqmc-dev"
```

`DQMC_DEV_ROOT` 缺失、为空或路径不存在时，相关工具会报 `configuration_error`，不会回退到硬编码路径。

script adapter catalog 当前维护在：

```bash
dqmc_tools/scripts/builtin_catalog.py
```

adapter catalog 是 hands 层对 dqmc-dev 脚本的白名单和执行契约，包含：

- `script_id`
- 脚本路径
- category / mode
- 参数 schema
- required input preflight
- output patterns
- parser id
- approval policy

底层 dqmc-dev 脚本更新后，adapter catalog 需要通过 audit 检查是否仍然匹配。

推荐验证：

```bash
.venv/bin/python scripts/audit_script_adapters.py
```

输出 JSON：

```bash
.venv/bin/python scripts/audit_script_adapters.py --json
```

audit 当前检查：

- adapter path 是否存在且是文件。
- Python/bash/direct launcher 是否可用。
- category 和 mode 是否是已知值。
- `args_schema.properties` 是否是 mapping。
- required 参数是否都声明在 properties 中。
- path role 是否是已知值。
- required input template 是否只引用已知参数。
- output pattern template 是否只引用已知参数。
- parser id 是否是已知 parser。
- script id 是否唯一。
- 脚本 size、mtime、SHA-256 fingerprint。

更新流程：

1. 更新 `DQMC_DEV_ROOT` 指向的 `dqmc-dev` checkout。
2. 运行 adapter audit。
3. 如果 audit 失败，按报告同步 `dqmc_tools/scripts/builtin_catalog.py`。
4. 如果底层脚本 CLI 变化，同步 adapter 的 `args_schema`。
5. 如果输入文件约束变化，同步 `required_inputs`。
6. 如果输出文件名或目录变化，同步 `output_patterns` 和 parser。
7. 更新或新增 tests。
8. 重启 MCP server。
9. 跑完整测试。

推荐完整验证：

```bash
.venv/bin/python scripts/audit_script_adapters.py
.venv/bin/python -m pytest
```

## `code_map.md`

`code_map.md` 是 dqmc-dev 能力地图和人工知识源。当前 hands 层不会在运行时读取它。

更新流程：

1. 编辑 `code_map.md`。
2. 对照更新内容检查 `dqmc_tools/scripts/builtin_catalog.py` 是否需要同步。
3. 如果新增或修改脚本能力，补 adapter audit 和对应 tests。
4. 需要 agent 检索时，重新生成或刷新 agent 的知识索引。

## `diagnostics_playbook.md`

`diagnostics_playbook.md` 是诊断经验知识源。当前 hands 层不会在运行时读取它，也不会自动执行其中的物理判断。

更新流程：

1. 编辑 `diagnostics_playbook.md`。
2. 刷新 agent 知识索引或后续的 structured diagnostic registry。
3. 如果新增规则需要工具层支持，先定义工具返回的事实字段，再由 agent 层应用诊断规则。

## 重启规则

需要重启 MCP server：

- 修改 `dqmc_tools/` 代码。
- 修改 `dqmc_mcp_server.py`。
- 修改 `dqmc_tools/scripts/builtin_catalog.py`。
- 修改 adapter parser、path policy、approval policy。

通常不需要重启 MCP server：

- 只修改 `registry.yaml` 内容。
- 只通过 `DQMC_REGISTRY_PATH` 或 MCP 参数切换 registry 文件。
- 只修改用户提供的 HDF5/run 数据目录。

需要刷新 agent 知识索引：

- 修改 `code_map.md`。
- 修改 `diagnostics_playbook.md`。
- 修改面向 agent 检索的 semantic/io/repo index。
