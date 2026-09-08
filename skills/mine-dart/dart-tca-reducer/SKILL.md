---
name: dart-tca-reducer
description: Use when writing or changing a Dart TCA `<x>_feature.dart` — the Feature subclass, build(), the _reduce fan-out switch, state mutation, dependency getters, action helpers or reducer-level asserts.
---

# Dart TCA — reducer body shape

```dart
final class TodayFeature extends Feature<TodayState, TodayAction> {
  // MARK: Dependencies
  ChallengeClient get _challenge => dependency((d) => d.challenge);
  DateClient get _date => dependency((d) => d.date);

  // MARK: Body
  @override
  Reducer<TodayState, TodayAction> build() => Reduce(_reduce);

  Effect<TodayAction> _reduce(Inout<TodayState> state, TodayAction action) {
    switch (action) {
      case TodayActionView(:final view):
        return _reduceView(state, view);
      case TodayActionInternal(:final internal):
        return _reduceInternal(state, internal);
      case TodayActionOutput():
        return Effect.none();     // for the parent only
    }
  }

  // MARK: Private
  Effect<TodayAction> _reduceView(Inout<TodayState> state, TodayView view) { … }

  // MARK: Action helpers
  TodayAction get _loadAction =>
      TodayActionEnum.internal(TodayInternalEnum.load());
}
```

## Rules

- **The top-level `_reduce` is a pure fan-out** — a total `switch` that dispatches to one `_reduceX` per sub-enum, with no logic of its own. Sub-enums grouped into sub-sub-enums fan out the same way, one level deeper.
- **No `default:` in any switch, anywhere in the file.** Exhaustiveness must be compiler-enforced — that is what turns a new action case into a compile error instead of a silent no-op. A declared-but-deliberately-unhandled case gets its own branch with a comment.
- Destructure as `case XActionY(:final y):`.
- **Mutate only via `state.mutate((s) => s.copyWith(...))`; read via `state.value`.** Never `state.value = …`.
- **Dependencies are private lazy getters on the `Feature`** — `dependency((d) => d.x)`, read per call. Never constructor-injected, never cached in a field (a cached read escapes the override zone). Reading inside an `Effect.future`/`Effect.stream` closure is fine; zone values propagate into effects. → `dart-tca-dependencies`
- **No `typedef` aliases.** When a nested `…Enum.…` chain repeats, hoist a private getter under `// MARK: Action helpers`.
- Derived **state** predicates live in `extension XStateDerived on XState` (`dart-tca-state`); derived **dependency-backed** predicates live on the `Feature`.
- Invariants are `assert(...)` **plus a production fallback**, not throws.
- Section markers: `// MARK: Dependencies`, `// MARK: Body`, `// MARK: Private`, `// MARK: Action helpers`.
- Reducer and view are **always separate files**. The reducer file is `<x>_feature.dart` and the class is `XFeature` — **never** `XReducer`.

## Composition order

When a feature both scopes siblings and presents children, `build()` combines in this exact order — it is deliberate:

```dart
Reduce.combine([
  Scope(...),        // 1. sibling / tab reducers
  Reduce(_reduce),   // 2. this feature's own body
  _dest(...),        // 3. one IfLet per destination case
]);
```

The parent nulls a destination in its own `Reduce`, which runs **before** the `IfLet`; the `IfLet` then reads `null` and skips the child. Details and the key-path helpers: `dart-tca-navigation`.

## Stub features

Porting a screen whose child isn't ported yet? Don't port the child too. Add a stub exposing exactly the state constructor and action cases the parent references, with a no-op reducer:

```dart
final class ErrorScreenFeature extends Feature<ErrorScreenState, ErrorScreenAction> {
  @override
  Reducer<ErrorScreenState, ErrorScreenAction> build() =>
      Reduce((state, action) => Effect.none());
}
```

## The `appeared` pattern

`View.appeared` forwards to `Internal.load` (one-shot). Add `Internal.observeChanges` (long-lived subscription) as a **separate case**, so a re-load never re-subscribes — but only **if** a value can actually change while the screen lives.

```dart
case TodayInternalObserveChanges():
  if (state.value.isObserving) return Effect.none();     // the latch
  state.mutate((s) => s.copyWith(isObserving: true));
  return Effect.stream(() => _challenge.activeChanges().map(_loadedAction));
```

The latch is not optional when you do subscribe: a view re-fires `onAppear` when its store instance changes, and the package's cancellation is globally keyed and unusable as a guard (`dart-tca-effects`). Without the flag you get a second subscription and every change handled twice. Carry `isObserving` through **every** branch that rebuilds state from scratch.

A short-lived modal over a frozen parent gets `load` only — no `observeChanges`, no `isObserving`. When you omit it, justify the omission in the feature's library doc: what could change, and why it can't while this screen is up. Copying a Today-style template blindly adds a pointless subscription.
