# Shared State: One Isolated Instance Per Test

A dependency that is an object holding persisted `@Shared` properties
(`.fileStorage`, `.appStorage`) leaks state between parallel tests when every
test resolves it from `static let testValue = Store()`. That is one instance
for the whole process, so one test's writes appear in another. Don't paper
over it with `.serialized`. Give each test its own instance, built over fresh
backing storage, and pass it to the `TestStore`:

```swift
private func createSut(
    prepareState: ((inout MyFeature.State) -> Void)? = nil
) -> SystemUnderTests {
    // Each test gets its own shared state, not the process-wide testValue.
    let settingsStore = withDependencies {
        $0.defaultFileStorage = .inMemory                                  // for .fileStorage keys
        $0.defaultAppStorage = UserDefaults(suiteName: UUID().uuidString)! // for .appStorage keys
    } operation: {
        SettingsStore()
    }

    var initialState = MyFeature.State()
    prepareState?(&initialState)

    let store = TestStore(initialState: initialState) {
        MyFeature()
    } withDependencies: {
        $0.settingsStore = settingsStore
    }

    return .init(store: store, settingsStore: settingsStore)
}
```

Seed and assert through the instance on the SUT, after `createSut`:

```swift
let sut = createSut()
sut.settingsStore.$value.withLock { $0 = .fixture }
// ...
#expect(sut.settingsStore.value == nil)
```

Never read it through `@Dependency(\.settingsStore) var settingsStore` in the test
body — outside the store that resolves to the process-wide `testValue`, not the
instance the store uses.

## Only Nest When A State Init Reads The Dependency

The `TestStore`'s `withDependencies:` covers the reducer and its effects. It does
**not** cover building `initialState`, which runs before the store exists. Wrap
the state construction in a second, outer `withDependencies` only when some
`State.init` — the feature's or a child's built in `prepareState` — reads the
dependency (`@Dependency` in an init, `@Shared` property defaults):

```swift
return withDependencies {
    $0.settingsStore = settingsStore
} operation: {
    var initialState = MyFeature.State()   // reads settingsStore
    prepareState?(&initialState)
    let store = TestStore(initialState: initialState) { ... } withDependencies: { ... }
    return .init(store: store, settingsStore: settingsStore)
}
```

Check before adding it: grep the feature and child states for the dependency.
If every read is inside the reducer, keep `createSut` flat.

## The Initializer Is Internal

The live type usually has no explicit `init`, so its initializer is internal and
the test target cannot call it (`'X' initializer is inaccessible due to 'internal'
protection level`). Use `@testable import <ModuleOfTheType>` in the test file.
Don't add a `public init()` to production code just for tests.
