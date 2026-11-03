---
name: swift-testing-porting
description: Use when migrating, porting, or converting XCTest (XCTestCase) tests to Swift Testing (@Suite/@Test/#expect), or reviewing such a migration. Also use when a ported test crashes the test process with no failure message, hangs until the time limit, traps with SIGTRAP in dispatch_assert_queue / swift_task_isCurrentExecutor, or silently vanishes while the suite still reports success.
---

# Porting XCTest to Swift Testing

## Overview

A port keeps every assertion, wait and `// Given / When / Then` block, and changes only the framework. The danger is in what looks equivalent but isn't: `#expect` keeps going after it fails, `confirmation` never waits, and suite-level `@MainActor` changes the isolation of closures.

**REQUIRED SKILL:** `swift-testing-sut` and `swift-testing-spy` before you touch the test files. Also `swift-testing-tca` when the subject is a `TestStore`.

Mechanical mapping (asserts, declarations, `file:/line:`, `setUp`/`tearDown`): [references/mapping.md](references/mapping.md).

## The Four Rules

**1. `XCTAssertNotNil` → `#require`, never `#expect(x != nil)` followed by use.**
```swift
let status = try #require(calls.encoder.element(at: 0) as? Tenbeauty_Api_ManicureStatus)
#expect(status.status == .running)   // drop the `?.` that followed
```
`#expect` records the failure and carries on, so a later `x!` crashes the whole test process: every remaining suite is lost and there's no failure message. If `x` isn't optional (for example a function that throws instead of returning nil), the old check was always true, so **delete it** or assert something real.

**2. Never put `try?` inside `#expect` or around an assertion.** Mark the test `throws` and write `#expect(try sut.map(x) == y)`. With `try?` a thrown error only shows up as `nil == value`. `try? XCTAssertNoThrow(...)` swallows the error completely, so make the call with a plain `try`. If it ran inside `queue.async`, switch to `try queue.sync { ... }` so the error reaches the test, after checking that the path doesn't `DispatchQueue.main.sync`.

**3. An inverted expectation needs a watch window.** `isInverted` plus `wait(timeout: 0.5)` means "nothing happens within 0.5s". To keep that:
```swift
try await confirmation(expectedCount: 0) { event in
    let c = publisher.sink { _ in event() }
    await doWork()
    try await Task.sleep(for: .milliseconds(500))
    c.cancel()
}
```
`Confirmation` is `Sendable`, so this also replaces a captured `var` counter that a background queue changes.

**4. Every XCTest `wait(timeout:)` needs a matching bound.** A bare `withCheckedContinuation` or `await task.value` has no timeout, so a regression turns a 0.5s failure into a 60s `.timeLimit` kill. Bound Combine waits with `.timeout(...).replaceEmpty(with: false).first()`, and end long-running `TestStoreTask`s with `await task.cancel()`.

When a module has many `XCTestExpectation`s with `expectedFulfillmentCount` (work that notifies asynchronously), don't hand-convert each one into `confirmation`. Port them all onto one bounded, thread-safe expectation helper that keeps XCTest's semantics: return early once everything is fulfilled, and watch the full timeout for inverted ones. Reference: `Projects/Services/DeviceSimulator/Tests/Helpers/Helpers+Expectation.swift`.

## Isolation: Don't Add It, Don't Remove It

- Put `@MainActor` on the `@Suite` **only if every original test was `@MainActor`**. Leave suites whose tests were nonisolated without it. When the original isolation was mixed, keep `@MainActor` on just those tests.
- A helper that was nonisolated and builds spy handler closures (`spy.saveHandler = { ... }`) **must become `nonisolated`** inside a `@MainActor` suite. Otherwise the closures inherit `@MainActor`, production calls them from a background queue, and Swift 6 traps (`SIGTRAP` in `dispatch_assert_queue`). Never "clean up" an existing `nonisolated` helper like this.
- `[weak self]` doesn't compile in a struct suite. Capture `self` directly.

## Parallelism and Teardown

XCTest ran tests one at a time; Swift Testing runs them in parallel. If a suite touches global state (a mock simulator, `.shared` singletons, files), use `@Suite(.serialized)`. `tearDown` becomes a `final class` suite with `deinit`. `TrackForLeaks`/`addTeardownBlock` becomes `TestKitHelpers.withMemoryLeakTracking { leakTracker in ... }`, which needs `TestKit` + `IssueReportingTestSupport` on the test target. Custom error stubs become `TestKitHelpers.TestError.test`.

## Verify Every Test Still Ran

A crashed suite can still report "passed".
1. Record the baseline **before** editing: total from the xcresult (`xcrun xcresulttool get test-results summary --path <xcresult>`). XCTest's "Executed N tests" leaves out existing Swift Testing tests.
2. After the port, the totals and the per-suite counts must match. `testThat…` names and methods without `@MainActor` are easy for a regex to miss.
3. Grep the log: more than one `Test Suite 'Selected tests' started` means the process restarted. Check `~/Library/Logs/DiagnosticReports` for new `xctest-*.ips`.
4. Run it twice. Parallel execution plus tight timeouts shows flakiness on the second run.
5. `make generate_sim` after adding/renaming files and after every test run.

## Red Flags

| Thought | Reality |
|---|---|
| "`#expect(x != nil)` is the direct translation" | Use `#require`, or delete the check if `x` is non-optional (rule 1) |
| "`confirmation` replaces `XCTestExpectation`" | It doesn't wait, so async callbacks arrive after it has checked (rule 4) |
| "Suite-level `@MainActor` everywhere is cleaner" | It moves nonisolated handlers onto main, and they trap off-main |
| "This `nonisolated` looks redundant" | It keeps handler closures off `@MainActor`, so leave it |
| "All green, done" | Compare test counts with the baseline first |
| Code-review line numbers | They may be positions in the diff: grep for the code before editing |
