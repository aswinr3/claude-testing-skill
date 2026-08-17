# Wiring the suite into CI

A run ends. The gate persists. Everything else in this skill produces a verdict for one moment in time; this file is how that verdict keeps being re-earned on every commit without a human re-running anything.

**The goal is not "we have CI". It is that no one is ever the reason a regression shipped.** A suite that must be remembered is a suite that will be forgotten in the week someone is on leave.

## The economics, stated plainly

Manual regression is the single largest line item in most QA teams' hours, and it is the one that automates cleanly: identical steps, known oracles, zero judgement. Exploratory testing, severity calls and UX judgement do not automate and should not be attempted. Move the first category into the gate and hand the recovered hours to the second.

The measurable claim to make afterwards is **mean time to detect** (`test-strategy.md` § suite health) — commit to failing test. A suite run manually before a release detects in days. The same suite on a per-PR gate detects in minutes, and the defect is repaired by the person who wrote it while the change is still in their head.

## The gate ladder

Not everything runs on every trigger. Match cost to feedback value; the build order in `SKILL.md` § the pipeline is the *execution* order within each rung.

| Trigger | Runs | Budget | Gating? |
|---|---|---|---|
| **Pre-commit hook** | lint, changed unit files | < 15 s | Advisory — never block a commit |
| **Per-PR** | smoke → sanity → unit → integration → functional (changed areas) | **< 10 min** | **Yes.** Red blocks merge |
| **On merge / deploy** | full regression + UI audit | < 20 min | Yes — reverts the deploy |
| **Nightly** | full suite, all browsers, a11y, visual, non-functional | unbounded | No — files defects instead |
| **Pre-release** | everything, against the release build in the release environment | unbounded | Yes — release checklist |

Two rungs carry most of the value. **Per-PR** is where detection gets cheap. **Nightly** catches what no commit caused — backend drift, expired fixtures, third-party changes, data rot — which is exactly the class that manual regression is usually re-hired to find.

**The 10-minute rule is a hard constraint, not an aspiration.** Past ~15 minutes people stop running it locally, start merging on red, and the gate becomes theatre. When the budget is breached: push cases down the pyramid, shard across parallel jobs, run only tests touching changed areas per-PR, and move the slow remainder to nightly. Never fix it by deleting assertions.

## Target the environment, never hardcode it

The same suite must run against local, preview, staging and production without editing code.

```js
// playwright.config.js
const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
const IS_CI = !!process.env.CI;

module.exports = defineConfig({
  use: { baseURL: BASE_URL, trace: 'retain-on-failure', screenshot: 'only-on-failure', video: 'retain-on-failure' },
  forbidOnly: IS_CI,        // a committed .only silently skips the rest of the file
  retries: IS_CI ? 2 : 0,   // reveals flake — see below. Never set locally
  outputDir: './.playwright-artifacts',   // NOT test-results/ — that is the run record
});
```

`forbidOnly` deserves its place: a committed `.only` is listed in `review.md` as a critical finding precisely because CI stays green while testing almost nothing.

**Production safety carries into CI.** `targets.md` restricts production to read-only checks; a scheduled job inherits that restriction and is more dangerous for being unattended. Point write-path suites at staging via `BASE_URL`, and gate any production run to smoke only. Credentials are CI secrets, never committed — per-role logins (`SKILL.md` § dependency gate) become one secret per role.

## Artifacts are the bug report

This is where the largest slice of manual QA labour disappears, and it is almost always left switched off.

A Playwright trace holds the DOM at each step, network, console, and a video timeline. **Attaching it to the ticket replaces writing reproduction steps by hand** — the developer opens it and steps through the failure in a browser. `evidence.md` governs naming and storage; CI's only job is to make sure the artifact survives the runner.

```yaml
- name: Upload report
  if: always()      # a failed run is exactly when the evidence is needed
  uses: actions/upload-artifact@v4
  with:
    name: playwright-report-${{ github.run_number }}
    path: |
      playwright-report/
      .playwright-artifacts/
    retention-days: 14
```

`if: always()` is not optional. The default skips upload on failure, discarding the evidence for every run anyone cares about.

Two more that pay for themselves: the `github` reporter annotates failures on the PR diff, so reviewers see them without opening logs; and uploading the run record from `test-results/<date>-<time>/` keeps the module and per-type files (`results.md`) attached to the build that produced them.

## Retries reveal flake — they must never hide it

`retries: 2` on CI is correct, and it is also how a suite quietly rots. A test that passes on retry is **not a pass** (`test-strategy.md` § flaky test policy). CI must surface it rather than print green.

The distinction is in the JSON report: a test whose final `status` is `passed` with `retry > 0` flaked. Extract those, count them against the < 1% threshold, and file them — a flake that is never counted is never fixed.

```js
// flake rate from the JSON reporter output
const flaked = suites.flatMap(s => s.specs).flatMap(sp => sp.tests)
  .filter(t => t.status === 'expected' && t.results.length > 1);
```

**Retries are a diagnostic, never a remedy.** The remedy is in `review.md` § flakiness. Raising retries to make a red gate green converts a real signal into permanent noise, and it is the first step of the slow slide where the team stops trusting red.

Quarantine has a home in CI: a separate non-gating job, tagged, with a linked ticket and an expiry — visible, not silently `.skip`ped.

## Reference workflow

```yaml
name: E2E
on:
  pull_request:
  push: { branches: [main] }
  schedule: [{ cron: '0 2 * * *' }]     # nightly: catches drift no commit caused
  workflow_dispatch:                     # manual run against any environment
    inputs:
      base_url: { description: 'Target environment', required: false }

concurrency:                             # supersede stale runs on the same ref
  group: e2e-${{ github.ref }}
  cancel-in-progress: true

jobs:
  e2e:
    runs-on: ubuntu-latest
    timeout-minutes: 20                  # a hung suite must fail, not burn the runner
    env:
      BASE_URL: ${{ github.event.inputs.base_url || vars.BASE_URL }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: npm }
      - run: npm ci
      - uses: actions/cache@v4           # browser binaries: ~40 s per run
        with:
          path: ~/.cache/ms-playwright
          key: pw-${{ runner.os }}-${{ hashFiles('package-lock.json') }}
      - run: npx playwright install --with-deps chromium
      - run: npm test
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-report-${{ github.run_number }}
          path: |
            playwright-report/
            .playwright-artifacts/
```

Shard when the budget is breached — `--shard=${{ matrix.shard }}/4` across a matrix, then merge the blob reports.

## Handing the suite to the team

A gate only holds if the people who own the product can extend it. Where the QA team does not write code, the constraint is authoring, not running.

- **`npx playwright codegen <url>` records a session into runnable test code.** A manual tester clicks the flow they already know; the generated file becomes the starting point. Locators still need hardening to role/label (`playwright.md`) and a real oracle added — generated assertions are weak — but the blank page is gone, and that was the barrier.
- **`npx playwright test --ui` gives a watch-mode runner** with time-travel over each step. It is the debugging tool to hand someone who has never opened a terminal for this before.
- **Named scripts beat remembered flags.** `npm run test:smoke` gets run; `npx playwright test --grep @smoke --project=chromium` gets forgotten.
- **The suite is reviewed like code.** New tests get the `review.md` audit — above all, the one question: if the behaviour breaks, does this go red?

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Team merges on red | Suite is slow or flaky; red stopped meaning anything | Fix flake first, then re-gate. Never re-gate a suite above 5% flake |
| Green CI, bugs still ship | Tests assert what is easy, not what is risky | Escape rate, not test count. `test-strategy.md` |
| "Works locally, fails in CI" | Hidden env dependence — timezone, locale, seeded data, screen size | Pin `TZ`, viewport and locale in config; seed via API per test |
| Nightly is permanently red | No owner, so no one triages | A red nightly is a defect with a name on it, or the job is deleted |
| Suite grows, runtime explodes | Everything written as e2e | Push down the pyramid; only journeys stay e2e |
| Failure has no evidence | Upload step skipped on failure | `if: always()` |

The pattern underneath all six: **a gate no one trusts is worse than no gate**, because it costs runner time, blocks merges, and catches nothing anyone acts on. Fewer, reliable, fast checks that genuinely gate beat a broad suite everyone has learned to re-run.
