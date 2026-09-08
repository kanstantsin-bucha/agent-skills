---
name: dart-tca-codegen
description: Use when running build_runner on a Dart TCA project, setting up or vendoring the composable_architecture package, or when codegen fails — RangeError from the generator, 0 outputs written, "requires the 'dot-shorthands' language feature", missing .g.dart, avoid_types_as_parameter_names, or a detached library doc comment.
---

# Dart TCA — codegen and toolchain

```
fvm dart run build_runner build --delete-conflicting-outputs
```

(Drop `fvm` if the project does not use it; some projects use `flutter pub run build_runner`.)

Every annotated file needs `part '<name>.g.dart';`, placed immediately after the imports.

## What gets generated

Per `@KeyPathable`: `mixin _$X` (`copyWith` / `==` via `DeepCollectionEquality` / `hashCode` / `toString`) + `extension XPath` (a `WritableKeyPath` per field).

Per `@CaseKeyPathable`: `extension XEnum` (static case constructors) + one `final class X<Case>` per case + `extension XPath` (case paths). **No `_$` mixin.**

Two quirks worth knowing:

- A payload type with a zero-arg constructor becomes an **optional** parameter: `loadFailed([Object? p])`.
- Generated case setters **ignore the incoming root and construct a fresh case** — that is what makes key-path chaining work (`dart-tca-navigation`).

## `ignore_for_file` placement

Case names derive from type-parameter names, so cases called `Error` / `Internal` / `Destination` shadow real types and need:

```dart
// ignore_for_file: avoid_types_as_parameter_names

/// What this file replaces…
library;
```

It goes **above** the `///` library doc comment. Below it, the doc comment detaches from `library;`.

## Generator case cap

Upstream `case_key_path_generator.dart` indexes `const letters = ["A"…"I"]` by type-parameter position, so a **10th case fails codegen** with:

```
RangeError (length): Invalid value: Not in inclusive range 0..8: 9
```

— naming neither the class nor the cause, while build_runner still reports "wrote N outputs". Extending `letters` to the full alphabet is a one-line fix if you control the package (a vendored fork lifts the cap to 26). Either way, **past ~6 cases split the sub-enum into groups** for readability (`dart-tca-actions`).

## Analyzer ceiling and vendoring

The hosted package pins `analyzer ^7.2.0` (max language version 3.9), so **the generator cannot parse modern syntax in annotated files on a newer SDK** — dot-shorthands fail with `This requires the 'dot-shorthands' language feature to be enabled`, 0 outputs.

Vendoring a fork with `analyzer ^8` / `source_gen ^4` / `build ^4` raises the ceiling to 3.11. Keep `composable_architecture_flutter` hosted.

- **A path override does NOT auto-apply its builders.** Add a root `build.yaml` naming `composable_architecture:key_path` with `generate_for: [lib/**]`.
- The `SDK language version X is newer than 'analyzer' language version Y` warning narrows but never disappears — analyzer 8.x tops out at 3.11. **Expected, not a failure.** Genuine 3.12-only syntax will still fail codegen.
- Record provenance (upstream URL, commit, exact patch) in a `VENDORED.md`, and exclude `third_party/**` in `analysis_options.yaml` so vendored lints don't inflate your baseline.
- `dependency_overrides` must own the package — mixing hosted and forked copies breaks version solving and codegen.

## Codegen failures that are actually source errors

| Symptom | Real cause | Leaf |
|---|---|---|
| `Named parameters must be enclosed in curly braces`, a `T??` in `.g.dart` | Nullable type-parameter bound | `dart-tca-actions` |
| `No named parameter with the name '<x>'` | A getter on a `@KeyPathable` class | `dart-tca-state` |
| `flutter test`: "Not a constant expression" | Missing `package:collection` import in a state file | `dart-tca-state` |
| `unused_import` on `collection` | It was imported in an **action** file | `dart-tca-state` |
| `annotate_overrides` × N | State fields missing `@override` | `dart-tca-state` |
| Dozens of `The name 'XAction' isn't a type` pointing into a new `.g.dart` | Transitive bounds imports missing in a composing parent | `dart-tca-navigation/references/composing-at-scale.md` |
| `.g.dart` missing entirely | Re-run build_runner; check the `part` directive and the root `build.yaml` | — |
