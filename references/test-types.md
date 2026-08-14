# The nine test types

Each entry: what it answers, what goes in it, when it runs, and when it's done. If a case doesn't fit the type's purpose, it belongs in a different type — that discipline is what stops the suite becoming one undifferentiated blob.

**Build order** is the order below. **Execution order in CI** is: smoke → sanity → unit → integration → functional → regression → non-functional, failing fast at each gate. Exploratory is a human-in-the-loop session whose output feeds functional and regression.

---

## 1. Unit

**Answers:** does each function, class, or component obey its spec in isolation?

- **Scope:** one module. Collaborators are real if cheap and deterministic, faked otherwise.
- **Derive from:** every branch, boundary, and error path in the requirement. Equivalence partitioning + BVA do most of the work here.
- **Tool:** Vitest/Jest. Milliseconds per test; run on save.
- **Entry:** the function exists and its contract is written down.
- **Exit:** every branch has a case; every `throw` has a case; boundaries at `n-1/n/n+1`; the suite runs in seconds.

This is where the bulk of coverage belongs. A bug catchable by a unit test should never be chased by an e2e test.

---

## 2. Integration

**Answers:** do the seams hold — database, HTTP layer, ORM, queue, third-party client?

- **Scope:** two or more real components across a boundary. Use a real test database or container; stub only the third parties you don't own.
- **Derive from:** every requirement that mentions persistence, a status code, a transaction, or another service.
- **Tool:** Vitest/Jest with a test DB; Playwright's `request` fixture for API-level checks without a browser.
- **Entry:** unit tests green; a test database or container is available and resets between tests.
- **Exit:** each API endpoint has at least a happy path plus its documented error responses; each DB write is verified by reading it back.

Integration catches the wiring bugs unit tests mock away — wrong column name, missing migration, transaction not committed.

---

## 3. Mock (technique, applied at every level)

**Answers:** do we behave correctly when a dependency fails, stalls, or returns edge data?

Listed separately because dependency-failure behaviour is usually a documented requirement ("show a retry banner if payments is down") and almost always untested.

- **Scope:** wherever a boundary exists. `vi.mock` / `jest.mock` at unit level; `page.route` in Playwright at platform level.
- **Derive from:** for each external dependency — 500, 429, timeout, malformed body, empty result, slow response, network drop.
- **Exit:** every external call has at least one failure-path test; no test silently depends on a real network call.

Rules that keep mock-based tests honest: mock at boundaries you don't own, prefer a small working fake over a stack of `mockReturnValue`, and never let `expect(mock).toHaveBeenCalled()` be a test's only assertion.

---

## 4. Smoke — gate

**Answers:** is this build alive enough to be worth testing?

- **Scope:** a handful of critical paths — app loads, login succeeds, the main screen renders, the primary API responds. Under five minutes.
- **Derive from:** the paths whose failure makes every other test meaningless.
- **Tool:** Playwright, tagged `@smoke`.
- **Entry:** a deployed or locally running build.
- **Exit:** all smoke tests pass. **A red smoke run stops the pipeline** — running a 40-minute functional suite against a build that won't boot wastes 40 minutes to learn what smoke told you in two.

Smoke is broad and shallow: many features, one check each.

---

## 5. Sanity — gate

**Answers:** did this specific change or fix actually work?

- **Scope:** narrow — only the area that changed, plus its immediate neighbours. Not the whole suite.
- **Derive from:** the ticket. A bug fix gets a case that reproduces the original bug; confirm it fails on the old build.
- **Tool:** whichever level the change lives at.
- **Entry:** smoke green, and a specific change to verify.
- **Exit:** the changed behaviour is confirmed, and its immediate neighbours still work.

Sanity is narrow and deep — the mirror image of smoke. Use it to decide fast whether a build is worth a full regression pass.

---

## 6. Functional

**Answers:** does every documented requirement work end to end from a user's perspective?

- **Scope:** the full requirement set from `documents.md`, driven through the real UI or API.
- **Derive from:** the traceability matrix — one or more cases per requirement, each carrying its REQ ID.
- **Tool:** Playwright (UI and API).
- **Entry:** integration green; the platform is deployed and seeded.
- **Exit:** every requirement is Covered, Gap, Not implemented, or Ambiguous — with none silently unaccounted for.

This is the mode that produces the conformance verdict. Keep it requirement-driven, not screen-driven: coverage is measured against the document, not against the number of pages clicked.

---

## 7. Regression

**Answers:** did anything that used to work break?

- **Scope:** the accumulated suite — everything above, run together.
- **Derive from:** it grows by rule, not by design. **Every fixed bug adds a permanent case.** Every exploratory finding that turns out real adds one too.
- **Tool:** the full runner set, in CI.
- **Entry:** functional green for the new work.
- **Exit:** no previously-passing test fails. A newly-failing test is a regression until proven otherwise — never adjust the test to match the new behaviour without a documented decision.

Prune deliberately: delete cases for removed features, and quarantine flakes with a linked ticket rather than leaving them to erode trust in the suite.

---

## 8. Exploratory

**Answers:** what is broken that no document predicted?

Unscripted but not unstructured. Work in **charters** — a stated mission, a time box, and notes.

```
Charter:  Explore checkout with expired and edge-case payment methods
          to discover state-handling bugs.  Time box: 45 min.
Notes:    - Card expiring this month accepted; expiring last month → generic
            "error" with no message (BUG-1)
          - Back button after payment → order created twice (BUG-2)
          - Amount 0.00 → proceeds to Stripe, fails there with raw error (BUG-3)
```

- **Scope:** wherever curiosity leads — new features, recently-fixed areas, anything the team feels uneasy about.
- **Technique:** vary what scripted tests hold constant — timing, order, back/refresh, concurrency, unusual data, interrupted flows.
- **Entry:** a build stable enough to explore (smoke green).
- **Exit:** the time box expires. **Output is not pass/fail — it is a list of findings and new cases.** Every real finding becomes a functional case and joins the regression suite.

This is the only type that finds requirements nobody wrote down. Don't skip it because it doesn't produce a green tick.

---

## 9. Non-functional

**Answers:** does it meet the budgets the documents state — and the ones they should have?

| Dimension | Check | Tool |
|---|---|---|
| Performance | page load, LCP/CLS/INP, API p95, bundle size | Playwright timings, Lighthouse |
| Accessibility | WCAG violations, keyboard path, focus order, contrast | `@axe-core/playwright` |
| Security | authz on every endpoint, no secrets in responses, headers, injection | targeted Playwright + review |
| Compatibility | browser matrix, viewport matrix, locale, dark mode | Playwright projects |
| Resilience | dependency down, slow network, offline, rate limited | `page.route` fault injection |
| Data | retention, deletion, export correctness | integration |

- **Derive from:** every numeric or qualitative budget in the PRD and ADRs. Where the documents state none, propose one and log it as ambiguous rather than inventing a threshold silently.
- **Entry:** functional green — measuring the performance of a broken feature is wasted effort.
- **Exit:** each stated budget has a measurement and a verdict, with the measured number recorded so the next run can compare.

Accessibility and security are requirements, not extras. If the PRD omits them, that omission is itself a finding.
