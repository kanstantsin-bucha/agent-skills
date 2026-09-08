# TestStore failures — symptom → cause → fix

## The failure is often attributed to the wrong test

The action check runs inside `stream.listen`, so an `UnexpectedAction` throw is **not** caught by the enclosing `try` or by `expect`. It is frequently reported against whichever test happened to be running. **Suspect a mismatched action before suspecting the test you are looking at.**

| Symptom | Cause | Fix |
|---|---|---|
| `UnexpectedAction` | `receive` registered after the `send` that triggers it | Register every `receive` **before** the `send` |
| `UnexpectedAction`, or phantom pending updates | The same action (`==`) queued twice in one chain — the listener does both `removeAt(0)` and `remove(action)`, deleting both on first match while consuming one state closure | Split the scenario, or stall the effect with a `Completer<...>().future` spy knob |
| `UnexpectedAction` for an action you *did* register | `receive` registered for an action you then `send` directly — that desyncs the queue | Send it or expect it, never both |
| `ExpectedIsSameInstance` | The expected-state closure returned `s` | Return `s.copyWith()`; for a zero-field state return a fresh instance |
| `UnexpectedChanges` whose two sides print identically | A model in the state lacks `==`, so comparison fell back to identity | Give the model value `==`/`hashCode` (`dart-tca-state`) |
| `UnexpectedChanges` on a field you did not think about | Working as intended — `send`/`receive` are exhaustive | Predict the whole post-state, or fix the reducer |
| Unhandled zone error from inside a stream listener, test otherwise passing | `Effect.future`/`Effect.stream` `onError:` re-emits the raw error after converting it | See below, or try/catch inside the effect body instead of using `onError:` |
| `UnimplementedError` from inside an effect | A client the reducer reaches was not overridden; `.live()` closures throw by design | Install a benign spy for **every** reachable client |
| An expected action never arrives | Assertion ran before the microtask flush | `await Future<void>.delayed(Duration.zero)` after the `send` |
| Actions arrive in the "wrong" order | 3+-way `Effect.merge` can deliver later-listed effects first | Do not assert order; or verify empirically for that exact shape |
| `receive` never matches an action carrying a `List`/object payload | Case-subclass `==` compares payloads with plain `==` — identity for collections and reducer-built objects | Pass the same instance the reducer emits, or remove the payload (`dart-tca-actions`) |
| Overrides appear not to apply | The store escaped the `withDependencies` zone, or a dependency was cached in a field | Keep construction and every `send`/`await` inside the async body; read dependencies via lazy getters |

## Capturing the `onError:` re-emission

The action *is* delivered; the raw error is then re-added to the controller.

```dart
final unhandled = <Object>[];
await runZonedGuarded(() async {
  sut.store.send(triggerAction, (s) => s.copyWith());
  await Future<void>.delayed(Duration.zero);
}, (error, _) => unhandled.add(error));
sut.store.verifyNoPendingActions();
expect(unhandled, [failure]);
```

Reducers that try/catch inside the effect body instead of using `onError:` never hit this.
