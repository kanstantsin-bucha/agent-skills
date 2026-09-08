---
name: dart-tca-state
description: Use when writing or changing a Dart TCA `<x>_state.dart` — the @KeyPathable class, derived values, nullable fields, Presents, or model equality. Also when .g.dart reports "No named parameter with the name", analyze reports annotate_overrides or unused_import on `collection`, or `flutter test` fails with "Not a constant expression".
---

# Dart TCA — state classes

```dart
// ignore_for_file: avoid_types_as_parameter_names   ← if any case name shadows a type

/// Replaces TodayCubit. …translation notes…
library;

import 'package:collection/collection.dart';   // MANDATORY, see below

part 'today_state.g.dart';

// MARK: - State

@KeyPathable()
final class TodayState with _$TodayState, Presentable {   // Presentable only if it presents
  @override final String? challengeName;
  @override final bool isObserving;
  @override final Presents<TodayDestination?> destination;

  TodayState({
    this.challengeName,
    this.isObserving = false,
    Presents<TodayDestination?>? destination,
  }) : destination = destination ?? Presents(null);   // Presents is not const — init list
}

extension TodayStateDerived on TodayState {
  bool get canCheckIn => challengeName != null && todayStatus == null;
}
```

## Rules

- **Every field is `@override final`.** The generated `_$XState` mixin declares an abstract getter per field; without `@override` you get one `annotate_overrides` info **per field**.
- **A state file with fields MUST `import 'package:collection/collection.dart'`.** The generated `==` uses `DeepCollectionEquality`. `flutter analyze` passes without it; `flutter test` fails with a misleading **"Not a constant expression"**. (The action file must *not* import it — see `dart-tca-actions`.)
- **No getters on the class.** The generator scans getters as fields and emits them as `copyWith` parameters → `No named parameter with the name '<getter>'`. Derived **state** predicates go in `extension XStateDerived on XState`; derived **dependency-backed** predicates go on the `Feature`.
- **Zero-field states get no `copyWith`** — the mixin is only `==`/`hashCode`/`toString`. In tests return a fresh instance.
- Invariants are `assert(...)` **plus a production fallback**, never a throw.
- Section markers: `// MARK: - State`. Every non-generated file opens with a `///` doc comment ending in `library;` saying what it replaces.

## Nullable fields and `Presents`

**Generated `copyWith` is `?? this.x`, so it can NEVER null a nullable field.** This is not only a `Presents` problem — it applies to `String? validationError`, `DateTime? selectedDate`, everything.

- Clearing a plain nullable field means **constructing a fresh state**, which collides with carrying forward latch flags like `isObserving`. So **every nullable field needs an explicit "who clears it, and where" note in the state's library doc.**
- If a field must be cleared from several places, wrap it the way `Presents` wraps child state: `Presents<T?>`, cleared with `copyWith(x: Presents(null))`.
- Child state that can be dismissed is **always** `Presents<XDestination?>` — the class mixes in `Presentable`, the constructor parameter is nullable, and the default is in the initializer list. Never `= const Presents(null)` as a parameter default.

**A field with no sensible constant default** (e.g. `DateTime currentMonthDate`) keeps the live default (`DateTime.now()`), overwritten from the date client on load. Do NOT use a sentinel like `DateTime(2026)` — it renders visibly wrong for one frame.

## Models need value equality

TCA is the architecture; models support it, not the reverse. Without `==`, state equality, `TestStore` exhaustivity, `UnexpectedChanges` diffing and view rebuild decisions all silently degrade to identity — and the failures print as identical-looking objects.

- Every domain and DTO model implements `==`/`hashCode` over every field, deep for collections.
- If the domain layer is documented as package-free, hand-roll it with local `listEquals`/`mapEquals`/`Object.hashAll` helpers — never add `equatable`.
- A new model ships with `==`, `hashCode` and equality tests **in the same commit**. Not optional.

Note the asymmetry: `@KeyPathable` state `==` is `DeepCollectionEquality`, but generated **case-subclass** `==` compares payloads with plain `==` — a `List` payload compares by identity. That shapes action design (`dart-tca-actions`) and test expectations (`dart-tca-testing`).
