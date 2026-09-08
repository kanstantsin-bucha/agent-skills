---
name: dart-tca-code
description: Use when writing state/action classes, reducers, effects or TestStore tests in a Dart TCA project, or when build_runner emits Challenge?? / "Named parameters must be enclosed in curly braces", analyze reports annotate_overrides or unused_import on generated code, TestStore throws UnexpectedAction / UnexpectedChanges / ExpectedIsSameInstance, or a cancellable effect cancels the wrong thing.
---

# Dart TCA — codegen, effects and testing findings

## Overview

Findings verified against `composable_architecture` 0.2.0 by real compiler and test failures. Each one is a place where the **obvious Dart-idiomatic choice is wrong** because of how the generator and `TestStore` are built.

## Codegen

### Never use a nullable type-parameter bound

The generator appends `?` to the declared bound unconditionally.

```dart
// WRONG — emits WritableKeyPath<XInternal, Challenge??>
sealed class TodayInternal<ChallengeLoaded extends Challenge?> {}

// RIGHT — absence is a case, not a nullable payload
sealed class TodayInternal<ChallengeLoaded extends Challenge, ChallengeCleared> {}
```

The error does not name the cause: the parser gives up mid-file with `Named parameters must be enclosed in curly braces ('{' and '}')`, pointing at generated code, then cascades. Since "I loaded something that may be absent" is the most common action shape in any app, this bites every feature. Choose the case at the boundary:

```dart
TodayAction _loadedAction(Challenge? c) =>
    c == null ? _clearedAction : TodayActionEnum.internal(TodayInternalEnum.challengeLoaded(c));
```

### Every `@KeyPathable` field is `@override final`

The generated `_$XState` mixin declares an abstract getter per field. Without `@override` you get one `annotate_overrides` info **per field** — ten fields is an instant analyzer-baseline regression.

### `collection` import is state-only

- `@KeyPathable` **state** file with fields → **must** `import 'package:collection/collection.dart'`. The generated `==` uses `DeepCollectionEquality`; `flutter analyze` passes without it but `flutter test` fails with a misleading **"Not a constant expression"**.
- `@CaseKeyPathable` **action** file → **must not** import it. No `DeepCollectionEquality` is generated, so it fails analyze as `unused_import`.
- Zero-field states escape this (their `==` only compares `runtimeType`) — and get **no `copyWith`** at all.

### No getters on a `@KeyPathable` class

The generator scans getters as fields and emits them as `copyWith` parameters → `No named parameter with the name '<getter>'`. Put derived values in an extension:

```dart
extension TodayStateDerived on TodayState {
  bool get canCheckIn => challengeName != null && todayStatus == null;
}
```

### `ignore_for_file` goes above the doc comment

Case names derive from type-parameter names, so cases called `Error`/`Internal`/`Destination` shadow real types and need `// ignore_for_file: avoid_types_as_parameter_names`. Put it **above** the `///` library doc comment, or the doc comment detaches from `library;`.

### Sub-enum case cap

Upstream `case_key_path_generator.dart` indexes `const letters = ["A"…"I"]` by type-parameter position, so a **10th case fails codegen** with `RangeError (length): Invalid value: Not in inclusive range 0..8: 9` — naming neither the class nor the cause, while build_runner still reports "wrote N outputs". Extending `letters` to the full alphabet is a one-line fix if you control the package. Either way, past ~6 cases split the sub-enum into cohesive groups (each its own `@CaseKeyPathable` class) and fan out per group in the reducer.

### What actually gets generated

Per `@KeyPathable`: `mixin _$X` (copyWith / `==` via `DeepCollectionEquality` / hashCode / toString) + `extension XPath` (a `WritableKeyPath` per field).
Per `@CaseKeyPathable`: `extension XEnum` (static case constructors) + one `final class X<Case>` per case + `extension XPath` (case paths). **No `_$` mixin.**

Two quirks: a payload type with a zero-arg constructor becomes an **optional** parameter (`loadFailed([Object? p])`); and generated case setters **ignore the incoming root and construct a fresh case**, which is what makes key-path chaining work.

The trailing `//` before the closing `>` keeps `dart format` one-per-line. Keep it.

## Models need value equality

TCA is the architecture; models support it, not the reverse. Without `==`, state equality, `TestStore` exhaustivity, `UnexpectedChanges` diffing and view rebuild decisions all silently degrade to identity.

Give every domain and DTO model `==`/`hashCode` covering every field, deep for collections. If the domain layer is documented as package-free, hand-roll it with local `listEquals`/`mapEquals`/`Object.hashAll` helpers rather than adding `equatable`. New model ships with `==` and its equality tests in the same commit.

## Effects

| Fact | Consequence |
|---|---|
| `Effect.action` emits via `Stream.value` | Delivery is **asynchronous**; flush with `await Future<void>.delayed(Duration.zero)` before asserting |
| `Effect.merge` order is unspecified | With 3+ effects, later-listed ones can arrive first. Never write a test that depends on order unless verified for that shape |
| `onError:` re-emits the raw error after converting it | Surfaces as an unhandled zone error even though the action was delivered. Wrap the send in `runZonedGuarded` and assert on it, or try/catch inside the effect body instead |
| `Effect.async`/`Effect.sync` unused in practice | Call synchronous side effects inline in the reducer body |

### `Store.dispose()` does not cancel effect subscriptions

It only calls `_onDispose`. Combined with globally-keyed cancellation (below), **a long-lived `Effect.stream` can never be stopped safely** — it outlives the screen that started it.

- Stream is fine only for an effect meant to live as long as the app.
- For a finite long-lived effect (countdown, polling, retry), use a **self-terminating chain of one-shot effects** latched by a state flag, with every exit funnelling through one `_halt` that lowers the latch. Assert the **count of armed waits**, not the flag: a duplicate chain sets the same flag and just runs twice as fast.

### Cancellation is globally keyed and leaks

`effect.dart` holds `_cancellableEffects` and `_effectSubscriptions` as **library-level globals** keyed by the id value, and the map entry is never removed.

- A private `enum _CancelID` per feature file is safe **across features** (distinct enum values compare by identity).
- It is **not** safe across two live instances of the same feature — they share the id value and cancel each other.
- **Do not use `.cancellable`/`Effect.cancel` to prevent duplicate subscriptions.** Use a `bool isObserving` state flag instead.

## TestStore

### Register `receive` before the `send` that triggers it

The expected-action queue is consumed by the effect subscription as actions arrive. Registering after throws `UnexpectedAction`.

```dart
sut.store.receive(_internal(TodayInternalEnum.checkIn()), (s) => s.copyWith());
sut.store.receive(_internal(TodayInternalEnum.checkInSucceeded()),
    (s) => s.copyWith(checkInCompleted: true));
sut.store.send(_view(TodayViewEnum.checkInTapped()), (s) => s.copyWith());
await Future<void>.delayed(Duration.zero);
sut.store.verifyNoPendingActions();
```

### Failures surface as unhandled zone errors

The action check runs inside `stream.listen`, so an `UnexpectedAction` throw is **not** caught by the enclosing `try` or by `expect`. It is often attributed to whichever test was running. Suspect a mismatched action before suspecting the test you are looking at.

### `TestStore` has no `state` getter

Only `Store` does. Every assertion must live inside the exhaustive `send`/`receive` closures.

### Expected-state closure must return a new instance

`(s) => s` throws `ExpectedIsSameInstance`. Return `s.copyWith()`. A zero-field state has no `copyWith` — return a fresh instance, `(s) => StartScreenState()`.

`send` is exhaustive: the closure must reproduce the whole post-state or you get `UnexpectedChanges`. That is the point — it catches a field the reducer changed and the test did not predict. Fall back to a plain `Store` + field-by-field `expect`s only for a value that genuinely cannot have value equality, and say why in a comment.

### Duplicate queued actions desync the store

The listener does both `removeAt(0)` and `remove(action)`, so queueing the same action twice deletes both on first match while consuming one state closure — ending in `UnexpectedAction` or phantom pending updates. Split the scenario, or stall the effect with a hanging `Completer<...>().future` spy.

### Dependencies must stay inside the zone

There is no `TestStore` override hook. `withDependencies` must wrap store construction **and** every send/await — pass an async body and `await` the returned future so the microtask flush stays inside the zone. Install a benign spy for **every** client the reducer can reach; `.live()` closures throw by design, and a missing override shows up as an `UnimplementedError` inside an effect rather than a clear failure.

## Toolchain

The hosted package pins `analyzer ^7.2.0` (max language version 3.9), so the **generator cannot parse modern syntax** in annotated files on a newer SDK — dot-shorthands fail with `This requires the 'dot-shorthands' language feature to be enabled`, 0 outputs. Vendoring a fork with `analyzer ^8` / `source_gen ^4` / `build ^4` raises the ceiling to 3.11.

- A path override does **not** auto-apply its builders — add a root `build.yaml` naming `composable_architecture:key_path` with `generate_for: [lib/**]`.
- The `SDK language version X is newer than 'analyzer' language version Y` warning narrows but never disappears; analyzer 8.x tops out at 3.11. Expected, not a failure.
- Record provenance (upstream URL, commit, exact patch) in a `VENDORED.md`, and exclude `third_party/**` in `analysis_options.yaml` so vendored lints don't inflate your baseline.

## Common mistakes

| Mistake | Symptom |
|---|---|
| `extends Challenge?` bound | `Challenge??`; "Named parameters must be enclosed in curly braces" |
| Missing `@override` on state fields | One `annotate_overrides` info per field |
| `collection` imported in an action file | `unused_import` |
| `collection` missing from a state file | `flutter test`: "Not a constant expression" |
| Getter on a `@KeyPathable` class | "No named parameter with the name …" |
| `receive` after `send` | `UnexpectedAction`, reported against the wrong test |
| `(s) => s` in an expected-state closure | `ExpectedIsSameInstance` |
| Asserting state with an `==`-less model | `UnexpectedChanges` that looks identical when printed |
| `.cancellable` used as a subscription guard | Cancels another store's effect, or nothing |
| Assuming merge order | Passes locally, flakes later |
