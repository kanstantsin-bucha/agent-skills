---
name: unit-testing-escalation
description: Use when running or modifying Swift tests — covers the correct escalation order (single file → module → full suite) and the tuist command to run a single test class before committing to a full suite run.
---

# Tuist Test Escalation

## Overview

Always run tests in escalating scope. Never jump straight to the full suite when only one file changed.

## Order

1. **Single file** — after editing a test file, run only that class first
2. **Module** — once all modified the files passes, run the full module
3. **Full suite** — only after module passes

## Commands

### Single file, use for each modified test file once 
```bash
TUIST_APP_VARIANT=SIM mise x -- tuist test [SchemeName] -- -only-testing:[TestTarget]/[TestClassName]
```
Example:
```bash
TUIST_APP_VARIANT=SIM mise x -- tuist test CommonScreens -- -only-testing:CommonScreensTests/KioskModeServiceTests
```

### Module, use for each modified module once 
```bash
TUIST_APP_VARIANT=SIM mise x -- tuist test [SchemeName]
```
Example:
```bash
TUIST_APP_VARIANT=SIM mise x -- tuist test CommonScreens
```

### Full suite
```bash
make tuist_test
```

## Quick Reference

| Scope | When | Command |
|---|---|---|
| Single file | After editing one or several test classes | `tuist test Scheme -- -only-testing:Target/Class` |
| Module | After all single files passes, run for each modified module | `tuist test Scheme` |
| Full suite | After all modules passes | `make tuist_test` |

## Why

Catching compile errors and failures at the single-file level is fast. Running `make tuist_test` on every change wastes minutes per iteration and buries the signal in noise from unrelated targets.
