---
name: dart-tca-view
description: Use when writing or porting a Dart TCA `<x>_screen.dart` — the FeatureView subclass, reading store state, dispatching actions, modal/overlay layers, scoping a child store in the widget tree, Android back, interim hosting from a not-yet-migrated parent, or widget tests that hang.
---

# Dart TCA — the view layer

The widget is **`XScreen`**, never `XView` — that name is taken by the view-action enum. It subclasses the project's `FeatureView<XState, XAction>`, and lives in its own file, always separate from the reducer.

- `onAppear` sends `View.appeared`. Read `store.state`; dispatch `store.send(...)`.
- **Porting an existing widget tree? Port it VERBATIM.** A migration is a wiring change, not a redesign — only state reads and callbacks change. Report the diff as one line: "tree unchanged; N non-mechanical lines: …".

## Store ownership

**The host owns the store; `FeatureView` never disposes what it is given.** Whatever `State` creates a store (a `late final` field, or a memoized scoped child) disposes it.

- **Never build a store inside `build`** — it would be replaced on every rebuild, dropping state and re-firing `onAppear`.
- **Never call `store.view(...)` inside `build`** — it leaks a `syncStream` listener per call and nothing disposes it. Memoize the scoped child store in the `State`, drop it on dismissal, and null it in `didUpdateWidget` when `!identical(oldWidget.store, widget.store)` (a stale child keeps syncing from the old parent).
- **Never `dispose()` a scoped destination store** — `store.view` on a `Presentable` parent selects the auto-dismissing overload, whose `onDispose` nulls the parent's destination from a view callback. Drop the reference instead. (`dart-tca-navigation`)
- **Never `WithViewStore`.** It never re-subscribes when its store changes, which breaks under a declarative root switch that hands the screen a fresh scoped store on every rebuild.

`FeatureView`'s subscription field is a `SyncStreamSubscription<S>`, **not** a `dart:async` `StreamSubscription` — `Store.syncStream` is the package's own `SyncStream`, with a synchronous `cancel()`.

**`SyncStream.add` suppresses identical values via `!=`**, so a screen only rebuilds when state actually changes — but *only* because every state and model has value equality. A future state field whose type lacks `==` silently reverts the screen to rebuilding on every action. (`dart-tca-state`)

## Navigation and modals

- Navigation is a **declarative `switch` over `store.state.destination.value`**, never a `Navigator` push. `null` → the tab's own content.
- **Modals are a state-driven `Stack` layer** — `ModalBarrier(dismissible: false)` + a centred `Material` card — not `showDialog`. Dismissal is reducer-driven.
- Each layer is a nested `StatefulWidget` whose lifetime IS the presentation; that is what memoizes the scoped child store (`FeatureView`'s own `State` is private, so it cannot).
- **Android back:** `PopScope(canPop: false)` + send an action. Defer to a deeper level first: `if (store.state.destination.value != null) return;`.

## Interim hosting (parent not migrated yet)

While a screen is still presented by `showDialog` from a not-yet-migrated parent, create the store **per presentation** and dispose it when the route pops:

```dart
final store = Store(initialState: SlipLogState(), reducer: SlipLogFeature());
showDialog(
  context: context,
  barrierDismissible: false,
  builder: (_) => SlipLogScreen(store: store),
).whenComplete(store.dispose);
```

**Never build the store inside `builder:`** — it would be rebuilt on every dialog rebuild. Keep the original `Navigator.pop` alongside the new output-emitting `send`, tagged `// TODO(Task N)`, so the screen stays reachable until the parent dismisses on the output. Both the interim `showDialog` and the interim `pop` are removed when the parent takes over — grep the TODO tag rather than re-reading whole screens.

## Imports

**Use the exact `../` depth, and prefer `package:` across top-level directories.** Dart clamps excess `../` at the package root, so a wrong depth still compiles — invisible to review, and it survives a file move that should have broken it.

## Widget tests

- Install dependency wiring **before** `pumpWidget` — the appear effect fires synchronously on first build.
- **Never `pumpAndSettle`** — a spinner never settles. Use `tester.pump()`.

## Porting leftovers

`L10n`/asset references from a ported screen become local `const` strings marked `// TODO: wire real localization`; icons get placeholders; drop analytics screen-name hooks unless the project wires them.
