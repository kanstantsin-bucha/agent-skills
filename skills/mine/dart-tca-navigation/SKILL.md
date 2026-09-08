---
name: dart-tca-navigation
description: Use when a Dart/Flutter TCA feature presents another screen, sheet, modal or alert — destination enums, destinationIfLet composition, dismissal ownership, handling a child's Output, sending an Input down — or when a destination compiles but never routes.
---

# Dart TCA — destinations

**Presentation always goes through a destination enum. A child never dismisses itself** — it reports what happened, the parent decides.

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

Two parallel enums, **identical case names in the same order**. One `Presents<XDestination?>` field on state; the state class mixes in `Presentable` (`dart-tca-state`).

- Use a destination enum **even with one child today**. A bare `Presents<ChildState?>` forces a rewrite of the parent's state, actions and tests the moment a second child appears.
- The destination case lives at **`internal.destination.<case>`**, never as a fifth top-level action case. Top level stays exactly the four taxonomy words (`dart-tca-actions`).
- Present: `copyWith(destination: Presents(TodayDestinationEnum.slipLog(SlipLogState())))`. Dismiss: `copyWith(destination: Presents(null))`.
- **Auto-dismiss is never wired** (`NavigationDestination`, `Presents` auto-null-on-dispose). It mutates reducer state from a view's dispose callback, inverting the whole design. Every transition is explicit in a reducer.

## Composition

Confine every key-path hop to **one** helper. No feature, view or test file calls `.path` or `chainCase` directly.

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

`.path<S?>` needs the **explicit type argument**: the generated case path is already `WritableKeyPath<D, S?>`, and the `Presents` extension would otherwise infer a non-null `Deeper` and reject it. That TYPE requirement is the real — and only — reason `.path()` is used here.

> **A correction worth knowing.** Earlier revisions justified `.path()` by claiming its in-place `Presents` mutation is what propagates dismissal, and that `chainCase` would break it. That is **wrong in this flow**: swapping in a deliberately-wrong rebuild-the-cell hop left every reducer test passing, dismissal included. The parent nulls the destination in its own `Reduce`, which runs *before* the `IfLet`; the `IfLet` then reads `null` and skips the child. In-place mutation only matters for the auto-dismiss path, which is banned. **No test guards a regression here.**

Bind a per-feature wrapper once. It **cannot** be made generic over the parent — `XStatePath.destination` is a static on a generated extension with no interface to abstract over — so this 12-line wrapper is deliberate copy-paste per feature.

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

// build() — Scopes, then own Reduce, then the IfLets. Order matters.
Reduce.combine([
  Reduce(_reduce),
  _dest(TodayDestinationPath.slipLog, TodayDestinationActionPath.slipLog, SlipLogFeature()),
]);
```

⚠️ **Nothing type-checks that `stateCase` and `actionCase` name the SAME case.** `_dest(XDestinationPath.slipLog, XDestinationActionPath.milestone, …)` compiles and then silently never routes. It fails closed rather than corrupting state, but it is a nasty debugging trap. One `_dest` line per case; the two path names must match. Check this in review.

For the view side use a `destinationPaths(...)` twin in the same file, returning the `({state, action})` record for `store.view`. `destinationIfLet` delegates to it, so both sides share one implementation.

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

The output is payload-free; the parent re-derives the result from state (`dart-tca-actions`).

## Sending an Input down

A fully-nested parent action built from generated `…Enum.` factories, routed by the parent's `IfLet`. Never a direct key-path write, never bypassing the reducer.

```dart
store.send(TodayActionEnum.internal(TodayInternalEnum.destination(
    TodayDestinationActionEnum.slipLog(
        SlipLogActionEnum.input(SlipLogInputEnum.reset())))));
```

## The one view-side rule that belongs here

⚠️ **`store.view` on a `Presentable` parent silently selects the auto-dismissing overload.** `StorePresentable.view`'s `onDispose` writes `null` into the parent's `destination` — exactly the inversion this design bans.

**Consequence: never call `dispose()` on a scoped destination store.** Dropping the reference is the only safe teardown, at the cost of one leaked `syncStream` listener per presentation. A `StoreHost` mixin must NOT dispose-all on dismissal. Everything else about presenting in a widget tree is in `dart-tca-view`.

## Scaling up

A parent that scopes **tabs or siblings** as well as presenting destinations hits three further traps — single-hop `Scope` paths, `dynamic`-instantiated bounds, and transitive-bounds imports (worth 451 analyze errors when missed). Read `references/composing-at-scale.md` **before** writing such a parent, not after.

## Common mistakes

| Mistake | Symptom |
|---|---|
| Bare `Presents<ChildState?>` field | Works until child #2, then a parent rewrite |
| Destination as a fifth top-level case | Breaks the taxonomy; longer chains everywhere |
| Child dismisses itself | Reducer no longer owns navigation; races with the parent |
| `stateCase`/`actionCase` name different cases | Compiles, never routes, no error |
| `.path` without `<S?>` | "argument type `WritableKeyPath<D, S?>` can't be assigned" |
| `dispose()` on a scoped destination store | Auto-dismiss overload nulls parent state from a view callback |
| `Output` carries a reducer-built object | `UnexpectedAction` as an unhandled zone error in tests |
