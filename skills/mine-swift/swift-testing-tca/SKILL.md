---
name: swift-testing-tca
description: Use when writing, porting, or reviewing TCA TestStore tests under Swift Testing (@Suite/@Test) — covers target setup, suite isolation, send/receive assertions, long-running effects, shared @Shared/fileStorage/appStorage state between tests, and exhaustivity. Also use when a TestStore test crashes with EXC_BAD_ACCESS, SIGSEGV, or "Test crashed with signal segv" with no assertion message and no crash report, or when a test silently vanishes from the runner output while the suite still reports success.
---

# Testing TCA Features With Swift Testing

`TestStore` works under Swift Testing. Write TCA tests as `@Suite`/`@Test` like
any other test in this repo — there is no need to fall back to `XCTestCase`.

**REQUIRED SKILL:** `swift-testing-sut` for the `SystemUnderTests` / `createSut`
structure. **REQUIRED SKILL:** `swift-testing-spy` when the feature has
dependencies to stub.

## Load The Reference That Matches

Read the file before writing or fixing the test when its condition applies:

| Read | When |
|---|---|
| [references/shared-state.md](references/shared-state.md) | The feature depends on an object holding persisted `@Shared` (`.fileStorage`, `.appStorage`); tests see each other's values; you're tempted to add `.serialized` |
| [references/long-running-effects.md](references/long-running-effects.md) | An action starts a publisher, timer, or `AsyncStream`; the store complains about in-flight effects; a test is missing from the runner output |
| [references/segfault-troubleshooting.md](references/segfault-troubleshooting.md) | `EXC_BAD_ACCESS` / signal segv inside `TestStore.init` with no assertion message |
| [references/porting-from-xctest.md](references/porting-from-xctest.md) | Converting an `XCTestCase` to Swift Testing |

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
names it. If it is missing, every `TestStore` test in the target segfaults.

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

`@MainActor` is not `.serialized`. Tests still start concurrently and interleave
at every `await`. If you need true one-at-a-time execution, that is the
`.serialized` trait.

### Exhaustivity

Leave exhaustivity at its default (`.on`). Set `sut.store.exhaustivity = .off`
only when a specific test genuinely requires it — a feature with many irrelevant
state changes, or a large integrated store where pinning every mutation adds
noise rather than coverage.

Do not turn it off globally, by habit, or to make a failing assertion pass. That
discards the guarantee that makes `TestStore` worth using: every state mutation
and every received action is accounted for.

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
| End an effect that never finishes | hold the `TestStoreTask`, `await task.cancel()` — see long-running-effects |
| Relax assertions | `sut.store.exhaustivity = .off` — only when required |
| Isolate persisted `@Shared` state | fresh instance per test — see shared-state |

## Common Mistakes

| Mistake | Fix |
|---|---|
| `@MainActor` on `createSut` only, or on some tests but not others | Put it on the `@Suite` type once |
| `skipInFlightEffects` to quiet a live effect | `await task.cancel()` — skipping makes the test vanish from the output (long-running-effects) |
| Trusting the runner's `✔` count | A missing `Suite … passed` line means results were swallowed; check the `.xcresult` (long-running-effects) |
| `exhaustivity = .off` to quiet a failure | Fix the assertion; the failure is the point |
| `.serialized` because parallel tests see each other's persisted values | Build a fresh instance per test (shared-state) |
| `@Test(arguments:)` | Parameterized tests silently never run here — use a local `arguments` array and a `for` loop in the test body |
| Reaching for `XCTestCase` after a segfault | Check the target links `IssueReportingTestSupport` (segfault-troubleshooting) |
