`CAE_LOG_SCOPE` 通过 **RAII (Resource Acquisition Is Initialization)** 机制，结合 `ScopedTimer` 类实现了对作用域执行耗时的自动化处理。

以下是其实现的核心步骤和逻辑：

### 1. 宏定义 (注册计时器)

在 `src/cae_logger.h` 中，`CAE_LOG_SCOPE` 宏被定义为：

```cpp
#define CAE_LOG_SCOPE(level) \
    cae::ScopedTimer CAE_LOG_DETAIL_CONCAT(cae_log_scope_, __LINE__)(cae::Level::level); \
    CAE_LOG_DETAIL_CONCAT(cae_log_scope_, __LINE__)

```

* **原理**：该宏会在当前作用域内创建一个 `cae::ScopedTimer` 局部对象，并把该对象返回给后续 `.module(...).message(...).submit()` 链式配置。
* **唯一命名**：使用 `__LINE__` 确保在同一作用域内如果有多个计时器，变量名是唯一的，避免冲突。

### 2. 构造函数 (记录起点)

当执行流进入作用域时，`ScopedTimer` 的构造函数会被调用：

```cpp
ScopedTimer::ScopedTimer(Level level)
    : state_(std::make_unique<ScopedTimerState>()) {
    // 1. 记录当前系统时间作为起点
    state_->start = Clock::now(); 
    state_->level = level;
}

```

随后调用链式配置：

```cpp
CAE_LOG_SCOPE(Info)
    .module("Mesh")
    .message("Volume mesh generation completed.")
    .submit();
```

* **上下文管理**：`.module(...)` 和 `.message(...)` 只保存配置；`.submit()` 会将当前的模块、阶段和新生成的 `span_id` 压入线程本地的 `t_context_stack`，确保计时器能够关联到正确的异步任务链中。若调用方没有显式设置模块，`.submit()` 会使用默认模块补齐上下文。未调用 `.submit()` 的 scope 不写日志，也不会创建 scope 上下文。

### 3. 析构函数 (计算并提交耗时)

当执行流**离开**作用域（无论是正常结束、异常退出还是 `return`）时，局部对象 `ScopedTimer` 会自动销毁。如果已经调用 `.submit()`，析构函数会计算耗时并提交；如果没有调用 `.submit()`，析构函数只销毁对象，不写日志：

```cpp
ScopedTimer::~ScopedTimer() noexcept {
    if (!state_->is_submitted) {
        return;
    }

    // 1. 获取当前时间并计算耗时 (微秒)
    const auto elapsed = std::chrono::duration_cast<std::chrono::microseconds>(Clock::now() - state_->start).count();
    const auto duration_us = elapsed > 0 ? static_cast<std::uint64_t>(elapsed) : 1;
    
    // 2. 从 Context 栈中弹出当前作用域信息
    pop_scope_context(state_->span_id);
    
    // 3. 提交到 LoggerCore 进行持久化记录
    LoggerCore::instance().emit_scope_record(
        ..., duration_us, message, ...);
}

```

* **自动化**：`.submit()` 确认要写出该 scope 后，由 C++ 析构机制保证在离开作用域时执行差值计算；无论代码块如何退出，已提交 scope 的耗时都会被记录。

### 4. 数据落地 (EventKind::Span)

在 `LoggerCore::emit_scope_record` 中，该记录被标记为 `EventKind::Span`：

* **JSONL 输出**：在 `JsonlAnalysisPrinter::write` 中，如果记录的 `event_kind` 为 `Span`，程序会将计算出的 `duration_us` 写入 `.jsonl` 文件中的 `duration_us` 字段。
* **降级处理**：如果 `duration_us` 计算异常，代码会通过 `clamp_duration` 确保耗时至少为 1 微秒，避免记录为 0。

### 总结

`CAE_LOG_SCOPE` 的精妙之处在于它不需要开发者手动编写 `start` 和 `end` 代码。调用 `.submit()` 确认要写出后，**只要代码块结束，析构函数自动执行差值计算并调用 `emit_scope_record`**，从而将耗时数据无缝地集成到结构化日志（JSONL）中。
