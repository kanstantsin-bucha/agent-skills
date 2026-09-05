---
name: dart-tca-navigation
description: Use when a Dart/Flutter TCA feature presents another screen, sheet, modal or alert — designing Action sub-enums (View/Internal/Output/Input), destination enums, IfLet composition, dismissal, Android back, or scoping a child Store in a view.
---

# Dart TCA — actions and destinations

## Overview

Two rules cover almost every navigation bug in this port:

1. **Actions are split four ways** by *direction of travel* — `View`, `Internal`, `Output`, `Input`.
2. **Presentation always goes through a destination enum.** Never a bare `Presents<ChildState?>` field.

A child never dismisses itself. It reports what happened; the parent decides.

## The four sub-enums

```dart
@CaseKeyPathable()
sealed class TodayAction<
  View extends TodayView,
  Internal extends TodayInternal,
  Output extends TodayOutput //
> {}
```

| Sub-enum | Direction | Holds | Present? |
|---|---|---|---|
| `XView` | view → reducer | user intent: `checkInTapped`, `appeared` | whenever there is a view |
| `XInternal` | reducer → itself | effect results; shared step logic several `View` cases funnel into | usually |
| `XOutput` | child → parent | what happened, for the parent to act on | almost always |
| `XInput` | parent → child | commands pushed down into a presented child | only when needed |

**A `View` case never runs async work.** It mutates and returns `Effect.none()`, or forwards via `Effect.action(...)` to an `Internal` case that owns the effect. That is what makes one step reusable by several taps.

**A feature's own `Output` case is a no-op in its own reducer** — `case XActionOutput(): return Effect.none();`. It exists only for the parent. Exception: a root feature with no parent.

## Outputs carry no payload

The child writes its result to shared state (its client → repository), then emits a bare marker. The parent reacts and reads the value from state.

```dart
// WRONG — result travels through the screens
sealed class SlipLogOutput<SlipLogged extends Temptation> {}

// RIGHT
sealed class SlipLogOutput<SlipLogged, CancelRequested> {}
```

Why: one source of truth (a payload is a second copy that can drift); the parent usually re-derives from state anyway; and generated case `==` compares payloads with plain `==`, so a reducer-constructed object can never be matched by `TestStore.receive` — it fails as an unhandled zone error from inside a stream listener.

A payload is fine only for a value the **view** supplied (a tapped id, a typed string) or a primitive.

Name outputs for what happened (`slipLogged`, `cancelRequested`), not a fixed trio. **`failed` is never an output** — a failure is an `Internal` case that presents an error destination.

## Destinations, always

```dart
@CaseKeyPathable()
sealed class TodayDestination<
  SlipLog extends SlipLogState,
  Milestone extends MilestoneState //
> {}

@CaseKeyPathable()
sealed class TodayDestinationAction<
  SlipLog extends SlipLogAction,
  Milestone extends MilestoneAction //
> {}
```

Two parallel enums, **identical case names in the same order**. One `Presents<XDestination?>` field on state; the state class mixes in `Presentable`.

Use a destination enum **even with one child today** — a bare `Presents<ChildState?>` forces a state/action/test rewrite of the parent the moment a second child appears.

The destination case lives at **`internal.destination.<case>`**, never as a fifth top-level action case. Top level stays exactly the four taxonomy words.

```dart
TodayState({Presents<TodayDestination?>? destination})
    : destination = destination ?? Presents(null);   // not const; init-list, not a default
```

`Presents` exists because generated `copyWith` is `?? this.x` and **can never null a plain nullable field**. Present with `copyWith(destination: Presents(TodayDestinationEnum.slipLog(SlipLogState())))`; dismiss with `copyWith(destination: Presents(null))`.

## Composition

Confine every key-path hop to one helper. No feature, view or test file calls `.path` or `chainCase`.

```dart
Reducer<P, PA> destinationIfLet<P, PA, PI, D, DA, S, A>({
  required WritableKeyPath<P, Presents<D?>> destination,
  required WritableKeyPath<PA, PI?> internalAction,
  required WritableKeyPath<PI, DA?> destinationAction,
  required WritableKeyPath<D, S?> stateCase,
  required WritableKeyPath<DA, A?> actionCase,
  required Reducer<S, A> reducer,
}) =>
    IfLet<P, PA, S, A>(
      state: destination.path<S?>(stateCase),
      action: internalAction.chainCase(destinationAction).chainCase(actionCase),
      reducer: reducer,
    );
```

`.path<S?>` needs the **explicit type argument**: the generated case path is already `WritableKeyPath<D, S?>`, and the `Presents` extension otherwise infers a non-null `Deeper` and rejects it.

State side must use `.path()` — it mutates the `Presents` cell in place, and that reference mutation is what propagates dismissal. `chainCase` alone early-returns the root on null and silently breaks dismissal.

Bind a per-feature wrapper once (it cannot be generic — `XStatePath.destination` is a static on a generated extension):

```dart
Reducer<TodayState, TodayAction> _dest<S, A>(
  WritableKeyPath<TodayDestination, S?> stateCase,
  WritableKeyPath<TodayDestinationAction, A?> actionCase,
  Reducer<S, A> reducer,
) => destinationIfLet(
      destination: TodayStatePath.destination,
      internalAction: TodayActionPath.internal,
      destinationAction: TodayInternalPath.destination,
      stateCase: stateCase, actionCase: actionCase, reducer: reducer,
    );

// build(), in this order: Scopes, own Reduce, then the IfLets
Reduce.combine([
  Reduce(_reduce),
  _dest(TodayDestinationPath.slipLog, TodayDestinationActionPath.slipLog, SlipLogFeature()),
]);
```

⚠️ **Nothing type-checks that `stateCase` and `actionCase` name the same case.** Mismatched paths compile and then silently never route. Fails closed, but it is a nasty debugging trap — one `_dest` line per case, names must match. Check in review.

## Handling a child's output

```dart
case TodayDestinationActionSlipLog(:final slipLog):
  if (slipLog is SlipLogActionOutput) {
    switch (slipLog.output) {
      case SlipLogOutputSlipLogged():
      case SlipLogOutputCancelRequested():
        state.mutate((s) => s.copyWith(destination: Presents(null)));
    }
  }
  return Effect.none();
```

## Sending an Input down

A fully-nested parent action built from generated `…Enum.` factories, routed by the parent's `IfLet`. Never a direct key-path write, never bypassing the reducer.

```dart
store.send(TodayActionEnum.internal(TodayInternalEnum.destination(
    TodayDestinationActionEnum.slipLog(
        SlipLogActionEnum.input(SlipLogInputEnum.reset())))));
```

## View side

- Navigation is a declarative `switch` over `store.state.destination.value`. Never `Navigator.push`, never `NavigationDestination` auto-dispose (it nulls parent state from the view's dispose callback, bypassing the reducer).
- Modals are a state-driven `Stack` layer (`ModalBarrier(dismissible: false)` + centred `Material`), not `showDialog`.
- Android back: `PopScope(canPop: false)` + send an action. Defer to a deeper level first: `if (store.state.destination.value != null) return;`.
- **Never call `store.view(...)` inside `build`** — it leaks a `syncStream` listener per call and nothing disposes it. Memoize the scoped child store in the `State`, drop it on dismissal, null it in `didUpdateWidget` when `!identical(oldWidget.store, widget.store)`.

## The appeared pattern

`View.appeared` forwards to `Internal.load` (one-shot) **and** `Internal.observeChanges` (long-lived subscription) as two separate cases, so a re-load never re-subscribes. `observeChanges` must be idempotent:

```dart
case TodayInternalObserveChanges():
  if (state.value.isObserving) return Effect.none();
  state.mutate((s) => s.copyWith(isObserving: true));
  return Effect.stream(() => _challenge.activeChanges().map(_loadedAction));
```

Not optional: a view re-fires `onAppear` when its store instance changes, and the package's cancellation is globally keyed and unusable as a guard (see dart-tca-code). Without the flag you get a second subscription and every change handled twice.

## Common mistakes

| Mistake | Symptom |
|---|---|
| Bare `Presents<ChildState?>` field | Works until child #2, then a parent rewrite |
| Destination as a fifth top-level case | Breaks the taxonomy; longer chains elsewhere |
| Child dismisses itself | Reducer no longer owns navigation; races with the parent |
| `Output` carries a reducer-built object | `UnexpectedAction` as an unhandled zone error in tests |
| `chainCase` for the `Presents` hop | Dismissal silently stops working |
| `.path` without `<S?>` | "argument type `WritableKeyPath<D, S?>` can't be assigned" |
| `store.view` in `build` | Listener leak per rebuild |
| `stateCase`/`actionCase` name different cases | Compiles, never routes, no error |
| `View` case runs an effect | Step logic can't be reused by another tap |
