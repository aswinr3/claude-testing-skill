---
name: testing
description: Document-driven QA for a web platform — read the PRD, slice specs, permissions matrix, workflows, user flows and design system in full, derive precise traceable test cases from them, and verify the running platform with Playwright plus Jest/Vitest. Covers unit, integration, mock, smoke, sanity, functional, regression, exploratory and non-functional testing; compares the built UI against the design file and design system; runs a deterministic UI defect sweep; emits test cases as TSV for Google Sheets; and writes per-module and per-type result files after every run. Gathers every testing dependency up front (per-role credentials, disposable-data status, spec location) and waits for them — a missing critical dependency gates the run unless the user says to proceed without it — then runs the agreed scope end to end and reports a single verdict. Use when asked to test a platform against a PRD/spec/requirements doc, write or review tests, plan QA, build Playwright e2e coverage, check design conformance, hunt UI issues, generate test cases, close coverage gaps, run smoke/regression, or chase a flaky test.
---

# Testing

Testing here is **document-driven**: the PRD and its supporting documents are the source of truth, every test case traces to a numbered requirement, and the deliverable is a conformance verdict plus result files — not a pile of green checkmarks.

Platform-level verification runs on **Playwright**. Unit and integration run on the repo's **Jest/Vitest** setup.

| Job | Load |
|---|---|
| **Preflight — run this before anything else; it exits non-zero when the run would break** | `references/preflight.md` |
| **Branch to work on — named from the parent branch** | `references/branching.md` |
| **What you can reach — source, hosted URL, or both — and what you may claim** | `references/targets.md` |
| **Read the project's documents deeply — PRD, vertical slices, permissions, flows — and reconcile them** | `references/document-intelligence.md` |
| Which document holds what, and its ID scheme *(when the standard template set is in use)* | `references/document-map.md` |
| Extract requirements, derive cases, build the traceability matrix | `references/documents.md` |
| Which test type applies, in what order, entry/exit criteria | `references/test-types.md` |
| Risk-based prioritisation, suite shape, test data, exit criteria, suite health | `references/test-strategy.md` |
| Property-based, mutation, contract, load, authz depth, a11y limits | `references/advanced-techniques.md` |
| MCP servers — Playwright MCP, Context7, and what each is for | `references/tooling.md` |
| Write cases into Google Sheets (+ the Gemini prompt) | `references/test-cases-sheet.md` |
| Playwright mechanics — locators, auth, network mocking, a11y, perf | `references/playwright.md` |
| Jest/Vitest mechanics — structure, mocking, determinism | `references/unit-integration.md` |
| Built UI vs `design.html` vs the design system | `references/design-conformance.md` |
| Deterministic UI defect sweep (overflow, clipping, contrast, states) | `references/ui-audit.md` |
| Screenshot regression + AI triage of the diffs | `references/visual.md` |
| Auditing existing tests, triaging flakes | `references/review.md` |
| **Bug evidence — screenshot, store, link into the sheet** | `references/evidence.md` |
| **More than one session, agent or suite against one target — shared budgets, shared state, shared tooling** | `references/concurrency.md` |
| **Writing the result files — required at the end of every run** | `references/results.md` |
| Keeping the suite running after the run — CI gates, artifacts as bug reports, flake in CI | `references/ci.md` |

## Gather every dependency FIRST, then run to completion

**The order is fixed: collect all testing dependencies up front, get the answers, and only then start testing. Do not begin a run knowing a critical dependency is missing and quietly produce a partial result — that is half-baked work, and it wastes a run reporting mostly "Not run".**

### Step 1 — ask for everything, once, and wait

**Batch every dependency into a single request at the very start**, before writing a test. These are known in advance; there is no reason to discover them one at a time mid-run:

- The target URL(s), and which environment each is.
- **One account per role**, named — every role in the permissions matrix. Two accounts minimum, or authorization, tenancy, and role-boundary testing are all impossible. **A separate admin/staff account is a distinct dependency** — a merchant login does not test the admin panel.
- **Whether the environment holds disposable data** — decides whether write paths, exploratory, and load testing are permitted. Without it you are confined to read-only, which is a fraction of the product.
- Where the specification lives, if not in the working tree.
- Whether source access is available.

State plainly what each dependency unlocks, so the user sees the cost of leaving one blank. Then **wait for the answers.** Gathering dependencies is a genuine gate, not a formality you sail through.

### The rule you must not break

**A missing critical dependency (credentials for a role, disposable-data confirmation, the specification itself) is a reason to ask and wait — NOT a reason to proceed and hand back half the product tested.** If you cannot test the admin panel because you have no admin login, the answer is to say so and ask for it, not to test the merchant panel, call it done, and bury "admin: not run" in the report. The user asked for the platform to be tested; delivering a third of it as if that were the whole job is the failure this rule exists to prevent.

**Proceed without a dependency only when the user has explicitly told you to** — "test what you can without admin creds", "go ahead read-only for now", "I'll get you the login later, start on the rest". That is their decision to make, and once made you run to completion on the agreed scope and record the rest as `Not run — <dependency> not provided`. Absent that explicit instruction, a missing critical dependency **blocks the run** and you wait.

Distinguish critical from non-critical honestly:
- **Critical → ask and wait:** any per-role credential, disposable-data status, an unreachable target, authorisation to test a URL that is not obviously the user's own.
- **Non-critical → assume, note, and proceed:** a missing accessibility target (assume a defensible floor and say so), an unstated performance budget (measure and record rather than pass/fail), an ambiguous copy string. Prefer a stated assumption to a blocking question *for these*.

**Before treating a missing per-role login as a blocker, check whether the product lets you create the roles yourself.** On a disposable/staging target where signup is open and an owner/admin can invite teammates, the role set is self-serviceable: create the test accounts through the app's own signup and invite flows, or move one account through the roles with the role-change feature, then run the matrix. When that path exists, a missing per-role login is **not** grounds to block or to file the authorization matrix as "Not run" — set the roles up and run it. Steps are in `advanced-techniques.md` → "Self-provision the roles". This is a write action: staging only, never against a read-only production target. Genuinely blocked only when signup is closed *and* no invite is possible.

### Step 2 — once you have what you need, do not stop

With the dependencies in hand (or an explicit instruction to proceed without some), run the agreed scope end to end:

- **Never pause mid-run to report progress or ask permission to continue.** Finish the agreed scope, then report once.
- **Never ask a question you can answer by testing.** The route list, API surface, real query-parameter names, placeholder text, auth-storage mechanism — all discoverable in seconds by driving the app. Discover them; never ask.
- **"No specification" does not block functional testing** — but it is a dependency you still ask for. If it is genuinely unavailable, self-evident oracles (a wrong password must not grant a session; an unauthenticated call must be denied; an invalid parameter must not throw) are fair game; label the oracle source as self-evident. Product *decisions* — wording, thresholds, permitted values — still need the spec.

The one thing that always justifies stopping mid-run: an action that could damage real data or hit a system you are not authorised to touch. Confirm scope once, in Step 0, and never re-litigate it.

## Step 0 — Orient

Never skip. Report the result in a few lines before doing anything else.

0. **Run the preflight.** `eval "$(bash scripts/preflight.sh <repo>)" || exit 1`. It pins the repository (nested repos silently capture bare `git` commands), refuses the default branch and a detached HEAD, snapshots pre-existing changes so a run commit cannot sweep them in, namespaces the run directory and artefact directory, and fails when `outputDir` would wipe the run record. Everything after this uses `git -C "$RUN_REPO"`. `preflight.md`.
1. **Branch first.** Create `<parent>-test-<slug>` from the current branch and switch to it **before writing any file**. Nesting under the parent with a slash (`main/tests`) is impossible in git — see `branching.md` for why, plus the detached-HEAD and dirty-tree guards. Never run test work directly on `main`/`master`.
2. **Establish the target mode, and gather every dependency before testing.** Is the **source** present? Is a **running instance** reachable — locally, or as a hosted URL? Which environment is that URL? Do you have **one account per role** (a merchant login does not cover the admin panel), and is the data **disposable**? These decide which of the nine types are even possible. Batch all of it into one request, then **wait** — a missing critical dependency (per-role credentials, disposable-data status, the spec) gates the run: ask and wait unless the user has explicitly said to proceed without it. See "Gather every dependency FIRST". **Against production, run read-only checks only** — no load, no exploratory, no destructive flows, no test-data creation — and confirm you're authorised to test any URL that isn't obviously the user's own. `targets.md`.
3. **Read the documents deeply, then reconcile them.** This is a five-pass job, not a skim: inventory and pin every document (filesystem *and* git history), read each one **end to end**, extract into a **requirement index** with namespaced IDs anchored to a line or matrix cell, reconcile across documents for contradictions/duplications/orphans/silence, and finish with a coverage self-check. `document-intelligence.md` is the method; it is what makes "not specified" a credible claim. Check whether the project uses the standard template set — PRD, slice specs, permissions matrix, workflows, user flows, design system, data model, architecture, glossary, ADRs. **If it does**, `document-map.md` gives the ID scheme and per-document extraction. **If it doesn't**, fall back to generic discovery in `documents.md` §1 and derive an ID scheme from whatever the project uses. Either way, list each document with path and version and read them **completely** — a requirement in a section you skipped becomes a "not specified" you'll be wrong about. Documents may also live in git history rather than the working tree; check `git ls-tree -r --name-only HEAD` before concluding a document is missing.
4. **Detect the runners.** `package.json` scripts and deps, plus `playwright.config.*`, `vitest.config.*`, `jest.config.*`. Note which directories each owns.
5. **Get the platform running**, or pin the deployment. Dev command, base URL, seeded accounts, env. With a hosted target, record the build/commit identifier — without one, every later drift finding is ambiguous between "wrong code" and "stale deployment".
6. **Check the design file.** Is `design.html` present and non-empty? If it's a stub, say so and skip design-file comparison rather than silently degrading to a spec-only check.
7. **Establish the baseline.** Run the existing suites and record what already fails, so pre-existing red isn't attributed to your work.

Report as: `Mode D — source + staging URL. Docs: PRD v2.3, 4 slices, Permissions v1.1, Design System v0.4. Runners: Playwright 1.5 (e2e/), Vitest 2.1 (src/). App: staging.example.com, build 1.4.0-rc2 @ a91f2c3. Roles: 2 of 4 available. design.html: 0 bytes — comparison unavailable. Baseline: 143 pass, 2 pre-existing failures in billing/.`

## The pipeline

| # | Type | Answers | Tool |
|---|---|---|---|
| 1 | **Unit** | Does each module obey its spec in isolation? | Vitest/Jest |
| 2 | **Integration** | Do the seams hold — DB, API, router, third parties? | Vitest/Jest, Playwright `request` |
| 3 | **Mock** | Do we behave correctly when a dependency fails or stalls? | `vi.mock`, `page.route` |
| 4 | **Smoke** | Is this build alive enough to be worth testing? | Playwright |
| 5 | **Sanity** | Did this specific change actually work? | either |
| 6 | **Functional** | Does every documented requirement work end to end? | Playwright |
| 7 | **Regression** | Did anything that used to work break? | full suite |
| 8 | **Exploratory** | What's broken that no document predicted? | manual + ad-hoc |
| 9 | **Non-functional** | Perf, a11y, security, compatibility, resilience budgets | Playwright, axe, Lighthouse |

**Build order is not execution order.** In CI run: smoke → sanity → unit → integration → functional → regression → non-functional, failing fast at each gate. Exploratory is a human-in-the-loop session; its findings become functional and regression cases. Which rung runs on which trigger, and how to wire the gate itself, is `ci.md`.

**Mock is a technique, not a stage** — it appears inside the others. It's listed separately because dependency-failure behaviour is a documented requirement that routinely goes untested.

**Design conformance and the UI audit** are part of Functional and Non-functional, driven by `DESIGN_SYSTEM.md`, `USER_FLOWS.md`, and `design.html`.

## Test case accuracy

Vague cases are why green suites mean nothing. Every case carries:

- A **namespaced requirement ID** (`PRD:BR-03`, `SLICE-04:S04-02`) — the templates reuse `D-` for two different things, so bare IDs corrupt traceability.
- **Explicit preconditions** — state, seed data, role, flags.
- **Concrete data** — `user_verified@test.local`, `0`, `-1`, `999999`; never "some user".
- **A single observable oracle** — "login works" is rejected; "redirects to `/dashboard` and the header shows the user's email" is accepted.
- **A negative oracle** — what must *not* happen (no email sent, no second charge).
- **A named derivation technique** — boundary value, equivalence partition, decision table, state transition, pairwise, error guessing. Cases invented by intuition miss the same places every time.

Anything gated on an open decision (`Q-`, `PM-`, `UX-`, `DS-`, `DM-`, `S[NN]-`) is **not an approved requirement**. Test the safe default if useful, label it `Provisional — pending <ID>`, and never let it gate MVP acceptance.

Column contract and the Gemini prompt: `test-cases-sheet.md`.

## Coverage volume — derive the whole suite, not a sample

**A handful of happy-path cases is a smoke test, not a test suite.** Accuracy per case (above) and *count* of cases are different obligations, and both are mandatory. A green run over 20 cases on a product with dozens of screens, roles, and workflows proves almost nothing — it silently leaves the vast majority of behaviour untested and reports confidence you did not earn.

**Enumerate exhaustively, then derive every case each feature generates.** For every module/screen/endpoint, walk *all* of these and write a case wherever one applies — do not stop at the happy path:

- **Happy path** — each primary action, once per role that may perform it.
- **Alternate paths** — every branch, optional field, sort/filter/pagination, each tab/view, keyboard vs mouse, bulk vs single.
- **Boundary values** — min−1 / min / min+1 / max−1 / max / max+1 on every numeric, length, date, quantity, and money field.
- **Equivalence partitions** — one representative per valid and invalid class for every input.
- **Negative & error paths** — empty, whitespace, wrong type, duplicate, malformed, oversized, injection-shaped, expired/used token, cancelled dialog, back-button mid-flow.
- **State transitions** — every create → edit → delete → restore, draft ↔ published, each status change, empty-state vs populated.
- **Authorization** — every protected action attempted as **each** role, plus unauthenticated and cross-tenant (both the UI gate and the server endpoint).
- **Cross-cutting non-functional** — responsive breakpoints, a11y, and a security oracle per sensitive surface.

**Scale the target to the product, and hit it.** For a web application of the size seen here (multiple modules, several roles, workflow-heavy):

- **Minimum 200 cases. Up to ~500** as breadth warrants — a small tool floors lower, a large multi-module suite reaches the ceiling. Below ~200 for an app this size, treat the suite as *incomplete* and keep deriving, not done.
- Budget cases per module *before* writing: a substantial module (Finance, Projects/Tasks) will alone yield 30–60; a thin one (Inbox) 8–15. Sum them, and if the total undershoots, you have missed cases, not run out of them.
- **Never truncate the register to save effort or tokens.** If you must stage the work, write *all* the case rows first (they are cheap), then execute as many as the run allows and mark the rest `Not run` with a reason — a case you never wrote is invisible; a case written-but-not-run is honest coverage accounting. Silent under-generation is the failure this section exists to prevent.

**Coverage is measured, not asserted.** A register is a claim until something checks it. Derive each case's `covered` flag from **keys the run publishes at execution time**, never by hand-setting it while authoring — and generate the executed block *from the case log itself*. Then reconcile and print the comparison (`180 planned / 180 recorded`), so a register cannot drift away from what actually ran. Without this the count measures authoring effort rather than coverage, and a large number becomes less trustworthy than a small one.

**Separate "needs only a request" from "needs a fixture", and execute the cheap ones eagerly.** `Not run` is honest accounting for a case that is genuinely blocked — a missing fixture, an absent route, a destructive write that would corrupt another suite. It is not honest for a case that is one ordinary request and was simply deferred. In one observed module, **111 of 155 unrun cases had no blocker at all** beyond a contended rate limiter; they were filed as coverage accounting and were really deferred work. Split the register on that axis and the gap is visible on the first day instead of when someone asks.

`test-strategy.md` covers how to budget, partition, and prioritise the enumerated set.

**Prioritise by risk, not by document order.** `Risk = likelihood × impact`; high-impact paths (money, data loss, authz, the primary journey) get tested first and automated first, and silent-failure paths outrank loud ones. Push every case to the cheapest level that can still catch the failure. `test-strategy.md`.

## Non-negotiables

- **A test that cannot fail is worse than none.** Before claiming a new test works, make it fail on purpose — break the assertion or the behaviour, see red, restore green.
- **Never weaken a test to make it pass.** No loosened matcher, no `.skip`, no bumped timeout. A failing test is right until proven otherwise; if it's genuinely wrong, say so and explain why before touching it.
- **Drift is reported, not resolved.** When the platform contradicts a document, that's a finding for a human — the code may be wrong, or the doc may be stale. Never silently pick a winner or write the test to match whichever you found first.
- **A hidden control is not an authorization control.** For every permission-hidden element, call the endpoint directly and assert server-side denial.
- **Determinism is mandatory.** No dependence on wall-clock time, real network, execution order, locale, or another test's leftovers.
- **Never report a suite as passing without running it.** Paste real failures. A flake is not a pass.
- **Do not start a run with a critical dependency missing.** Per-role credentials, disposable-data confirmation, and the specification are gathered and answered *before* testing begins. Testing the reachable third of a platform and filing the rest as "Not run" is a half-baked run, not a partial one — the difference is whether the user chose the scope. Proceed on a reduced scope only when they explicitly said to.
- **A green check proves nothing until the fixture is proven.** Verifying that an *assertion* can fail is not enough — the setup feeding it must also be sound. A readiness helper that returns early makes accessibility scans read an empty DOM and layout checks measure a blank page: every check passes, nothing was tested. When a whole class of checks passes at once, suspect the fixture before believing the result, and prove it by mutating the *page*, not the assertion.
- **Assert both polarities on any "restricted to a known list" rule.** A test that only sends an invalid value passes when the parameter is rejected for an unrelated reason — wrong name, wrong shape, not supported at all. Send a valid value too and require it to succeed.
- **A red result from an oracle you wrote yourself deserves the same scepticism as a green one.** "A test that cannot fail" has a mirror that is just as expensive: a test that fails for the wrong reason. Before reporting a failure, prove the oracle can actually distinguish. Three real examples from one module: a leak detector matching `/FROM /` fired on eight cases because a notification body read *"deducted **from** your account"*; a control located as a checkbox reported "missing" when it was built as a button with the same label; a row selector written for `li`/`tr` matched nothing on a page built from `div`s. All three would have shipped as defects. Suspect string matching against *content*, and any selector you invented rather than read off the page — and re-run the request by hand before you write the finding up.
- **A refusal for an unrelated reason is neither a pass nor a fail — it is `Blocked`.** The endpoint that rejects your boundary value because an earlier case left a conflicting row, or because a fixture is missing, never evaluated the thing under test. Passing it is a refusal for the wrong reason; failing it invents a defect out of your own suite.
- **Confirm the effect, not the tool that reports it.** An exit code says the command ran, not that it worked. A runaway suite was reported killed three times while it kept writing, because the kill never matched and the process list was being read wrongly — the artefact still growing was the only honest signal. Verify state by observing the state.
- **Keep the runner's artefact directory out of the run record.** Playwright's `outputDir` defaults to `test-results/` and is wiped before every run, which deletes the very report you are writing. Point it elsewhere (`.playwright-artifacts/`).
- **When anything else runs against the same target, load `references/concurrency.md` first.** Shared rate limits, shared fixtures and shared tooling break assumptions this skill otherwise makes silently — including the one that costs most: a runner whose per-test timeout is shorter than the platform's rate-limit window kills its own tests mid-wait and reports them as failures.

## Every run ends with result files

**This is required, not optional.** Write to `test-results/<date>-<time>/` at the project root:

- `00-SUMMARY.md` — verdict, **module table first** where the project has slices, then the per-type table, blocking items, and a **Not covered** section.
- `modules/SLICE-NN-<name>.md` — **one file per vertical slice, including slices that were not tested at all.** This is the primary view: teams own features, not test types, so "is checkout releasable?" must not require grepping nine type files. Each states routes exercised, status, defects, results against the slice's four acceptance examples, and — the part everyone skips — which of its **Required evidence** is still owed.
- `by-type/01-unit.md` … `by-type/09-non-functional.md` — **one file per test type, including types that did not run.** A missing file reads as "nothing wrong"; a file saying `Not run — no time box allocated` reads as what it is.
- `conformance-matrix.md`, `design-conformance.md`, `ui-audit.md`, `defects.md`, `cases.tsv`.
- `screenshots/` — **every failing case gets a screenshot, no exceptions — UI and API/backend alike.** UI failures are shot at the moment of failure with the offending element highlighted; API/CLI/backend failures are shot by rendering the request+response transcript to an image (see `evidence.md` §2c). One image per `Fail` row, named `TC-####__rule__WxH.png`, plus Playwright traces. **The count of failure screenshots must equal the count of `Fail` rows** — a failing case with no screenshot is an incomplete run, not a partial one.
- **A "What this run changed" section**, naming the irreversible parts by id: records emptied, counters spent, flags set and whether they were restored, accounts created, data a defect destroyed before it was understood. Test data is disposable, but it must be *attributable* — the next run inherits this state, and a fixture nobody can account for is debugged from scratch every time. Where a case could not be evaluated because an earlier case consumed its fixture, say so there as well as in the case row.

**Organise cases by module, not by test type.** Every case carries `Module (Slice)` as its first column, so the register groups and filters by the thing a team actually owns. Where the project has no slices, derive modules from route groups, bounded contexts, or top-level features — and say which you used.

A module's verdict is measured against **its own Required-evidence list**, not against the tests you happened to write. Passing every case you wrote while skipping the evidence the slice demands is not a pass.

`cases.tsv` pastes back into the Google Sheet to update `Status` / `Last Run` / `Defect Ref` / `Evidence` — the sheet is the case register, the result files are the run record, reconciled by `Case ID`.

Evidence links use `=HYPERLINK()`, not `=IMAGE()` — `=IMAGE()` needs a publicly-served URL and renders `#VALUE!` for Drive files shared with named people. Capture, upload, and linking: `references/evidence.md`. Result file format and honesty rules: `references/results.md`.
