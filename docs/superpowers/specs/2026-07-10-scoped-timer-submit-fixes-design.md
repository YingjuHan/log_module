# ScopedTimer Explicit Submit Fixes Design

## Context

Commit `9a573fec` changed `ScopedTimer` so that a span is emitted only after an
explicit `submit()` call. The project remains version `1.0.0`, and this work
does not preserve source or binary compatibility with callers that relied on
the previous automatic-emission behavior.

The follow-up fixes address exception safety, behavioral test coverage, and
public documentation without changing the selected explicit-submit contract.

## Public behavior

- `CAE_LOG_SCOPE(level)` creates an inactive timer configuration.
- `module(...)` and `message(...)` only configure the timer.
- `submit()` creates the scope context and arms the timer.
- A submitted timer emits its elapsed-time span when it leaves scope.
- A timer that was not submitted emits nothing and creates no scope context.
- Directly constructed `cae::ScopedTimer` objects follow the same explicit
  submit contract and require `timer.submit()`.
- `cancel()` removes an existing scope context and prevents span emission.
- The package version remains `1.0.0`; compatibility with callers compiled or
  written for the previous automatic-submit behavior is not a requirement.

## Exception safety

`ensure_scope_context()` must treat context creation and state initialization
as one transaction. After `push_scope_context()` succeeds, any exception while
copying the returned seed into `ScopedTimerState` must pop the newly created
context before propagating the exception.

`submit()` remains `noexcept`: it calls the transactional helper, marks the
timer submitted only after the state is complete, and suppresses any exception
after rollback. A failed submission therefore leaves the timer unsubmitted and
does not affect later events on the same thread.

## Tests

The runtime scope test will verify all externally observable context behavior:

1. An unsubmitted scope emits no span.
2. A normal event written inside an unsubmitted scope has no timer parent span.
3. A submitted scope does not emit its span until scope exit.
4. A normal event written inside a submitted scope uses the timer span as its
   `parent_span_id` and shares its `trace_id`.
5. The emitted scope span contains a positive `duration_us`.

The public-header contract test will continue to assert that `submit()` is part
of the `ScopedTimer` API. Existing CTest and Python suites remain regression
gates.

The allocation-failure rollback path is implemented structurally with a local
rollback guard because deterministic allocation-failure injection would require
test-only production hooks or global allocator replacement. The runtime parent
context checks cover the normal transaction boundaries without adding such
hooks.

## Documentation

The public API table and direct-construction examples will state that
`cae::ScopedTimer(module, level, message)` requires `timer.submit()`. Macro
documentation continues to show `.module(...).message(...).submit()`.

## Verification

- Run the focused runtime scope CTest from a fresh consumer build.
- Run all seven CTest smoke tests.
- Run `python -m unittest discover -s tools/tests` from `test`.
- Run `git diff --check`.
- Review the final diff for version stability, exception rollback, context
  assertions, and documentation consistency.
