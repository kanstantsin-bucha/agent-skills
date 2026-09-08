---
name: dart-tca-actions
description: Use when writing or changing a Dart TCA `<x>_action.dart` — the View/Internal/Output/Input sub-enums, case payloads, grouping large enums, or output naming. Also when build_runner emits a doubled type like `Challenge??` or dies with "Named parameters must be enclosed in curly braces".
---

# Dart TCA — action enums

Actions split four ways **by direction of travel**. A `@CaseKeyPathable` sealed class's cases ARE its type parameters: `extends T` gives the case a payload of `T`, a bare name gives a zero-arg marker.

```dart
@CaseKeyPathable() sealed class TodayView<Appeared, CheckInTapped> {}
@CaseKeyPathable() sealed class TodayInternal<Load, ChallengeLoaded extends Challenge, ChallengeCleared> {}
@CaseKeyPathable() sealed class TodayOutput<SlipLogged, CancelRequested> {}

@CaseKeyPathable()
sealed class TodayAction<
    View extends TodayView,
    Internal extends TodayInternal,
    Output extends TodayOutput //
    > {}
```

The action file **must NOT `import 'package:collection/collection.dart'`** — no `DeepCollectionEquality` is generated, so it fails analyze as `unused_import`. (The state file must.)

The trailing `//` before the closing `>` is deliberate: it forces `dart format` to keep one type parameter per line. Keep it.

| Sub-enum | Direction | Holds | Present? |
|---|---|---|---|
| `XView` | view → reducer | user intent only: `checkInTapped`, `appeared` | whenever there is a view |
| `XInternal` | reducer → itself | effect results, and shared step logic several `View` cases funnel into | usually |
| `XOutput` | child → parent | what happened, for the parent to act on | almost always |
| `XInput` | parent → child | commands pushed down into a presented child | only when a parent must drive the child |

Top level stays **exactly** these four words. A destination is not a fifth case — it nests at `internal.destination.<case>` (`dart-tca-navigation`).

## A `View` case never runs async work

It either mutates state and returns `Effect.none()`, or forwards via `Effect.action(...)` to an `Internal` case that owns the effect. **The hop is mandatory even when there is only one caller** — it is what makes a step reusable by several taps, and it keeps the effect in one testable place.

A feature's own `Output` case is a no-op in its own reducer (`case XActionOutput(): return Effect.none();`); it exists only for the parent. Exception: a root feature with no parent.

## Never a nullable type-parameter bound

The generator appends `?` to the declared bound unconditionally, so `<Loaded extends Challenge?>` emits `WritableKeyPath<XInternal, Challenge??>`.

```dart
// WRONG — does not compile
sealed class TodayInternal<ChallengeLoaded extends Challenge?> {}

// RIGHT — absence is a case, not a nullable payload
sealed class TodayInternal<ChallengeLoaded extends Challenge, ChallengeCleared> {}
```

The error never names the cause: the parser gives up mid-file with **`Named parameters must be enclosed in curly braces ('{' and '}')`** pointing at generated code, then cascades. Since "I loaded something that may be absent" is the commonest action shape in any app, this bites every feature. Choose the case at the boundary:

```dart
TodayAction _loadedAction(Challenge? c) => c == null
    ? _clearedAction
    : TodayActionEnum.internal(TodayInternalEnum.challengeLoaded(c));
```

## Payloads: only what the view supplied

A payload is acceptable only for a value the **view** handed in (a tapped id, a typed string) or a primitive. **Never for an object the reducer built.**

Generated case-subclass `==` compares payloads with plain `==`, so a reducer-constructed object is identity-only — `TestStore.receive` can never match it, and the failure surfaces as an unhandled zone error from inside a stream listener rather than a clean assertion.

**Outputs are payload-free.** The child writes its result to shared state (its client → repository), then emits a bare marker; the parent reacts to the marker and reads the value from state.

```dart
// WRONG — the result travels through the screens
sealed class SlipLogOutput<SlipLogged extends Temptation> {}

// RIGHT — the child persisted it; the marker just says what happened
sealed class SlipLogOutput<SlipLogged, CancelRequested> {}
```

Why: one source of truth (a payload is a second copy that can drift, at every screen it passes through); the parent re-derives from state anyway; and it keeps actions matchable in tests.

## Naming

- Domain names, not a fixed trio: `slipLogged`, `cancelRequested`, `checkInSucceeded`. `succeed` when there is no better domain name.
- **`failed` is never an Output.** A failure is an `Internal` failure case that presents an error destination — never reported upward.
- Construct via the generated extension (`TodayActionEnum.internal(TodayInternalEnum.load())`); match with `case TodayActionInternal(:final internal):`.
- Generated names are `<Class><Case>` and get long. Do **not** reach for import prefixes — Dart has no namespaces and prefixes break generated cross-feature references.

## Grouping: sub-enums stay small

Past roughly **six cases, split the sub-enum into cohesive groups**, each its own `@CaseKeyPathable` class, and fan out per group in the reducer exactly as `_reduce` fans out per sub-enum.

```dart
sealed class UrgeLoggerInternal<
    Loading extends UrgeLoggerLoadingInternal,
    Breathing extends UrgeLoggerBreathingInternal,
    Audio extends UrgeLoggerAudioInternal //
    > {}
```

Do this for readability. There is also a hard generator cap on case count — see `dart-tca-codegen` if you hit a `RangeError` from the generator.

## Ambient values a bloc view used to read from a parent

A `BlocBuilder` could reach up with `context.watch<AppCubit>()`. A TCA feature has no ambient parent state, so **those values become fields on the feature's own state, loaded by its own client on `appeared`.** Not an `Input` from the parent, not a client read at render time — this is the only shape that keeps the feature standalone and testable.

## Cases that shadow real types

Case names derive from type-parameter names, so cases called `Error`, `Internal` or `Destination` shadow real types and need `// ignore_for_file: avoid_types_as_parameter_names` — placed **above** the `///` library doc comment. See `dart-tca-codegen`.
