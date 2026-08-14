# Reviewing tests

Auditing an existing suite, or triaging a flaky test.

## The one question

**If I break the behaviour this test claims to guard, does it go red?**

Everything else is secondary. Check it directly on anything suspicious: comment out the logic or invert a condition, run the test, see whether it notices. A green test over broken code is the worst outcome in a suite — it's a false assurance someone is relying on.

## Audit checklist

Work through by severity. Report findings with file:line and a concrete failure scenario, not a style opinion.

### Critical — the test doesn't test

- No assertion, or only `expect(x).toBeDefined()` / `toBeTruthy()` on something that's always defined.
- Passes with the implementation removed (verify, don't guess).
- Assertion inside a callback that never runs — a `then` without `await`, an `expect` in an unreached branch.
- `try/catch` around the assertion that swallows the failure.
- Async without `await` — the test finishes before the assertion resolves and always passes.
- Mock asserted instead of behaviour: the whole test is `expect(mock).toHaveBeenCalled()`.
- `.only` committed (silently skips the rest of the file in CI), or `.skip` with no reason or ticket.

### High — the test lies about what it covers

- Name says one thing, body asserts another. The name is what future readers trust.
- Over-mocked to the point that the code under test is barely executed — every collaborator stubbed, only glue left.
- Snapshot as the sole assertion for logic, especially large or auto-regenerated snapshots.
- Only the happy path — no error branch, no boundary, no invalid input.
- Tests the mock's configuration rather than the system's behaviour.
- Asserts implementation details (private methods, internal call order, exact number of renders) so it fails on refactors and passes on regressions.

### High — flakiness

Look for these before reaching for a timeout bump:

- Real `Date.now()` / `new Date()` against computed expectations — breaks near midnight, month ends, DST.
- Real timers, `sleep`, or fixed `waitFor` delays standing in for a condition.
- Unmocked network, or a stubbed client that falls through to the real one on unmatched routes.
- Shared state: module-level singletons, a DB not reset between tests, `beforeAll` mutation, leaked mocks (no `restoreMocks`).
- Order dependence — confirm by running the file with `--shuffle` / `--randomize`.
- Parallel workers contending for the same fixture, port, or table.
- Locale/timezone-sensitive formatting without a pinned `TZ`.

Fix the cause. A longer timeout converts a fast failure into a slow one.

### High — flakiness, Playwright-specific

- `expect(await locator.isVisible())` instead of `await expect(locator).toBeVisible()` — the first evaluates once, the second retries. The single most common source of e2e flake.
- `page.waitForTimeout(n)` anywhere — an undiagnosed race with a delay taped over it.
- Parallel workers writing the same backend rows, user account, port, or screenshot path. Each test must create its own data (`workerIndex` / `testId` in the key).
- Locator chains tied to layout (`div > div:nth-child(3)`) rather than role or label.
- Conditional page-state branching (`if (await x.isVisible()) { ... }`) — the test then passes without asserting anything.
- Logging in through the UI in every test — slow, and every login is another chance to flake. Use `storageState`.
- Visual tests without `animations: 'disabled'`, a frozen clock, masked dynamic regions, or pinned fonts.
- Third-party scripts (analytics, ads, session replay) left unblocked in the browser context.

### Medium — maintainability

- Duplicated setup that should be a factory/builder; giant shared fixtures obscuring the field under test.
- Branching (`if`/`for`) in test bodies — split, or use `it.each`.
- Unclear names: `it('works')`, `it('test case 2')`.
- Wrong level: an e2e test doing what a unit test could, paying the slowness and flakiness tax for nothing.
- Dead tests guarding removed behaviour.

## Coverage that lies

- High line coverage, weak assertions — code executed but nothing checked.
- Branch coverage well below line coverage means error paths are unexercised; that's where the bugs are.
- Files excluded from the coverage config — check the ignore globs, not just the number.
- Rising coverage from tests added alongside a feature that never fail: check a sample can actually fail.

## Triaging one flaky test

1. Reproduce — run it 20–50× in a loop (`--repeat` / a shell loop). Record the failure rate.
2. If it never fails alone, it's contamination from another test: run the file, then the suite, then `--shuffle`. Bisect until you find the pair.
3. If it fails alone, it's internal nondeterminism: time, random, async ordering, or an unawaited promise.
4. Fix the cause; re-run the loop to confirm the failure rate is zero. Say what the rate was before and after.
5. Only quarantine (`.skip` + a linked ticket) if the cause is genuinely external and it's blocking others — and say so explicitly rather than leaving a silent skip.

## Reporting

Order by severity, lead with the ones that mean coverage is imaginary:

```
### Critical
- `checkout.test.ts:88` — "applies discount" passes with the discount logic deleted.
  Only assertion is `expect(total).toBeDefined()`. Verified: commented out
  `applyDiscount`, test still green.

### High
- `auth.test.ts:23` — flaky ~1 in 12 runs. Asserts against `Date.now()` while the
  code rounds to the minute; fails when the call crosses a minute boundary.
  Fix: `vi.setSystemTime`.

### Medium
- `user.test.ts` — 40 lines of duplicated setup across 6 tests; extract `makeUser`.
```

Don't pad with style nits. Three real findings beat thirty cosmetic ones.
