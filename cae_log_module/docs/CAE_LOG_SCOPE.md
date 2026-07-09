`CAE_LOG_SCOPE` 通过 **RAII (Resource Acquisition Is Initialization)** 机制，结合 `ScopedTimer` 类实现了对作用域执行耗时的自动化处理。

以下是其实现的核心步骤和逻辑：

### 1. 宏定义 (注册计时器)

在 `src/cae_logger.h` 中，`CAE_LOG_SCOPE` 宏被定义为：

```cpp
#define CAE_LOG_SCOPE(level, module, ...) \
    cae::ScopedTimer CAE_LOG_DETAIL_CONCAT(cae_log_scope_, __LINE__)(module, cae::Level::level, fmt::format(__VA_ARGS__))

```

* **原理**：该宏会在当前作用域内创建一个 `cae::ScopedTimer` 局部对象。
* **唯一命名**：使用 `__LINE__` 确保在同一作用域内如果有多个计时器，变量名是唯一的，避免冲突。

### 2. 构造函数 (记录起点)

当执行流进入作用域时，`ScopedTimer` 的构造函数会被调用：

```cpp
ScopedTimer::ScopedTimer(const char* module, Level level, std::string message)
    : state_(std::make_unique<ScopedTimerState>()) {
    // 1. 推入 Context 栈，记录 trace_id, span_id 等上下文信息
    const ScopeSeed seed = push_scope_context(...);
    
    // 2. 记录当前系统时间作为起点
    state_->start = Clock::now(); 
    // ... 保存其他状态 ...
}

```

* **上下文管理**：`push_scope_context` 会将当前的模块、阶段和新生成的 `span_id` 压入线程本地的 `t_context_stack`，确保计时器能够关联到正确的异步任务链中。

### 3. 析构函数 (计算并提交耗时)

当执行流**离开**作用域（无论是正常结束、异常退出还是 `return`）时，局部对象 `ScopedTimer` 会自动销毁，触发析构函数：

```cpp
ScopedTimer::~ScopedTimer() noexcept {
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

* **自动化**：由于析构函数是 C++ 保证执行的，无论代码块如何退出，耗时都会被准确记录。

### 4. 数据落地 (EventKind::Span)

在 `LoggerCore::emit_scope_record` 中，该记录被标记为 `EventKind::Span`：

* **JSONL 输出**：在 `JsonlAnalysisPrinter::write` 中，如果记录的 `event_kind` 为 `Span`，程序会将计算出的 `duration_us` 写入 `.jsonl` 文件中的 `duration_us` 字段。
* **降级处理**：如果 `duration_us` 计算异常，代码会通过 `clamp_duration` 确保耗时至少为 1 微秒，避免记录为 0。

### 总结

`CAE_LOG_SCOPE` 的精妙之处在于它不需要开发者手动编写 `start` 和 `end` 代码。**只要代码块结束，析构函数自动执行差值计算并调用 `emit_scope_record**`，从而将耗时数据无缝地集成到结构化日志（JSONL）中。