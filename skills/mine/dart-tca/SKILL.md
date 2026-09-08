---
name: dart-tca
description: Router for writing or porting TCA (Composable Architecture) features in Dart/Flutter. Load this FIRST for any TCA work — state/action classes, reducers, effects, dependencies, navigation, views, tests — or when build_runner, flutter analyze or TestStore fails on a TCA file. It names the one leaf skill to load next; do not load leaves speculatively.
---

# Dart TCA — router

States are immutable `@KeyPathable` classes with generated `copyWith`/`==`. Action enums are `@CaseKeyPathable` sealed classes whose **cases are type parameters** (`extends T` = payload of `T`, no bound = zero-arg marker). Dependencies are zone-scoped. Codegen is `build_runner`.

**How to use this skill: read the rules below, then load ONE leaf — the one matching the file you are about to write or the error you are looking at. Do not load a leaf you have no immediate use for.** Leaves do not repeat each other; each fact has exactly one home.

## Non-negotiables (violating any of these costs a rewrite or a silent bug)

1. **Never a nullable type-parameter bound.** `extends Challenge?` emits `Challenge??` and fails codegen. Model absence as a second case. → `dart-tca-actions`
2. **Every `@KeyPathable` field is `@override final`.** → `dart-tca-state`
3. **No getters on a `@KeyPathable` class** — derived values go in an extension. → `dart-tca-state`
4. **Generated `copyWith` is `?? this.x`; it can never null a nullable field.** → `dart-tca-state`
5. **A `View` case never runs async work** — it mutates and returns `Effect.none()`, or hops to an `Internal` case. → `dart-tca-actions`
6. **Presentation only through a destination enum**, even with one child; a child never dismisses itself. → `dart-tca-navigation`
7. **Never `.cancellable` / `Effect.cancel`** (globally keyed, leaks) and **never `dispose()` a scoped destination store**. → `dart-tca-effects`, `dart-tca-navigation`
8. **No `default:` in any switch** — exhaustiveness must be compiler-checked. → `dart-tca-reducer`

## Which leaf to load

| You are about to write / do | Load |
|---|---|
| `<x>_state.dart` — state class, derived values, `Presents` field | `dart-tca-state` |
| `<x>_action.dart` — the View/Internal/Output/Input sub-enums | `dart-tca-actions` |
| `<x>_feature.dart` — reducer body, fan-out, dependency getters | `dart-tca-reducer` |
| Anything returning an `Effect` — futures, streams, timers, retries | `dart-tca-effects` |
| Present a child screen / sheet / modal / alert; dismissal; Android back | `dart-tca-navigation` |
| Compose a parent that scopes tabs or siblings **and** presents destinations | `dart-tca-navigation/references/composing-at-scale.md` |
| `<x>_screen.dart` — the widget tree, store scoping, modal layers | `dart-tca-view` |
| Add or change a dependency client, or the `DependencyValues` registry | `dart-tca-dependencies` |
| Any test — reducer (`TestStore`) or widget | `dart-tca-testing` |
| Run `build_runner`; set up the package/fork/`build.yaml` | `dart-tca-codegen` |
| Port an existing **Swift** TCA feature | `dart-tca/references/swift-map.md` |

## Which leaf owns your error

| Symptom | Load |
|---|---|
| `Named parameters must be enclosed in curly braces` / a `T??` type in `.g.dart` | `dart-tca-actions` |
| `No named parameter with the name '<x>'` in `.g.dart` | `dart-tca-state` |
| `annotate_overrides`, or `unused_import` on `collection` | `dart-tca-state` |
| `flutter test`: "Not a constant expression" in `.g.dart` | `dart-tca-state` |
| `RangeError … 0..8: 9` from the generator, or 0 outputs written | `dart-tca-codegen` |
| `avoid_types_as_parameter_names`, or a detached library doc comment | `dart-tca-codegen` |
| Dozens of `The name 'XAction' isn't a type` pointing into your new `.g.dart` | `dart-tca-navigation/references/composing-at-scale.md` |
| `UnexpectedAction`, `UnexpectedChanges`, `ExpectedIsSameInstance` | `dart-tca-testing/references/teststore-failures.md` |
| An unhandled zone error from inside a stream listener | `dart-tca-testing/references/teststore-failures.md` |
| An effect fires twice, or keeps running after its screen is gone | `dart-tca-effects` |
| A destination compiles but never routes; a leaked `syncStream` listener | `dart-tca-navigation` |

## Project facts are not in this tree

Which clients exist, which data store a feature reads, forbidden directories, and the build command are **per-project**. Load the project's own TCA skill (e.g. `resist-tca-project`) or its `CLAUDE.md` before writing feature code.
