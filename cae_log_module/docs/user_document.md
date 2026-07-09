# CAE Logger 开发者接入参考文档
适用对象：CAE 软件业务模块开发者、插件开发者、求解器/前后处理模块开发者

本文档中的可执行示例已在 `sample/user/user_document_demo.cpp` 中落地，并已接入 `sample/CMakeLists.txt` 的构建与 CTest smoke test，可作为本文档的最小验证入口。
---

## 1. 目标

`cae_logger` 不是普通文本打印工具，而是面向 CAE 工业软件工作流的结构化日志组件。开发者接入后，日志应能支持：

1. 开发定位：快速回答“哪个模块、哪个阶段、哪个对象、哪个动作、为什么失败”。
2. 业务追溯：还原一次 case 从几何、网格、求解到后处理的关键节点。
3. 性能分析：统计导入、网格生成、求解迭代、导出等真实业务耗时。
4. 求解诊断：记录 residual、iteration、Courant/CFL、time step、converged 等收敛证据。
5. HPC/分布式关联：通过 session、trace、span、node、rank、thread 合并多线程、多进程、多节点日志。
6. 自动化消费：让 JSONL 日志可被校验、摘要、告警和报表工具稳定解析。

核心原则：

* 日志是结构化事件，不是随手打印的调试文本。
* 业务字段必须进入独立字段或 `metrics`，不要只塞进 `message`。
* 只有真实业务生命周期才能产生 `span` 耗时。
* WARN/ERROR 必须有稳定 `result` 和 `reason`。
* 日志不得泄露客户模型、路径、许可证、账号、token 或大块结果数据。

---

## 2. 成熟 CAE 软件实践借鉴

本组件的字段和宏语义以 `cae_logger.h` 和本项目日志规范为准；成熟 CAE 商业和开源软件只作为设计借鉴，不作为本组件 schema 的直接来源。

借鉴点如下：

| 软件/体系        | 可借鉴实践                                                                                     | 本组件中的落地方式                                                                                                           |
| ------------ | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| OpenFOAM     | 求解日志关注 residual、initial/final residual、iteration、convergence flag、Courant number、runtime。 | 求解阶段通过 `metrics` 记录 `residual`、`initial_residual`、`final_residual`、`iteration`、`converged`、`courant`、`duration_us`。 |
| SU2          | 区分 screen output、history output、volume/surface output；history 可定制字段和输出频率。                 | 区分文本日志和 JSONL 分析日志；高频求解历史需要采样、聚合或按频率输出。                                                                             |
| Ansys Fluent | transcript 记录会话输入输出、开始/结束/总时间；monitor 记录 residual、force、surface、volume 等变化。               | `TaskScope`/`ScopedTimer` 记录生命周期 span；Builder API 记录 monitor 指标和导出/后处理事件。                                           |
| Code_Aster   | `.mess` 和消息系统面向诊断，消息有等级、代码和定位语义。                                                          | 使用稳定 `level`、`component`、`stage`、`action`、`reason`，让错误可归类、可定位、可自动分析。                                                |

---

## 3. 快速接入

### 3.1 最小接入

```cpp
#include "cae_logger.h"

int main() {
    cae::init();

    cae::set_session("Case_001");
    cae::set_thread_name("MainThread");

    CAE_LOG_INFO("System")
        .message("CAE application started.")
        .submit();

    cae::shutdown();
    return 0;
}
```

### 3.2 推荐生产接入

```cpp
#include "cae_logger.h"

int main() {
    cae::LoggerOptions options;
    options.thread_model = cae::ThreadModel::MultiThread;
    options.process_model = cae::ProcessModel::MultiProcess;
    options.io_mode = cae::IOMode::Async;

    options.enable_console = false;
    options.enable_text_log = true;
    options.enable_analysis_log = true;
    options.truncate_file = false;

    options.min_level = cae::Level::Info;
    options.flush_level = cae::Level::Error;

    options.log_dir = "logs";
    options.analysis_log_name = "cae_events.jsonl";

    options.enable_call_chain_analysis = true;
    options.call_chain_min_level = cae::Level::Error;
    options.call_chain_max_depth = 16;
    options.call_chain_skip = 0;

    cae::init(options);

    cae::set_session("Case_20260615_001");
    cae::set_thread_name("MainThread");
    cae::set_node_id("node-a");
    cae::set_mpi_rank(0);

    CAE_LOG(Info)
        .module("System")
        .stage("Workflow")
        .action("application_start")
        .result("started")
        .message("CAE application started.")
        .submit();

    cae::shutdown();
    return 0;
}
```

### 3.3 配置文件接入

```cpp
cae::init("cae_logger.conf");
```

Read an INI file, modify the resulting options, then initialize:

```cpp
auto options = cae::load_options_from_file("cae_logger_config.ini");
options.min_level = cae::Level::Debug;
options.log_dir = "debug_logs";
cae::init(options);
```

Apply runtime changes to later log records:

```cpp
auto options = cae::get_options();
options.min_level = cae::Level::Debug;
options.log_dir = "new_logs";
cae::update_options(options);
```

`get_options()` returns a copy. Changing that copy takes effect only after
calling `update_options()`. When initialized with a config file path, file
mtime changes are still checked lazily on the next log emission.

推荐验证入口：

```powershell
test\build.cmd --config Debug --skip-e2e
test\build.cmd --config Debug --ctest-only
pushd test
.\build\Debug\user_document_demo.exe DocCase_1
python -m tools.cae validate .\build\Debug\logs\cae_events_pid*.jsonl --strict
popd
```

### 3.4 独立消费者接入

如果开发者在自己的工程里接入，最小 CMake 方式如下：

```cmake
find_package(cae_logger REQUIRED CONFIG)
add_executable(my_consumer main.cpp)
target_link_libraries(my_consumer PRIVATE cae_logger::cae_logger)
```

Windows 下通常还需要把 `libcae_logger.dll` 复制到可执行文件目录，或者把它所在目录加入 `PATH`。默认 header-only spdlog 模式不需要额外的 spdlog DLL；只有显式接入 spdlog package/library 模式时才需要处理对应运行库。若使用 `cae::init(options)`，建议显式设置 `log_dir` 和 `analysis_log_name`，避免日志写到不期望的工作目录或与历史文件混写。

仓库中可直接参考的独立消费者示例位于 `sample/user/independent_consumer/`，已验证可独立配置、编译并生成 `build/independent_consumer/doc_logs/consumer_events.jsonl`。

配置示例：

```ini
thread_model=mt
process_model=mp
io_mode=async
truncate_file=false

async_queue_size=8192
async_thread_count=1

enable_console=false
enable_text_log=true
enable_analysis_log=true

min_level=info
flush_level=error

log_dir=logs
analysis_log_name=cae_events.jsonl
global_pattern=[%Y-%m-%d %H:%M:%S.%e] [%t] [%n] [%^%l%$] %v

enable_call_chain_analysis=true
call_chain_min_level=error
call_chain_max_depth=16
call_chain_skip=0
```

---

## 4. 配置项说明

| 配置项                          | 类型/可选值                                     | 默认/建议              | 说明                          |
| ---------------------------- | ------------------------------------------ | ------------------ | --------------------------- |
| `thread_model`               | `st`/`single_thread`/`mt`/`multi_thread`   | CAE 常规程序建议 `mt`    | 决定 logger 是否按多线程 sink 运行。   |
| `process_model`              | `sp`/`single_process`/`mp`/`multi_process` | 多进程/HPC 建议 `mp`    | 多进程时文件名带 PID，避免覆盖。          |
| `io_mode`                    | `sync`/`async`                             | 性能敏感建议 `async`     | 同步/异步日志 I/O。                |
| `truncate_file`              | bool                                       | `false`            | 启动时是否覆盖旧日志。生产默认不要覆盖。        |
| `async_queue_size`           | size_t                                     | `8192`             | 异步队列容量。                     |
| `async_thread_count`         | size_t                                     | `1`                | 异步日志后台线程数。                  |
| `enable_console`             | bool                                       | 本地调试可开，批处理/HPC 可关  | 是否输出控制台日志。                  |
| `enable_text_log`            | bool                                       | `true`             | 是否输出传统文本日志，供人工排障。           |
| `enable_analysis_log`        | bool                                       | `true`             | 是否输出 JSONL 分析日志。生产分析链路必须开启。 |
| `min_level`                  | `trace/debug/info/warn/error/critical`     | 生产建议 `info`        | 低于该等级的日志不输出。                |
| `flush_level`                | 同上                                         | `error`            | 达到该等级触发 flush。              |
| `log_dir`                    | string                                     | `logs`             | 日志目录。                       |
| `analysis_log_name`          | string                                     | `cae_events.jsonl` | JSONL 分析日志文件名。              |
| `global_pattern`             | spdlog pattern                             | 默认即可               | 只影响文本/控制台，不影响 JSONL 字段。     |
| `enable_call_chain_analysis` | bool                                       | `true`             | 是否捕获 C++ 调用链。               |
| `call_chain_min_level`       | level                                      | `error`            | 达到该等级才捕获调用链。                |
| `call_chain_max_depth`       | size_t                                     | `16`               | 最大调用链深度；实现会限制过大值。           |
| `call_chain_skip`            | size_t                                     | `0`                | 跳过外部调用帧数量；实现会限制过大值。         |

---

## 5. API 必填、业务必填、自动处理字段

本节区分三种“必填”：

1. **API 必填**：不传会编译失败。
2. **业务规范必填**：不传也可能编译运行，但日志不可分析或不符合规范。
3. **实现自动处理**：开发者不应手工构造，由 logger 自动生成或兜底。

### 5.1 API 必填

| API/宏                                                       | API 必填参数                                 | 说明                                                              |
| ----------------------------------------------------------- | ---------------------------------------- | --------------------------------------------------------------- |
| `CAE_LOG(level)`                                            | `level`                                  | 必须是 `Trace/Debug/Info/Warn/Error/Critical` 这样的枚举标识符片段，不能传运行时变量。 |
| `CAE_LOG_TRACE/DEBUG/INFO/WARN/ERROR/CRITICAL(module)` | `module`               | 返回链式 builder；消息通过 `.message(...).submit()` 写出。        |
| `CAE_LOG_*_DUR(module, duration_us)`                   | `module`、`duration_us` | 返回带顶层 `duration_us` 的链式 builder，消息通过 `.message(...).submit()` 写出。 |
| `CAE_LOG_SCOPE(level, module, ...)`                         | `level`、`module`、fmt format、fmt 参数       | 创建 RAII span，退出作用域时写日志。                                         |
| `CAE_LOG_SCOPE_*`                                           | `module`、fmt format、fmt 参数               | 对 `CAE_LOG_SCOPE(level, ...)` 的等级快捷封装。                          |
| `CAE_SCOPE_TASK(level, module, stage, ...)`                 | `level`、`module`、`stage`                 | action 和 trace_id 选填。                                           |
| `cae::TaskScope(module, stage, level, ...)`                 | `module`、`stage`                         | action 和 trace_id 选填。                                           |
| `cae::ScopedTimer(module, level, message)`                  | `module`、`level`、`message`               | 创建简易计时 scope。                                                   |

### 5.2 业务规范必填

这些字段不一定由 C++ 类型系统强制，但业务关键日志必须填写。

| 字段/变量                     | 填写方式                                         | 规范                                                              |
| ------------------------- | -------------------------------------------- | --------------------------------------------------------------- |
| `component` / `module`    | `.module(...)` 或宏 `module`                   | 业务模块名，建议稳定层级名，如 `Solver`、`PostProcess.Output`。                  |
| `stage`                   | `.stage(...)` 或 `TaskScope`/`CAE_SCOPE_TASK` | 业务阶段，如 `Geometry`、`Mesh`、`Iteration`、`Output`。                  |
| `action`                  | `.action(...)` 或 `TaskScope` action          | 稳定动作名，如 `reader_open`、`nonlinear_step`、`quality_gate`、`export`。 |
| `message`                 | `.message(...)`                                | 面向人的简短英文说明。机器分析所需数据不要只放在 message。                               |
| `result`                  | `.result(...)`                               | 关键节点、WARN、ERROR 必填。                                             |
| `reason`                  | `.reason(...)`                               | WARN、ERROR、降级、跳过、取消必须填写。                                        |
| `object_type/object_name` | `.object(type, name)`                        | 涉及对象时填写，并且必须脱敏。                                                 |
| `metrics`                 | `.metric(...)`                               | residual、iteration、cells、fields 等可分析指标必须写入 metrics。             |
| `session`                 | `cae::set_session(...)`                      | 每个 case、进程或任务实例设置一次。                                            |
| `thread_name`             | `cae::set_thread_name(...)`                  | 重要线程必须设置可读名称。                                                   |
| `node_id`                 | `cae::set_node_id(...)`                      | 多节点/HPC 必须设置。                                                   |
| `mpi_rank`                | `cae::set_mpi_rank(...)`                     | MPI/multi-rank 必须设置；非 MPI 可不设置。                                 |
| `trace_id`                | `TaskScope` 自动生成或跨线程显式传递                     | 跨线程/跨进程继续同一 workflow 时必须显式传递。                                   |

### 5.3 实现自动处理字段

| 字段               | 自动处理方式                                                      |
| ---------------- | ----------------------------------------------------------- |
| `timestamp`      | 自动生成本地 ISO 时间，毫秒精度。                                         |
| `date` / `time`  | 自动从 timestamp 派生。                                           |
| `source`         | 自动生成为 `pid:PID/tid:TID`。                                |
| `level`          | 由宏或 Builder 的 `Level` 决定。                                   |
| `event_kind`     | Builder/文本宏为 `point`；DUR/Scope/TaskScope 为 `span`。          |
| `duration_us`    | point 自动为 0；scope 自动测量；DUR 使用调用方传入值。                        |
| `size`           | 自动取 message 字符长度。                                           |
| `sequence`       | 单进程内自动递增。                                                   |
| `trace_id`       | 无上下文时自动生成；scope 嵌套时继承；跨线程需手工传递。                             |
| `span_id`        | 每条记录自动生成或 scope 自动生成。                                       |
| `parent_span_id` | scope 嵌套时自动设置。                                              |
| `thread_name`    | 未设置时默认 `tid:ID`。                                          |
| `node_id`        | 未设置时尝试从 `COMPUTERNAME`/`HOSTNAME` 派生，否则为 `unknown-node`。    |
| `message`        | Builder 未设置 message 时实现会兜底为 `structured event`；业务规范仍要求显式填写。 |
| `component`      | 未设置时实现会兜底为当前上下文或 `default`；业务规范仍要求显式填写。                     |
| `stage`          | 未设置时实现会使用上下文 stage 或从 component 派生；业务规范仍要求显式填写。             |
| `action`         | 未设置时会按事件来源兜底：Builder/文本 point 常为当前上下文 action 或 `message`，`TaskScope` 默认为 `scope`，`ScopedTimer` 默认为 `timed_scope`；业务规范仍要求显式填写。                |
| `memory_mb`      | Windows 上 span 结束时可能自动写入 `metrics.memory_mb`；其他平台可能没有。      |

### 5.4 当前实现扩展字段

当前 JSONL 实现会额外输出以下调用链字段：

| 字段                   | 说明                                                      |
| -------------------- | ------------------------------------------------------- |
| `call_chain_status`  | `captured`、`disabled` 或 `boost_stacktrace_unavailable`。 |
| `call_chain_summary` | 调用链摘要；没有捕获时可为 `null`。                                   |
| `call_chain`         | 调用链帧数组。                                                 |

注意：这三个字段是当前实现输出的扩展字段。若要把它们纳入严格 schema 必需字段，需要同步更新 validator、summary、GoAccess/E2E 等工具。

---

## 6. JSONL 顶层字段规范

每条 JSONL 分析日志是一行完整 JSON object。

### 6.1 当前规范必需字段

| 字段            | 类型      | 来源     | 说明                                      |
| ------------- | ------- | ------ | --------------------------------------- |
| `timestamp`   | string  | 自动     | 本地 ISO 时间，毫秒精度。                         |
| `date`        | string  | 自动     | `YYYY-MM-DD`。                           |
| `time`        | string  | 自动     | `HH:MM:SS`。                             |
| `source`      | string  | 自动     | `pid:PID/tid:TID`。                  |
| `component`   | string  | 调用方/兜底 | 模块名。业务规范要求显式填写。                         |
| `stage`       | string  | 调用方/兜底 | 业务阶段。业务规范要求显式填写。                        |
| `action`      | string  | 调用方/兜底 | 稳定动作名。业务规范要求显式填写。                       |
| `level`       | string  | API 自动 | `TRACE/DEBUG/INFO/WARN/ERROR/CRITICAL`。 |
| `message`     | string  | 调用方/兜底 | 人类可读说明。业务规范要求显式填写。                      |
| `event_kind`  | string  | 自动     | `point` 或 `span`。                       |
| `duration_us` | integer | 自动/调用方 | point 为 0；span 必须 > 0。                  |
| `size`        | integer | 自动     | 当前 message 字符长度。                        |
| `sequence`    | integer | 自动     | 单进程内递增。                                 |
| `trace_id`    | string  | 自动/显式  | 32 位小写十六进制。                             |
| `span_id`     | string  | 自动     | 16 位小写十六进制。                             |
| `session`     | 调用方/兜底  | string | 未设置时默认 `Single`；生产不应依赖默认值。              |
| `thread_name` | 调用方/兜底  | string | 未设置时默认 `tid:ID`。                      |
| `metrics`     | object  | 调用方/自动 | 值只能是数字、布尔或字符串。                          |

### 6.2 可空字段

| 字段               | 类型           | 说明         |
| ---------------- | ------------ | ---------- |
| `parent_span_id` | string/null  | 父 span ID。 |
| `object_type`    | string/null  | 对象类别。      |
| `object_name`    | string/null  | 脱敏对象名。     |
| `result`         | string/null  | 动作结果枚举。    |
| `reason`         | string/null  | 原因枚举。      |
| `mpi_rank`       | integer/null | MPI rank。  |

### 6.3 可选/可为空语义字段

| 字段        | 类型     | 说明                                  |
| --------- | ------ | ----------------------------------- |
| `node_id` | string | 多节点标识；未设置时实现会自动探测或写 `unknown-node`。 |

### 6.4 语义约束

* `event_kind="point"` 时，`duration_us == 0`。
* `event_kind="span"` 时，`duration_us > 0`。
* `trace_id` 应为 32 位小写十六进制。
* `span_id` 和非空 `parent_span_id` 应为 16 位小写十六进制。
* `metrics` 必须是 JSON object。
* `metrics` 的值只允许整数、浮点、布尔或字符串。
* `message` 不承担机器解析职责；机器分析字段必须进入独立字段或 `metrics`。
* 调用方不得依赖 `message` 中换行、回车、Tab 或控制字符被原样保留；当前实现会将换行、回车、Tab 转为空格，以保证 JSONL 单行安全。

---

## 7. API 选择原则

优先级从高到低：

1. `CAE_LOG(level)` Builder API
   用于业务关键节点、可分析指标、失败原因、对象和结果。新业务优先使用它。

2. `CAE_SCOPE_TASK(level, module, stage, ...)` 或 `cae::TaskScope`
   用于真实业务生命周期，例如几何导入、网格生成、求解循环、导出任务。自动生成 span、duration、trace/span 关系。

3. `CAE_LOG_*_DUR(module, duration_us)`
   用于已有真实耗时的外部计时结果。`duration_us` 会作为顶层字段写出。

4. `CAE_LOG_INFO/WARN/ERROR/...`
   用于简单人工可读补充，不承载核心分析字段。

5. `TRACE/DEBUG`
   仅用于开发诊断、临时排障或受控采样，不作为业务报表依据。

---

## 8. 宏合法用法总览

### 8.1 `CAE_LOG(level)`

用途：创建结构化 `LogBuilder`。

支持等级：

```cpp
CAE_LOG(Trace)
CAE_LOG(Debug)
CAE_LOG(Info)
CAE_LOG(Warn)
CAE_LOG(Error)
CAE_LOG(Critical)
```

推荐：

```cpp
CAE_LOG(Info)
    .module("Solver")
    .stage("Iteration")
    .action("nonlinear_step")
    .result("completed")
    .metric("iteration", static_cast<std::int64_t>(42))
    .metric("residual", 1.2e-4)
    .metric("courant", 0.81)
    .message("Nonlinear iteration completed.")
    .submit();
```

运行时等级变量不能直接传给 `CAE_LOG(level)`：

```cpp
cae::Level lv = cae::Level::Info;

// 错误：宏会展开成 cae::Level::lv
// CAE_LOG(lv).module("Solver").message("Started.").submit();

// 正确：运行时等级使用 make_log_builder
cae::make_log_builder(lv)
    .module("Solver")
    .stage("Setup")
    .action("start")
    .result("started")
    .message("Solver started.")
    .submit();
```

`std::string` 作为 Builder 字符串参数时，应使用 `.c_str()`：

```cpp
std::string module = "Solver";
std::string stage = "Iteration";

CAE_LOG(Info)
    .module(module.c_str())
    .stage(stage.c_str())
    .action("nonlinear_step")
    .result("completed")
    .message("Nonlinear iteration completed.")
    .submit();
```

### 8.2 Builder 字段能力

```cpp
.module(const char*)
.stage(const char*)
.action(const char*)
.object(const char* object_type, const char* object_name)
.entity(const char* entity_type, const char* entity_name)
.event_type(cae::EventType)
.phase(cae::EventPhase)
.domain(cae::Domain)
.result(const char*)
.reason(const char*)
.metric(const char* key, std::int64_t)
.metric(const char* key, double)
.metric(const char* key, bool)
.metric(const char* key, const std::string&)
.metric(const char* key, const char*)
.duration_us(std::uint64_t)
.message(fmt::format_string&lt;Args...&gt;, Args&&...)
.submit()
```

#### 8.2.1 链式方法语义

链式方法的调用顺序不影响字段写入，但推荐按“归属、业务语义、结果、指标、文本、提交”的顺序组织，最后必须调用 `.submit()`。

| 方法 | 写入字段/效果 | 含义 | 使用方式 |
| --- | --- | --- | --- |
| `.module("Solver")` | `component` | 日志所属模块或组件。它应是稳定名称，不建议写临时文件名、对象名或自然语言句子。 | 每条业务日志都建议设置，例如 `"Geometry"`、`"Mesh"`、`"Solver"`、`"PostProcess.Output"`。 |
| `.stage("Iteration")` | `stage` | 所在业务阶段或流程阶段，用于把同一模块内的日志按工作流分组。 | 适合写 `"Import"`、`"Mesh"`、`"Iteration"`、`"Output"` 这类阶段名。 |
| `.action("nonlinear_step")` | `action` | 当前发生的具体动作，建议使用稳定英文标识。 | 用于统计、告警和定位动作，例如 `"read_file"`、`"quality_check"`、`"nonlinear_step"`、`"export"`。 |
| `.object("file", "result.csv")` | `object_type`、`object_name` | 当前动作直接影响或处理的对象。 | 有明确对象时使用，例如 `.object("mesh_zone", "inlet")`、`.object("field", "pressure")`。 |
| `.entity("case", "Case_001")` | `entity_type`、`entity_name` | schema 层面的分析实体。未显式设置时，会优先从 `object` 推导，否则从 `stage/action` 推导。 | 需要报表或分析工具按实体聚合时使用，例如 `.entity("case", case_name.c_str())`。 |
| `.event_type(cae::EventType::Mesh)` | `event_type` | 覆盖自动推断的事件类型。 | 默认推断不准确，或核心事件需要明确归类时使用。可选值包括 `Geometry`、`Mesh`、`Solve`、`IO`、`UI`、`MPI`、`PostProcess`、`System`。 |
| `.phase(cae::EventPhase::Progress)` | `phase` | 覆盖自动推断的事件阶段。 | 当事件明确表示开始、过程或结束时使用，可选值为 `Start`、`Progress`、`End`。 |
| `.domain(cae::Domain::CFD)` | `domain` | 覆盖自动推断的工程领域。 | 需要跨模块按领域分析时使用，可选值为 `CFD`、`FEM`、`Pre`、`Post`、`System`。 |
| `.result("completed")` | `result` | 动作结果状态。 | 关键节点建议设置；`WARN/ERROR` 必须尽量设置。推荐稳定值：`"started"`、`"completed"`、`"failed"`、`"skipped"`、`"cancelled"`、`"degraded"`。 |
| `.reason("non_convergence")` | `reason` | 失败、告警、降级、跳过或取消的原因码。 | `WARN/ERROR/degraded/skipped/cancelled` 场景建议设置，使用稳定英文原因码，例如 `"disk_full"`、`"missing_field"`。 |
| `.metric("residual", 1.2e-4)` | `metrics.key` | 可被机器分析的指标。 | 数字、布尔、字符串指标都放这里，不要只塞进 `message`。key 必须非空，建议稳定 snake_case；有单位时写进 key，例如 `"duration_us"`、`"memory_mb"`。 |
| `.duration_us(mesh_us)` | `duration_us`，`event_kind="span"` | 设置顶层耗时，单位微秒，并按 span 事件写出。 | 只在已有真实耗时时使用。也可以通过 `CAE_LOG_*_DUR(module, duration_us)` 入口设置。不要把耗时作为普通 metric 替代它。 |
| `.message("done {}", n)` | `message` | 人类可读说明，支持 `fmt` 风格格式化。 | 用于补充上下文；机器要分析的数据仍应放到 `result/reason/object/metric` 等结构化字段里。 |
| `.submit()` | 写出日志 | 提交当前 builder。 | 链式调用的最后一步；忘记 `.submit()` 不会写出任何记录。 |

推荐写法：

```cpp
CAE_LOG(Info)
    .module("Solver")
    .stage("Iteration")
    .action("nonlinear_step")
    .object("equation", "pressure")
    .result("completed")
    .metric("iteration", static_cast<std::int64_t>(42))
    .metric("residual", 1.2e-4)
    .message("Nonlinear iteration completed.")
    .submit();
```

失败或告警日志应把结果和原因拆成结构化字段：

```cpp
CAE_LOG(Error)
    .module("PostProcess.Output")
    .stage("Output")
    .action("export")
    .object("file", "result.csv")
    .result("failed")
    .reason("disk_full")
    .message("Export failed.")
    .submit();
```

已有真实耗时时，使用 `_DUR` 宏或 `.duration_us()` 写顶层耗时：

```cpp
CAE_LOG_INFO_DUR("Mesh", mesh_us)
    .stage("Mesh")
    .action("volume_mesh")
    .result("completed")
    .message("Volume mesh completed.")
    .submit();
```

整数 metric 推荐显式转为 `std::int64_t`：

```cpp
int iteration = 42;

CAE_LOG(Info)
    .module("Solver")
    .stage("Iteration")
    .action("nonlinear_step")
    .result("completed")
    .metric("iteration", static_cast<std::int64_t>(iteration))
    .metric("residual", 1.2e-4)
    .message("Nonlinear iteration completed.")
    .submit();
```

### 8.3 文本宏

用途：写入简单 point 文本日志。

完整宏列表：

```cpp
CAE_LOG_TRACE(module)
CAE_LOG_DEBUG(module)
CAE_LOG_INFO(module)
CAE_LOG_WARN(module)
CAE_LOG_ERROR(module)
CAE_LOG_CRITICAL(module)
```

示例：

```cpp
CAE_LOG_TRACE("Mesh")
    .message("Visiting cell {}", cell_id)
    .submit();
CAE_LOG_DEBUG("Geometry")
    .message("Detected {} candidate sliver faces.", sliver_faces)
    .submit();
CAE_LOG_INFO("System")
    .message("Workflow started for case {}.", case_id)
    .submit();
CAE_LOG_WARN("PostProcess.Reader")
    .message("Optional field {} is missing.", field_name)
    .submit();
CAE_LOG_ERROR("PostProcess.Output")
    .message("Failed to open output file {}.", safe_basename)
    .submit();
CAE_LOG_CRITICAL("Solver")
    .message("Result database is corrupted; solver will abort.")
    .submit();
```

`module` 是 `const char*`，如果模块名是 `std::string`：

```cpp
std::string module = "Solver";
CAE_LOG_INFO(module.c_str())
    .message("Solver setup started.")
    .submit();
```

限制：

* `event_kind` 为 `point`。
* `duration_us` 自动为 0。
* 不支持直接填写 `stage`、`action`、`result`、`reason`、`metrics`。
* 不适合业务关键日志、告警统计和报表分析。
* WARN/ERROR 如需稳定 reason，应改用 `CAE_LOG(Warn/Error)` Builder。

### 8.4 DUR 耗时宏

用途：写入已有真实耗时的 span 文本日志。

完整宏列表：

```cpp
CAE_LOG_TRACE_DUR(module, duration_us)
CAE_LOG_DEBUG_DUR(module, duration_us)
CAE_LOG_INFO_DUR(module, duration_us)
CAE_LOG_WARN_DUR(module, duration_us)
CAE_LOG_ERROR_DUR(module, duration_us)
CAE_LOG_CRITICAL_DUR(module, duration_us)
```

示例：

```cpp
CAE_LOG_TRACE_DUR("Solver.Assembly", assembly_us)
    .message("Element assembly batch completed.")
    .submit();
CAE_LOG_DEBUG_DUR("Geometry", bbox_us)
    .message("Bounding box scan completed.")
    .submit();
CAE_LOG_INFO_DUR("Mesh", mesh_us)
    .message("Volume mesh completed.")
    .submit();
CAE_LOG_WARN_DUR("Solver", step_us)
    .message("Time step completed with residual plateau.")
    .submit();
CAE_LOG_ERROR_DUR("PostProcess.Output", export_us)
    .message("Export failed after retry.")
    .submit();
CAE_LOG_CRITICAL_DUR("System", shutdown_us)
    .message("Emergency shutdown sequence completed.")
    .submit();
```

限制：

* `duration_us` 必须来自真实计时。
* 不允许为了报表好看给普通 point 事件伪造耗时。
* 不支持结构化 `result/reason/metrics`。
* 新业务不要优先使用 DUR 宏记录业务生命周期；优先使用 `CAE_SCOPE_TASK`，并用 Builder 记录结果和指标。

### 8.5 `CAE_LOG_SCOPE(level, module, ...)`

用途：在当前 C++ 作用域创建 RAII 计时器，作用域退出时自动写入 span。

```cpp
void run_mesher() {
    CAE_LOG_SCOPE(Info, "Mesh", "Volume mesh generation completed.");
    generate_volume_mesh();
}
```

支持：

```cpp
CAE_LOG_SCOPE(Trace, module, ...)
CAE_LOG_SCOPE(Debug, module, ...)
CAE_LOG_SCOPE(Info, module, ...)
CAE_LOG_SCOPE(Warn, module, ...)
CAE_LOG_SCOPE(Error, module, ...)
CAE_LOG_SCOPE(Critical, module, ...)
```

限制：

* 退出作用域才写日志。
* stage 从 module 派生。
* action 固定为 `timed_scope`。
* message 由调用方提供。
* 不支持 result/reason/metrics。
* 需要结构化生命周期时，优先使用 `CAE_SCOPE_TASK` 或 `cae::TaskScope`。

### 8.6 Scope 等级快捷宏

完整宏列表：

```cpp
CAE_LOG_SCOPE_TRACE(module, ...)
CAE_LOG_SCOPE_DEBUG(module, ...)
CAE_LOG_SCOPE_INFO(module, ...)
CAE_LOG_SCOPE_WARN(module, ...)
CAE_LOG_SCOPE_ERROR(module, ...)
CAE_LOG_SCOPE_CRITICAL(module, ...)
```

示例：

```cpp
CAE_LOG_SCOPE_TRACE("Solver.Kernel", "Kernel interpolation completed.");
CAE_LOG_SCOPE_DEBUG("Mesh.Partition", "Partition exchange completed.");
CAE_LOG_SCOPE_INFO("Geometry", "Geometry healing completed.");
CAE_LOG_SCOPE_WARN("Mesh", "Mesh local repair completed with degraded quality.");
CAE_LOG_SCOPE_ERROR("PostProcess.Output", "Export failed.");
CAE_LOG_SCOPE_CRITICAL("System", "Crash recovery scope completed.");
```

### 8.7 `CAE_SCOPE_TASK(level, module, stage, ...)`

用途：创建结构化任务生命周期，自动生成 span、duration、trace/span 上下文，并在作用域结束写入完成日志。

调用形态：

```cpp
CAE_SCOPE_TASK(Info, "Geometry", "Geometry");
CAE_SCOPE_TASK(Info, "Mesh", "Mesh", std::string("volume_mesh"));
CAE_SCOPE_TASK(Info, "Solver", "Iteration", std::string("nonlinear_loop"), trace_id);
```

参数：

| 参数         | 是否 API 必填 | 说明                                                        |
| ---------- | --------- | --------------------------------------------------------- |
| `level`    | 是         | `Trace/Debug/Info/Warn/Error/Critical`，不加 `cae::Level::`。 |
| `module`   | 是         | 最终进入 `component`。                                         |
| `stage`    | 是         | 业务阶段。                                                     |
| `action`   | 否         | 不填时默认为 `scope`。                                           |
| `trace_id` | 否         | 跨线程/跨进程继续已有 trace 时填写。                                    |

正常生命周期示例：

```cpp
void build_mesh() {
    CAE_SCOPE_TASK(Info, "Mesh", "Mesh", std::string("volume_mesh"));

    create_surface_mesh();
    create_volume_mesh();
    check_quality();
}
```

跨线程传递 trace：

```cpp
void submit_solver_task() {
    CAE_SCOPE_TASK(Info, "System", "Workflow", std::string("full_pipeline"));

    const std::string trace_id = cae::get_trace_id();

    std::thread worker([trace_id]() {
        cae::set_thread_name("SolverWorker");

        CAE_SCOPE_TASK(
            Info,
            "Solver",
            "Iteration",
            std::string("nonlinear_loop"),
            trace_id);

        run_solver();
    });

    worker.join();
}
```

重要限制：

* `TaskScope` 析构时会自动写 `result="completed"` 的 span。
* 如果业务失败、取消或异常，不要让该 scope 自然析构并误写 completed。
* 失败路径应调用 `cancel()`，再用 Builder 显式写 WARN/ERROR。

失败路径推荐写法：

```cpp
void solve_case() {
    cae::TaskScope scope(
        "Solver",
        "Iteration",
        cae::Level::Info,
        "nonlinear_loop");

    try {
        run_solver_loop();

        CAE_LOG(Info)
            .module("Solver")
            .stage("Iteration")
            .action("convergence_summary")
            .result("completed")
            .metric("converged", true)
            .message("Solver converged.")
            .submit();
    } catch (const std::exception&) {
        scope.cancel();

        CAE_LOG(Error)
            .module("Solver")
            .stage("Iteration")
            .action("nonlinear_loop")
            .result("failed")
            .reason("non_convergence")
            .message("Solver nonlinear loop failed.")
            .submit();

        throw;
    }
}
```

取消路径推荐写法：

```cpp
void generate_mesh() {
    cae::TaskScope scope(
        "Mesh",
        "Mesh",
        cae::Level::Info,
        "volume_mesh");

    if (user_cancelled()) {
        scope.cancel();

        CAE_LOG(Warn)
            .module("Mesh")
            .stage("Mesh")
            .action("volume_mesh")
            .result("cancelled")
            .reason("user_cancelled")
            .message("Volume mesh generation cancelled by user.")
            .submit();

        return;
    }

    run_mesher();
}
```

### 8.8 内部拼接宏

```cpp
CAE_LOG_DETAIL_CONCAT_INNER(lhs, rhs)
CAE_LOG_DETAIL_CONCAT(lhs, rhs)
```

说明：

* 这是内部宏，用于拼接 scope 变量名，业务代码不要直接使用。
* 不要在同一物理行放置多个 scope 宏；变量名基于 `__LINE__`，同一行可能冲突。

### 8.9 可移植性注意事项

`CAE_SCOPE_TASK` 当前使用 `##__VA_ARGS__` 处理空可变参数，这是 GCC/MinGW 常见扩展。若项目要求严格标准 C++20，可考虑在组件实现中改为 `__VA_OPT__(,)`，或提供无 action、有 action、有 trace_id 的多个显式宏。

---

## 9. 等级使用规范

| 等级         | 使用场景         | CAE 示例                       |
| ---------- | ------------ | ---------------------------- |
| `Trace`    | 极细粒度诊断，默认关闭  | 单元级装配、每次内部插值、锁竞争细节。          |
| `Debug`    | 开发定位，生产可关闭   | 每批 body bbox、分区交换、局部质量样本。    |
| `Info`     | 正常业务关键节点     | 导入完成、网格摘要、迭代样本、收敛摘要、导出完成。    |
| `Warn`     | 可恢复但需要关注     | 高 skewness、残差平台、缺少可选字段、自动降级。 |
| `Error`    | 当前动作失败或结果不可用 | 读文件失败、格式不支持、求解未收敛并停止、导出失败。   |
| `Critical` | 进程级严重问题      | 崩溃前抢救、结果库损坏、许可证/资源导致全局中止。    |

禁止：

* 用 `Error` 表示普通用户取消。
* 用 `Info` 隐藏会导致结果缺失的问题。
* 长期在生产开启高频 `Trace/Debug`。
* 每个底层函数都打印成功日志，造成重复。
* 将大量数据、坐标、路径、许可证、token 写入日志。

---

## 10. result 与 reason 枚举

### 10.1 result

| 值           | 含义                   | 使用场景                   |
| ----------- | -------------------- | ---------------------- |
| `started`   | 动作已开始。               | 长任务入口、导入开始、导出开始。       |
| `completed` | 动作正常完成。              | 工作流结束、导入完成、求解完成。       |
| `applied`   | 配置、参数或变更已应用。         | filter 属性、显示状态、边界条件应用。 |
| `skipped`   | 动作被跳过，但整体可继续。        | 输入缺少可选字段、无可处理对象。       |
| `retrying`  | 动作失败后正在重试。           | 文件写入重试、网络/许可证重试。       |
| `degraded`  | 降级完成，结果可用但质量或性能受影响。  | 网格局部重修、求解降阶、渲染降级。      |
| `failed`    | 当前动作失败，结果不可用或需要人工处理。 | 导出失败、读文件失败、求解中止。       |
| `cancelled` | 动作被用户或调度器取消。         | 用户取消、超时取消、批处理停止。       |

### 10.2 reason

| 值                        | 含义                   | 典型处理                           |
| ------------------------ | -------------------- | ------------------------------ |
| `unsupported_format`     | 输入格式不受支持。            | 提示转换格式或升级 reader。              |
| `disk_full`              | 磁盘空间不足。              | 清理空间或更换输出路径。                   |
| `timeout`                | 操作超时。                | 检查数据规模、资源、远端服务。                |
| `invalid_input`          | 输入参数或文件内容非法。         | 校验输入、定位字段或对象。                  |
| `license_unavailable`    | 许可证不可用。              | 检查许可证服务器或并发配额。                 |
| `out_of_memory`          | 系统内存不足。              | 降低规模、开启分块、增加内存。                |
| `vram_exhausted`         | GPU 显存不足。            | 降低渲染质量、减少场数据、切换 CPU 路径。        |
| `non_convergence`        | 求解未收敛。               | 检查网格、边界条件、物理模型和松弛参数。           |
| `residual_plateau`       | 残差停滞。                | 调整 under-relaxation、时间步或非线性策略。 |
| `courant_limit_exceeded` | Courant/CFL 超过稳定性限制。 | 减小时间步或调整局部网格。                  |
| `mesh_quality_failed`    | 网格质量门禁失败。            | 局部重网格或调整尺寸控制。                  |
| `negative_volume`        | 出现负体积单元。             | 修复几何/网格并禁止继续求解。                |
| `missing_field`          | 缺少必需结果场或输入字段。        | 检查结果文件、变量名映射或导出设置。             |
| `empty_selection`        | 选择集为空。               | 调整选择条件或检查数据范围。                 |
| `user_cancelled`         | 用户主动取消。              | 记录可恢复状态，不作为系统故障。               |

新增枚举时，必须补充含义、典型场景和处理建议，并同步校验/摘要/告警工具。

---

## 11. metrics 命名规范

`metrics` 只放可聚合、可比较、可告警的值。键名必须稳定，单位明确。

允许类型：

* `std::int64_t`
* `double`
* `bool`
* `std::string`
* `const char*`

不允许：

* 数组。
* 对象。
* 任意嵌套结构。
* 大块文本。
* 网格坐标。
* 字段数组。
* 二进制内容。
* 许可证串、token、密码、账号。
* 同一指标用多个名称，例如同时使用 `cell_count` 和 `cells`。

推荐：

```cpp
CAE_LOG(Info)
    .module("Solver")
    .stage("Iteration")
    .action("nonlinear_step")
    .result("completed")
    .metric("iteration", static_cast<std::int64_t>(42))
    .metric("residual", 0.00012)
    .metric("courant", 0.81)
    .metric("converged", false)
    .message("Nonlinear iteration completed.")
    .submit();
```

---

## 12. CAE 工作流推荐日志点

### 12.1 系统工作流

推荐 action：

* `application_start`
* `case_open`
* `full_pipeline`
* `case_close`
* `application_shutdown`

示例：

```cpp
CAE_SCOPE_TASK(Info, "System", "Workflow", std::string("full_pipeline"));

CAE_LOG(Info)
    .module("System")
    .stage("Workflow")
    .action("case_open")
    .object("case", "Case_001")
    .result("started")
    .message("Case workflow started.")
    .submit();
```

必记：

* session
* case 安全 ID
* node/rank/thread
* full pipeline span
* 总耗时
* 失败原因

### 12.2 几何日志

推荐 action：

* `import_body`
* `topology_check`
* `healing`
* `validation_summary`

推荐 metrics：

| 指标                    | 含义            |
| --------------------- | ------------- |
| `bodies`              | 几何体数量。        |
| `faces`               | 几何面数量。        |
| `edges`               | 几何边数量。        |
| `sliver_faces`        | 小薄面数量。        |
| `repaired_edges`      | 修复边数量。        |
| `suppressed_faces`    | 抑制小面数量。       |
| `watertight_solids`   | 通过封闭性检查的实体数量。 |
| `geometry_unit_scale` | 几何单位换算比例。     |

示例：

```cpp
CAE_LOG(Info)
    .module("Geometry")
    .stage("Geometry")
    .action("import_body")
    .object("file", "case_geometry.step")
    .result("completed")
    .metric("bodies", static_cast<std::int64_t>(18))
    .metric("faces", static_cast<std::int64_t>(2456))
    .metric("geometry_unit_scale", 0.001)
    .message("Geometry import completed.")
    .submit();
```

### 12.3 网格日志

推荐 action：

* `sizing_control`
* `surface_mesh`
* `volume_mesh`
* `quality_gate`
* `export_summary`

推荐 metrics：

| 指标                       | 含义           |
| ------------------------ | ------------ |
| `nodes`                  | 网格节点总数。      |
| `cells`                  | 体网格单元总数。     |
| `elements`               | 求解器视角元素总数。   |
| `triangles`              | 表面三角面片数量。    |
| `partitions`             | 网格分区数量。      |
| `max_skewness`           | 最大 skewness。 |
| `min_orthogonal_quality` | 最小正交质量。      |
| `negative_volume_cells`  | 负体积单元数量。     |
| `inflation_layers`       | 边界层层数。       |
| `refinement_passes`      | 局部加密执行次数。    |

示例：

```cpp
CAE_LOG(Warn)
    .module("Mesh")
    .stage("Mesh")
    .action("quality_gate")
    .object("region", "region_03")
    .result("degraded")
    .reason("mesh_quality_failed")
    .metric("max_skewness", 0.94)
    .metric("negative_volume_cells", static_cast<std::int64_t>(0))
    .message("Mesh quality gate degraded; local remesh requested.")
    .submit();
```

### 12.4 求解日志

推荐 action：

* `setup`
* `linear_solve`
* `nonlinear_step`
* `nonlinear_loop`
* `checkpoint`
* `convergence_summary`

推荐 metrics：

| 指标                     | 含义                   |
| ---------------------- | -------------------- |
| `iteration`            | 当前迭代编号。              |
| `time_step_index`      | 当前时间步编号。             |
| `physical_time_s`      | 当前物理时间。              |
| `delta_t_s`            | 当前时间步长。              |
| `residual`             | 当前归一化残差或主残差。         |
| `initial_residual`     | 本次求解开始残差。            |
| `final_residual`       | 本次求解结束残差。            |
| `linear_iterations`    | 线性求解器迭代次数。           |
| `nonlinear_iterations` | 非线性迭代次数。             |
| `courant`              | 当前或平均 Courant/CFL 数。 |
| `max_courant`          | 当前步最大 Courant/CFL 数。 |
| `mass_imbalance`       | 质量守恒不平衡量。            |
| `energy_imbalance`     | 能量守恒不平衡量。            |
| `converged`            | 是否收敛。                |
| `checkpoint_index`     | checkpoint 编号。       |

示例：

```cpp
CAE_LOG(Error)
    .module("Solver")
    .stage("Iteration")
    .action("convergence_summary")
    .result("failed")
    .reason("non_convergence")
    .metric("iteration", static_cast<std::int64_t>(500))
    .metric("final_residual", 2.8e-3)
    .metric("converged", false)
    .message("Solver failed to converge within the iteration limit.")
    .submit();
```

采样建议：

* 小规模求解可每步记录。
* 大规模求解记录前 5 步、最后 5 步、每 N 步、数量级变化、阈值跨越、WARN/ERROR。
* 收敛判断不要只看 residual，应结合工程 monitor，如 force、displacement、mass flow、temperature、stress、安全系数等。

### 12.5 后处理日志

推荐 action：

* `reader_open`
* `apply`
* `representation_update`
* `selection`
* `export`
* `animation_export`
* `task_summary`

推荐 metrics：

| 指标                   | 含义                |
| -------------------- | ----------------- |
| `fields`             | 结果场数量。            |
| `timesteps`          | 时间步数量。            |
| `blocks`             | 多块网格或数据块数量。       |
| `changed_properties` | 本次 apply 修改的属性数量。 |
| `output_cells`       | 输出单元数量。           |
| `matches`            | 查询/选择命中数量。        |
| `time_step_index`    | 当前时间步编号。          |
| `export_bytes`       | 导出文件大小。           |
| `frames`             | 动画帧数。             |
| `fps`                | 动画帧率。             |
| `max_stress`         | 最大应力。             |
| `safety_factor`      | 安全系数。             |

示例：

```cpp
CAE_LOG(Error)
    .module("PostProcess.Output")
    .stage("Output")
    .action("export")
    .object("file", "stress_summary.csv")
    .result("failed")
    .reason("disk_full")
    .message("Export failed. Please check available disk space.")
    .submit();
```

---

## 13. 隐私、安全和知识产权

禁止记录：

* 密码、token、许可证密钥、账号、个人信息。
* 客户模型完整路径、网络共享路径、项目真实名称。
* CAD/网格/结果文件完整内容。
* 几何坐标、网格节点列表、单元连接表、完整边界条件表。
* 用户脚本全文、命令行中的秘密参数。
* 大型数组、图片二进制、结果场二进制。

可以记录：

* 系统生成的 case/session ID。
* 文件扩展名、脱敏 basename、大小、hash。
* 数量级统计、质量统计、收敛统计。
* 稳定 reason 枚举和安全阈值。

推荐：

```cpp
.object("file", "result_001.vtu")
```

禁止：

```cpp
.object("file", "D:/CustomerA/SecretProject/engine_xxx/result_001.vtu")
```

---

## 14. 性能与限流

1. 高频路径不得逐项刷屏。
2. 几何体、网格单元、节点、积分点、粒子、每帧渲染等应采样或聚合。
3. 复杂字符串、数组摘要、hash 计算应先判断是否需要记录。
4. 正常生产建议 `min_level=Info`；排障临时改为 `Debug/Trace`。
5. 正常退出必须调用 `cae::shutdown()`。
6. ERROR 及以上应保留可操作原因和必要上下文。
7. 多进程写日志时使用 `ProcessModel::MultiProcess`，避免多个进程写同一文件。
8. `flush_level` 不建议低于 `Error`，否则高频日志可能显著影响性能。

---

## 15. 推荐模板

### 15.1 成功 point

```cpp
CAE_LOG(Info)
    .module("PostProcess.Reader")
    .stage("PostProcess")
    .action("reader_open")
    .object("file", "result.vtu")
    .result("completed")
    .metric("fields", static_cast<std::int64_t>(12))
    .metric("timesteps", static_cast<std::int64_t>(101))
    .message("Reader opened.")
    .submit();
```

### 15.2 可恢复 WARN

```cpp
CAE_LOG(Warn)
    .module("Solver")
    .stage("Iteration")
    .action("nonlinear_step")
    .result("degraded")
    .reason("residual_plateau")
    .metric("iteration", static_cast<std::int64_t>(120))
    .metric("residual", 8.5e-4)
    .message("Residual plateau detected; under-relaxation adjusted.")
    .submit();
```

### 15.3 失败 ERROR

```cpp
CAE_LOG(Error)
    .module("Geometry")
    .stage("Geometry")
    .action("import_body")
    .object("file", "geometry.step")
    .result("failed")
    .reason("unsupported_format")
    .message("Geometry import failed. Please check the input format.")
    .submit();
```

### 15.4 正常生命周期 span

```cpp
void export_results() {
    CAE_SCOPE_TASK(Info, "PostProcess.Output", "Output", std::string("export"));

    write_result_file();

    CAE_LOG(Info)
        .module("PostProcess.Output")
        .stage("Output")
        .action("export")
        .object("file", "result.vtu")
        .result("completed")
        .metric("export_bytes", static_cast<std::int64_t>(export_size))
        .message("Result export completed.")
        .submit();
}
```

### 15.5 失败生命周期 span

```cpp
void export_results() {
    cae::TaskScope scope(
        "PostProcess.Output",
        "Output",
        cae::Level::Info,
        "export");

    try {
        write_result_file();
    } catch (const std::exception&) {
        scope.cancel();

        CAE_LOG(Error)
            .module("PostProcess.Output")
            .stage("Output")
            .action("export")
            .object("file", "result.vtu")
            .result("failed")
            .reason("disk_full")
            .message("Export failed. Please check available disk space.")
            .submit();

        throw;
    }
}
```

### 15.6 跨线程 workflow

```cpp
void run_pipeline() {
    CAE_SCOPE_TASK(Info, "System", "Workflow", std::string("full_pipeline"));

    const std::string trace_id = cae::get_trace_id();

    std::thread solver([trace_id]() {
        cae::set_thread_name("SolverWorker");

        CAE_SCOPE_TASK(
            Info,
            "Solver",
            "Iteration",
            std::string("nonlinear_loop"),
            trace_id);

        run_solver_loop();
    });

    solver.join();
}
```

---

## 16. 发布前代码审查清单

提交涉及日志的代码时，至少检查：

* 是否优先使用 Builder API 承载业务字段。
* 是否区分“能编译”和“符合业务规范”。
* 是否有稳定 `component/stage/action`。
* WARN/ERROR 是否有 `result` 和 `reason`。
* point/span 是否符合语义。
* `duration_us` 是否来自真实测量。
* residual、iteration、cells、fields 等是否写入 metrics。
* metrics 键名是否稳定且单位明确。
* 是否设置 session、thread_name、node_id、mpi_rank。
* 跨线程是否显式传递 trace_id。
* `TaskScope` 失败/取消路径是否调用 `cancel()`，避免误写 completed。
* 高频路径是否采样或聚合。
* 是否泄露客户路径、许可证、脚本、模型内容或大块结果数据。
* 异常日志是否可操作，而不是只写 `failed`。
* 是否在程序退出时调用 `cae::shutdown()`。
* schema 新增/变更是否同步 validator、summary、GoAccess/E2E。
* 如果项目要求严格标准 C++，是否评估 `##__VA_ARGS__` 的可移植性。

---

## 17. 最低校验要求

变更日志字段、枚举、采样策略或报告字段后，至少执行：

```powershell
python -m tools.cae validate .\logs\cae_events.jsonl --strict
python -m tools.cae summary --input .\logs\cae_events.jsonl --output-dir .\reports
```

涉及 GoAccess、schema、恶意样本或端到端链路时，执行：

```powershell
python -m tools.cae verify
```
