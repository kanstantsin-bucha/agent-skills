# Troubleshooting: TestStore Segfault

**Symptoms:** `EXC_BAD_ACCESS` / `KERN_INVALID_ADDRESS` at a small address (e.g.
`0x1f0`) inside `TestStore.init`, before any `send`. No assertion message, no
crash report surfaced by the runner, which may silently relaunch the suite in a
loop. Pure-value tests in the same suite pass. The same assertions pass under
`XCTestCase`. Reproduces with a single test, no parallelism.

**Cause:** the target does not link `IssueReportingTestSupport`. `TestStore.init`
→ `SharedChangeTracker.track` → `CachedValues.CacheKey.init` → `TestContext.current`
→ `IssueReporting._currentTest()`, which `dlsym`s a symbol from that dylib. When
the lookup fails, DEBUG builds fall back to a hand-maintained replica of Swift
Testing's internal `Test` struct filled via `unsafeBitCast`; a layout mismatch
makes ARC's outlined destroy release a field at a wrong offset. XCTest is immune
only because `Test.current` is `nil` there, so the replica is never built — which
is why porting to `XCTestCase` appears to "fix" it while hiding the real cause.

**Fix:** add the dependency (see Target Setup in `SKILL.md`), `make generate_sim`,
then verify:

```bash
grep -o 'IssueReportingTestSupport.framework' \
  Projects/<Path>/<Name>.xcodeproj/project.pbxproj
```

**Does not help** — all tried, crash survived: `@MainActor` on the suite or test
(correct for other reasons, but irrelevant here), `await store.finish()`,
`exhaustivity = .off`, `@Suite(.serialized)`, porting back to `XCTestCase`
(hides it, doesn't fix it).

**Confirming a fresh crash.** The runner prints nothing useful, so read the real
backtrace rather than guessing:

```bash
ls -t ~/Library/Logs/DiagnosticReports/xctest-*.ips | head -1
```

The `.ips` is JSON-lines: a metadata line, then the body. Parse
`body['threads'][body['faultingThread']]['frames']` and map each `imageIndex`
through `body['usedImages']` for symbol names. Frames reading
`outlined destroy of Test?` → `_swift_release_dealloc` confirm this diagnosis;
anything else is a different bug.
