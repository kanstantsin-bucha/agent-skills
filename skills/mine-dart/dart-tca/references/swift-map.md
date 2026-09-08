# Swift TCA → Dart TCA

Only needed when porting an existing **Swift** TCA feature. For greenfield Dart work, skip this.

| Swift | Dart |
|---|---|
| `@Reducer` / `Reduce { }` | `Feature` subclass / `Reduce((state, action) {…})` |
| `@ObservableState struct` | `@KeyPathable() final class` + mixin `_$X` + `part 'x.g.dart'` |
| `@CasePathable enum Action` | `@CaseKeyPathable() sealed class` — cases are **type params**; `extends T` = payload of `T`, no bound = zero-arg marker |
| `state.x = y` | `state.mutate((s) => s.copyWith(x: y))` |
| `.ifLet(\.child, action:)` | `IfLet(state:, action:, reducer:)` |
| `@Presents var dest` | `Presents<T?>` field + `Presentable` mixin |
| `PresentationAction` | dropped — destination actions nest directly; dismiss = `Presents(null)` |
| `.send(.foo)` | `Effect.action(FooEnum.foo())` |
| `.run { send in … }` single result + catch | `Effect.future(() async {…}, onError: (e, st) => …)` |
| `.publisher` / long-lived `.run` | `Effect.stream(() => stream.map(…))` |
| `Publishers.Merge(a, b)` | `mergeStreams([a, b])` (helper in `dart-tca-effects`) |
| `.cancellable(id:)` / `.cancel(id:)` | **banned in this port** — use a state-flag latch (`dart-tca-effects`) |
| `cancelInFlight: true` | no analog; see above |
| `Scope(state:, action: \.internal.child)` | `Scope(state: StatePath.child, action: <single-hop path>)` — chaining lives only in the key-paths helper (`dart-tca-navigation`) |
| `@CasePathable` enum **in state** (loading phases) | same `@CaseKeyPathable` sealed class; `.is(\.loaded)` → `state.x is <Class>Loaded` |
| `@Dependency(\.foo)` | `FooClient get _foo => dependency((d) => d.foo);` |
| `withDependencies` | `withDependencies((d) { d.foo = …; }, () {…})` — Zone-scoped |
| `SystemUnderTests` / `createSut` | `_Sut` record + `_runSut` body callback (`dart-tca-testing`) |
| Swift computed `State` property | `extension XStateDerived on XState` — **never** a getter on the class |
| View named `XView` | **`XScreen`** — `XView` is taken by the view-action enum |
| `.dialogOverlay` | state-driven `Stack` layer (`ModalBarrier` + centred `Material`), never `showDialog` |

## Divergences from the Swift reference — deliberate

1. **Four sub-enums, not two.** The reference has only `Internal` + `Output` and puts tap intents in `Internal`. We split out `View` (and `Input` where a parent must drive a child), which the reference's own design doc calls a missing requirement.
2. **Destinations only.** The reference mixes a `Presents<Destination?>` case-enum router *with* bare `Presents<ChildState?>` fields. We use only the router.
3. **State, action and reducer are separate files.** The reference puts all three in one; our features are larger, and split files keep each `.g.dart` small and its regeneration cheap.

The reference implementation also does two things you must **not** copy: it uses `WithViewStore` in its root view (after documenting why that is broken), and it leaks a `store.view` listener per build in `device_setup_root_view.dart`. See `dart-tca-view`.

## Porting mechanics

- Port the widget tree **verbatim** — a migration is a wiring change, not a redesign.
- A child that isn't ported yet gets a **stub feature** with a no-op reducer, not a port (`dart-tca-reducer`).
- `L10n`/asset references become local `const` strings marked `// TODO: wire real localization`.
