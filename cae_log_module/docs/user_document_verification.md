# user_document.md 验收清单

本文件记录 `docs/user_document.md` 的章节级验证结果，目标是把“规范说明”和“当前实现已证实的行为”区分开。

验证基线：

- 文档目标文件：`docs/user_document.md`
- 对应示例代码：`sample/user/user_document_demo.cpp`
- 构建入口：`sample/CMakeLists.txt`
- 主要实现依据：`src/cae_logger.h`、`src/cae_*.h`、`src/cae_*.cpp`
- 主要校验工具：`python -m tools.cae validate`、`python -m tools.cae summary`，低层模块为 `tools.pipeline.validate_cae_events`、`tools.reporting.summarize_cae_report`

本轮实测命令：

```powershell
test\build.cmd --config Debug --skip-e2e
test\build.cmd --config Debug --ctest-only
pushd test
.\build\Debug\user_document_demo.exe DocAudit_1
python -m tools.cae validate .\build\Debug\logs\cae_events_pid*.jsonl --strict
python -m tools.cae summary --input .\build\Debug\logs\cae_events_pid19900.jsonl --output-dir .\out\reports\user_doc_audit
popd
```

本轮实测产物：

- JSONL：`test/build/Debug/logs/cae_events_pid19900.jsonl`
- 摘要：`test/out/reports/user_doc_audit/cae_summary.json`
- 模块统计：`test/out/reports/user_doc_audit/cae_module_stats.csv`
- 告警：`test/out/reports/user_doc_audit/cae_alerts.json`

## 验收结果

| 章节 | 结果 | 证据 | 备注 |
| --- | --- | --- | --- |
| 1. 目标 | `PASS` | 示例日志覆盖结构化事件、span、trace、metrics、warn/error、跨线程 trace 续传 | 这是目标描述，不是逐句可执行断言 |
| 2. 成熟 CAE 软件实践借鉴 | `PASS` | 文档明确写为“设计借鉴”，未把外部产品行为写成组件强约束 | 属于设计背景说明 |
| 3. 快速接入 | `PASS` | `sample/user/user_document_demo.cpp` 覆盖最小接入、`LoggerOptions`、配置文件接入等价路径 | 文档已补充验证入口 |
| 4. 配置项说明 | `PASS` | `load_options_from_file()`、`normalize_options()`、`LoggerOptions` 字段定义可对照验证 | `call_chain_max_depth`/`skip` 上限 128 已实现 |
| 5. API 必填、业务必填、自动处理字段 | `PASS` | `src/cae_logger.h`、`src/cae_*.h` 和 `src/cae_*.cpp` 已核对；`action` 默认值已修正文档 | 业务必填属于规范要求，不是编译器强制 |
| 6. JSONL 顶层字段规范 | `PASS` | `python -m tools.cae validate` 严格校验通过；`cae_events_pid19900.jsonl` 共 28 条有效事件 | `node_id` 为可选语义字段，与实现一致 |
| 7. API 选择原则 | `PASS` | 示例中分别覆盖 `CAE_LOG`、`CAE_SCOPE_TASK`、`*_DUR`、文本宏、`CAE_LOG_SCOPE*` | 属于推荐规范 |
| 8. 宏合法用法总览 | `PASS` | `sample/user/user_document_demo.cpp` 对应覆盖 8.1-8.7；8.8/8.9 由头文件宏定义和实现佐证 | `CAE_SCOPE_TASK` 使用 `##__VA_ARGS__` 已验证 |
| 9. 等级使用规范 | `PASS` | 示例中出现 `Trace/Debug/Info/Warn/Error/Critical`；错误场景含 `reason` | 属于规范建议，非自动校验项 |
| 10. result 与 reason 枚举 | `PASS` | 示例和日志中已出现 `started/completed/cancelled/failed/degraded`、`disk_full/user_cancelled/non_convergence/mesh_quality_failed` | 枚举表是规范，不是代码枚举类型 |
| 11. metrics 命名规范 | `PASS` | 示例覆盖 `iteration/residual/courant/converged/export_bytes` 等键；校验器验证类型 | “键名稳定”仍需靠人工评审维持 |
| 12. CAE 工作流推荐日志点 | `PASS` | 示例覆盖 System/Geometry/Mesh/Solver/PostProcess.Output 等代表性日志点 | 推荐项不是强制完整列表 |
| 13. 隐私、安全和知识产权 | `PASS` | 示例全部使用脱敏文件名和 case/session 名称，未泄露路径、token、模型数据 | 主要依赖代码评审，不是自动工具强校验 |
| 14. 性能与限流 | `PASS` | 文档表述与实现无冲突；`flush_level=Error`、`ProcessModel::MultiProcess` 已实测 | 属于运行策略建议 |
| 15. 推荐模板 | `PASS` | 示例代码逐类覆盖 success point、warn、error、正常/失败 span、跨线程 workflow | 可直接对照 `sample/user/user_document_demo.cpp` |
| 16. 发布前代码审查清单 | `PASS` | 与当前实现和示例一致，没有发现明显误导项 | 这是审查清单，不是执行结果 |
| 17. 最低校验要求 | `PASS` | `python -m tools.cae validate`、`python -m tools.cae summary` 已实测通过 | `python -m tools.cae verify` 当前可用，但对本次文档验证不是最小必需 |

## 已确认的关键实现事实

1. `TaskScope` 默认 `action` 是 `scope`。
2. `ScopedTimer` 默认 `action` 是 `timed_scope`。
3. `TaskScope` 自然析构会自动写入 `result="completed"` 的 `span`；`ScopedTimer` 需要先调用 `.submit()`，再由析构写入 span。
4. `cancel()` 会阻止上述自动 completed span 落盘。
5. `ProcessModel::MultiProcess` 会把 JSONL 输出到 `cae_events_pidID.jsonl`，而不是固定的 `cae_events.jsonl`。
6. 未设置 `thread_name` 时默认 `tid:ID`。
7. 未设置 `node_id` 时会尝试取 `COMPUTERNAME`/`HOSTNAME`，否则为 `unknown-node`。
8. Builder 未设置 `message` 时会兜底为 `structured event`。
9. `span` 事件在 Windows 上会自动附带 `metrics.memory_mb`。
10. `tools.pipeline.validate_cae_events` 已严格检查 `event_kind`、`duration_us`、`trace_id`、`span_id`、`parent_span_id`、`metrics` 类型。

## 本轮发现并已修复的问题

1. 文档原先把默认 `action` 描述得过于宽泛，已改为按事件来源区分。
2. 文档原先给出的 JSONL 校验路径写成固定 `cae_events.jsonl`，与 `MultiProcess` 示例不一致，已改为 `cae_events_pid*.jsonl`。
3. 文档原先没有给出对应的可执行验证代码入口，已补充 `sample/user/user_document_demo.cpp` 与构建/测试入口。

## 仍需注意的边界

1. 第 9、13、14、16 章大部分是规范性要求，当前更多依赖代码评审和人工约束，而不是自动工具强校验。
2. 全量 `ctest --test-dir test/build/Debug -C Debug --output-on-failure` 在当前环境下耗时较长，本轮多次超过 300 秒超时；因此它更适合作为回归测试，不适合作为文档最小验证命令。
3. `python -m tools.cae verify` 属于更重的端到端链路验证，低层模块是 `tools.verify.e2e_verify`，适合在 schema、报表链路或日志聚合逻辑有改动时补跑。


## 独立消费者接入验证

- 独立工程：sample/user/independent_consumer/
- 构建：cmake -S sample/user/independent_consumer -B build/independent_consumer -Dcae_logger_DIR=D:/workspace/log/log_module/build/install/main/lib/cmake/cae_logger
- 编译：cmake --build build/independent_consumer
- 运行：build/independent_consumer/independent_consumer.exe
- 产物：build/independent_consumer/doc_logs/consumer_events.jsonl
- 校验：python -m tools.cae validate build/independent_consumer/doc_logs/consumer_events.jsonl --strict
- 结果：通过，日志包含 1 条结构化事件，session=IndependentCase_001。
