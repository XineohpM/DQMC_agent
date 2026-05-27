# DQMC Hands 重写技术设计

状态：草案，等待审阅后再实现。

## 设计原则

1. 手只执行动作、返回事实；物理解释由上游 agent 结合三份“眼睛”完成。
2. MCP adapter 不拥有领域逻辑；真实逻辑在普通 Python 包里。
3. 已有 `dqmc-dev/util` 和 `dqmc-dev/scripts` 是主要执行资产；手层负责安全封装、参数契约、输出解析和 provenance。
4. 所有工具默认 bounded；原始数据只读，派生文件和 workflow 文件修改必须显式受控。
5. 新增抽象只服务于稳定契约，不复制脚本内部物理/统计逻辑。
6. 任何白名单脚本的真实执行都需要用户本次显式同意；preflight 和 dry-run 不等于同意执行。

## 包结构

建议从干净结构重建：

```text
dqmc_tools/
  __init__.py
  config.py
  errors.py
  paths.py
  registry.py
  hdf5.py
  runs.py
  scripts/
    __init__.py
    definitions.py
    runner.py
    parsers.py
    builtin_catalog.py
  slurm.py
  manifest.py
dqmc_mcp_server.py
tests/
```

其中：

- `registry.py`：读取并解析 `registry.yaml` 的真实字段，不引入不存在的 registry 字段。
- `hdf5.py`：只做 `DQMC_DEV_ROOT` 指向的 `util/util.py` 中 `load()`、`load_file()`、`load_firstfile()`、`jackknife()`、`jackknife_noniid()` 的安全包装和 JSON-safe 汇总。
- `runs.py`：只对用户显式输入的目录做 bounded summary 和 metadata aggregation；不做 run discovery。
- `scripts/`：脚本白名单、参数 schema、subprocess runner、执行前同意检查、输出 manifest、解析器。
- `slurm.py`：只读 `squeue`。
- `dqmc_mcp_server.py`：仅注册 MCP tools 并转发到 `dqmc_tools`。

## 配置

环境变量：

| 变量 | 用途 |
| --- | --- |
| `DQMC_ALLOWED_ROOTS` | 原始数据读取白名单，使用 `os.pathsep` 分隔 |
| `DQMC_OUTPUT_ROOT` | 派生文件输出根目录；未设置时默认当前工程 `outputs/` |
| `DQMC_REGISTRY_PATH` | 可选 registry override |
| `DQMC_SCRIPT_TIMEOUT_SECONDS` | 默认脚本超时时间 |

`dqmc-dev` 根目录来自必填环境变量 `DQMC_DEV_ROOT`。调用参数可以覆盖 output 子路径和 allowed roots，但仍必须通过同样的安全检查。

## Registry 设计

### 真实输入格式

`registry.yaml` 中 observable 的主要字段是：

```yaml
id: density
aliases: [...]
physics: ...
code:
  measurement:
    file: meas.c
    function: measure_eqlt()
    variable: m->density
  generation:
    file: gen_1band_unified_hub.py
    variable: meas_eqlt/density
    flags: [...]
requirements: ...
normalization: ...
units: ...
data_layout: ...
```

parameter 的主要字段是：

```yaml
id: chemical_potential
aliases: [...]
physics: ...
code:
  generation:
    file: gen_1band_unified_hub.py
    variable: mu
type: float
required: true
default: null
units: ...
normalization: ...
```

### Runtime view

`registry.py` 返回原始 entry 的深拷贝，并只添加少量运行时辅助字段：

```python
{
  "entry_type": "observable" | "parameter",
  "id": "...",
  "aliases": [...],
  "dataset_key": "meas_eqlt/density",  # 从 code.generation.variable 派生
  "source_entry": {...}                # registry 原条目
}
```

`dataset_key` 是运行时派生字段，不是 registry 原字段。文档和代码都不应假装 registry 里存在其他标识体系。

### Resolve 规则

匹配顺序：

1. exact `id`
2. exact alias
3. exact `code.generation.variable`
4. `code.generation.variable` 的尾部

多个匹配必须报 `registry_ambiguous`，返回候选条目的 `id`、aliases、`code.generation.variable` 和 `entry_type`，不猜。

## HDF5 设计

HDF5 数值读取必须复用 `dqmc-dev` 已有工具：

- `util/util.py::load_file(path, *dataset_keys)`
- `util/util.py::load_firstfile(path, *dataset_keys)`
- `util/util.py::load(path, *dataset_keys)`
- `util/util.py::jackknife()`
- `util/util.py::jackknife_noniid()`

手层只负责路径安全、registry 解析、bounded summary、JSON-safe 转换和 provenance。不直接使用 `h5py`，不做 HDF5 tree 枚举，不新增读取语义。

### `inspect_hdf5`

这个名称保留给 MCP 兼容，但语义改为“对明确给定的 dataset keys 做 util.py wrapper inspection”：

输入：

- `path`：单个 `.h5` 文件，或目录。
- `dataset_keys`：明确要读取的 dataset key 列表，例如 `["meas_eqlt/density", "meas_eqlt/sign"]`。
- `mode`：`file`、`firstfile`、`directory`，分别对应 `load_file()`、`load_firstfile()`、`load()`。
- `max_items`
- `allowed_roots`

输出：

- 每个 requested dataset 的 shape、dtype、bounded preview、size、numeric summary。
- 使用的 util.py function 名称。
- 失败项的错误事实。

它不列出文件里有哪些 group/dataset，也不做未知结构发现。

### `read_dataset`

`read_dataset(path, dataset_key, mode="file")` 是 `inspect_hdf5` 的单 key 版本：

- `mode="file"` 调 `load_file()`。
- `mode="firstfile"` 调 `load_firstfile()`。
- `mode="directory"` 调 `load()`。

返回 bounded summary。它不返回误差。

### `read_registered_quantity`

流程：

1. `resolve_registry_entry(name)`。
2. 从 `code.generation.variable` 得到 `dataset_key`。
3. 用 `load_file()`、`load_firstfile()` 或 `load()` 读取事实。
4. 提取 metadata facts 时同样使用明确 dataset keys 和 util.py。
5. 返回 registry entry、dataset facts、metadata facts。

单个文件没有误差估计；一组文件读取也只是返回 raw per-file/bin array summary，除非调用 jackknife 估计工具。

### `estimate_registered_observable`

这个工具负责 observable 的组误差估计：

输入：

- `directory`：同一组 `.h5` 文件所在目录。
- `observable_name`：registry 的 `id` 或 alias。
- `estimator`：`jackknife` 或 `jackknife_noniid`。
- `dataset_keys_override`：可选，用于脚本或 registry 不足时显式给出 numerator/sign/sample keys。
- `max_items`

默认流程：

1. resolve registry entry。
2. 用 entry 的 `code.generation.variable` 和必要 normalization facts 确定要读取的 dataset key。
3. 用 `util.load(directory + "/", ...)` 读取所有 `.h5` 文件，第一维作为 bin/file 维。
4. 使用 `util.jackknife()` 或 `util.jackknife_noniid()` 返回 `{mean, error}`。
5. 返回使用的 function、输入文件数量、dataset keys、shape 和 bounded preview。

这个工具仍然只返回统计事实，不判断误差是否足够小。

## Run 设计

不实现 `list_runs`。agent 不扫描 scratch 根目录，不根据文件名自行发现需要处理的 run。所有 run 目录、T 目录或脚本输入目录都必须由用户显式给出。

### `summarize_run`

对用户给定目录做 bounded 摘要：

- 统计目录内 `.h5` 文件数量。
- 对少量 metadata keys 调 `load_firstfile()`。
- 对 registry 中的关键 entry，可按 `code.generation.variable` 尝试读取第一份文件，返回 available/missing 事实。
- sibling log facts：是否存在、tail、completion markers。

复杂 completion 扫描仍优先走 `check_h5_completion` 脚本 adapter，并且真实执行前需要用户同意。

## 脚本白名单设计

### `ScriptDefinition`

```python
@dataclass(frozen=True)
class ScriptDefinition:
    script_id: str
    description: str
    category: str
    mode: str
    path: Path
    args_schema: dict
    default_timeout_seconds: int
    parser_id: str | None
    output_patterns: list[str]
    required_inputs: list[InputRequirement]
    requires_output_root: bool
    approval_required: bool
    notes: list[str]
```

`approval_required` 对所有白名单脚本都必须是 `True`。dry-run、describe、preflight 不算脚本执行，可以不要求 approval。

`InputRequirement` 描述脚本运行前必须存在的输入：

```python
@dataclass(frozen=True)
class InputRequirement:
    name: str
    kind: str              # hdf5, npy, npz, directory, file, glob
    path_template: str
    required: bool = True
    shape_hint: tuple[int | None, ...] | None = None
```

典型例子：`plot_JNJN` 不直接读原始 HDF5，它要求 `params.path` 下已有 `JNJN_xx_perbin.npy` 或指定的 per-bin current correlator 文件；`conductivity_plot` / `resistivity_plot` 要求 MaxEnt 输出目录下已有 `omega.npy` 和谱函数相关 `.npy`。

### `run_script_adapter`

输入：

- `script_id`
- `params`
- `cwd`
- `allowed_roots`
- `output_root`
- `timeout_seconds`
- `dry_run`
- `user_confirmation`

流程：

1. 查白名单。
2. 校验 `params`，拒绝未知参数。
3. resolve 所有 input/output path。
4. 执行 `required_inputs` preflight：检查文件/目录/glob、后缀、必要 shape hint。preflight 失败时不启动脚本，返回缺失输入事实。
5. 构造 argv list，不使用 shell。
6. 若 `dry_run=true`，只返回 command/provenance/preflight，不执行。
7. 若 `dry_run=false`，要求 `user_confirmation.approved == true`，且包含本次用户同意文本；否则返回 `user_approval_required`。
8. 执行并捕获 stdout/stderr。
9. 根据 `output_patterns` 和 parser 生成 manifest。

输出：

```python
{
  "ok": true,
  "script_id": "check_warm",
  "command": [...],
  "cwd": "...",
  "user_confirmation": {"approved": true, "text": "..."},
  "returncode": 0,
  "stdout_tail": "...",
  "stderr_tail": "...",
  "output_files": [...],
  "parsed_outputs": {...},
  "provenance": {...}
}
```

### 第一版脚本目录

`builtin_catalog.py` 初始注册：

- `gen_beta_scan`
- `gen_beta_mu_scan`
- `gen_1band_unified_hub`
- `dqmc_info`
- `dqmc_summary`
- `print_n`
- `check_h5_completion`
- `check_warm`
- `extract_energy_perfile`
- `extract_local_moment`
- `extract_1_particle_local_g`
- `extract_perbin_jj`
- `make_bootstrap`
- `save_boot_stats`
- `plot_double_occ`
- `plot_charge_order`
- `plot_JNJN`
- `conductivity_plot`
- `resistivity_proxy`
- `resistivity_plot`
- `run_maxent`
- `run_maxent_anneal`
- `run_maxent_phoenix`
- `plot_dos`

说明：`gen_beta_mu_scan` 留在 input generation 内，因为第一版允许真实生成输入文件；best-mu 选择、compressibility 绘图、coarse/fine mu-tuning 目录工作流不进入第一版。

第一版暂不注册：

- `check_sum_rule`
- `plot_compressibility_from_best_mu`
- `plot_compressibility_from_n_mu`
- `get_n_from_best_mu`
- `get_mu`
- `scripts/mu_tuning_*`

`workflow` 类脚本第一版允许登记并运行：

- `util/push.py`
- `scripts/run_stack_owners.sh`
- `scripts/run_stack_simes.sh`
- `scripts/multi_dir_push_stack.sh`

提交作业类脚本第一版不注册：

- `scripts/multi_dir_submit_sbatch.sh`

workflow-mutating 工具必须在 schema 中明确哪些文件会被改动，并通过 preflight 确认 stack 文件路径、相对路径列表和 cwd 都在允许范围内。提交/取消 SLURM job 仍不允许。

## MCP 设计

MCP 注册工具：

| MCP tool | 内部函数 | 说明 |
| --- | --- | --- |
| `summarize_run` | `runs.summarize_run` | 摘要用户给定目录 |
| `inspect_hdf5` | `hdf5.inspect_hdf5` | 对明确 dataset keys 调 util.py wrapper |
| `read_dataset` | `hdf5.read_dataset` | 读取一个明确 dataset key 的 bounded summary |
| `resolve_registry_entry` | `registry.resolve_entry` | 按 registry 真实字段解析 observable/parameter |
| `read_registered_quantity` | `hdf5.read_registered_quantity` | 按 registry 的 `code.generation.variable` 读取事实 |
| `estimate_registered_observable` | `hdf5.estimate_registered_observable` | 对一组 `.h5` 文件做 jackknife 误差估计 |
| `list_script_adapters` | `scripts.list_scripts` | 列白名单脚本 |
| `describe_script_adapter` | `scripts.describe_script` | 看脚本参数契约和 preflight |
| `run_script_adapter` | `scripts.run_script` | 运行白名单脚本；真实执行必须带本次用户同意 |
| `query_slurm` | `slurm.query_slurm` | 只读队列查询 |

MCP description 必须包含：

- 何时使用。
- 何时不要使用。
- 参数示例。
- 返回值结构。
- 安全限制。
- 对 `run_script_adapter`，明确要求 agent 先把命令和读写路径展示给用户，并获得本次同意。

## 现有实现差距

当前工程已有的 `dqmc_tools` 基础方向正确，但重写时需要补齐：

- registry 当前包装层引入了不存在于 `registry.yaml` 的派生标识；重写后只使用真实字段和 `dataset_key` 运行时辅助字段。
- analysis registry 为空，缺少对 `dqmc-dev/scripts` 的白名单调度。
- MCP tool 面缺少 `estimate_registered_observable`、脚本 catalog/runner、脚本执行同意检查。
- run summary 目前还带有 run discovery 思路；重写后只处理用户显式输入目录。
- HDF5 读取目前直接用 `h5py` 做结构检查和数值读取；重写后只做 `util.py` wrapper，不新增 tree inspection 逻辑。
- 误差目前被描述成单文件可读事实；重写后误差只来自多文件 jackknife 估计或后处理脚本产物。
- provenance、output manifest、script timeout、preflight 还不完整。

## 安全边界

- `read_only`：只读数据或队列事实，例如 `query_slurm`；若是脚本，真实执行仍需要用户同意。
- `writes_output`：要求 output root，例如 `check_warm`、plot、extract、bootstrap、MaxEnt；真实执行需要用户同意。
- `mutates_workflow_files`：第一版允许，但必须显式登记输入、输出和被修改文件，例如 `push.py`、`--push_stack`；真实执行需要用户同意。
- `submits_jobs`：第一版不注册，例如 `multi_dir_submit_sbatch.sh`。

所有等级都记录 provenance。

## 测试设计

单元测试：

- registry load/resolve/list ambiguity，且不出现不存在的 registry 字段假设。
- path safety。
- `util.py` wrapper：`load_file()`、`load_firstfile()`、`load()`。
- `jackknife()` / `jackknife_noniid()` 组误差估计。
- summarize user-provided run。
- script schema validation。
- script input preflight for derived-data scripts。
- script runner dry-run、timeout、stdout/stderr、manifest、缺少用户同意。
- SLURM unavailable/fallback。
- MCP registration/forwarding。

集成测试：

- 小型 HDF5 fixture 验证 `read_registered_quantity("density")` 读取 registry `id: density` 对应的 `code.generation.variable`。
- 多 HDF5 fixture 验证 `estimate_registered_observable("density")` 用 jackknife 返回 mean/error。
- fake script 写 TSV/NPY/PNG，验证 parser 和 output manifest。
- `dqmc-dev/scripts/gen_beta_scan.py --dry_run` smoke test 和真实 input generation 临时 output root 测试。
- `run_script_adapter` 没有用户同意时拒绝执行。
- `plot_JNJN.py` 缺少 `JNJN_xx_perbin.npy` 时 preflight 失败，不启动脚本。

## 迁移策略

- 保留公共函数名兼容：`inspect_hdf5`、`read_observable`、`resolve_observable`、`query_slurm`。
- 新增更准确名称：`resolve_registry_entry`、`read_registered_quantity`、`estimate_registered_observable`。
- `read_observable` 可作为 `read_registered_quantity(entry_type="observable")` 的兼容 wrapper，但返回字段必须基于 registry 真实格式。
- 旧 tests 通过后，再增加脚本 runner 和 jackknife tests。
