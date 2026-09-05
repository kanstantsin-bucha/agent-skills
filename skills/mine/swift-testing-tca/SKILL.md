---
name: swift-testing-tca
description: Use when writing, porting, or reviewing TCA TestStore tests under Swift Testing (@Suite/@Test) — covers target setup, suite isolation, send/receive assertions, long-running effects, and exhaustivity. Also use when a TestStore test crashes with EXC_BAD_ACCESS, SIGSEGV, or "Test crashed with signal segv" with no assertion message and no crash report, or when a test silently vanishes from the runner output while the suite still reports success.
---

# Testing TCA Features With Swift Testing

`TestStore` works under Swift Testing. Write TCA tests as `@Suite`/`@Test` like
any other test in this repo — there is no need to fall back to `XCTestCase`.

**REQUIRED SKILL:** `swift-testing-sut` for the `SystemUnderTests` / `createSut`
structure. **REQUIRED SKILL:** `swift-testing-spy` when the feature has
dependencies to stub.

## Target Setup

A test target running `TestStore` under Swift Testing must link
`IssueReportingTestSupport`. Add it once per target, then `make generate_sim`:

```swift
// Project.swift — the unit-tests target
dependencies: [
    .target(name: "MyModule"),
    .external(name: "ComposableArchitecture"),
    .external(name: "IssueReportingTestSupport"),   // required for TestStore
]
```

Tuist prunes SPM products nothing references, so this is not built until a target
names it. If it is missing, every `TestStore` test in the target segfaults — see
Troubleshooting.

## Writing The Test

```swift
@Suite
@MainActor
struct MyFeatureTests {

    @Test("confirmTapped sends output confirmed")
    func confirmTapped_sendsOutputConfirmed() async {
        // Given
        let sut = createSut()
        sut.service.stubbedItems = [.fixture]

        // When
        await sut.store.send(.view(.confirmTapped))

        // Then
        await sut.store.receive(.output(.confirmed))
    }

    // MARK: - Helpers

    private struct SystemUnderTests {
        let store: TestStoreOf<MyFeature>
        let service: MyServiceSpy
    }

    private func createSut(
        title: String = "Title",
        prepareState: ((inout MyFeature.State) -> Void)? = nil
    ) -> SystemUnderTests {
        var initialState = MyFeature.State(title: title)
        prepareState?(&initialState)

        let serviceSpy = MyServiceSpy()

        let store = TestStore(initialState: initialState) {
            MyFeature()
        } withDependencies: {
            $0.myService = serviceSpy
        }

        return .init(store: store, service: serviceSpy)
    }
}
```

### Annotate the whole suite `@MainActor`

`TestStore` is declared `@preconcurrency @MainActor`. Put `@MainActor` on the
`@Suite` type, not on individual members — one annotation then covers every
`@Test`, `createSut`, and any private helper that touches the SUT.

```swift
@Suite
@MainActor
struct MyFeatureTests { ... }
```

Per-member annotation is the trap. The moment a nonisolated helper receives the
`SystemUnderTests` struct back from a `@MainActor createSut`, a non-`Sendable`
`TestStoreOf<Feature>` crosses an isolation boundary. It compiles only because of
that `@preconcurrency`, and it is an error under Swift 6 strict concurrency.
Scattering `@MainActor` across some tests but not others produces the same slip
by accident and hides it behind whichever tests happen not to await an effect.

**This costs no parallelism.** `TestStore.init` sets the process-global
`uncheckedUseMainSerialExecutor = true`, which hooks `swift_task_enqueueGlobal_hook`
so every job enqueued anywhere in the process is redirected to `MainActor.shared`
for as long as any store is alive. All test work is already funnelled onto the
main thread; the annotation just makes the compiler check the isolation you
already have.

Once the suite is isolated, `createSut` is a synchronous call from a
main-actor context: write `let sut = createSut()`, not `await createSut()`.
The `await` is only required while the test body is nonisolated, and the
compiler warns about it here.

`@MainActor` is not `.serialized`. Tests still start concurrently and interleave
at every `await` — suites with long suspensions overlap exactly as before. If you
need true one-at-a-time execution, that is the `.serialized` trait.

### Long-Running Effects: Cancel The Task

When an action starts an effect that never completes on its own — a `.publisher`
subscription, a timer, an `AsyncStream` — hold the `TestStoreTask` that `send`
returns and cancel it. That is what the view's `.task` modifier does on dismissal,
so the test models the real lifecycle:

```swift
let task = await sut.store.send(.internal(.task))

await sut.store.receive(\.internal.stateChanges) { $0.items = [...] }

await task.cancel()
```

**Never reach for `skipInFlightEffects` to satisfy the store.** It looks like the
tidy way to say "I'm done with the leftovers," and under Swift Testing it makes
the test disappear:

`skipInFlightEffects` finds a live effect, and reports it through
`reportIssueHelper(overrideExhaustivity: .off(showSkippedAssertions: true))`,
which wraps the report in `withExpectedIssue`. Under Swift Testing that resolves
to `Testing.withKnownIssue`, so the test is recorded as **`Expected Failure`** —
and xcbeautify prints no line at all for that result. The runner shows four `✔`
for a six-test suite, omits the `Suite … passed` line, and still exits
`Test Succeeded`. Nothing hangs and nothing is skipped; the result is simply
invisible.

Under XCTest the same code took the `XCTExpectFailure` branch, which the
formatter *does* print — which is why this only surfaces after a port.

**Confirming it:** the runner output is not authoritative. Read the result bundle:

```bash
R=$(ls -td ~/Library/Developer/Xcode/DerivedData/*/Logs/Test/*.xcresult | head -1)
xcrun xcresulttool get test-results tests --path "$R"
```

A `"result" : "Expected Failure"` node for a test with no visible line confirms
this diagnosis. `await task.cancel()` turns it back into `Passed`.

`await sut.store.finish()` remains correct for effects that *do* complete — it
waits for them rather than declaring them unexamined.

### Exhaustivity

Leave exhaustivity at its default (`.on`). Set `sut.store.exhaustivity = .off`
only when a specific test genuinely requires it — a feature with many irrelevant
state changes, or a large integrated store where pinning every mutation adds
noise rather than coverage.

Do not turn it off globally, by habit, or to make a failing assertion pass. That
discards the guarantee that makes `TestStore` worth using: every state mutation
and every received action is accounted for.

### Porting From XCTest

| From | To |
|---|---|
| `final class X_Tests: XCTestCase` | `@Suite @MainActor struct XTests` |
| `func test_foo_bar()` | `@Test("human readable description") func foo_bar()` |
| `XCTAssertEqual(a, b)` | `#expect(a == b)` |
| `XCTAssertNil(a)` / `XCTAssertTrue(a)` / `XCTAssertFalse(a)` | `#expect(a == nil)` / `#expect(a)` / `#expect(!a)` |

`import XCTest` pulls in Foundation transitively; `import Testing` does not. Any
file declaring `LocalizedError` stubs, using `Date`, `URL`, `Data`, etc. needs an
explicit `import Foundation` added during the port.

Preserve every assertion and the `// Given` / `// When` / `// Then` structure. A
port is not a rewrite of the test logic.

## Quick Reference

| Need | Do |
|---|---|
| Isolate the tests | `@MainActor` on the `@Suite` type, once |
| Build the store | `private func createSut(...) -> SystemUnderTests` |
| Seed state | `prepareState` closure, last param, optional, defaults `nil` |
| Stub a dependency | `withDependencies:` in `createSut`, spy exposed on the SUT struct |
| Send a view action | `await sut.store.send(.view(.tapped))` |
| Assert an effect's action | `await sut.store.receive(.output(.confirmed))` |
| Assert a state change | trailing closure on `send`/`receive` |
| Wait for effects that finish | `await sut.store.finish()` |
| End an effect that never finishes | hold the `TestStoreTask`, `await task.cancel()` |
| Relax assertions | `sut.store.exhaustivity = .off` — only when required |

## Common Mistakes

| Mistake | Fix |
|---|---|
| `@MainActor` on `createSut` only | Put it on the `@Suite` type — otherwise the non-`Sendable` SUT crosses an isolation boundary on the way back |
| `@MainActor` on some tests but not others | Annotate the suite once; per-test isolation drifts silently |
| `skipInFlightEffects` to quiet a live effect | `await task.cancel()` — skipping records a known issue and the test vanishes from the output |
| Trusting the runner's `✔` count | A missing `Suite … passed` line means results were swallowed; check the `.xcresult` |
| `exhaustivity = .off` to quiet a failure | Fix the assertion; the failure is the point |
| `@Test(arguments:)` | Parameterized tests silently never run here — use a local `arguments` array and a `for` loop in the test body |
| Reaching for `XCTestCase` after a segfault | Check the target links `IssueReportingTestSupport` first |
| `Cannot find type 'LocalizedError'` after porting | Add `import Foundation` — `import XCTest` provided it transitively, `import Testing` does not |

## Troubleshooting: TestStore Segfault

**Symptoms:** `EXC_BAD_ACCESS` / `KERN_INVALID_ADDRESS` at a small address (e.g.
`0x1f0`) inside `TestStore.init`, before any `send`. No assertion message, no
crash report surfaced by the runner, which may silently relaunch the suite in a
loop. Pure-value tests in the same suite pass. The same assertions pass under
`XCTestCase`. Reproduces with a single test, no parallelism.

**Cause:** the target does not link `IssueReportingTestSupport`. `TestStore.init`
→ `SharedChangeTracker.track` → `CachedValues.CacheKey.init` → `TestContext.current`
→ `IssueReporting._currentTest()`, which `dlsym`s a symbol from that dylib. When
the lookup fails, DEBUG builds fall back to a hand-maintained replica of Swift
Testing's internal `Test` struct filled via `unsafeBitCast`; a layout mismatch
makes ARC's outlined destroy release a field at a wrong offset. XCTest is immune
only because `Test.current` is `nil` there, so the replica is never built — which
is why porting to `XCTestCase` appears to "fix" it while hiding the real cause.

**Fix:** add the dependency (see Target Setup), `make generate_sim`, then verify:

```bash
grep -o 'IssueReportingTestSupport.framework' \
  Projects/<Path>/<Name>.xcodeproj/project.pbxproj
```

**Does not help** — all tried, crash survived: `@MainActor` on the suite or test
(correct for other reasons, see above, but irrelevant here), `await store.finish()`,
`exhaustivity = .off`, `@Suite(.serialized)`.

**Confirming a fresh crash.** The runner prints nothing useful, so read the real
backtrace rather than guessing:

```bash
ls -t ~/Library/Logs/DiagnosticReports/xctest-*.ips | head -1
```

The `.ips` is JSON-lines: a metadata line, then the body. Parse
`body['threads'][body['faultingThread']]['frames']` and map each `imageIndex`
through `body['usedImages']` for symbol names. Frames reading
`outlined destroy of Test?` → `_swift_release_dealloc` confirm this diagnosis;
anything else is a different bug.
