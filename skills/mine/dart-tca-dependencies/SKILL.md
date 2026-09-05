---
name: dart-tca-dependencies
description: Use when adding or modifying dependency clients in a Dart TCA project — struct-of-closures clients, the DependencyValues registry, zone-scoped withDependencies overrides, or wiring a new service for reducers and tests.
---

# Dependency clients & zone-scoped injection

The Dart analog of Swift TCA's `@DependencyClient` + `@Dependency` + `withDependencies`. Two libraries own the pattern: a *clients* library (one struct-of-closures per service) and a *dependency values* library (the ambient registry + zone plumbing). Companion skills: dart-tca (reducers/effects), dart-testing-sut (spy clients in tests).

## Clients: struct-of-closures

One plain `final class` per Swift `@Dependency` service; every field is a closure. No interfaces, no mock framework — a test double is just closures capturing a sink.

```dart
/// Throws for not-yet-implemented client closures. Returning `Never` lets it
/// be used where any return type is expected (e.g. `Stream<void> Function()`).
Never _unimplemented(String name) =>
    throw UnimplementedError('$name is not implemented yet');

final class ConnectivityClient {
  final Stream<void> Function() stateChanges;
  final bool Function() isDeviceConnected;
  final Future<void> Function(String identifier) connect;
  final Future<void> Function() disconnect;

  const ConnectivityClient({
    required this.stateChanges,
    required this.isDeviceConnected,
    required this.connect,
    required this.disconnect,
  });

  factory ConnectivityClient.live() => ConnectivityClient(
        stateChanges: () => _unimplemented('ConnectivityClient.stateChanges'),
        isDeviceConnected: () =>
            _unimplemented('ConnectivityClient.isDeviceConnected'),
        connect: (_) => _unimplemented('ConnectivityClient.connect'),
        disconnect: () => _unimplemented('ConnectivityClient.disconnect'),
      );

  /// Same as live while live is stubbed; explicit "not for real use".
  factory ConnectivityClient.unimplemented() => ConnectivityClient.live();
}
```

Conventions:

- A Combine `stateChanges` publisher in Swift becomes a `Stream<void> Function()` field.
- `.live()` closures **throw** until real platform wiring exists — construction is always safe, *use* fails loudly. Hosts install benign wiring at startup; tests override per-test.
- Controllable time gets dedicated clients with test factories:

```dart
final class DateClient {
  final DateTime Function() now;
  const DateClient({required this.now});
  factory DateClient.live() => DateClient(now: DateTime.now);
  factory DateClient.constant(DateTime value) => DateClient(now: () => value);
}

final class ClockClient {
  final Future<void> Function(Duration) sleep;
  const ClockClient({required this.sleep});
  factory ClockClient.live() => ClockClient(sleep: Future<void>.delayed);
  /// Test: every sleep completes immediately (timeouts fire right away).
  factory ClockClient.immediate() => ClockClient(sleep: (_) async {});
  /// Test: no sleep ever completes (timeouts never fire).
  factory ClockClient.suspending() =>
      ClockClient(sleep: (_) => Completer<void>().future);
}
```

## DependencyValues: the ambient registry

One mutable class holding every client. Mutable fields let `withDependencies` override on a clone; the clients themselves stay immutable.

```dart
final class DependencyValues {
  ConnectivityClient connectivity;
  AnalyticsClient analytics;
  DateClient date;
  ClockClient clock;
  // …one field per client.

  DependencyValues({
    required this.connectivity,
    required this.analytics,
    required this.date,
    required this.clock,
  });

  factory DependencyValues.live() => DependencyValues(
        connectivity: ConnectivityClient.live(),
        analytics: AnalyticsClient.live(),
        date: DateClient.live(),
        clock: ClockClient.live(),
      );

  /// Shallow clone used by [withDependencies] before applying overrides.
  DependencyValues copyWith() => DependencyValues(
        connectivity: connectivity,
        analytics: analytics,
        date: date,
        clock: clock,
      );
}
```

**When adding a client, touch all four places:** the field, the constructor parameter, `live()`, and `copyWith()` — forgetting `copyWith()` silently drops the client from every `withDependencies` scope.

## Zone plumbing

```dart
const _dependenciesKey = #tcaDependencies;

/// Fallback when no [withDependencies] scope is active (the running app).
DependencyValues _root = DependencyValues.live();

/// Replaces the global (live) values. Call once at app startup.
set rootDependencies(DependencyValues values) => _root = values;

DependencyValues get _current =>
    (Zone.current[_dependenciesKey] as DependencyValues?) ?? _root;

/// Reads a dependency from the values currently in effect.
T dependency<T>(T Function(DependencyValues) get) => get(_current);

/// Runs [operation] with overrides applied by [mutate]. Zone values propagate
/// across Future/Stream continuations, mirroring Swift task-locals.
R withDependencies<R>(
  void Function(DependencyValues) mutate,
  R Function() operation,
) {
  final overridden = _current.copyWith();
  mutate(overridden);
  return runZoned(operation, zoneValues: {_dependenciesKey: overridden});
}
```

## Usage

Reducer side — a getter per dependency on the `Feature`:

```dart
ConnectivityClient get _connectivity => dependency((d) => d.connectivity);
```

App startup — install real/demo wiring once:

```dart
rootDependencies = demoDependencies(); // a DependencyValues with benign closures
```

Test side — overrides are zone-scoped, so the zone must stay alive across every `send`/`await` (see the dart-testing-sut skill for the full factory pattern):

```dart
await withDependencies((d) {
  d.clock = ClockClient.immediate();
  d.date = DateClient.constant(DateTime(2024));
}, () async {
  final store = TestStore(initialState: MyState(), reducer: MyFeature());
  // send / receive / await here, inside the zone
});
```

Reading a dependency inside an `Effect.future`/`Effect.stream` closure is fine — zone values propagate into effects. What does **not** work: returning the store out of `withDependencies` and using it later (the zone is gone), or overriding after the store captured a value at construction time (reads happen lazily per `dependency(...)` call, so ordinary reducer reads are safe, but cached reads are not).
