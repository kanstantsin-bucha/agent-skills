# Long-Running Effects: Cancel The Task

When an action starts an effect that never completes on its own — a `.publisher`
subscription, a timer, an `AsyncStream` — hold the `TestStoreTask` that `send`
returns and cancel it. That is what the view's `.task` modifier does on dismissal,
so the test models the real lifecycle:

```swift
let task = await sut.store.send(.internal(.task))

await sut.store.receive(\.internal.stateChanges) { $0.items = [...] }

await task.cancel()
```

## Never `skipInFlightEffects`

It looks like the tidy way to say "I'm done with the leftovers," and under Swift
Testing it makes the test disappear:

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

## Confirming A Vanished Test

The runner output is not authoritative. Read the result bundle:

```bash
R=$(ls -td ~/Library/Developer/Xcode/DerivedData/*/Logs/Test/*.xcresult | head -1)
xcrun xcresulttool get test-results tests --path "$R"
```

A `"result" : "Expected Failure"` node for a test with no visible line confirms
this diagnosis. `await task.cancel()` turns it back into `Passed`.

## `task.cancel()` Asserts Nothing

Do not let it stand in for a check. A reducer that stops returning the effect
still passes a test that only sends and cancels. If the point of the test is that
the effect is running, assert it directly before cancelling: push through the
spy's subject and `receive` the resulting action, or advance the `TestClock` past
the interval and `receive` the timer's action.

`await sut.store.finish()` remains correct for effects that *do* complete — it
waits for them rather than declaring them unexamined.
