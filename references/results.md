# Results output — write the run to disk

Every run ends by writing result files. Terminal output scrolls away and CI logs expire; the result files are the record the team reads, diffs, and attaches to a release decision.

## Location

Write to a `test-results/` directory at the **project root** — the parent of wherever the tests live (`e2e/`, `src/`, `tests/`). One dated directory per run, plus a `latest` pointer:

```
<project-root>/
├── e2e/
├── src/
└── test-results/
    ├── 2026-08-14-1432/
    │   ├── 00-SUMMARY.md
    │   ├── modules/                    ← primary view when slices exist
    │   │   ├── SLICE-01-identity-authentication-access.md
    │   │   ├── SLICE-02-onboarding-dashboard.md
    │   │   └── …one file per slice, INCLUDING untested ones
    │   ├── by-type/                    ← the nine pipeline types
    │   │   ├── 01-unit.md
    │   │   ├── 02-integration.md
    │   │   ├── 03-mock.md
    │   │   ├── 04-smoke.md
    │   │   ├── 05-sanity.md
    │   │   ├── 06-functional.md
    │   │   ├── 07-regression.md
    │   │   ├── 08-exploratory.md
    │   │   └── 09-non-functional.md
    │   ├── conformance-matrix.md
    │   ├── design-conformance.md
    │   ├── ui-audit.md
    │   ├── defects.md
    │   ├── cases.tsv
    │   └── screenshots/
    │       ├── TC-0142__text-clipped__375x812.png
    │       └── traces/TC-0142.zip
    └── latest -> 2026-08-14-1432
```

**When the project has vertical slices, `modules/` is the primary view and
`by-type/` is the secondary one.** Both are always written — they answer
different questions. "Is checkout releasable?" is a module question; "did
regression run?" is a type question. A reader who owns one feature should not
have to grep nine type files to assemble its status.

Where there are no slices, derive modules from whatever the project does have —
route groups, bounded contexts, top-level features — and say which you used. Flat
`NN-type.md` files at the root remain acceptable only when the product genuinely
has no module structure to speak of.

Dated directories so regression comparison has history; `latest` so links and scripts don't need updating. If the project already has a results convention, follow it instead and say so.

**Commit the run record** — it is the deliverable and the reason the test branch
exists (`branching.md`). Add `test-results/` to `.gitignore` only when the team
explicitly does not want run history in git. Ask once, then follow the answer.

## The rule that matters most

**Write a file for all nine test types on every run, even the ones that didn't run.** A missing file reads as "nothing wrong here"; a file saying `Not run` reads as what it is.

```markdown
# 08 — Exploratory

**Status:** Not run
**Reason:** No time box allocated this run. Last exploratory session: 2026-08-02
(3 findings, all now in regression).
**Risk:** Unscripted defects in the new refund flow would not be caught by any
other type in this run.
```

That file takes thirty seconds to write and is the difference between "we tested" and "we tested these things and not those".

## Per-type file

Same shape for all nine, so they diff cleanly between runs.

```markdown
# 06 — Functional

**Status:** Fail
**Run:** 2026-08-14 14:32 · commit `a91f2c3` · env `staging`
**Command:** `npx playwright test --project=chromium --grep @functional`
**Duration:** 4m 12s

## Totals
| Passed | Failed | Skipped | Flaky | Total |
|---|---|---|---|---|
| 78 | 4 | 2 | 1 | 84 |

## Requirements exercised
Covered 41 · Gaps 6 · Drift 2 · Not implemented 3
Full matrix: `conformance-matrix.md`

## Failures
### TC-0142 — Reset token expires after 30 minutes
- **Requirement:** PRD:BR-07, SLICE-03:S03-01
- **Expected:** 400 `token_expired` at T+30:00
- **Actual:** 200, password changed
- **Root cause:** `auth/token.ts:12` uses 3600s, not 1800s
- **Classification:** Drift — code contradicts PRD §9. Not a test defect.
- **Artefact:** `playwright-report/#TC-0142`

### TC-0155 — ...

## Flaky
- TC-0091 failed once, passed on retry. Cause not yet identified — **not
  counted as a pass.** Tracked as BUG-118.

## Skipped
- TC-0177, TC-0178 — blocked on PM:PM-01 (conditional permission undecided).
```

Rules:

- **Failures name a root cause and a classification** — Drift, Gap, Not implemented, Test defect, Environment. "It failed" is not a result.
- **Flaky is never a pass.** Record it separately with a ticket. A suite reporting flakes as green is lying by omission.
- **Skipped says why**, and links the blocking decision ID.
- **Include the exact command**, so anyone can reproduce without asking.

## Per-module file

One per slice, **including slices that were not tested at all** — same rule as
the nine types, and for the same reason. A missing module file reads as "fine";
a file saying `Not run — no admin credentials` reads as what it is.

```markdown
# SLICE-09 — Order Management

| | |
|---|---|
| Panel | Merchant |
| Routes exercised | `/orders` |
| Status | **Partial** — 13 checks, 5 passed, 8 failed |
| Defects | DEF-02, DEF-03, DEF-12, DEF-14, DEF-15 |
| Spec | `slices/09-order-management.md` |

### Verified against the slice

| Slice acceptance example | Result |
|---|---|
| 1 — Successful outcome | ✅ |
| 2 — Permission boundary | ❌ not run, no second account |
| 3 — Failure or recovery | ✅ |
| 4 — Integrity or concurrency | ⏭ write path |

### Required evidence still owed

The slice's own "Required evidence" list names authorization tests in both
polarities and a tenancy suite. Neither was run — record that here, because a
slice whose definition of done is unmet is not done, whatever the pass count.

### Failures
…

### Not covered
Every order action — the substance of this module.
```

The **"Required evidence still owed"** block is the one people skip. A slice
specifies what proves it complete; comparing your run against that list is how a
module gets an honest verdict rather than a green tick for the 20% that was easy
to automate.

## `00-SUMMARY.md`

Written last, read first. One screen, verdict at the top.

**Lead with the module table when slices exist** — it is what a reader acts on.
Keep the per-type table below it.

```markdown
| Module | Cases | Pass | Fail | Blocking defects |
|---|---:|---:|---:|---|
| SLICE-01 Identity & Access | 29 | 21 | 8 | DEF-10 |
| SLICE-09 Order Management | 13 | 5 | 8 | DEF-15 |
| SLICE-19 Admin — Merchants | 0 | — | — | Not run: no admin credentials |
```

```markdown
# Test run — 2026-08-14 14:32

**Verdict:** ❌ Not releasable — 2 drifts and 1 unimplemented P0 requirement.

**Build:** commit `a91f2c3` · branch `release/1.4` · env `staging`
**Documents:** PRD v2.3, 4 slices, Permissions v1.1, Design System v0.4

| # | Type | Status | Pass | Fail | Skip | Notes |
|---|---|---|---|---|---|---|
| 1 | Unit | ✅ Pass | 412 | 0 | 3 | |
| 2 | Integration | ✅ Pass | 96 | 0 | 0 | |
| 3 | Mock | ⚠️ Partial | 22 | 0 | 8 | Payments failure paths not built |
| 4 | Smoke | ✅ Pass | 8 | 0 | 0 | 41s |
| 5 | Sanity | ✅ Pass | 12 | 0 | 0 | Refund fix verified |
| 6 | Functional | ❌ Fail | 78 | 4 | 2 | 2 drifts |
| 7 | Regression | ❌ Fail | 301 | 1 | 6 | TC-0044 regressed |
| 8 | Exploratory | ⏭ Not run | — | — | — | No time box allocated |
| 9 | Non-functional | ⚠️ Partial | 14 | 2 | 0 | LCP over budget |

## Blocking
1. **PRD:BR-07 drift** — token expiry 60 min in code, 30 min in PRD. Security
   relevant. Fix code or amend the PRD; both need sign-off.
2. **PRD:AC-04 not implemented** — single-use tokens absent. P0.
3. **TC-0044 regression** — bulk export leaks out-of-scope rows (PM §6).

## Non-blocking
- LCP 3.1s vs NFR-01 budget 2.5s on `/dashboard`.
- 11 medium UI issues — see `ui-audit.md`.

## Not covered
- Exploratory: not run.
- Payments dependency-failure paths: no test double available.
- Mobile Safari: not in the project matrix.
```

**"Not covered" is mandatory.** It is the section that stops a green summary being read as complete coverage.

## Supporting files

| File | Contents |
|---|---|
| `conformance-matrix.md` | The full requirement → test → status table from `documents.md`, plus gaps, drift, conflicts, ambiguities |
| `design-conformance.md` | Token / component / layout findings, each labelled implementation drift, stale spec, or stale design file |
| `ui-audit.md` | The DOM sweep grouped by route and viewport, high severity first |
| `defects.md` | One entry per confirmed defect: repro steps, expected vs actual, affected requirement, severity as user impact, evidence paths, suggested owner |
| `screenshots/` | Evidence captured at the moment of failure, named `TC-####__rule__WxH.png`, plus `traces/` |
| `cases.tsv` | `Module (Slice)`, `Case ID`, `Status`, `Last Run`, `Defect Ref`, `Evidence`, `Evidence Path` for every executed case — paste back into the Google Sheet to update it. **`Module (Slice)` is the first column**, so the sheet groups and filters by module without rework |

`cases.tsv` closes the loop with `test-cases-sheet.md`: the sheet is the case register, this is the run record, reconciled by `Case ID`.

## Honesty rules

These are the ones worth enforcing, because the failure mode is a report that reads better than the run went:

- **Never report a suite as passing without running it.** Paste real output.
- **A type that didn't run is `Not run`**, never omitted and never inferred from another type passing.
- **A flake is not a pass.**
- **A drift is not a test failure to be fixed by editing the test.** Report it and let a human decide which side is wrong.
- **State the environment.** A pass on a seeded local database is not a pass on staging.
- **Pre-existing failures are labelled as such**, so they aren't attributed to this change — and are still counted as failures.
- **Every module gets a file, including untested ones.** Reporting only the modules you reached makes a partial run look like a full one — the same failure mode as omitting a test type.
- **A module's verdict is measured against its own "Required evidence" list**, not against the tests you happened to write. Passing every case you wrote while skipping the evidence the slice demands is not a pass.
