# XCTest → Swift Testing Mapping

| From | To |
|---|---|
| `import XCTest` | `import Testing` (+ `import Foundation` if `Date`/`URL`/`Data`/`NSError`/`LocalizedError` are used — XCTest imported it transitively) |
| `final class XTests: XCTestCase` | `@Suite struct XTests` (`@MainActor` only per the isolation rule) |
| `func test_foo_bar()` | `@Test("human readable description") func foo_bar()` |
| `XCTAssertEqual(a, b)` / `XCTAssertNotEqual` | `#expect(a == b)` / `#expect(a != b)` — parenthesise operands containing `?:`, `\|\|`, `&&` |
| `XCTAssertTrue(a)` / `XCTAssertFalse(a)` | `#expect(a)` / `#expect(!a)` |
| `XCTAssertNil(a)` | `#expect(a == nil)` |
| `XCTAssertNotNil(a)` | `let a = try #require(a)` — see rule 1 |
| `XCTAssertEqual(a, b, "msg")` | `#expect(a == b, "msg")` |
| `guard let x = … else { XCTFail("msg"); return }` | `let x = try #require(…, "msg")` |
| `XCTFail("msg")` | `Issue.record("msg")` |
| `XCTAssertThrowsError(try f()) { … == .e }` | `#expect(throws: E.e) { try f() }` (needs `Equatable`); otherwise `let error = #expect(throws: (any Error).self) { … }` |
| `XCTAssertNoThrow(try f())` | `try f()` in a `throws` test |
| `file: StaticString = #filePath, line: UInt = #line` | `sourceLocation: SourceLocation = #_sourceLocation` |
| `file: file, line: line` | `sourceLocation: sourceLocation` |
| `override func setUp()` | `init()` of the suite |
| `override func tearDown()` | `final class` suite + `deinit` |
| `wait(for:timeout:)` / `fulfillment(of:timeout:)` | bounded wait — rules 3 and 4 |

Converting hundreds of asserts? Script the mechanical part (balanced-paren argument splitting), then review by hand every `NotNil`, `try?`, expectation, `XCTFail` and `setUp`/`tearDown` the script flags. Check the script didn't eat blank lines or capture newlines into indentation.
