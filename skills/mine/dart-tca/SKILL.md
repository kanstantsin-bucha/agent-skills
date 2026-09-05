---
name: dart-tca
description: Use when writing or porting TCA (Composable Architecture) features in Dart/Flutter — reducers, state/action classes, effects, dependencies, navigation/destinations, or when build_runner codegen fails on @KeyPathable/@CaseKeyPathable classes.
---

# Dart TCA (Composable Architecture port)

## Overview

Porting Swift TCA features to Dart with the `composable_architecture` package (use a patched fork pinned via `dependency_overrides` when the hosted version's analyzer ceiling breaks codegen; the Flutter binding `composable_architecture_flutter` can stay hosted). States are immutable `@KeyPathable` classes with generated `copyWith`/`==`; action enums are `@CaseKeyPathable` sealed classes; dependencies are zone-scoped.

**Companion skills — invoke the relevant one before working in its area:**
- **dart-tca-dependencies** — dependency clients (struct-of-closures) + the `DependencyValues` registry and zone plumbing. Required when adding/altering a client or the injection machinery.
- **dart-testing-sut** — the `_Sut`/`_runSut` unit-test pattern (TestStore, spies, `prepareState`). Required before writing any reducer test.
- **dart-tca-navigation** — the four-way action taxonomy (View/Internal/Output/Input), destination enums, `destinationIfLet` composition, dismissal and child-store scoping. Required whenever a feature presents another screen or defines its Action enums.
- **dart-tca-code** — verified codegen, effect and `TestStore` gotchas (nullable bounds, `@override` fields, `collection` import scoping, globally-keyed cancellation, `receive`-before-`send`). Read when writing state/action classes or when codegen/tests fail confusingly.

## Swift → Dart quick map

| Swift | Dart |
|---|---|
| `@Reducer` / `Reduce { }` | `Feature` subclass / `Reduce((state, action) {...})` |
| `@ObservableState struct` | `@KeyPathable() final class` + mixin `_$X` + `part 'x.g.dart'` |
| `@CasePathable enum Action` | `@CaseKeyPathable() sealed class` — cases are **type params**; `extends T` = payload of `T`, no bound = zero-arg marker |
| `state.x = y` | `state.mutate((s) => s.copyWith(x: y))` |
| `.ifLet(\.child, action:)` | `IfLet(state:, action:, reducer:)` |
| `@Presents var dest` | `Presents<T?>` field + `Presentable` mixin |
| `.send(.foo)` | `Effect.action(FooEnum.foo())` |
| `.run { send in … }` single result + catch | `Effect.future(() async {...}, onError: (e, st) => …)` |
| `.publisher` / long-lived `.run` | `Effect.stream(() => stream.map(...))` |
| `Publishers.Merge(a, b)` | `mergeStreams([a, b])` (helper below) |
| `.cancellable(id:)` / `.cancel(id:)` | `.cancellable(id)` extension / `Effect.cancel(id)` (enum `_CancelID { … }`) |
| `cancelInFlight: true` | no direct analog — prepend `Effect.cancel(id)` via `Effect.merge` |
| `Scope(state:, action: \.internal.child)` | `Scope(state: StatePath.child, action: ActionPath.internal.chainCase(InternalPath.child), reducer:)` |
| `@CasePathable` enum **in state** (e.g. loading phases) | same `@CaseKeyPathable` sealed class; `.is(\.loaded)` → `state.x is <Class>Loaded` (see equality caveat below) |
| `@Dependency(\.foo)` | getter: `FooClient get _foo => dependency((d) => d.foo);` |
| `withDependencies` | `withDependencies((d) { d.foo = …; }, () {...})` (Zone-scoped) |
| `PresentationAction` | dropped — destination actions nest directly; dismiss = `Presents(null)` |

## State and action shape

```dart
@KeyPathable()
final class TurnOnScreenState with _$TurnOnScreenState, Presentable {
  @override
  final Presents<ErrorScreenState?> error;   // dismissible child

  TurnOnScreenState({Presents<ErrorScreenState?>? error})
      : error = error ?? Presents(null);     // Presents is not const
}

@CaseKeyPathable()
sealed class TurnOnScreenOutput<CancelRequested, Succeed> {}   // zero-arg markers

@CaseKeyPathable()
sealed class TurnOnScreenInternal<
    NextTapped,
    DiscoverResult extends DiscoveryStatus,  // payload case
    DiscoverFailure extends Object //
    > {}

@CaseKeyPathable()
sealed class TurnOnScreenAction<
    Output extends TurnOnScreenOutput,
    Internal extends TurnOnScreenInternal,
    Error extends ErrorScreenAction //       // shadowing core's Error — see below
    > {}
```

- Construct cases via the generated extension: `TurnOnScreenActionEnum.internal(TurnOnScreenInternalEnum.nextTapped())`. Match with `case TurnOnScreenActionInternal(:final internal):`.
- Case-name-derived type params sometimes must shadow core types (`Error`, `Internal`): add `// ignore_for_file: avoid_types_as_parameter_names`.
- Generated names are `<Class><Case>` (long): alias locally with private typedefs (`typedef _Cancelled = FooActionCancelled;`) — works in patterns and constructors. Dart has no namespaces; import prefixes break generated cross-feature references.

## Codegen (build_runner)

- `flutter pub run build_runner build --delete-conflicting-outputs` (through `fvm` if the project uses it).
- Annotated file needs `part 'name.g.dart';`.
- **`@KeyPathable` class WITH fields → the library MUST `import 'package:collection/collection.dart'`** (generated `==` uses `DeepCollectionEquality`; `flutter analyze` passes without it but `flutter test` fails with a misleading "Not a constant expression").

## State rules

- `copyWith` uses `?? this.x` → **can never null a plain nullable field**. Any child state that must be dismissible is `Presents<Child?>`; dismiss with `copyWith(child: Presents(null))`.
- Zero-field states get **no** `copyWith` at all (mixin is only `==`/`hashCode`/`toString`).
- **No getters on a `@KeyPathable` class** — the generator scans getters as if they were fields and emits them as `copyWith` parameters ("No named parameter with the name …"). Put Swift computed `State` properties in an extension:

  ```dart
  extension MachineConnectingScreenStateDerived on MachineConnectingScreenState {
    bool get isConnected => isConnectSuccess && isNetworkServicesConnected;
  }
  ```
- Generated case-class `==` compares payloads with plain `==` — a `List` payload (e.g. `loaded([PodColor])`) compares by **identity**, unlike `@KeyPathable` field `==` (DeepCollectionEquality). Fine when the same instance flows through the reducer; in TestStore expectations reuse the instance you sent.

## Composition

Destination enum + one `IfLet` per case (no auto `Destination.body`):

```dart
@CaseKeyPathable()
sealed class Destination<
    Start extends StartScreenState,
    TurnOn extends TurnOnScreenState //
    > {}
```

The generated case paths are `WritableKeyPath<Root, Prop?>` and the built-in `.path` extensions only chain *non-null* props, so nested action enums (`internal → destination → start`) need this helper:

```dart
extension CasePathChain<A, B> on WritableKeyPath<A, B?> {
  /// Chains an inner case path; `set` rebuilds the nested enum (each generated
  /// case setter constructs a fresh case), matching how IfLet maps child
  /// effects back up.
  WritableKeyPath<A, C?> chainCase<C>(WritableKeyPath<B, C?> inner) {
    return WritableKeyPath<A, C?>(
      get: (A root) {
        final mid = get(root);
        return mid == null ? null : inner.get(mid);
      },
      set: (A? root, C? value) {
        if (value == null) return root as A;
        return set(root, inner.set(null, value));
      },
    );
  }
}
```

Action path per case: `RootActionPath.internal.chainCase(RootInternalPath.destination).chainCase(DestinationActionPath.turnOn)`.

Directly-presented child (no case enum, e.g. an error overlay) uses an identity keypath so the nullable-`Presents` `.path()` extension can unwrap it:

```dart
WritableKeyPath<T, T> _identity<T>() =>
    WritableKeyPath(get: (value) => value, set: (_, value) => value);

IfLet<TurnOnScreenState, TurnOnScreenAction, ErrorScreenState, ErrorScreenAction>(
  state: TurnOnScreenStatePath.error.path(_identity<ErrorScreenState>()),
  action: TurnOnScreenActionPath.error,
  reducer: ErrorScreenFeature(),
),
```

- Child "output" events: parent switches on the nested action (`case DestinationActionTurnOn(:final turnOn): if (turnOn is TurnOnScreenActionOutput) ...`).
- Porting a screen whose child isn't ported yet? Don't port the child too — add a stub feature exposing *exactly* the state constructor + action cases the parent references, with a no-op reducer:

  ```dart
  final class ErrorScreenFeature extends Feature<ErrorScreenState, ErrorScreenAction> {
    @override
    Reducer<ErrorScreenState, ErrorScreenAction> build() =>
        Reduce((state, action) => Effect.none());
  }
  ```

## Effects

Merging long-lived service streams (Swift `Publishers.Merge`), dependency-free:

```dart
Stream<T> mergeStreams<T>(List<Stream<T>> streams) {
  final controller = StreamController<T>();
  final subscriptions = <StreamSubscription<T>>[];
  var remaining = streams.length;
  for (final stream in streams) {
    subscriptions.add(stream.listen(
      controller.add,
      onError: controller.addError,
      onDone: () {
        remaining -= 1;
        if (remaining == 0) controller.close();
      },
    ));
  }
  controller.onCancel = () async {
    for (final subscription in subscriptions) {
      await subscription.cancel();
    }
  };
  return controller.stream;
}
```

## Dependencies

Full pattern (client anatomy, `DependencyValues` registry, zone plumbing, test overrides): the **dart-tca-dependencies** skill. The essentials:

- Clients are struct-of-closures (modern TCA's `@DependencyClient`); `.live()` closures **throw** by design — hosts install real (or demo) wiring at startup, tests override via `withDependencies((d) { d.kioskMode = …; }, () async {...})`.
- Reducer reads: `KioskModeClient get _kioskMode => dependency((d) => d.kioskMode);` — lazy per call, safe inside `Effect.future`/`Effect.stream` closures (zone values propagate into effects).
- When adding a client, update all four spots in `DependencyValues`: field, constructor, `live()`, `copyWith()` — a missed `copyWith()` silently drops it from every override scope.

## Effect/TestStore runtime quirks

These are behaviors of the library itself; account for them when writing reducers or their tests.

- **Nested `Effect.merge([a, b, c])` delivers later-listed effects first.** `merge` folds left, so earlier effects sit behind an extra internal stream hop; with 3+ effects the actions arrive roughly in reverse list order (a binary `merge([a, b])` is unaffected). In tests, register `receive`s accordingly: for `merge([Effect.cancel(id), Effect.action(a), Effect.action(b)])` expect `b` **before** `a`.
- **`TestStore` desyncs on duplicate queued expectations.** Its listener does both `removeAt(0)` and `remove(action)`, so if the same action (by `==`) is queued twice — e.g. two `check`s in one chain — matching the first also deletes the second while only one state-update closure is consumed, ending in `UnexpectedAction`/phantom pending updates. Design each test so no chain expects the same action twice: split the scenario, or stop the chain early (a spy knob returning `Completer<...>().future` keeps the effect pending).
- **`Effect.future`/`Effect.stream` `onError` re-emits the raw error.** After converting the error to an action it also does `controller.addError(error)`, which surfaces as an unhandled zone error in tests even though the action was delivered. Capture and assert it:

  ```dart
  final unhandled = <Object>[];
  await runZonedGuarded(() async {
    sut.store.send(triggerAction, (s) => s.copyWith());
    await Future<void>.delayed(Duration.zero);
  }, (error, _) => unhandled.add(error));
  sut.store.verifyNoPendingActions();
  expect(unhandled, [failure]);
  ```

  Reducers that try/catch inside the effect body instead of using `onError:` don't hit this.

## View layer

- Navigation = declarative `switch` over `state.destination.value`; never `NavigationDestination` auto-dispose (it mutates state from the view). Android back: `PopScope(canPop: false)` → send an action; defer to a deeper level if `destination.value != null`.
- Don't use the binding's `WithViewStore` for screens under a declarative root switch — it never re-subscribes when its `store` changes, and every root rebuild hands the screen a fresh scoped store. Use a `StatefulWidget` wrapper that listens to `store.syncStream`, re-subscribes in `didUpdateWidget` when `!identical(oldWidget.store, widget.store)`, and cancels on dispose (fire the Swift `.task` equivalent once in `initState`).
- Presented children (`Presents<Child?>`): memoize the scoped store in the screen's `State` — `store.view(...)` per build leaks a listener each call:

  ```dart
  Store<ErrorScreenState, ErrorScreenAction>? _error;

  @override
  void didUpdateWidget(MyScreenView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.store, widget.store)) {
      _error = null;  // stale child would keep syncing from the old parent
    }
  }

  void _syncChildStores(Store<MyState, MyAction> store) {
    if (store.state.error.value == null) {
      _error = null;
    } else {
      _error ??= store.view(
        state: MyStatePath.error.path(_identity<ErrorScreenState>()),
        action: MyActionPath.error,
      );
    }
  }
  ```

- Swift `.dialogOverlay` → a state-driven `Stack` layer over the scaffold (`ModalBarrier(dismissible: false)` + centered `Material` card); no `showDialog` route — dismissal is reducer-driven.
- `L10n`/asset references: local `const` strings marked `// TODO: wire real localization`; icon placeholders; drop `.analyticsScreenName`.
- Widget tests: install the root dependency wiring before `pumpWidget`; never `pumpAndSettle` (a spinner never settles) — use `tester.pump()`.

## Common mistakes

| Mistake | Symptom / fix |
|---|---|
| Missing `package:collection` import | `flutter test` "Not a constant expression" in `.g.dart` — add import |
| Getter on a `@KeyPathable` class | `.g.dart` "No named parameter with the name '<getter>'" — move it to an extension |
| Porting an unported child a screen `Scope`s/`ifLet`s | Add a no-op stub feature instead (pattern above) |
| `copyWith(x: null)` to dismiss | Old value silently kept — field must be `Presents<T?>` |
| Calling case constructor unqualified | Undefined — prefix with `…Enum.` |
| Mixing hosted + forked `composable_architecture` | Version solve/codegen breaks — `dependency_overrides` must own it |
| New Dart syntax newer than build_runner's analyzer ceiling in `lib/**` | Codegen fails — avoid the syntax or bump the analyzer override |
| `.g.dart` missing after adding annotations | Re-run build_runner; check `part` directive and root `build.yaml` |
| Expecting merged-effect actions in list order | 3+-way `Effect.merge` delivers later-listed effects first — reverse the `receive` order |
| Two equal actions queued via `receive` | TestStore removes both on first match → desync — split the test or stall the effect with a hanging spy future |
| `onError:` effect fails a passing test with an unhandled error | By design it re-emits the raw error — wrap in `runZonedGuarded` and assert on it |
