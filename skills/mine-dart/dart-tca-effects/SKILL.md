---
name: dart-tca-effects
description: Use when a Dart TCA reducer returns anything other than Effect.none() — futures, streams, merges, timers, countdowns, polling, retries, error handling — or when an effect fires twice, keeps running after its screen is gone, or a cancellable effect cancels the wrong thing.
---

# Dart TCA — effects

## The roster

| Effect | Use |
|---|---|
| `Effect.none()` | the default return |
| `Effect.action(a)` | forwarding to another case. Emits via `Stream.value`, i.e. **asynchronously** |
| `Effect.merge([a, b])` | always the list-literal **static** form, never the instance `.merge` |
| `Effect.future(() async {…}, onError: (e, st) => …)` | one result plus a terminal failure action |
| `Effect.stream(() => …)` | long-lived subscription; build with `mergeStreams([...]).map((_) => action)` |
| `Effect.async` / `Effect.sync` | unused — call synchronous side effects inline in the reducer body |

## Three library behaviours that shape every reducer

**1. `Effect.action` delivery is asynchronous.** It goes through `Stream.value`. Tests must flush with `await Future<void>.delayed(Duration.zero)` before asserting.

**2. `Effect.merge` order is unspecified.** `merge` folds left, so earlier effects sit behind an extra internal stream hop; with **3+ effects later-listed ones can arrive first** (a binary `merge([a, b])` is unaffected). Never write a test that depends on merge order unless you have verified it for that exact shape.

**3. `onError:` re-emits the raw error after converting it.** The action *is* delivered, and then `controller.addError(error)` surfaces as an unhandled zone error. Either catch inside the effect body instead of using `onError:`, or capture it in the test (`dart-tca-testing/references/teststore-failures.md`).

## Cancellation is globally keyed and leaks — do not use it

`effect.dart` holds `_cancellableEffects` and `_effectSubscriptions` as **library-level globals keyed by the id VALUE**, and entries are never removed. Also, **`Store.dispose()` does not cancel effect subscriptions** — it only calls `_onDispose`.

- A private `enum _CancelID` per feature file is safe **across features** (distinct enum values compare by identity).
- It is **not** safe across two live instances of the *same* feature — they share the id value and cancel each other. Avoid presenting two stores of one feature simultaneously.
- **Never use `.cancellable` / `Effect.cancel` as a duplicate-subscription guard.** Use a `bool` state flag (the `appeared` latch — `dart-tca-reducer`).

Consequence: **a genuinely long-lived `Effect.stream` can never be stopped safely.** It outlives the screen that started it.

- A stream is acceptable ONLY for an effect meant to live as long as the app (e.g. a root store's `observeChanges`).
- For any **finite** long-lived effect — countdown, progress polling, scheduled retry — use a **self-terminating chain of one-shot effects**, latched by a state flag.

```dart
case BreathingInternalStart():
  if (state.value.timerActive) return Effect.none();          // the latch
  state.mutate((s) => s.copyWith(timerActive: true));
  return Effect.action(_scheduleTickAction);

case BreathingInternalScheduleTick():
  if (!state.value.timerActive) return Effect.none();
  return Effect.stream(() async* { await _clock.sleep(_tick); yield _tickAction; });

case BreathingInternalTick():
  if (!state.value.timerActive) return Effect.none();          // an in-flight tick dies here
  …re-arm or stop
```

Every exit path funnels through one private `_halt(state)` that lowers the latch. **Test it by asserting the count of armed sleeps, not the flag** — a duplicate chain sets the same flag and merely ticks twice as fast.

## Merging streams

The Swift `Publishers.Merge` analog, dependency-free:

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

## Time is a dependency

**Never `DateTime.now()`, never a bare `Future.delayed`, never `Random()` in a reducer or effect.** Read a date/clock/uuid client (`dart-tca-dependencies`) so tests can control them.
