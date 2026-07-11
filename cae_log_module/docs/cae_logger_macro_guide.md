# cae_logger.h 宏使用说明

本文档说明 `src/cae_logger.h` 中对外提供的日志宏的意义、参数、输出语义、推荐场景和常见误用方式。

相关参考：

- 日志规范：[rule/cae_log_specification.md]
- 头文件定义：[src/cae_logger.h]

## 宏总表

| 宏 | 参数 | 产生日志语义 | 推荐场景 | 不推荐场景 |
| --- | --- | --- | --- | --- |
| `CAE_LOG(level)` | `level` | 结构化业务事件，通常是 `point` | 需要 `module/stage/action/result/reason/metrics` 的核心业务日志 | 只想随手打一条纯文本消息 |
| `CAE_LOG(Trace).module(module)` | `module` | 链式文本事件 builder，`TRACE` 等级 | 极细粒度调试 | 生产常规业务日志 |
| `CAE_LOG(Debug).module(module)` | `module` | 链式文本事件 builder，`DEBUG` 等级 | 开发定位、局部诊断 | 承载核心业务字段 |
| `CAE_LOG(Info).module(module)` | `module` | 链式文本事件 builder，`INFO` 等级 | 正常状态提示、简短摘要 | 需要被分析工具稳定提取的数据 |
| `CAE_LOG(Warn).module(module)` | `module` | 链式文本事件 builder，`WARN` 等级 | 可恢复异常提醒 | 需要 `reason/result/metrics` 的正式告警 |
| `CAE_LOG(Error).module(module)` | `module` | 链式文本事件 builder，`ERROR` 等级 | 当前动作失败的简短报错 | 替代结构化失败日志 |
| `CAE_LOG(Critical).module(module)` | `module` | 链式文本事件 builder，`CRITICAL` 等级 | 崩溃前、全局严重故障 | 普通失败或可恢复问题 |
| `CAE_LOG_TRACE_DUR(module, duration_us)` | `module`, `duration_us` | 带真实耗时的链式文本事件，`TRACE` | 极细耗时调试 | 随便填一个耗时 |
| `CAE_LOG_DEBUG_DUR(module, duration_us)` | 同上 | 带真实耗时的链式文本事件，`DEBUG` | 局部性能诊断 | 核心生命周期建模 |
| `CAE_LOG_INFO_DUR(module, duration_us)` | 同上 | 带真实耗时的链式文本事件，`INFO` | 已有精确耗时值的正常业务事件 | 应该用 `TaskScope` 的完整任务 |
| `CAE_LOG_WARN_DUR(module, duration_us)` | 同上 | 带真实耗时的链式文本事件，`WARN` | 可恢复异常且需要体现耗时 | 替代结构化 `WARN` 告警 |
| `CAE_LOG_ERROR_DUR(module, duration_us)` | 同上 | 带真实耗时的链式文本事件，`ERROR` | 失败动作且已有耗时值 | 只写错误句子、不写失败原因 |
| `CAE_LOG_CRITICAL_DUR(module, duration_us)` | 同上 | 带真实耗时的链式文本事件，`CRITICAL` | 全局致命故障且需记录耗时 | 日常异常 |
| `CAE_LOG_SCOPE(level)` | `level`，再通过 `.module(...).message(...).submit()` 链式配置；遗漏 `.submit()` 会编译失败 | 局部代码块自动计时 | 函数/局部作用域耗时统计 | 真实业务 workflow/span 主入口 |
| `CAE_SCOPE_TASK(level, module, stage, ...)` | `level`, `module`, `stage`, 可选 `action/trace_id` | 真实业务生命周期 `span` | 几何导入、网格生成、求解循环、导出任务 | 只是一条瞬时状态变更 |

说明：

- `CAE_LOG_DETAIL_CONCAT_INNER` 和 `CAE_LOG_DETAIL_CONCAT` 是内部辅助宏，不属于业务对外接口。
- 规范中优先级最高的是 `CAE_LOG(level)` 和 `CAE_SCOPE_TASK(...)`。

## 1. `CAE_LOG(level)`

定义位置：`src/cae_logger.h`

意义：

- 创建一个 `LogBuilder`
- 用于写结构化日志
- 这是最推荐的业务日志入口

参数：

- `level`：`Trace`、`Debug`、`Info`、`Warn`、`Error`、`Critical`

推荐场景：

- 需要 `module/stage/action/result/reason/metrics` 的关键业务日志
- 需要被 JSONL、摘要、告警、报表工具稳定消费的日志

示例：

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

不推荐：

- 只想打印一句纯文本提示时使用它
- 忘记 `.submit()`

### 1.1 链式字段说明

`CAE_LOG(level).module(...)` 写法以及带 `duration_us` 的 `_DUR` 宏（例如 `CAE_LOG_INFO_DUR("Mesh", mesh_us)`）都会返回 `LogBuilder`，因此可以继续追加以下链式方法。链式方法的顺序不影响字段写入，但推荐最后调用 `.message(...).submit()`；忘记 `.submit()` 时不会写出日志。

| 方法 | 意义 | 典型用法 |
| --- | --- | --- |
| `.module("Solver")` | 设置日志所属模块，最终写入 `component`。 | 稳定模块名，例如 `"Mesh"`、`"Solver"`、`"PostProcess.Output"`。 |
| `.stage("Iteration")` | 设置业务阶段，表示当前处于哪个流程段。 | `"Import"`、`"Mesh"`、`"Iteration"`、`"Output"`。 |
| `.action("nonlinear_step")` | 设置具体动作，建议使用稳定英文标识。 | `"read_file"`、`"quality_check"`、`"nonlinear_step"`、`"export"`。 |
| `.object("file", "result.csv")` | 设置当前动作处理的对象类别和对象名。 | `.object("mesh_zone", "inlet")`、`.object("field", "pressure")`。 |
| `.entity("case", "Case_001")` | 设置 schema 分析实体；未设置时会从 `object` 或 `stage/action` 推导。 | 需要报表按实体聚合时使用。 |
| `.event_type(...)` | 覆盖自动推断的事件类型。 | 默认推断不准确时使用，例如 `.event_type(cae::EventType::Mesh)`。 |
| `.phase(...)` | 覆盖自动推断的事件阶段。 | 明确表达开始、过程、结束时使用，例如 `.phase(cae::EventPhase::Progress)`。 |
| `.domain(...)` | 覆盖自动推断的工程领域。 | 跨模块按领域分析时使用，例如 `.domain(cae::Domain::CFD)`。 |
| `.result("completed")` | 设置动作结果状态。 | 推荐 `"started"`、`"completed"`、`"failed"`、`"skipped"`、`"cancelled"`、`"degraded"`。 |
| `.reason("non_convergence")` | 设置失败、告警、降级、跳过或取消原因。 | `WARN/ERROR`、`degraded`、`skipped`、`cancelled` 场景优先填写稳定原因码。 |
| `.metric("residual", 1.2e-4)` | 添加可分析指标，写入 `metrics`。 | 数值、布尔、字符串指标都放这里；key 非空，建议 snake_case，带单位时写成 `"duration_us"`、`"memory_mb"`。 |
| `.duration_us(mesh_us)` | 设置顶层 `duration_us`，并按 `span` 事件写出。 | 已有真实耗时时使用；`CAE_LOG_*_DUR(module, duration_us)` 已经设置了该字段。 |
| `.message("done {}", n)` | 设置人类可读消息，支持 `fmt` 风格格式化。 | 不要把可分析数据只写进 message，应优先写入结构化字段或 metric。 |
| `.submit()` | 提交并真正写出日志。 | 所有链式写法的最后一步。 |

完整示例：

```cpp
CAE_LOG(Info).module("Solver")
    .stage("Iteration")
    .action("nonlinear_step")
    .object("equation", "pressure")
    .result("completed")
    .metric("iteration", static_cast<std::int64_t>(42))
    .metric("residual", 1.2e-4)
    .message("Nonlinear iteration completed.")
    .submit();
```

失败日志示例：

```cpp
CAE_LOG(Error).module("PostProcess.Output")
    .stage("Output")
    .action("export")
    .object("file", "result.csv")
    .result("failed")
    .reason("disk_full")
    .message("Export failed.")
    .submit();
```

## 2. `CAE_LOG(level).module(module)`

这种链式写法用于写一条指定等级的纯文本瞬时日志。

包含：

- `CAE_LOG(Trace).module(module)`
- `CAE_LOG(Debug).module(module)`
- `CAE_LOG(Info).module(module)`
- `CAE_LOG(Warn).module(module)`
- `CAE_LOG(Error).module(module)`
- `CAE_LOG(Critical).module(module)`

意义：

- 写一条单点日志
- 返回链式 builder，通过 `.message(...).submit()` 写出
- 更适合补充说明，不适合承载核心结构化字段

参数：

- `module`：模块名，例如 `"Solver"`、`"Mesh"`、`"PostProcess.Output"`
- 消息内容在 `.message(...)` 中填写，支持 `fmt` 风格格式化参数

示例：

```cpp
CAE_LOG(Info).module("Geometry")
    .message("Imported CAD body {} of {}", index, total)
    .submit();
CAE_LOG(Warn).module("Mesh")
    .message("High skewness detected in region {}", region_id)
    .submit();
CAE_LOG(Error).module("PostProcess.Output")
    .message("Export failed: {}", reason)
    .submit();
```

推荐场景：

- 简短人工可读消息
- 局部提示
- 调试输出

不推荐：

- 将 `iteration`、`residual`、`result`、`reason` 等核心字段只写到文本里

## 3. `CAE_LOG_*_DUR`

这组宏用于写“带明确耗时”的文本日志。

包含：

- `CAE_LOG_TRACE_DUR(module, duration_us)`
- `CAE_LOG_DEBUG_DUR(module, duration_us)`
- `CAE_LOG_INFO_DUR(module, duration_us)`
- `CAE_LOG_WARN_DUR(module, duration_us)`
- `CAE_LOG_ERROR_DUR(module, duration_us)`
- `CAE_LOG_CRITICAL_DUR(module, duration_us)`

意义：

- 记录一条带真实耗时的日志
- `duration_us` 单位是微秒
- 适合“已经测量出耗时”的事件

参数：

- `module`
- `duration_us`：真实耗时，单位微秒
- `...`：格式化消息

示例：

```cpp
CAE_LOG_INFO_DUR("PostProcess.Output", export_us)
    .message("Export completed.")
    .submit();
CAE_LOG_WARN_DUR("PostProcess.Import", import_us)
    .message("Import completed with missing columns.")
    .submit();
```

推荐场景：

- 调用方已有准确耗时值
- 局部动作结束后补记耗时

不推荐：

- 为了“看起来有耗时”而伪造 `duration_us`
- 用它替代真实业务生命周期的 `TaskScope`

## 4. `CAE_LOG_SCOPE(level)`

意义：

- 创建一个 `ScopedTimer`
- 进入当前作用域开始计时；链式配置必须以 `.submit()` 结束，否则编译失败；离开作用域时自动结束并写出
- 面向“这段代码花了多久”

参数：

- `level`
- `.module(...)`：模块名
- `.message(...)`：消息文本，支持 `fmt` 风格格式化参数
- `.submit()`：确认该 scope 需要在退出作用域时写出

示例：

```cpp
void export_result() {
    CAE_LOG_SCOPE(Info)
        .module("PostProcess.Output")
        .message("Exporting result file")
        .submit();
    // ...
}
```

推荐场景：

- 函数级或局部代码块级别的自动计时
- 快速性能诊断

不推荐：

- 作为业务主工作流 `span` 的唯一建模方式

## 5. `CAE_SCOPE_TASK(level, module, stage, ...)`

意义：

- 创建一个 `TaskScope`
- 表示一个真实业务生命周期
- 自动形成 `span`
- 自动带上 `trace_id`、`span_id`、`parent_span_id` 和 `duration_us`

参数：

- `level`
- `module`
- `stage`
- `...`
  - 不传：使用默认 action
  - 传 1 个：通常表示 `action`
  - 传 2 个：通常表示 `action, trace_id`

示例：

```cpp
CAE_SCOPE_TASK(Info, "System", "Workflow", "full_pipeline");
CAE_SCOPE_TASK(Info, "Solver", "Solver", "nonlinear_loop");
CAE_SCOPE_TASK(Info, "PostProcess.Output", "Output", "export");
```

跨线程继续同一链路时：

```cpp
std::string trace_id = cae::get_trace_id();
CAE_SCOPE_TASK(Info, "Solver", "Iteration", "child_stage", trace_id);
```

推荐场景：

- 几何导入
- 网格生成
- 求解循环
- 后处理导出
- 整个 workflow/case

不推荐：

- 只描述一个瞬时状态变化时使用它

## 6. `CAE_LOG_SCOPE(level)` 等级写法

使用保留的 `CAE_LOG_SCOPE` 主入口按等级创建作用域计时。

包含：

- `CAE_LOG_SCOPE(Trace).module(module).message(...).submit()`
- `CAE_LOG_SCOPE(Debug).module(module).message(...).submit()`
- `CAE_LOG_SCOPE(Info).module(module).message(...).submit()`
- `CAE_LOG_SCOPE(Warn).module(module).message(...).submit()`
- `CAE_LOG_SCOPE(Error).module(module).message(...).submit()`
- `CAE_LOG_SCOPE(Critical).module(module).message(...).submit()`

意义：

- 显式写出 `level`
- 调用 `.submit()` 后保持作用域自动计时语义

示例：

```cpp
void rebuild_cache() {
    CAE_LOG_SCOPE(Info)
        .module("System")
        .message("Rebuilding cache")
        .submit();
}
```

推荐场景：

- 局部作用域计时
- 不需要额外区分 `level` 传参形式时

不推荐：

- 代替 `CAE_SCOPE_TASK(...)` 表达完整业务生命周期

## 7. 宏选择建议

推荐按下面规则选择：

- 要被分析工具稳定消费：`CAE_LOG(level)`
- 要表达真实业务生命周期：`CAE_SCOPE_TASK(...)`
- 要做局部代码块自动计时：`CAE_LOG_SCOPE(level).module(...).message(...).submit()`
- 已经有真实耗时值：`CAE_LOG_*_DUR`
- 只补一句简短文本：`CAE_LOG(level).module(...)`

## 8. 不同 CAE 业务推荐用法

### Geometry

- 导入摘要、拓扑检查、healing 结果：`CAE_LOG(Info/Warn/Error)`
- 几何导入全过程：`CAE_SCOPE_TASK(Info, "Geometry", "Geometry", "import_body")`

### Mesh

- 质量门禁、单元数、分区数：`CAE_LOG(...)`
- 网格生成全过程：`CAE_SCOPE_TASK(...)`

### Solver

- 迭代样本、残差、Courant：`CAE_LOG(Info/Warn/Error)`
- 非线性循环：`CAE_SCOPE_TASK(...)`

### PostProcess

- reader、filter、selection、export：`CAE_LOG(...)`
- 导出任务、动画生成：`CAE_SCOPE_TASK(...)`

## 9. 常见误用

- 用 `CAE_LOG(Info).module(...)` 代替结构化 `CAE_LOG(Info)...submit()`
- 用 `CAE_LOG_*_DUR` 伪造耗时
- 用 `CAE_LOG_SCOPE(Info).module(...).message(...).submit()` 替代真实业务任务 `span`
- 在高频路径长期使用 `TRACE/DEBUG`
- 把核心业务字段只写进 `message`

## 10. 一句话记忆

- `CAE_LOG`：结构化事件
- `CAE_LOG_*`：文本事件
- `CAE_LOG_*_DUR`：文本事件 + 手工耗时
- `CAE_LOG_SCOPE*`：局部代码块自动计时
- `CAE_SCOPE_TASK`：业务任务自动计时 + trace/span
