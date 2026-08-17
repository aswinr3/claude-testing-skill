# The Testing Skill — complete reference

Everything this skill is, everything it does, what has been measured about it, and what it
still cannot do. One file, kept honest.

- **Name:** `testing`
- **Size:** `SKILL.md` (152 lines) + 20 reference files (3,846 lines) + 5 scripts + 8 eval specs
- **Runners:** Playwright (platform), Jest/Vitest (unit + integration); Cypress detected and adapted
- **Gates:** 4, enforced in CI on every push

---

## 1. What it is

A **document-driven QA skill**. The PRD and its supporting documents are the source of truth;
every test case traces to a numbered requirement; and the deliverable is a **conformance
verdict plus result files** — not a pile of green checkmarks.

A conventional suite answers "did my assertions pass?" This skill answers **"does the built
product match what was specified, and where exactly does it not?"** Those are different
questions, and the second is the one a release decision needs.

| Claim | How it holds it up |
|---|---|
| Every case traces to a requirement | Namespaced IDs, a requirement index anchored to line/cell, a conformance matrix, a coverage self-check |
| A passing test actually tested something | Falsifiability is mandatory — the *page* is mutated, not the assertion |
| The findings are correct | The sweep is scored on fixtures: **precision 1.00, recall 1.00** |
| The report is trustworthy | Result files are written for types and slices that **did not run**, saying so explicitly |
| The skill does not contradict itself | 9 machine checks including a contradiction registry |

---

## 2. Architecture

```
SKILL.md                  routing table · dependency gate · Step 0 · pipeline · non-negotiables
├── references/           20 files, loaded on demand — never all at once
├── scripts/
│   ├── preflight.sh      run this first; exits non-zero when the run would break
│   ├── validate.py       9 structural + consistency checks over the skill itself
│   ├── run_evals.py      static / live / baseline eval runner
│   ├── eval_patterns.py  the pattern grammar both modes share
│   └── check.sh          all four gates in one command
├── evals/
│   ├── skill/            7 capability specs, 109 cases
│   └── ui-audit/         precision/recall harness + fixtures
└── .github/workflows/    CI: validate · static evals ≥95% · preflight · sweep 1.00/1.00
```

`SKILL.md` is deliberately thin: a routing table naming the one file to load for the job at
hand. Reference files carry the depth.

---

## 3. The reference library

### Orientation and scope

| File | What it gives you |
|---|---|
| `preflight.md` | The seven run-breaking failures and the executable script that gates each |
| `branching.md` | `<parent>-test-<slug>`; why `main/tests` is impossible in git; detached-HEAD and dirty-tree guards |
| `targets.md` | Four target modes (A source+run, B code only, C hosted URL only, D both) and **what you may claim in each**; production safety |
| `document-intelligence.md` | **Deep document comprehension** — five passes from inventory to coverage self-check |
| `document-map.md` | Which document holds what, and its ID scheme, for the standard template set |
| `documents.md` | Generic fallback: read → extract → derive → matrix → verify → report, with the five finding classes |

### Planning

| File | What it gives you |
|---|---|
| `test-types.md` | Entry/exit criteria for each of the nine types |
| `test-strategy.md` | Risk-based prioritisation, suite shape, test data, exit criteria, flaky-test policy |
| `advanced-techniques.md` | Property-based, mutation, contract, load/soak, authz depth, the honest limits of automated a11y |

### Execution

| File | What it gives you |
|---|---|
| `playwright.md` | Locator priority, never-sleep waiting, fixtures over page objects, auth, network faults, API without a browser |
| `unit-integration.md` | Jest/Vitest differences, structure, mocking, determinism |
| `tooling.md` | Playwright MCP, Context7, per-mode tool→task map |
| `ci.md` | The gate ladder per trigger, the 10-minute budget, artifacts as bug reports, flake in CI, handing the suite to the team |

### UI and design

| File | What it gives you |
|---|---|
| `ui-audit.md` | **The deterministic UI defect sweep** — 10 rule families, scored 1.00/1.00 |
| `design-conformance.md` | Token / component / side-by-side layers; drift vs stale design file vs unimplemented |
| `visual.md` | Pixel diff plus vision triage; what it decides and what it doesn't |

### Output and review

| File | What it gives you |
|---|---|
| `test-cases-sheet.md` | The 22-column contract (`A`–`V`), paste-clean rows, the Gemini prompt, the results round-trip |
| `evidence.md` | Capture, **sequence evidence**, naming, storage layout, Drive upload, defect format, honesty rules |
| `results.md` | Required result-file set and format; per-type and per-module templates |
| `review.md` | Auditing an existing suite; coverage that lies; triaging a flake |

---

## 4. Core features

### 4.1 The dependency gate

**Batched once, at the very start:** target URLs and environments · **one account per role**
(a merchant login does not test the admin panel) · **disposable-data confirmation** · spec
location · source access. Then it **waits**.

| Class | Behaviour |
|---|---|
| **Critical** — per-role credentials, disposable-data status, spec, unreachable target | Ask and **wait**. Blocks the run. |
| **Non-critical** — a11y target, perf budget, ambiguous copy | Assume a defensible floor, **state it**, proceed. |

*Testing the reachable third of a platform and filing the rest as "Not run" is a half-baked
run, not a partial one — the difference is whether the user chose the scope.*

### 4.2 Step 0 — Orient

0. **Run the preflight** — mechanical, not remembered
1. **Branch first** — `<parent>-test-<slug>`, before writing any file
2. **Establish target mode** and gather every dependency
3. **Read the documents deeply, then reconcile them** — the five passes below
4. **Detect the runners**
5. **Get the platform running**, or pin the deployment build/commit
6. **Check the design file** — a stub means say so, not silently degrade
7. **Establish the baseline**

### 4.3 Document intelligence — the five passes

1. **Inventory and pin** — enumerate from the filesystem *and* git history (including deleted
   documents); record the revision each was read at
2. **Structural read** — every document end to end, extracted per class: PRD, **vertical slice
   specs** (routes, acceptance examples, *Required evidence*, dependencies, out-of-scope),
   permissions matrix, workflows, user flows, design system, data model, ADRs, glossary
3. **Requirement index** — machine-readable, namespaced (`PRD:BR-03`, `SLICE-04:S04-02`,
   `PERM:P-17`), **anchored to a line or matrix cell**, with `derived` and `provisional` marked
4. **Reconcile** — contradiction / duplication / orphan / silence across documents. Precedence
   is never invented; a contradiction is a finding for a human
5. **Coverage self-check** — six checkboxes that must be answered before "not specified" is a
   credible claim

A skipped section becomes a missed requirement, and a missed requirement becomes a confident
"not specified" that is simply wrong. That is the most expensive error in the process.

### 4.4 The nine-type pipeline

| # | Type | Answers | Tool |
|---|---|---|---|
| 1 | Unit | Does each module obey its spec in isolation? | Vitest/Jest |
| 2 | Integration | Do the seams hold? | Vitest/Jest, Playwright `request` |
| 3 | Mock | Do we behave correctly when a dependency fails or stalls? | `vi.mock`, `page.route` |
| 4 | Smoke | Is this build alive enough to be worth testing? | Playwright |
| 5 | Sanity | Did this specific change actually work? | either |
| 6 | Functional | Does every documented requirement work end to end? | Playwright |
| 7 | Regression | Did anything that used to work break? | full suite |
| 8 | Exploratory | What's broken that no document predicted? | manual + ad-hoc |
| 9 | Non-functional | Perf, a11y, security, compatibility, resilience | Playwright, axe, Lighthouse |

CI order: smoke → sanity → unit → integration → functional → regression → non-functional,
failing fast at each gate. Mock is a *technique* applied inside the others.

### 4.5 Test-case accuracy contract

Namespaced requirement ID · explicit preconditions · concrete data · a single observable
oracle · **a negative oracle** · a named derivation technique (boundary value, equivalence
partition, decision table, state transition, pairwise, error guessing).

Anything gated on an open decision (`Q-`, `PM-`, `UX-`, `DS-`, `DM-`) is **not an approved
requirement**: label it `Provisional — pending <ID>` and never let it gate acceptance.

### 4.6 The deterministic UI sweep — 10 rule families

Runs in-page, needs no baseline image, produces zero flake.

| Rule | Detection | Severity |
|---|---|---|
| `text-clipped` | `scrollWidth > clientWidth` **gated on `overflow` actually being `hidden`/`clip`**, no ellipsis | high |
| `interactive-occluded` | `document.elementFromPoint` at the centre returns a different, non-ancestor element | high |
| `touch-target-too-small` | < 24px, with **SC 2.5.8 exceptions** — inline-in-sentence, and effective target = control ∪ label | medium |
| `broken-image` | `complete && naturalWidth === 0` | high |
| `image-missing-alt` | no `alt` attribute | medium |
| `control-missing-accessible-name` | full name computation; **form controls never use `textContent`** | high |
| `placeholder-as-only-label` | named, but the name vanishes once the field has a value | medium |
| `duplicate-id` | silently breaks `label[for]`, `aria-labelledby`, anchors | medium |
| `page-overflows-horizontally` | names the widest offender, not `body` | high |
| `contrast-below-aa` | WCAG 1.4.3; **skipped, never guessed**, when the backdrop is an image, gradient, or translucent stack | medium |

Plus console/network capture attached *before* navigating, screen-state coverage, and checks
generated from the design system's tokens.

**Only functionally-verified conditions carry `high`.**

### 4.7 Evidence

**Single-shot bugs** get one highlighted screenshot. **Sequence bugs** — the ones that need
four actions to reach — get a per-step trail, because a screenshot at the end shows the
wreckage, not the route:

```
screenshots/
├── single/
│   └── TC-0142__text-clipped__375x812.png
└── sequences/
    └── MOD-03-checkout/TC-0301/
        ├── TC-0301__s01__open-the-signup-form__1280x720.png
        ├── … s02 … s03 … s04 … s05 …
        ├── TC-0301__FAIL__app-root-emptied__1280x720.png
        ├── repro.md          ← generated from the run, not from memory
        ├── video.webm
        └── trace.zip
```

Grouped by module, one self-contained folder per case. The repro carries URL and elapsed ms
per step. **Bisect** to report the *minimal* failing sequence, and state whether the bug is
order-dependent or accumulation-dependent. `RUN_DIR` has no default and throws if unset.

### 4.8 The run record

`test-results/<date>-<time>/` — `00-SUMMARY.md` (module table first), `modules/SLICE-NN-*.md`
**including untested slices**, `by-type/01..09` **including types that did not run**,
`conformance-matrix.md`, `design-conformance.md`, `ui-audit.md`, `defects.md`, `cases.tsv`,
`screenshots/`.

A missing file reads as "nothing wrong"; a file saying `Not run — no time box allocated` reads
as what it is. **Organise by module, not test type** — teams own features. A module's verdict
is measured against **its own Required-evidence list**, not the tests you happened to write.

---

## 5. Non-negotiables

1. **A test that cannot fail is worse than none.** Make it fail on purpose first.
2. **Never weaken a test to make it pass.** No loosened matcher, no `.skip`, no bumped timeout.
3. **Drift is reported, not resolved.**
4. **A hidden control is not an authorization control.** Assert server-side denial.
5. **Determinism is mandatory.**
6. **Never report a suite as passing without running it.** A flake is not a pass.
7. **Do not start a run with a critical dependency missing.**
8. **A green check proves nothing until the fixture is proven.** When a whole class of checks
   passes at once, suspect the fixture — and prove it by mutating the **page**, not the assertion.
9. **Assert both polarities on any "restricted to a known list" rule.**
10. **Keep the runner's artefact directory out of the run record.**
11. **A harness that exits 0 having run zero tests is a failed run**, not a pass.

---

## 6. Self-verification

```bash
bash scripts/check.sh          # all four gates
```

| Gate | What it proves |
|---|---|
| `validate.py` | 9 checks: frontmatter, line budget, dangling refs, orphans, column-count claims, first-column agreement, one run-directory template, round-trip contiguity, **contradiction registry** |
| `run_evals.py --static` | 109 cases across 7 capability specs. **Deferred cases are excluded from the rate, never counted as passes** |
| `preflight.sh` | Parses and gates correctly |
| `evals/ui-audit/harness.mjs` | Precision and recall on 13 seeded defects and 15 traps |

The eval runner supports `--static`, `--live` (through `claude -p`), and `--baseline` (no
skill, to prove a case has teeth). It runs on **Python 3.9**.

---

## 7. Measured accuracy

| Measure | Result |
|---|---|
| Static evals | **109/109 = 100%**, 0 deferred |
| Eval discrimination — own content vs 50 unrelated QA skills | **98.1% vs 13.9%** (84.2-point gap) |
| UI sweep, fixtures | **precision 1.00, recall 1.00** on 13 defects / 15 traps |
| UI sweep, six unseen real apps | **0 false build failures** (the prior version produced 4) |
| Live site (`saucedemo.com`, 5 pages) | **15 findings, 15 verified against the DOM = precision 1.00** |
| — vs axe-core on the same pages | axe found **1**; the sweep found **6 distinct defects**, 5 of which axe structurally cannot report |
| Self-contradictions | **0**, machine-checked |

Two rule bugs were found *by* the live run and fixed: an unlabelled `<select>` was missed
(name computation wrongly accepted option text), and placeholder-only inputs were falsely
reported (per HTML-AAM a placeholder *is* a name). Both became permanent fixtures.

---

## 8. Known limitations

| Area | Status |
|---|---|
| Multi-role authorization | Never measured — no campaign has run with two real role accounts |
| Design conformance | Never measured against a real `design.html` |
| Visual regression | Never measured |
| Live eval mode | Implemented, not yet run at scale — CI still gates on static |
| Breadth | One skill. A 50-skill library covers domains this does not: payments, email, mobile, database, analytics, chaos |
| Sample size | Three campaigns (TodoMVC, saucedemo, a seeded crash fixture), none with auth roles or a backend |

---

## 9. Design principles

**Documents over intuition.** Cases derived from requirements find the *specified* bugs — the
ones anyone can be held to.

**Falsifiability over green.** Any suite can be green. The only evidence a suite works is
watching it go red for the right reason.

**Report, don't resolve.** When product and document disagree, the job ends at stating the
contradiction precisely.

**Absence must be visible.** Untested is a finding. A gap that isn't written down reads
exactly like a pass.

**Measure the detector.** A defect detector is itself software with its own false positives
and negatives. Precision and recall are tracked on fixtures *and* on unseen real pages, and
**every false positive a real run produces becomes a new fixture shape**.

**Make the mechanics executable.** Prose guidance did not prevent a single one of the seven
run-breaking failures. A script that exits non-zero did.
