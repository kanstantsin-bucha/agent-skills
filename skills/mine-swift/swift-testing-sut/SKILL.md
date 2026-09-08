---
name: swift-testing-sut
description: Use when writing any Swift test file — structuring the SystemUnderTests struct, createSut method, spy dependencies, and prepareState closure. Use when setting up a new test class or adding tests that need controlled initial state or dependency access.
---

# Swift Testing SUT Pattern

## Overview

Every test class uses a `SystemUnderTests` struct and a `createSut` factory method to wire up the subject under test, spy dependencies, and initial state in one place.

**REQUIRED SKILL:** Load `swift-testing-spy` to understand how spies are structured and how `.spy` is accessed on them.

**REQUIRED SKILL:** Load `swift-testing-tca` when the subject is a TCA reducer. `TestStore` has suite-isolation and effect-lifecycle rules this skill does not cover, and the canonical `createSut` for a reducer lives there — do not adapt the plain-class example below for it.

## SystemUnderTests Struct

Defined as a `private struct` inside the test class. Contains the subject under test and every spy dependency the tests need to interact with.

```swift
private struct SystemUnderTests {
    let service: MyService
    let networkClient: NetworkClientSpy
    let storage: StorageSpy
}
```

- One property per spy — tests access spies via `sut.networkClient`, etc.
- Never put derived state or helpers here — only the subject and raw spies.

## createSut Method

**Rules:**
- Parameters = only what varies between tests to configure the subject or initial state.
- All spies are created **inside** `createSut`, never passed in from outside.
- `prepareState` is always the last parameter and always optional with `nil` default — use it when the subject has state that needs to be pre-populated before the test action.
- Add `@MainActor` when the subject or test framework requires it. (For TCA, isolation goes on the `@Suite` type instead — see `swift-testing-tca`.)

### Example: Service / Plain Class

```swift
private struct SystemUnderTests {
    let service: MyService
    let networkClient: NetworkClientSpy
    let storage: StorageSpy
}

private func createSut(
    baseURL: URL = URL(string: "https://example.com")!,
    prepareState: ((inout MyService.Cache) -> Void)? = nil
) -> SystemUnderTests {
    let clientSpy = NetworkClientSpy()
    let storageSpy = StorageSpy()

    var cache = MyService.Cache()
    prepareState?(&cache)

    let service = MyService(
        baseURL: baseURL,
        cache: cache,
        client: clientSpy,
        storage: storageSpy
    )

    return .init(service: service, networkClient: clientSpy, storage: storageSpy)
}
```

Omit `prepareState` entirely when the subject has no pre-populatable state.

Usage:
```swift
// Default
let sut = createSut()

// Pre-populated state
let sut = createSut {
    $0.cachedUsers = [.stub]
}

// Both
let sut = createSut(baseURL: .stagingURL) {
    $0.cachedUsers = [.stub]
}

sut.networkClient.spy.stubbedResponse = .success(UserResponse.fixture)
let user = try await sut.service.fetchUser(id: "123")
```

## Static Helper Factories

Use `private static func` for building complex model values shared across tests. Always provide sensible defaults so callers can omit params in the common case.

```swift
private static func createUserStub(
    role: Role = .standard,
    createdAt: Date = .now
) -> User {
    .init(id: "stub", role: role, createdAt: createdAt)
}
```

- `static` because they don't use instance state.
- Named `createXxx` matching the `createSut` convention.
- Default arguments that represent the typical test scenario.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Passing spies into `createSut` as parameters | Create spies inside `createSut`; expose via SUT struct |
| Mixing construction params with arbitrary config | Only params that feed directly into construction; use `prepareState` for the rest |
| Calling `prepareState` before constructing initial state | Always construct first, then call `prepareState?(&initialState)` |
| Making `SystemUnderTests` a class | Use `struct` — value semantics, no accidental sharing |
| Hand-rolling a `TestStore` SUT from this skill alone | Load `swift-testing-tca` — reducer tests have isolation and effect rules beyond this pattern |
