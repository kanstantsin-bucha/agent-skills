# Porting From XCTest

| From | To |
|---|---|
| `final class X_Tests: XCTestCase` | `@Suite @MainActor struct XTests` |
| `func test_foo_bar()` | `@Test("human readable description") func foo_bar()` |
| `XCTAssertEqual(a, b)` | `#expect(a == b)` |
| `XCTAssertNil(a)` / `XCTAssertTrue(a)` / `XCTAssertFalse(a)` | `#expect(a == nil)` / `#expect(a)` / `#expect(!a)` |

`import XCTest` pulls in Foundation transitively; `import Testing` does not. Any
file declaring `LocalizedError` stubs, using `Date`, `URL`, `Data`, etc. needs an
explicit `import Foundation` added during the port (symptom:
`Cannot find type 'LocalizedError'`).

Preserve every assertion and the `// Given` / `// When` / `// Then` structure. A
port is not a rewrite of the test logic.

Two traps that only appear after a port:

- `skipInFlightEffects` worked under XCTest and now makes tests vanish from the
  runner output — read `long-running-effects.md`.
- A `TestStore` that ran fine under XCTest now segfaults — the target is missing
  `IssueReportingTestSupport`; read `segfault-troubleshooting.md`.
