# ScopedTimer Explicit Submit Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make explicit `ScopedTimer::submit()` context handling exception-safe, cover parent-span behavior, and document direct-construction requirements while keeping version `1.0.0` and intentionally not preserving old behavior.

**Architecture:** Keep the public explicit-submit contract unchanged. Add a local RAII rollback guard around the already-existing TLS context push, expand the runtime smoke test to observe inherited trace/span fields, and add static contract tests that force the new runtime and documentation coverage to exist.

**Tech Stack:** C++11, CMake/Ninja, MinGW GCC, CTest, Python `unittest`, Markdown.

---

## File map

- `cae_log_module/src/cae_scoped_timer.cpp`: make scope-context state initialization transactional.
- `cae_log_module/src/cae_scoped_timer.h`: clarify that every constructor requires `submit()` before scope exit.
- `test/sample/runtime_scope_submit.cpp`: verify unsubmitted and submitted parent/trace context behavior using real JSONL output.
- `test/tools/tests/test_cpp_schema_contract.py`: enforce the rollback guard and runtime context assertions as repository contracts.
- `cae_log_module/docs/user_document.md`: document direct construction with `timer.submit()`.
- `test/tools/tests/test_cae_logger_docs_install_contract.py`: enforce the direct-construction documentation example.

### Task 1: Cover scope parent-context behavior

**Files:**
- Modify: `test/tools/tests/test_cpp_schema_contract.py:90-98`
- Modify: `test/sample/runtime_scope_submit.cpp:59-170`

- [ ] **Step 1: Add a failing static contract for the missing runtime assertions**

Add this method to `CppSchemaContractTests`:

```python
    def test_runtime_scope_submit_verifies_parent_context(self) -> None:
        runtime_test = (TEST_ROOT / "sample" / "runtime_scope_submit.cpp").read_text(
            encoding="utf-8"
        )

        self.assertIn("string_json_field", runtime_test)
        self.assertIn("scope_without_submit_child_has_no_parent", runtime_test)
        self.assertIn("scope_with_submit_child_inherits_parent", runtime_test)
        self.assertIn('string_json_field(submitted_line, "span_id")', runtime_test)
        self.assertIn('string_json_field(submitted_child_line, "parent_span_id")', runtime_test)
```

- [ ] **Step 2: Run the contract test and verify RED**

Run from `D:\workspace\log_module\test`:

```powershell
python -m unittest tools.tests.test_cpp_schema_contract.CppSchemaContractTests.test_runtime_scope_submit_verifies_parent_context
```

Expected: one failure because `runtime_scope_submit.cpp` does not contain `string_json_field` or the two child-event markers.

- [ ] **Step 3: Add JSON string parsing and real parent-context assertions**

Add this helper after `line_containing()` in `runtime_scope_submit.cpp`:

```cpp
std::string string_json_field(const std::string& line, const std::string& key) {
    const std::string marker = "\"" + key + "\":\"";
    const std::size_t start = line.find(marker);
    require_true(start != std::string::npos, "missing JSON string field: " + key);

    const std::size_t value_begin = start + marker.size();
    const std::size_t value_end = line.find('"', value_begin);
    require_true(value_end != std::string::npos, "unterminated JSON string field: " + key);
    return line.substr(value_begin, value_end - value_begin);
}
```

Replace `test_scope_requires_submit_and_keeps_elapsed_time()` with this complete function:

```cpp
void test_scope_requires_submit_and_keeps_elapsed_time(const std::string& base_dir) {
    const std::string log_dir = join_path(base_dir, "scope_submit");
    make_directory(log_dir);

    const std::string skipped_message = "scope_without_submit_should_not_emit";
    const std::string unsubmitted_child_message = "scope_without_submit_child_has_no_parent";
    const std::string submitted_message = "scope_with_submit_records_elapsed_time";
    const std::string submitted_child_message = "scope_with_submit_child_inherits_parent";
    const std::string text_log = text_log_path(log_dir, "ScopeSubmit");
    const std::string analysis_log = analysis_log_path(log_dir);

    cae::init(make_options(log_dir));
    {
        CAE_LOG_SCOPE(Info)
            .module("ScopeSubmit")
            .message(skipped_message);
        CAE_LOG(Info)
            .module("ScopeSubmit")
            .message(unsubmitted_child_message)
            .submit();
        tiny_work();
    }
    require_true(!file_contains(text_log, skipped_message),
                 "CAE_LOG_SCOPE without submit should not write when its local block exits");

    const std::string unsubmitted_child_line = line_containing(analysis_log, unsubmitted_child_message);
    require_true(!unsubmitted_child_line.empty(), "unsubmitted scope child event should be present");
    require_true(string_json_field(unsubmitted_child_line, "parent_span_id").empty(),
                 "unsubmitted scope must not create a parent span context");

    std::string submitted_child_parent_span_id;
    std::string submitted_child_trace_id;
    {
        CAE_LOG_SCOPE(Info)
            .module("ScopeSubmit")
            .message(submitted_message)
            .submit();
        tiny_work();
        CAE_LOG(Info)
            .module("ScopeSubmit")
            .message(submitted_child_message)
            .submit();

        const std::string submitted_child_line = line_containing(analysis_log, submitted_child_message);
        require_true(!submitted_child_line.empty(), "submitted scope child event should be present");
        submitted_child_parent_span_id = string_json_field(submitted_child_line, "parent_span_id");
        submitted_child_trace_id = string_json_field(submitted_child_line, "trace_id");
        require_true(!submitted_child_parent_span_id.empty(),
                     "submitted scope child event should inherit a parent span");
        require_true(!file_contains(text_log, submitted_message),
                     "CAE_LOG_SCOPE with submit should not write before its local block exits");
        require_true(line_containing(analysis_log, submitted_message).empty(),
                     "CAE_LOG_SCOPE with submit should not write analysis before its local block exits");
    }

    require_true(file_contains(text_log, submitted_message),
                 "CAE_LOG_SCOPE with submit should write a text record when its local block exits");
    require_true(!file_contains(analysis_log, skipped_message),
                 "CAE_LOG_SCOPE without submit should not write an analysis record");

    const std::string submitted_line = line_containing(analysis_log, submitted_message);
    require_true(!submitted_line.empty(), "submitted scope should be present in analysis log");
    require_true(submitted_line.find("\"event_kind\":\"span\"") != std::string::npos,
                 "submitted scope should be written as a span event");
    require_true(unsigned_json_field(submitted_line, "duration_us") > 0,
                 "submitted scope should record elapsed time in duration_us");
    require_true(string_json_field(submitted_line, "span_id") == submitted_child_parent_span_id,
                 "submitted scope span should be the child event parent");
    require_true(string_json_field(submitted_line, "trace_id") == submitted_child_trace_id,
                 "submitted scope and child event should share a trace id");

    cae::shutdown();
}
```

- [ ] **Step 4: Run the static contract and focused runtime test**

Run:

```powershell
python -m unittest tools.tests.test_cpp_schema_contract.CppSchemaContractTests.test_runtime_scope_submit_verifies_parent_context
cmake --build D:/workspace/log_module/test/build/codex_review --target runtime_scope_submit -j1
ctest --test-dir D:/workspace/log_module/test/build/codex_review -C Debug -R runtime_scope_submit_smoke --output-on-failure
```

Expected: the Python contract passes and `runtime_scope_submit_smoke` reports `1/1` passed.

- [ ] **Step 5: Commit the context coverage**

```powershell
git add -- test/sample/runtime_scope_submit.cpp test/tools/tests/test_cpp_schema_contract.py
git commit -m "test: verify scoped timer parent context"
```

### Task 2: Make scope-context setup transactional

**Files:**
- Modify: `test/tools/tests/test_cpp_schema_contract.py:90-115`
- Modify: `cae_log_module/src/cae_scoped_timer.cpp:1-147`

- [ ] **Step 1: Add a failing exception-safety contract**

Add this method to `CppSchemaContractTests`:

```python
    def test_scoped_timer_context_setup_has_rollback_guard(self) -> None:
        implementation = (MODULE_ROOT / "src" / "cae_scoped_timer.cpp").read_text(
            encoding="utf-8"
        )

        self.assertIn("class ScopeContextRollback", implementation)
        self.assertIn("detail::pop_scope_context(mySpanId);", implementation)
        self.assertIn("ScopeContextRollback aRollback(aSeed.span_id);", implementation)
        self.assertIn("aRollback.release();", implementation)
```

- [ ] **Step 2: Run the contract test and verify RED**

Run from `D:\workspace\log_module\test`:

```powershell
python -m unittest tools.tests.test_cpp_schema_contract.CppSchemaContractTests.test_scoped_timer_context_setup_has_rollback_guard
```

Expected: one failure because `ScopeContextRollback` is not defined.

- [ ] **Step 3: Add the minimal rollback guard**

In `cae_scoped_timer.cpp`, add `<type_traits>` to the standard includes and add this anonymous-namespace helper after `ScopedTimerState`:

```cpp
namespace
{

static_assert(std::is_nothrow_move_constructible<detail::ScopeSeed>::value,
              "ScopeSeed must be nothrow movable after its context is pushed");

class ScopeContextRollback
{
  public:

    explicit ScopeContextRollback(const std::string& theSpanId) noexcept
    : mySpanId(theSpanId)
    {
    }

    ~ScopeContextRollback() noexcept
    {
        if (myIsActive)
        {
            detail::pop_scope_context(mySpanId);
        }
    }

    void release() noexcept
    {
        myIsActive = false;
    }

  private:

    const std::string& mySpanId;
    bool               myIsActive = true;
};

} // namespace
```

Change the start and end of `ensure_scope_context()` so the returned seed is non-const and guarded until state initialization finishes:

```cpp
    const std::string aModule = !myState->component.empty() ? myState->component : "default";
    detail::ScopeSeed aSeed =
        detail::push_scope_context(aModule, detail::derive_stage_from_component(aModule), "timed_scope", "");
    ScopeContextRollback aRollback(aSeed.span_id);

    myState->component = aSeed.component;
    myState->stage = aSeed.stage;
    myState->action = aSeed.action;
    myState->trace_id = aSeed.trace_id;
    myState->span_id = aSeed.span_id;
    myState->parent_span_id = aSeed.parent_span_id;
    myState->has_scope_context = true;
    aRollback.release();
```

- [ ] **Step 4: Run focused contracts and rebuild the library**

Run:

```powershell
python -m unittest tools.tests.test_cpp_schema_contract.CppSchemaContractTests.test_scoped_timer_context_setup_has_rollback_guard
cmake --build D:/workspace/log_module/cae_log_module/build/codex_review --target cae_logger -j1
cmake --install D:/workspace/log_module/cae_log_module/build/codex_review --config Debug --prefix D:/workspace/log_module/cae_log_module/install/codex_review
cmake --build D:/workspace/log_module/test/build/codex_review --target runtime_scope_submit -j1
ctest --test-dir D:/workspace/log_module/test/build/codex_review -C Debug -R runtime_scope_submit_smoke --output-on-failure
```

Expected: the contract passes, the library and consumer rebuild successfully, and the focused CTest reports `1/1` passed.

- [ ] **Step 5: Commit the exception-safety fix**

```powershell
git add -- cae_log_module/src/cae_scoped_timer.cpp test/tools/tests/test_cpp_schema_contract.py
git commit -m "fix: roll back failed scoped timer submission"
```

### Task 3: Document direct-construction submission

**Files:**
- Modify: `test/tools/tests/test_cae_logger_docs_install_contract.py:16-69`
- Modify: `cae_log_module/docs/user_document.md:232-242,643-676`
- Modify: `cae_log_module/src/cae_scoped_timer.h:29-36`

- [ ] **Step 1: Add a failing documentation contract**

Add this method to `CaeLoggerDocsInstallContractTests`:

```python
    def test_scoped_timer_direct_construction_documents_submit(self) -> None:
        user_document = (MODULE_ROOT / "docs" / "user_document.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("cae::ScopedTimer timer(", user_document)
        self.assertIn('"PostProcess.Reader",', user_document)
        self.assertIn("timer.submit();", user_document)
        self.assertIn("直接构造同样必须显式调用", user_document)
```

- [ ] **Step 2: Run the documentation contract and verify RED**

Run from `D:\workspace\log_module\test`:

```powershell
python -m unittest tools.tests.test_cae_logger_docs_install_contract.CaeLoggerDocsInstallContractTests.test_scoped_timer_direct_construction_documents_submit
```

Expected: one failure because the direct-construction example and explicit sentence are absent.

- [ ] **Step 3: Update the public documentation and constructor comments**

Change the API table description for `cae::ScopedTimer(module, level, message)` to:

```markdown
| `cae::ScopedTimer(module, level, message)`                  | `module`、`level`、`message`               | 创建简易计时 scope；必须显式调用 `timer.submit()` 后才会在退出作用域时写出。 |
```

After the macro example in section 8.5, add:

````markdown
直接构造同样必须显式调用 `submit()`：

```cpp
void open_reader() {
    cae::ScopedTimer timer(
        "PostProcess.Reader",
        cae::Level::Info,
        "Reader open scope completed.");
    timer.submit();
    open_result_reader();
}
```
````

Update both constructor comments in `cae_scoped_timer.h` to say:

```cpp
    //! Starts a timer for the specified module and message; call `submit()` to arm it.
```

- [ ] **Step 4: Run the focused documentation contract**

Run:

```powershell
python -m unittest tools.tests.test_cae_logger_docs_install_contract.CaeLoggerDocsInstallContractTests.test_scoped_timer_direct_construction_documents_submit
```

Expected: one test passes.

- [ ] **Step 5: Commit the documentation fix**

```powershell
git add -- cae_log_module/docs/user_document.md cae_log_module/src/cae_scoped_timer.h test/tools/tests/test_cae_logger_docs_install_contract.py
git commit -m "docs: require submit for direct scoped timers"
```

### Task 4: Full verification and final review

**Files:**
- Verify all files changed in Tasks 1-3.

- [ ] **Step 1: Confirm the version remains intentionally unchanged**

Run:

```powershell
rg -n "PROJECT_VERSION|PROJECT_VERSION_MAJOR|SOVERSION|SameMajorVersion" D:/workspace/log_module/cae_log_module/CMakeLists.txt
```

Expected: `PROJECT_VERSION 1.0.0`, major version `1`, `SOVERSION` based on that major, and `SameMajorVersion` remain present.

- [ ] **Step 2: Rebuild and reinstall the library from current source**

Run:

```powershell
cmake --build D:/workspace/log_module/cae_log_module/build/codex_review --target cae_logger -j1
cmake --install D:/workspace/log_module/cae_log_module/build/codex_review --config Debug --prefix D:/workspace/log_module/cae_log_module/install/codex_review
```

Expected: both commands exit with code `0`.

- [ ] **Step 3: Rebuild all test consumers and run CTest**

Run:

```powershell
cmake --build D:/workspace/log_module/test/build/codex_review -j1
ctest --test-dir D:/workspace/log_module/test/build/codex_review -C Debug --output-on-failure
```

Expected: all seven CTest tests pass.

- [ ] **Step 4: Run the complete Python suite**

Run from `D:\workspace\log_module\test`:

```powershell
python -m unittest discover -s tools/tests
```

Expected: the suite exits with code `0`; the environment may report one existing skipped test.

- [ ] **Step 5: Inspect formatting, diff, and repository state**

Run:

```powershell
git diff --check HEAD~3 HEAD
git status --short
git diff HEAD~3 HEAD -- cae_log_module/src/cae_scoped_timer.cpp cae_log_module/src/cae_scoped_timer.h test/sample/runtime_scope_submit.cpp test/tools/tests/test_cpp_schema_contract.py test/tools/tests/test_cae_logger_docs_install_contract.py cae_log_module/docs/user_document.md
```

Expected: no whitespace errors; only the pre-existing untracked archive files remain outside committed work; the diff contains the rollback guard, context assertions, and direct-construction documentation.

- [ ] **Step 6: Request an independent code review**

Provide the reviewer with the implementation commit range and ask them to check explicit-submit semantics, rollback lifetime/reference safety, trace/span assertions, documentation accuracy, and version stability. Resolve any P0-P2 finding before completion.
