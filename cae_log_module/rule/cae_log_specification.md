# CAE 日志编写规范

版本：2026-06-08  
适用范围：`log_module` 中的 C++ `cae_logger`、JSONL 分析日志、GoAccess 输入日志、Python 校验/摘要/告警工具，以及后续接入的 CAE 业务模块。

## 1. 目标

本规范用于统一 CAE 工业软件场景下的日志内容、字段、等级、采样、隐私和分析语义，使日志同时满足：

- 开发定位：能快速回答“哪个模块、哪个阶段、哪个对象、哪个动作、为什么失败”。
- 业务追溯：能还原一次 CAE 工作流的几何、网格、求解、后处理关键节点。
- 性能分析：能可靠统计真实业务耗时、资源使用、迭代收敛和导出耗时。
- 分布式排障：能在多进程、多线程、多节点、MPI rank 间合并和关联。
- 自动分析：能被 `python -m tools.cae validate`、`python -m tools.cae tail`、`python -m tools.cae summary`、GoAccess 和后续告警工具稳定消费。

核心原则：日志是结构化事件，不是调试时随手打印的文本。只有真实业务生命周期才能产生 `span` 耗时。

## 2. 参考来源与取舍

本规范综合了以下公开规范和 CAE 工具实践，并按本仓库当前 Patch 3/Patch 4 基线裁剪：

- OpenHarmony/HiLog 日志指南：强调合适等级、主导模块记录、避免重复和高频正常路径、隐私标记、限流、who-does-what、状态变化和参数格式。
- HiLog API：`{public}` 明文、`{private}` 默认脱敏的隐私模型。本项目暂未实现格式级隐私标签，因此要求调用方在进入日志 API 前完成脱敏。
- OpenTelemetry Logs Data Model：采用 severity、trace/span 关联、body/attributes 的结构化思路；本项目字段对应为 `level`、`trace_id`、`span_id`、`message`、`metrics`。
- OWASP Logging Cheat Sheet：每条关键日志应覆盖 when、where、who、what；本项目映射为时间、source/component/stage/action、session/thread/node/rank、message/result/reason/object/metrics。
- NIST SP 800-92：日志管理需要覆盖生成、传输、存储、分析、处置和保留策略。
- JSON Lines：分析日志使用 UTF-8，每行一个完整 JSON 值，便于流式消费和单行隔离。
- OpenFOAM：求解日志和 `solverInfo` 关注时间步、残差、初始/最终残差、迭代次数、收敛标志、Courant 数、运行时间。
- SU2：区分屏幕输出、history 输出和体/面结果输出；history 文件记录收敛历史，可定制字段和输出频率。
- Ansys Fluent：transcript 记录会话输入/输出、开始/结束/总时间、迭代墙钟时间；residual、force、surface、volume 等 monitor 用于动态观察收敛。
- Code_Aster：`.mess` 和消息系统面向诊断，消息带等级/代码，能提取错误消息并定位命令。

## 3. 总体规则

### 3.1 必须结构化

面向分析的日志必须写入 JSONL，业务字段必须放在独立字段或 `metrics` 中，不得只嵌入 `message`。

正确：

```cpp
CAE_LOG(Info)
    .module("Solver")
    .stage("Iteration")
    .action("nonlinear_step")
    .metric("iteration", static_cast<std::int64_t>(42))
    .metric("residual", 1.2e-4)
    .metric("courant", 0.81)
    .message("Nonlinear iteration completed.")
    .submit();
```

不推荐：

```cpp
CAE_LOG_INFO("Solver")
    .message("iter=42 residual=1.2e-4 courant=0.81")
    .submit();
```

后者只能人工阅读，摘要工具难以稳定提取。

### 3.2 一条日志只描述一个事件

一条日志应表达一个业务事实：对象、动作、结果、原因、指标。不要把多个阶段、多个对象、多个结果塞入同一条日志。

### 3.3 关键路径由主导模块记录

同一业务节点只由主导模块记录一次。被调用的底层函数不应重复记录相同成功日志，可在错误分支或 DEBUG 诊断中补充局部信息。

### 3.4 成功可摘要，异常要具体

成功路径记录开始、结束、摘要和关键里程碑。异常路径必须记录：

- `result="failed"` 或适当结果。
- `reason` 使用稳定枚举。
- 失败对象的安全标识。
- 可执行的处置方向，但不要泄露敏感数据。

### 3.5 高频路径默认采样或聚合

生产环境不得在高频正常路径逐项刷屏。几何体、网格单元、粒子、节点、积分点、每帧渲染、内部锁轮询等高频事件必须聚合、采样或仅在异常时打印。

允许逐步记录的场景：

- 求解迭代历史是业务证据，且规模受控。
- 已启用 DEBUG/TRACE 或诊断开关。
- 发生阈值跨越、收敛停滞、发散、重试、降阶、自动修复等异常。

### 3.6 日志不能改变业务行为

日志代码不得调用有副作用的业务接口，不得触发求解、读写模型、改变状态机或消耗大量内存生成消息。高成本字符串、数组摘要、哈希计算应在等级开关或采样策略判断后执行。

### 3.7 默认使用英文运行时消息

本项目当前日志样例和报告链路以英文消息为主。运行时 `message` 默认使用简洁英文，便于跨团队、工具和第三方 CAE 术语一致；中文解释应放在文档、报告 UI 或外部字典中。

## 4. 编码角度规范

### 4.1 API 选择

优先级如下：

1. `CAE_LOG(level)` Builder API：用于业务关键节点、可分析指标、失败原因、对象和结果。
2. `cae::TaskScope`：用于真实业务生命周期，自动生成 `span`、`trace_id`、`span_id`、`parent_span_id` 和 `duration_us`。
3. `CAE_LOG_*_DUR`：用于调用方已有明确耗时的事件，但必须确保耗时来自真实测量。
4. `CAE_LOG_INFO/WARN/ERROR` 等链式文本宏：只用于简单人工可读补充，不承载核心分析字段。
5. `TRACE/DEBUG`：仅用于开发诊断或临时排障，默认不作为业务报表依据。

### 4.2 point 与 span

`event_kind` 必须符合下列语义：

| 类型 | 语义 | `duration_us` | 典型来源 |
| --- | --- | --- | --- |
| `point` | 某一时刻发生的事件 | 必须为 `0` | 状态变化、阈值告警、迭代样本、对象创建 |
| `span` | 有开始和结束的业务生命周期 | 必须 `> 0` | 工作流、几何导入、网格生成、求解循环、导出 |

禁止为了让报表好看而给 point 事件硬填耗时。禁止把无法测量的文本日志包装成 span。

### 4.3 等级定义

| 等级 | 使用场景 | CAE 示例 |
| --- | --- | --- |
| `TRACE` | 极细粒度调试，默认关闭 | 单元级装配、每次内部插值、锁竞争细节 |
| `DEBUG` | 开发定位，默认可关闭 | 每批 body 的 bbox、局部网格质量样本、分区交换细节 |
| `INFO` | 关键业务节点和正常摘要 | 工作流开始/结束、导入完成、网格摘要、收敛摘要、导出完成 |
| `WARN` | 可恢复但需要关注 | sliver faces、局部高 skewness、残差平台、缺列但可继续 |
| `ERROR` | 当前动作失败或结果不可用 | 读文件失败、格式不支持、导出失败、求解未收敛且停止 |
| `CRITICAL` | 进程即将崩溃、数据损坏或结果可信性丧失 | 崩溃前抢救日志、数据库/结果文件损坏、许可证/资源导致全局中止 |

等级必须匹配影响范围。不要用 ERROR 表示普通业务拒绝，也不要用 INFO 隐藏会导致结果缺失的问题。

### 4.4 追踪上下文

每条结构化日志必须能参与链路关联：

- `trace_id`：一次 case/session/workflow 的主关联键，32 位小写十六进制。
- `span_id`：当前事件唯一 span 标识，16 位小写十六进制。
- `parent_span_id`：父生命周期，可为空。
- `session`：业务会话或进程会话，例如 `Proc_1`、`Case_001`。
- `thread_name`：重要线程必须设置可读名称。
- `node_id`：分布式节点标识。
- `mpi_rank`：MPI rank，可为空。
- `sequence`：单进程内单调递增，用于同时间戳排序和断点排查。

跨线程继续同一工作流时，必须显式传递 `trace_id`。跨进程/节点合并时，不得仅依赖本地时间排序。

### 4.5 字段命名

- 字段名使用小写 `snake_case`。
- 单位写入字段名，例如 `duration_us`、`memory_mb`、`vram_mb`、`wall_time_s`。
- 布尔指标使用明确含义，例如 `converged=true`。
- 枚举值使用小写 `snake_case`，例如 `unsupported_format`、`disk_full`、`residual_plateau`。
- `component` 使用模块层级名，例如 `PostProcess.Output`。
- `stage` 使用业务阶段名，例如 `Geometry`、`Mesh`、`Iteration`。
- `action` 使用稳定动作名，例如 `reader_open`、`nonlinear_step`、`export`。

### 4.6 当前 JSONL schema

当前结构化 JSONL 每行必须包含下列字段。

必需字符串字段：

- `timestamp`
- `date`
- `time`
- `source`
- `component`
- `stage`
- `action`
- `level`
- `message`
- `event_kind`
- `trace_id`
- `span_id`
- `session`
- `thread_name`

必需整数字段：

- `duration_us`
- `size`
- `sequence`

可空字段：

- `parent_span_id`
- `object_type`
- `object_name`
- `result`
- `reason`
- `mpi_rank`

可选/可为空字符串字段：

- `node_id`

对象字段：

- `metrics`

语义约束：

- `timestamp` 使用本地 ISO 时间并带毫秒，例如 `2026-06-08T13:59:33.456`。
- `event_kind="point"` 时，`duration_us == 0`。
- `event_kind="span"` 时，`duration_us > 0`。
- `trace_id` 为 32 位小写十六进制。
- `span_id` 和 `parent_span_id` 为 16 位小写十六进制；`parent_span_id` 可为 `null`。
- `metrics` 必须是 JSON object，值只能是数字、布尔或字符串。
- `date` 和 `time` 保留用于 GoAccess 稳定解析；结构化主时间字段是 `timestamp`。

### 4.7 字段与变量字典

所有字段和变量必须有稳定含义。新增字段或指标时，必须按本节格式补充解释。

#### 4.7.1 JSONL 顶层字段

| 字段 | 类型 | 是否必填 | 含义 | 示例/约束 |
| --- | --- | --- | --- | --- |
| `timestamp` | string | 是 | 事件发生时刻，是结构化分析的主时间字段。 | 本地 ISO 时间，毫秒精度，例如 `2026-06-08T13:59:33.456`。 |
| `date` | string | 是 | 事件日期，主要用于 GoAccess 兼容解析。 | `YYYY-MM-DD`，例如 `2026-06-08`。 |
| `time` | string | 是 | 事件时间，主要用于 GoAccess 兼容解析。 | `HH:MM:SS`，例如 `13:59:33`。 |
| `source` | string | 是 | 事件来源，标识进程和线程等运行实体。 | `pid:13068/tid:15992`。 |
| `component` | string | 是 | 产生日志的模块或子模块。 | `Solver`、`PostProcess.Output`。 |
| `stage` | string | 是 | 业务阶段，用于横向聚合一次工作流中的阶段。 | `Geometry`、`Mesh`、`Iteration`、`Workflow`。 |
| `action` | string | 是 | 稳定动作名，用于统计“发生了什么动作”。 | `reader_open`、`nonlinear_step`、`export`。 |
| `level` | string | 是 | 日志等级，表达事件影响范围和紧急程度。 | `TRACE`、`DEBUG`、`INFO`、`WARN`、`ERROR`、`CRITICAL`。 |
| `message` | string | 是 | 面向人的简短说明。机器分析所需数据不得只放在这里。 | `Nonlinear iteration completed.` |
| `event_kind` | string | 是 | 事件类型，决定 `duration_us` 语义。 | `point` 表示瞬时事件；`span` 表示生命周期事件。 |
| `duration_us` | integer | 是 | 事件耗时，单位微秒。 | `point` 必须为 `0`；`span` 必须大于 `0`。 |
| `size` | integer | 是 | 当前实现中为 `message` 的字符长度，用于 GoAccess size 字段和粗略体量统计。 | 非负整数。 |
| `sequence` | integer | 是 | 单进程内递增序号，用于同时间戳排序和缺口排查。 | 从 1 开始递增。 |
| `trace_id` | string | 是 | 一次 workflow/case/session 的关联 ID。 | 32 位小写十六进制。 |
| `span_id` | string | 是 | 当前事件或生命周期节点的 ID。 | 16 位小写十六进制。 |
| `parent_span_id` | string/null | 可空 | 父生命周期节点 ID，用于构建调用树。 | `null` 或 16 位小写十六进制。 |
| `session` | string | 是 | 业务会话、进程会话或 case 运行实例。 | `Proc_1`、`Case_001`。 |
| `thread_name` | string | 是 | 业务线程名或线程 ID。 | `MainThread`、`SolverWorker`。 |
| `object_type` | string/null | 可空 | 事件涉及的对象类别。 | `file`、`reader`、`region`、`filter`。 |
| `object_name` | string/null | 可空 | 事件涉及的对象标识，应脱敏。 | `result.csv`、`region_03`。 |
| `result` | string/null | 可空 | 动作结果，推荐使用稳定枚举。 | `completed`、`failed`、`skipped`。 |
| `reason` | string/null | 可空 | 结果原因，尤其用于 WARN/ERROR/降级事件。 | `disk_full`、`unsupported_format`。 |
| `node_id` | string | 可选/可空 | 分布式节点或机器标识。 | `local-workstation`、`node-a`。 |
| `mpi_rank` | integer/null | 可空 | MPI rank 编号，用于并行求解和多进程合并。 | `0`、`1`、`null`。 |
| `metrics` | object | 是 | 可聚合的指标集合。值只能是数字、布尔或字符串。 | `{"residual":0.001,"iteration":42}`。 |

#### 4.7.2 核心上下文变量

| 变量 | 含义 | 生产者 | 使用方式 |
| --- | --- | --- | --- |
| `module` | 调用日志 API 时传入的模块名，最终进入 `component`。 | 业务代码。 | 按所属业务模块填写，子模块用点分层级。 |
| `stage` | 业务阶段名。 | Builder API 或 `TaskScope`。 | 用于阶段统计，必须稳定，不要放动态编号。 |
| `action` | 动作名。 | Builder API 或 `TaskScope`。 | 用于统计和告警规则，必须稳定，不要放对象名。 |
| `session_id` | 会话 ID，最终进入 `session`。 | `cae::set_session()`。 | 每次 case、进程或任务实例设置一次。 |
| `thread_name` | 线程名。 | `cae::set_thread_name()` 或默认线程 ID。 | 跨线程工作流必须设置可读名称。 |
| `node_id` | 节点 ID。 | `cae::set_node_id()` 或默认探测。 | 多节点/HPC 环境必须设置。 |
| `mpi_rank` | MPI rank。 | `cae::set_mpi_rank()`。 | 多 rank 求解必须设置；非 MPI 可为空。 |
| `trace_id` | 工作流关联 ID。 | `TaskScope` 自动生成或显式传入。 | 跨线程/跨阶段传递，用于聚合一次工作流。 |
| `span_id` | 当前 span 或事件 ID。 | logger 自动生成。 | 用于唯一定位事件和构建父子关系。 |
| `parent_span_id` | 父 span ID。 | `TaskScope` 上下文栈。 | 用于还原嵌套业务生命周期。 |

#### 4.7.3 配置变量

| 变量 | 含义 | 推荐值/约束 |
| --- | --- | --- |
| `thread_model` | 线程模型，决定 logger 是否按多线程安全路径运行。 | CAE 常规桌面/HPC 程序使用 `MT`。 |
| `process_model` | 进程模型，决定多进程写日志时的文件隔离策略。 | 多进程 demo/HPC 使用 `MP`。 |
| `io_mode` | I/O 模式。 | 性能敏感场景使用 `Async`；排障可临时使用 `Sync`。 |
| `truncate_file` | 启动时是否覆盖同名日志文件。 | 默认 `false`，避免误删历史证据。 |
| `async_queue_size` | 异步日志队列容量。 | 建议为 2 的幂；过小会增加丢日志/阻塞风险。 |
| `async_thread_count` | 异步日志后台线程数。 | 默认 `1`；高吞吐需基准测试后调整。 |
| `enable_console` | 是否输出控制台日志。 | 本地调试可开；批处理/HPC 可关。 |
| `enable_text_log` | 是否输出传统文本日志。 | 保留给人工排障和兼容工具。 |
| `enable_analysis_log` | 是否输出 JSONL 分析日志。 | 分析链路必须开启。 |
| `log_dir` | 日志目录。 | 默认 `logs`；构建产物可用 `build/Debug/logs`。 |
| `analysis_log_name` | JSONL 分析日志文件名。 | 默认 `cae_events.jsonl`。 |
| `global_pattern` | 文本日志格式。 | 不影响 JSONL schema，但影响人工文本日志。 |
| `min_level` | 最低输出等级。 | 生产常用 `INFO`；排障临时降到 `DEBUG/TRACE`。 |
| `flush_level` | 达到该等级时触发 flush。 | 默认不低于 `ERROR`。 |

#### 4.7.4 `result` 枚举

| 值 | 含义 | 使用场景 |
| --- | --- | --- |
| `started` | 动作已开始。 | 长任务入口、导入开始、导出开始。 |
| `completed` | 动作正常完成。 | 工作流结束、导入完成、求解完成。 |
| `applied` | 配置、参数或变更已应用。 | filter 属性、显示状态、边界条件应用。 |
| `skipped` | 动作被跳过，但整体可继续。 | 输入缺少可选字段、无可处理对象。 |
| `retrying` | 动作失败后正在重试。 | 文件写入重试、网络/许可证重试。 |
| `degraded` | 降级完成，结果可用但质量或性能受影响。 | 网格局部重修、求解降阶、渲染降级。 |
| `failed` | 当前动作失败，结果不可用或需要人工处理。 | 导出失败、读文件失败、求解中止。 |
| `cancelled` | 动作被用户或调度器取消。 | 用户取消、超时取消、批处理停止。 |

#### 4.7.5 `reason` 枚举

| 值 | 含义 | 典型处理 |
| --- | --- | --- |
| `unsupported_format` | 输入格式不受支持。 | 提示转换格式或升级 reader。 |
| `disk_full` | 磁盘空间不足。 | 清理空间或更换输出路径。 |
| `timeout` | 操作超时。 | 检查数据规模、资源、远端服务。 |
| `invalid_input` | 输入参数或文件内容非法。 | 校验输入、定位字段或对象。 |
| `license_unavailable` | 许可证不可用。 | 检查许可证服务器或并发配额。 |
| `out_of_memory` | 系统内存不足。 | 降低规模、开启分块、增加内存。 |
| `vram_exhausted` | 显存不足。 | 降低渲染质量、减少场数据、切换 CPU 路径。 |
| `non_convergence` | 求解未收敛。 | 检查网格、边界条件、物理模型和松弛参数。 |
| `residual_plateau` | 残差停滞。 | 调整 under-relaxation、时间步或非线性策略。 |
| `courant_limit_exceeded` | Courant/CFL 超过稳定性限制。 | 减小时间步或调整局部网格。 |
| `mesh_quality_failed` | 网格质量门禁失败。 | 局部重网格或调整尺寸控制。 |
| `negative_volume` | 出现负体积单元。 | 修复几何/网格并禁止继续求解。 |
| `missing_field` | 缺少必需结果场或输入字段。 | 检查结果文件、变量名映射或导出设置。 |
| `empty_selection` | 选择集为空。 | 调整选择条件或检查数据范围。 |
| `user_cancelled` | 用户主动取消。 | 记录可恢复状态，不作为系统故障。 |

### 4.8 schema 演进

- 不兼容变更必须升级 schema，并同步更新 validator、summary、GoAccess 配置和 E2E。
- 新增字段优先保持可选，不破坏旧读者。
- 字段删除、类型变化、枚举语义变化属于不兼容变更。
- 当前 Patch 3 validator 不要求日志行内包含 `schema_version`。跨版本归档、跨系统交换或长期存储时，建议在文件级元数据或后续 schema 中增加 `schema_version`。

### 4.9 `message` 写法

`message` 应清楚说明发生了什么，但不要承担机器解析职责。

推荐格式：

- 事件：`Actor action result.`
- 状态变化：`state_name: old_state->new_state, reason=...`
- 参数摘要：`key=value, key2=value2`
- 成功：`xxx completed.`
- 失败：`xxx failed. Please check ...`

示例：

```text
Reader opened.
Geometry validation summary completed.
Residual plateau detected; under-relaxation adjusted.
Export failed. Please check available disk space.
```

避免：

```text
1234
Error happened
failed!!!
maybe wrong
```

### 4.10 `result` 与 `reason`

`result` 和 `reason` 必须使用稳定枚举，具体含义见 4.7.4 和 4.7.5。新增枚举时必须补充说明、典型场景和处理建议。

禁止在 `reason` 中写长句、堆栈、路径或动态数字。详细说明写入 `message`，可聚合指标写入 `metrics`。

### 4.11 `metrics` 写法

`metrics` 只放可聚合、可比较、可告警的值。键名必须稳定，单位明确。

推荐：

```json
{
  "iteration": 42,
  "residual": 0.00012,
  "courant": 0.81,
  "cells": 1513840,
  "memory_mb": 912.5
}
```

不允许：

- 数组、对象、任意嵌套结构。
- 大块文本、网格坐标、字段数组、二进制内容。
- 含个人信息、客户项目密钥、许可证串、访问 token。
- 同一指标用多个名称，例如同时使用 `cell_count` 和 `cells`。

### 4.12 隐私、安全与知识产权

CAE 日志常包含客户模型、材料、边界条件、几何命名、文件路径和结果指标，这些都可能是商业敏感信息。

必须遵守：

- 不记录密码、token、许可证密钥、账号、个人信息、硬件序列号。
- 不记录完整客户文件路径、网络共享路径、模型原始文件名，除非确认可公开。
- 不记录几何坐标、网格节点列表、完整边界条件表、结果场数组。
- 文件可记录脱敏 basename、扩展名、大小、hash 或系统生成 ID。
- 用户输入、脚本、表达式、SQL/命令行参数必须脱敏后记录。
- 错误日志不得输出未脱敏异常对象全文。

本项目没有 HiLog `{public}/{private}` 级别的格式化隐私标记，因此调用方必须先脱敏再传给日志 API。

### 4.13 性能与限流

- 默认 `min_level` 应能热重载，生产环境不应长期启用 `TRACE/DEBUG`。
- 高频日志必须有采样、聚合或阈值触发策略。
- 批量文件、批量几何体、批量单元操作只记录汇总数量和失败数量。
- 异步日志队列容量应基于吞吐测试配置；队列满的策略必须可观测。
- `flush_level` 默认不低于 ERROR；正常退出必须调用 `cae::shutdown()`。
- 崩溃路径抢救式 flush 属于高风险能力，实现前必须评审 Windows 重入和文件损坏风险。

### 4.14 文件与 JSONL 输出

- JSONL 必须使用 UTF-8。
- 每行必须是一个完整 JSON object。
- 一条记录只能占一行，`message` 内换行必须转义。
- 文件名应包含模块和 PID，避免多进程覆盖，例如 `Module_pidPID.log`、`cae_events_pidPID.jsonl`。
- 合并后的分析文件为 `logs/cae_events.jsonl`。
- 无效行进入 `logs/schema_invalid_requests.log` 或对应 invalid report，不能静默丢弃。

### 4.15 校验要求

变更日志字段、枚举、采样策略或报告字段后，至少执行：

```powershell
python -m tools.cae validate .\logs\cae_events.jsonl --strict
python -m tools.cae summary --input .\logs\cae_events.jsonl --output-dir .\reports
```

涉及 GoAccess、schema、恶意样本或端到端链路时，执行：

```powershell
python -m tools.cae verify
```

## 5. 业务角度规范

### 5.1 CAE 工作流主线

一次完整 CAE 工作流建议按下列阶段组织：

| 阶段 | component | 关键 action | 必记信息 |
| --- | --- | --- | --- |
| 系统工作流 | `System` | `full_pipeline` | session、case、node、rank、开始/结束、总耗时 |
| 几何 | `Geometry` | `import_body`、`topology_check`、`healing`、`validation_summary` | body 数、面/边数量、修复数量、失败原因 |
| 网格 | `Mesh` | `sizing_control`、`surface_mesh`、`volume_mesh`、`quality_gate`、`export_summary` | nodes、cells、elements、质量指标、分区数 |
| 求解 | `Solver` | `setup`、`nonlinear_step`、`nonlinear_loop`、`checkpoint`、`convergence_summary` | iteration、residual、courant、time_step、收敛状态 |
| 后处理 | `PostProcess.*` | `reader_open`、`apply`、`representation_update`、`selection`、`export`、`task_summary` | fields、timesteps、结果范围、导出文件摘要、工程指标 |

### 5.2 几何日志

必须记录：

- CAD/几何导入开始和结束。
- body/part 数量、单位、坐标系摘要。
- topology check 结果。
- healing 操作摘要，例如修复边、闭合间隙、抑制小面数量。
- 命名选择集摘要。
- 失败时的对象类型、脱敏对象名、reason。

推荐指标：

| 指标 | 含义 | 单位/类型 | 记录时机 |
| --- | --- | --- | --- |
| `bodies` | 导入或参与处理的几何体数量。 | count/integer | CAD 导入摘要、几何校验摘要。 |
| `faces` | 几何面数量。 | count/integer | body 特征识别、拓扑校验摘要。 |
| `edges` | 几何边数量。 | count/integer | body 特征识别、拓扑校验摘要。 |
| `sliver_faces` | 检测到的小薄面数量。 | count/integer | topology check、healing 前后。 |
| `repaired_edges` | healing 合并或修复的边数量。 | count/integer | healing 完成摘要。 |
| `suppressed_faces` | 为网格或求解前处理而抑制的面数量。 | count/integer | 几何简化或 validation summary。 |
| `watertight_solids` | 通过封闭性检查的实体数量。 | count/integer | 几何 validation summary。 |
| `geometry_unit_scale` | 几何单位换算到内部标准单位的比例。 | ratio/double | CAD 导入完成或单位识别后。 |

禁止记录：

- 完整几何坐标。
- 客户零件完整命名体系。
- 原始 CAD 绝对路径。

### 5.3 网格日志

必须记录：

- 尺寸控制、边界层、曲率/邻近加密摘要。
- surface mesh、volume mesh 的规模。
- 质量门禁结果。
- 局部质量异常和自动修复/重网格动作。
- mesh export 摘要。

推荐指标：

| 指标 | 含义 | 单位/类型 | 记录时机 |
| --- | --- | --- | --- |
| `nodes` | 网格节点总数。 | count/integer | mesh summary、export summary。 |
| `cells` | 体网格单元总数。 | count/integer | volume mesh 完成、export summary。 |
| `elements` | 求解器视角的元素总数，可能与 `cells` 一致或按求解器映射后统计。 | count/integer | 求解前检查、mesh export。 |
| `triangles` | 表面三角面片数量。 | count/integer | surface mesh 完成。 |
| `partitions` | 网格分区数量。 | count/integer | 并行分区或导出摘要。 |
| `max_skewness` | 最大 skewness，越高通常表示质量越差。 | ratio/double | quality gate、异常告警。 |
| `min_orthogonal_quality` | 最小正交质量，越低通常表示质量越差。 | ratio/double | quality gate、质量摘要。 |
| `negative_volume_cells` | 负体积单元数量。 | count/integer | 网格质量检查；大于 0 通常应 ERROR。 |
| `inflation_layers` | 边界层/膨胀层层数。 | count/integer | inflation setup、mesh summary。 |
| `refinement_passes` | 自适应或局部加密执行次数。 | count/integer | refinement summary。 |

WARN 示例：

```cpp
CAE_LOG(Warn)
    .module("Mesh")
    .stage("Mesh")
    .action("quality_gate")
    .object("region", "region_03")
    .result("degraded")
    .reason("high_skewness")
    .metric("max_skewness", 0.94)
    .message("High skewness pocket detected; local remesh requested.")
    .submit();
```

### 5.4 求解日志

求解日志是 CAE 可追溯性的核心，必须能还原收敛过程。

必须记录：

- solver setup 摘要：物理模型、材料/载荷/边界条件数量、求解器类型摘要。
- 每个重要迭代周期的 residual、Courant/CFL、time step、线性/非线性迭代次数。
- checkpoint 写出。
- 收敛、停滞、发散、降阶、重启、自动调整 under-relaxation 等事件。
- 最终 convergence summary。

推荐指标：

| 指标 | 含义 | 单位/类型 | 记录时机 |
| --- | --- | --- | --- |
| `iteration` | 当前迭代编号。 | index/integer | 迭代样本、残差记录。 |
| `time_step_index` | 当前时间步编号。 | index/integer | 瞬态求解、后处理时间步切换。 |
| `physical_time_s` | 当前物理时间。 | seconds/double | 瞬态求解时间步记录。 |
| `delta_t_s` | 当前时间步长。 | seconds/double | 时间步调整、稳定性告警。 |
| `residual` | 当前归一化残差或主残差。 | ratio/double | 每 N 步、阈值跨越、收敛摘要。 |
| `initial_residual` | 本次线性/非线性求解开始时的残差。 | ratio/double | solver iteration 明细。 |
| `final_residual` | 本次线性/非线性求解结束时的残差。 | ratio/double | solver iteration 明细、收敛摘要。 |
| `linear_iterations` | 线性求解器迭代次数。 | count/integer | 每个非线性步或线性系统求解完成。 |
| `nonlinear_iterations` | 非线性迭代次数。 | count/integer | 非线性循环摘要。 |
| `courant` | 当前或平均 Courant/CFL 数。 | ratio/double | 流体/显式求解稳定性监控。 |
| `max_courant` | 当前步最大 Courant/CFL 数。 | ratio/double | 稳定性告警、时间步调整。 |
| `mass_imbalance` | 质量守恒不平衡量。 | ratio 或 domain unit/double | 收敛 monitor、最终摘要。 |
| `energy_imbalance` | 能量守恒不平衡量。 | ratio 或 domain unit/double | 热/能量方程 monitor。 |
| `converged` | 当前求解、时间步或整体任务是否收敛。 | boolean | convergence summary、失败判断。 |
| `checkpoint_index` | checkpoint 编号。 | index/integer | checkpoint 写出完成。 |

生产采样建议：

- 小规模迭代可每步记录。
- 大规模迭代至少记录前 5 步、最后 5 步、每 N 步、残差数量级变化、阈值跨越、WARN/ERROR。
- 收敛判断不能只看 residual；应结合工程关注量 monitor，例如力、位移、质量流量、能量、最大应力、温度等。

### 5.5 后处理日志

后处理日志需要证明结果如何被读取、变换、展示和导出。

必须记录：

- reader 创建和打开结果。
- mesh/field/timestep 摘要。
- pipeline filter 创建、属性变化、执行耗时和输出规模。
- display、colormap、transfer function 的关键状态变化。
- selection/find data 的输入和输出数量。
- screenshot/data export/animation 的开始、结束、失败原因。
- engineering summary。

推荐指标：

| 指标 | 含义 | 单位/类型 | 记录时机 |
| --- | --- | --- | --- |
| `fields` | 结果场数量。 | count/integer | reader 打开、mesh/field summary。 |
| `timesteps` | 结果文件包含的时间步数量。 | count/integer | reader 打开、导入摘要。 |
| `blocks` | 多块网格或数据块数量。 | count/integer | 导入摘要、pipeline 输入摘要。 |
| `changed_properties` | 本次 apply 修改的属性数量。 | count/integer | filter/display apply。 |
| `output_cells` | filter、selection 或导出后的输出单元数量。 | count/integer | filter 执行、selection 提取。 |
| `matches` | 查询、选择或 find data 命中的对象数量。 | count/integer | selection/find data。 |
| `time_step_index` | 当前查看或导出的时间步编号。 | index/integer | 视图同步、动画导出、时间步切换。 |
| `rescale_operations` | 色标/传递函数范围重映射次数。 | count/integer | colormap/transfer summary。 |
| `opacity_control_points` | 透明度传递函数控制点数量。 | count/integer | transfer function 更新。 |
| `export_bytes` | 导出文件大小。 | bytes/integer | 文件导出成功后。 |
| `frames` | 动画或序列导出的帧数。 | count/integer | animation summary。 |
| `fps` | 动画帧率。 | frames per second/double | animation start 或 summary。 |
| `max_stress` | 最大应力工程指标。 | domain unit/double，例如 MPa | engineering summary。 |
| `safety_factor` | 安全系数。 | ratio/double | engineering summary、设计审查告警。 |

ERROR 示例：

```cpp
CAE_LOG(Error)
    .module("PostProcess.Output")
    .stage("Output")
    .action("export")
    .object("file", "result_big.plt")
    .result("failed")
    .reason("disk_full")
    .message("Export failed. Please check available disk space.")
    .submit();
```

### 5.6 分布式与 HPC 日志

多进程、多节点、MPI 场景必须记录：

- `node_id`
- `mpi_rank`
- `session`
- `trace_id`
- `thread_name`
- per-process `sequence`

合并策略：

- 单进程内按 `sequence` 排序。
- 跨进程按 `timestamp` + `source` + `sequence` 排序。
- 跨节点必须考虑时钟偏移；后续如实现 clock alignment，应将偏移信息写入合并报告。
- rank 局部错误应包含 rank、分区、对象摘要；全局错误由协调 rank 或主导模块汇总一次。

### 5.7 资源遥测

当前基线支持 span 默认采集 `metrics.memory_mb`。资源指标解释如下：

| 指标 | 含义 | 单位/类型 | 记录时机 |
| --- | --- | --- | --- |
| `memory_mb` | 当前进程内存占用。 | MB/double | 当前基线在 span 结束时默认采样。 |
| `vram_mb` | GPU 显存占用。 | MB/double | 后续扩展；渲染/求解 GPU 路径采样。 |
| `cpu_percent` | 进程或任务 CPU 使用率。 | percent/double | 周期采样或 span 摘要。 |
| `io_read_mb` | 任务期间读取数据量。 | MB/double | 导入、求解 checkpoint、后处理读取摘要。 |
| `io_write_mb` | 任务期间写出数据量。 | MB/double | checkpoint、结果导出、报告生成摘要。 |
| `queue_depth` | 异步队列当前或峰值深度。 | count/integer | logger/任务队列监控。 |
| `thread_count` | 当前进程线程数量或任务线程数量。 | count/integer | span 摘要、资源告警。 |

资源指标必须说明采样点：span 结束、周期采样、异常采样或外部采样。不能把不同采样语义混入同一字段。

### 5.8 告警语义

WARN/ERROR 应能被规则引擎消费。推荐为每条可告警事件提供：

- 稳定 `component`
- 稳定 `stage`
- 稳定 `action`
- `result`
- `reason`
- 至少一个可比较 `metrics`

示例告警条件：

| 指标/条件 | 含义 | 告警建议 |
| --- | --- | --- |
| `span p95_us` | 某范围内 span 耗时的 95 分位，单位微秒，通常由摘要工具从 `duration_us` 派生。 | 超过阶段基线时 WARN，严重超时 ERROR。 |
| `residual` 长时间不下降 | 主残差在多个采样窗口内改善不足。 | WARN，并记录 `reason="residual_plateau"`。 |
| `max_courant` 超稳定性限制 | 最大 Courant/CFL 数超过求解策略允许值。 | WARN 或 ERROR，并建议减小 `delta_t_s`。 |
| `negative_volume_cells > 0` | 存在负体积单元。 | 通常 ERROR，阻止继续求解。 |
| `safety_factor < threshold` | 安全系数低于工程阈值。 | WARN 或 ERROR，取决于业务门禁。 |
| `export failed` | `action="export"` 且 `result="failed"`。 | ERROR，并要求提供 `reason`。 |

### 5.9 不应记录的 CAE 内容

禁止或默认脱敏：

- 客户模型完整路径、项目名、人员名、组织名。
- CAD/网格/结果文件的完整内容。
- 几何坐标、节点坐标、单元连接、材料完整参数表。
- 许可证信息、服务器地址、访问凭据。
- 用户脚本全文、命令行中的秘密参数。
- 大型数组、图片二进制、结果场二进制。

可以记录：

- 系统生成的 case/session ID。
- 文件扩展名、大小、hash、脱敏 basename。
- 数量级统计、质量统计、收敛统计。
- 与诊断直接相关的安全枚举和阈值。

## 6. 示例日志

### 6.1 point 事件

```json
{"timestamp":"2026-06-08T13:59:28.186","date":"2026-06-08","time":"13:59:28","source":"pid:13068/tid:15992","component":"Solver","stage":"Iteration","action":"nonlinear_step","level":"INFO","message":"Nonlinear iteration completed.","event_kind":"point","duration_us":0,"size":31,"session":"Proc_1","thread_name":"SolverWorker","sequence":42,"trace_id":"287db1b1dc7ad91c8bc92fe3b39ce7a6","span_id":"0f7d958c057470f7","parent_span_id":"8d3a436b07ec8076","object_type":null,"object_name":null,"result":"completed","reason":null,"node_id":"local-workstation","mpi_rank":0,"metrics":{"iteration":42,"residual":0.00012,"courant":0.81}}
```

### 6.2 span 事件

```json
{"timestamp":"2026-06-08T13:59:33.456","date":"2026-06-08","time":"13:59:33","source":"pid:13068/tid:15992","component":"System","stage":"Workflow","action":"full_pipeline","level":"INFO","message":"Workflow full_pipeline completed.","event_kind":"span","duration_us":5302095,"size":33,"session":"Proc_1","thread_name":"MainThread","sequence":558,"trace_id":"287db1b1dc7ad91c8bc92fe3b39ce7a6","span_id":"b95164388bb8e55c","parent_span_id":null,"object_type":null,"object_name":null,"result":"completed","reason":null,"node_id":"local-workstation","mpi_rank":0,"metrics":{"memory_mb":9.63671875}}
```

## 7. 代码审查清单

提交涉及日志的代码时，至少检查：

- 是否使用 Builder API 承载业务字段。
- `level` 是否与影响范围匹配。
- `point/span` 和 `duration_us` 是否真实。
- 是否设置 `stage`、`action`、`result`、`reason`。
- 指标是否放入 `metrics`，且单位明确。
- 是否包含 `trace_id`、`span_id`、`session`、`thread_name`、`node_id`、`mpi_rank`。
- 高频路径是否采样或聚合。
- 是否泄露路径、账号、许可证、客户模型或大块结果数据。
- 异常日志是否可操作，而不是只写 `failed`。
- schema 变更是否更新 validator、summary、GoAccess 和 E2E。

## 8. 参考链接

- Huawei/OpenHarmony Logging Guide: https://gitcode.com/chqyhsl/docs/blob/master/en/contribute/OpenHarmony-Log-guide.md
- OpenHarmony HiLog API: https://gitee.com/openharmony/docs/blob/44e8e413bdf0cc5d71ab18f6a97ce5351509d8b3/en/application-dev/reference/apis/js-apis-hilog.md
- OpenTelemetry Logs Data Model: https://opentelemetry.io/docs/specs/otel/logs/data-model/
- OWASP Logging Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- NIST SP 800-92: https://csrc.nist.gov/pubs/sp/800/92/final
- JSON Lines: https://jsonlines.org/
- OpenFOAM Solver information: https://www.openfoam.com/documentation/guides/latest/doc/guide-fos-utilities-solverinfo.html
- OpenFOAM Residuals: https://doc.openfoam.com/2306/tools/processing/numerics/solvers/residuals/
- OpenFOAM Monitoring jobs: https://www.openfoam.com/documentation/user-guide/6-solving/6.4-monitoring-and-managing-jobs
- SU2 History and Solution Output: https://su2code.github.io/docs_v7/Custom-Output/
- SU2 Post-processing outputs: https://su2code.github.io/docs/Post-processing/
- Ansys Fluent Transcript Files: https://ansyshelp.ansys.com/public/Views/Secured/corp/v252/en/flu_ug/flu_ug_TranscriptFile.html
- PyFluent residual monitors: https://fluent.docs.pyansys.com/version/stable/api/solver/tui/solve/monitors/residual/residual_contents.html
- Code_Aster user messages: https://codeaster.readthedocs.io/en/latest/devguide/code_aster/Messages.html
- Code_Aster error message extraction: https://codeaster.readthedocs.io/en/latest/_modules/run_aster/error_messages.html
