---
name: swift-testing-spy
description: Use when creating Swift test doubles for protocols that need call verification, configurable behavior (handlers), or publisher control. Use when deciding between mock/stub/spy naming, structuring a test double class, or adding thread-safe call recording.
---

# Swift Testing Spy

## Overview

A **spy** records interactions for later assertion and exposes control hooks (handlers, subjects) for the test to drive and verify behavior. Use a spy when you need both: configure behavior AND verify calls were made.

## Structure

Two-class pattern — outer satisfies the protocol, inner `Spy` is the test's control surface:

```
ConnectivityServiceSpy        ← protocol conformance, delegates to spy
  └── Spy                     ← @unchecked Sendable, NSLock, records calls
```

## Naming

| Role | Name |
|------|------|
| Outer class | `[ProtocolName]Spy` |
| Inner class | `Spy` |
| Test access | `connectivityService.spy.calls` |
| Protocol state | On outer class directly |

## Implementation

### Outer Class

```swift
public extension TestKitHelpers {

    final class ConnectivityServiceSpy: ConnectivityService {
        public let stateChanges: AnyPublisher<Void, Never>
        nonisolated(unsafe) public var isDeviceConnected: Bool = false
        nonisolated(unsafe) public var disconnectedAt: Date?

        public init() {
            stateChanges = spy.stateChanges.eraseToAnyPublisher()
        }

        public func connect(to id: UUID) async throws {
            spy.record(.connect(id: id))
            try spy.connectHandler?()
        }

        public func disconnect() async throws {
            spy.record(.disconnect)
            try spy.disconnectHandler?()
        }

        public let spy = Spy()
    }
}
```

### Inner Spy Class

```swift
public final class Spy: @unchecked Sendable {

    public let stateChanges = PassthroughSubject<Void, Never>()
    public var connectHandler: (() throws -> Void)?
    public var disconnectHandler: (() throws -> Void)?

    public enum MethodCall: Equatable {
        case connect(id: UUID)
        case disconnect
    }

    private let lock = NSLock()
    private var _calls: [MethodCall] = []

    public var calls: [MethodCall] { lock.withLock { _calls } }

    func record(_ call: MethodCall) {
        lock.withLock { _calls.append(call) }
    }
}
```

## Usage in Tests

```swift
let service = TestKitHelpers.ConnectivityServiceSpy()

// Configure behavior
service.spy.connectHandler = { throw BluetoothError.timeout }

// Drive publisher events
service.spy.stateChanges.send(())

// Set protocol state
service.isDeviceConnected = true

// Assert recorded calls
XCTAssertEqual(service.spy.calls, [.connect(id: someUUID)])
```

## Rules

| What | Where |
|------|-------|
| Protocol state (`isDeviceConnected`, `disconnectedAt`) | Outer class, `nonisolated(unsafe) var` |
| Publisher backing (`PassthroughSubject`) | Inner `Spy`; outer forwards as `AnyPublisher` in `init` |
| Handlers (`connectHandler`) | Inner `Spy`; use `throws` if the protocol method throws |
| Call recording (`_calls`, `lock`) | Inner `Spy` always — never on outer class |
| Grouping | `public extension TestKitHelpers { ... }` |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| No lock on `_calls` | Concurrent tests corrupt the array — always use `NSLock` |
| `nonisolated(unsafe)` missing on outer vars | Compiler error: mutable var in `Sendable` type |
| Protocol state inside `Spy` | `service.spy.isDeviceConnected` is awkward — keep it on the outer class |
| `MethodCall` not `Equatable` | `XCTAssertEqual` on calls won't compile |
| Naming it `Mock` | A class that records calls is a spy, not a mock — use `Spy` suffix |
