# Composing a parent with tabs + destinations

Read before writing a parent that both `Scope`s siblings/tabs **and** presents destinations. Proved on a shell with 4 tabs and 7 destinations.

## 1. Scoped siblings are TOP-LEVEL action cases

`Scope` needs a **single-hop** `WritableKeyPath<ParentAction, ChildAction?>`, and only the key-paths helper file may chain hops. So:

- **Tab / sibling** actions are **top-level** cases of the parent action, alongside `view` / `internal` / `output`.
- Only **destination** actions nest at `internal.destination.<case>`.

This is the one sanctioned exception to "top level stays exactly the four taxonomy words".

## 2. Write scoped bounds out fully `dynamic`-instantiated

A raw `XDestinationAction` bound instantiates-to-bounds with `dynamic`. The consequences are silent and severe:

- every `switch` over it becomes non-exhaustive, and
- every `is XActionOutput` check is **statically false** — the child's outputs are never seen.

**Write the bounds out fully `dynamic`-instantiated, copying the spelling from the generated path types.** It is verbose; it is the only form that matches codegen.

## 3. Transitive-bounds imports — the 451-error trap

**Symptom:** dozens of `The name 'SlipLogAction' isn't a type`, all pointing INTO your newly generated `.g.dart`, on a hand-written file whose own source looks complete.

**Cause:** codegen expands a scoped child's bounds **recursively** into the PARENT's `.g.dart`. So the parent action file must import every type reachable from each child action — its grandchildren's `View` / `Internal` / `Output` / destination enums *and their payload types* — even though the hand-written file never names one of them.

**Fix:** copy the child action file's **entire import block verbatim**, then add the child itself. A root composing a shell action needs all of that shell action file's imports.

**Do not prune these to "clean up".** They carry no `unused_import` warning, because the generated part file genuinely uses them.

## 4. Duplicate type names across layers

When two layers define the same type name (e.g. a `Challenge` in `business/` and another in `data/models/`), use `show` on **both** imports. This interacts with rule 3: the copied import block must keep its `show` clauses intact.

## 5. One store per presentation, in the view

`FeatureView`'s `State` is private, so a `FeatureView` subclass cannot memoize a scoped child store itself. Wrap each presentation in a **nested `StatefulWidget` whose lifetime IS the presentation** — it memoizes naturally, and it is the shape a `StoreHost` mixin should be built on. One state-driven layer per destination. Never `dispose()` the scoped store; drop the reference. See `dart-tca-view`.
