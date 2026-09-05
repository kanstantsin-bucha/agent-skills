---
name: dart-testing-sut
description: Use when writing or restructuring Dart TCA unit tests — TestStore reducer tests, widget tests needing dependency overrides, structuring test files, creating spy clients, or pre-populating initial state.
---

# Dart Testing SUT Pattern

## Overview

Every test file wires its subject, spy dependencies, and initial state in one place: a `_Sut` record plus a factory. This is the Swift `SystemUnderTests`/`createSut` pattern adapted to the Dart TCA port (zone-scoped dependencies, immutable `copyWith` states, synchronous `TestStore`). Companion skills: dart-tca (reducers/effects — includes the Effect/TestStore runtime quirks that shape expectations), dart-tca-dependencies (client/`withDependencies` machinery).

## The _Sut record

A `typedef` record — value semantics, named fields, no class boilerplate:

```dart
typedef _Sut = ({
  TestStore<MyState, MyAction> store,
  List<AnalyticsEvent> analyticsEvents,   // spy recording sink
});
```

- One field per spy sink the tests assert against. Only the subject and raw sinks — no derived state or helpers.

## Two factory shapes

**Decision:** does the feature read `dependency(...)`?

**No dependencies → `_createSut()` returns directly** (Swift-style):

```dart
_Sut _createSut() => (
      store: TestStore(initialState: MyState(), reducer: MyFeature()),
    );
```

**Has dependencies → `_runSut(...)` with body callback.** Overrides are zone-scoped (`withDependencies`; there is NO TestStore override API), and the zone must stay alive across every `send` and `await` — so the factory cannot return; it hands the SUT to an async body:

```dart
Future<void> _runSut({
  required Future<void> Function(_Sut sut) body,
  Destination? destination,            // feeds initial-state construction
  bool paired = false,                 // spy knobs — only what varies
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

**Rules (same as Swift):**
- Spies are created inside the factory, never passed in; expose their sinks via `_Sut`.
- Parameters = only what varies between tests.
- `prepareState` is last, optional, `null` default. Dart has no `inout` — it is a pure `State → State` transform: `prepareState: (s) => s.copyWith(loadedColors: colors)`.
- Install a benign spy for **every** client the reducer can touch — never rely on the throwing `.live()` defaults.

## Spy clients

Clients are struct-of-closures; a spy is just closures capturing a sink (no mock framework):

```dart
AnalyticsClient _recordingAnalytics(List<AnalyticsEvent> sink) =>
    AnalyticsClient(log: sink.add, isConfigured: () => true,
        cleanup: () {}, setMachine: (_) {});
```

Wire only the closures the tested path calls; configuration knobs become named parameters with defaults (`_accessorySetup({paired = false})`). A knob returning `Completer<...>().future` stalls an effect deliberately (useful to stop an action chain early). Shared model builders: top-level `_createXxx()` functions with sensible defaults.

## Test body essentials

```dart
test('...', () async {
  await _runSut(destination: ..., body: (sut) async {
    sut.store.receive(expectedFollowUp, (s) => s.copyWith());  // if effect emits
    sut.store.send(action, (s) => s.copyWith(field: newValue));
    await Future<void>.delayed(Duration.zero);   // flush microtask-delivered actions
    sut.store.verifyNoPendingActions();
    expect(sut.analyticsEvents, [AnalyticsEvent.setupStarted]);
  });
});
```

## Common mistakes

| Mistake | Fix |
|---|---|
| Passing spies into the factory | Create inside; expose sinks via `_Sut` |
| `createSut` returns while feature has dependencies | Zone dies at return — use the `_runSut` body-callback shape |
| Expected-state closure returns `s` unchanged | Throws `ExpectedIsSameInstance` — return `s.copyWith()` |
| `s.copyWith()` on a zero-field state | Not generated — return a fresh instance, e.g. `(s) => StartScreenState()` |
| Sync `verifyNoPendingActions()` right after `send` when an effect emits | Follow-ups arrive on a microtask — `await Future<void>.delayed(Duration.zero)` first |
| `receive` with a rebuilt `List` payload | Case-subclass `==` is identity for lists — pass the same instance the reducer emits |
| Nulling child state via `copyWith(x: null)` | `?? this.x` keeps old value — fields are `Presents<T?>`; use `Presents(null)` |
| Same action queued twice via `receive` | TestStore removes both on first match → desync — split the test or stall the effect with a hanging spy future |
| Expecting merged-effect actions in list order | 3+-way `Effect.merge` delivers later-listed effects first — reverse the `receive` order |
| `onError:` effect fails the test with an unhandled zone error | By design it re-emits the raw error — wrap send+flush in `runZonedGuarded`, assert the captured error |
