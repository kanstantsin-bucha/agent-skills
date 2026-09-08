---
name: dart-tca-testing
description: Use when writing or restructuring any Dart TCA test — TestStore reducer tests, the _Sut/_runSut factory pattern, spy clients, pre-populating initial state, or widget tests needing dependency overrides. Replaces the older dart-testing-sut skill.
---

# Dart TCA — tests

Every test file wires its subject, spy dependencies and initial state in **one** place: a `_Sut` record plus a factory.

```dart
typedef _Sut = ({
  TestStore<MyState, MyAction> store,
  List<AnalyticsEvent> analyticsEvents,   // one field per spy sink asserted against
});
```

Only the subject and raw sinks — no derived state, no helpers.

## Pick the factory shape

**Does the feature read `dependency(...)`?**

**No → `_createSut()` returns directly:**

```dart
_Sut _createSut() => (store: TestStore(initialState: MyState(), reducer: MyFeature()));
```

**Yes → `_runSut(...)` with a body callback.** Overrides are zone-scoped (`withDependencies`) and **there is no `TestStore` override hook**, so the zone must stay alive across store construction *and* every `send`/`await`. The factory therefore cannot return — it hands the SUT to an async body:

```dart
Future<void> _runSut({
  required Future<void> Function(_Sut sut) body,
  Destination? destination,                 // feeds initial-state construction
  bool paired = false,                      // spy knobs — only what varies
  MyState Function(MyState)? prepareState,  // pure transform, always last
}) {
  final analyticsEvents = <AnalyticsEvent>[];
  return withDependencies((d) {
    d.analytics = _recordingAnalytics(analyticsEvents);   // spies built INSIDE
    d.accessorySetup = _accessorySetup(paired: paired);
  }, () async {
    var initialState = MyState(destination: Presents(destination));
    initialState = prepareState?.call(initialState) ?? initialState;
    final store = TestStore(initialState: initialState, reducer: MyFeature());
    await body((store: store, analyticsEvents: analyticsEvents));
  });
}
```

Rules:

- **Spies are created inside the factory**, never passed in; expose their sinks via `_Sut`.
- Parameters = only what varies between tests.
- `prepareState` is last, optional, `null` default. Dart has no `inout` — it is a pure `State → State` transform: `prepareState: (s) => s.copyWith(loadedColors: colors)`.
- **Install a benign spy for every client the reducer can reach.** `.live()` closures throw by design; a missing override surfaces as an `UnimplementedError` from inside an effect, not a clear failure.
- Pass an **async** body and `await` the returned future, so the microtask flush stays inside the zone.

## Spy clients

Clients are struct-of-closures, so a spy is just closures capturing a sink — no mock framework (`dart-tca-dependencies`).

```dart
AnalyticsClient _recordingAnalytics(List<AnalyticsEvent> sink) =>
    AnalyticsClient(log: sink.add, isConfigured: () => true,
        cleanup: () {}, setMachine: (_) {});
```

Wire only the closures the tested path calls. Configuration knobs become named parameters with defaults. **A knob returning `Completer<...>().future` stalls an effect deliberately** — the standard way to stop an action chain early. Shared model builders are top-level `_createXxx()` functions with sensible defaults.

## Test body

```dart
test('...', () async {
  await _runSut(destination: …, body: (sut) async {
    sut.store.receive(expectedFollowUp, (s) => s.copyWith());   // BEFORE the send
    sut.store.send(action, (s) => s.copyWith(field: newValue));
    await Future<void>.delayed(Duration.zero);                  // flush microtask delivery
    sut.store.verifyNoPendingActions();
    expect(sut.analyticsEvents, [AnalyticsEvent.setupStarted]);
  });
});
```

Four rules that cause most failures:

1. **Register `receive` BEFORE the `send` that triggers it.** The expected-action queue is consumed by the effect subscription as actions arrive; registering afterwards throws `UnexpectedAction`.
2. **Flush before asserting.** `Effect.action` emits through `Stream.value`, asynchronously.
3. **The expected-state closure must return a NEW instance** — `(s) => s` throws `ExpectedIsSameInstance`. Return `s.copyWith()`; a zero-field state has no `copyWith`, so return a fresh instance.
4. **`TestStore` has no `state` getter** (only `Store` does). Every assertion lives inside the `send`/`receive` closures.

`send`/`receive` closures are **exhaustive** — they must reproduce the whole post-state or you get `UnexpectedChanges`. That is the point: it catches a field the reducer changed and the test did not predict. Falling back to a plain `Store` + field-by-field `expect`s is a **last resort**, only for a value that genuinely cannot have value equality; say why in a comment.

## Test design constraints

- **Never queue the same action twice in one chain.** The listener does both `removeAt(0)` and `remove(action)`, so matching the first deletes the second while consuming only one state closure → `UnexpectedAction` or phantom pending updates. Split the scenario, or stall the effect with a hanging spy future.
- **Never assert on `Effect.merge` ordering** with 3+ effects unless verified for that exact shape (`dart-tca-effects`).
- **A latched effect chain is proved by counting armed waits, not by reading the flag** — a duplicate chain sets the same flag and just runs twice as fast.
- **Red-proof only NEW guard mechanisms.** Do not re-prove a guard already proven elsewhere in the suite.

## Widget tests

Install dependency wiring **before** `pumpWidget` (the appear effect fires synchronously on first build), and never `pumpAndSettle` — a spinner never settles. Use `tester.pump()`.

## When a test fails confusingly

`references/teststore-failures.md` — `UnexpectedAction` / `UnexpectedChanges` / `ExpectedIsSameInstance`, unhandled zone errors, and failures attributed to the wrong test.
