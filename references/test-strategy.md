# Strategy — what to test, how much, and when to stop

Exhaustive testing is impossible. Even one form with five fields has more input combinations than you can run. So testing is an allocation problem, and the question is never "did we test everything" but **"did we spend the effort where failure costs most."**

---

## Risk-based prioritisation

Score every requirement before writing cases:

```
Risk = Likelihood of failure × Impact of failure
```

**Likelihood** rises with: new code, recently changed code, complex branching, a component with a bug history, unclear requirements, many integration points, work done under deadline pressure.

**Impact** rises with: money movement, data loss, security or privacy exposure, legal/compliance obligation, blocking the primary user journey, silent corruption (worse than a loud crash — nobody notices until it's everywhere).

| | Impact low | Impact high |
|---|---|---|
| **Likelihood high** | Test after the P0s | **Test first, automate, run every commit** |
| **Likelihood low** | Exploratory only | Test thoroughly, run nightly |

This maps onto the priority column you already have in `PRD §5` and the sheet:

- **P0** — high impact, regardless of likelihood. Gates MVP acceptance.
- **P1** — high likelihood, moderate impact.
- **P2** — everything else; exploratory coverage may be enough.

Two rules that follow:

- **A requirement nobody can state the impact of is a requirement nobody has thought about.** Push back before writing cases for it.
- **Silent-failure paths outrank loud ones.** A crash gets reported in minutes; a permissions leak or a wrong total gets discovered in an audit. Weight the quiet ones up.

## Coverage is a smoke detector, not a goal

| Metric | What it tells you | What it hides |
|---|---|---|
| Line coverage | Which lines executed | Nothing was asserted about them |
| Branch coverage | Which decisions were taken both ways | Still nothing about assertions |
| **Mutation score** | Whether tests actually **detect** injected defects | — this is the honest one |

100% line coverage with weak assertions catches nothing. The useful question is *"if I break this line, does a test go red?"* — and mutation testing answers it mechanically (see `advanced-techniques.md`).

Where branch coverage sits well below line coverage, error paths are unexercised — and error paths are where the bugs are.

## Shape of the suite

```
        /\          e2e — few. Critical journeys only.
       /  \         Slow, flaky-prone, expensive to maintain.
      /----\
     /      \       integration — more. The seams: DB, API, auth.
    /        \      Where wiring bugs actually live.
   /----------\
  /            \    unit — many. Fast, precise, run on save.
 /______________\
```

**The inverted version — the "ice cream cone" — is the most common failure mode**: a thick e2e layer over almost no unit tests. It looks like thorough testing and behaves terribly. Every bug takes a 6-minute suite run to reproduce, failures point at a screen rather than a function, and the flake rate makes the whole suite untrusted within a quarter.

The economic argument, per bug caught:

| Level | Runtime | Failure tells you | Maintenance |
|---|---|---|---|
| Unit | ms | The exact function and input | Low — breaks only when behaviour changes |
| Integration | seconds | The seam that's wrong | Medium |
| E2E | minutes | "Checkout is broken" | High — breaks on any UI change |

**Rule:** push every test to the cheapest level that can still catch the failure you care about. If a unit test can catch it, an e2e test for it is waste that you pay for on every CI run forever.

The exception worth respecting: for UI-heavy products, integration-level component tests (rendering real components with real DOM, mocking only network) often carry more weight than pure unit tests. Coverage should follow how the product actually breaks.

## How many cases — budget the count before you write

The SKILL's *Coverage volume* rule is non-negotiable: for a web application of real size (multiple modules, several roles, workflow-heavy), the register floors at **200 cases and ranges up to ~500**. This section is the method for hitting that honestly rather than padding.

**1. Enumerate the surface first.** Before writing any case, list every module × screen × role × primary action, plus every input field and every state a record can be in. This inventory *is* the case budget — you are not inventing cases, you are reading them off the product.

**2. Multiply each feature by the derivation techniques.** A single "edit amount" field is not one case. It is: happy edit, min−1/min/max/max+1 boundaries, empty, non-numeric, negative, huge, wrong-locale decimal, plus "no permission to edit" per role. One field routinely yields 8–12 rows. Apply this expansion to *every* input, not a chosen few.

**3. Per-module rough yields** (calibrate to what the module actually does):

| Module weight | Example | Expected cases |
|---|---|---|
| Heavy (money, complex CRUD, multi-view) | Finance, Projects/Tasks | 30–60 each |
| Medium (CRUD + collaboration) | Chat, Dashboards, Members | 15–30 each |
| Light (mostly read, few actions) | Inbox, single settings tab | 8–15 each |
| Cross-cutting | Auth, authorization matrix, non-functional | 30–80 combined |

Sum the per-module budgets. **If the total lands under the floor for the product's size, you have missed cases — go back to step 1 and find them.** Undershooting is a signal, not a stopping point.

**4. The authorization matrix multiplies fast and is where suites are thinnest.** Every protected action × every role (here: Owner/Admin/Member/Limited/Guest) × {UI-gate hidden?, server endpoint denied?} is a case. A dozen protected actions across five roles is already ~120 authorization rows on its own — assert both the hidden control *and* the server-side denial (a hidden button is not an access control).

**5. Write every row, then execute what the run allows.** Rows are cheap; execution is expensive. Generate the *entire* enumerated register up front with `Status = Not run`, then flip rows to Pass/Fail as you execute, leaving the remainder as honest `Not run — <reason>` accounting. Never let a token or time budget shrink the *register*; it only shrinks how many rows you execute this pass. A case never written is coverage you falsely claim to have considered.

## Test data strategy

The biggest practical cause of flake in a parallel Playwright suite is shared data.

**Every test creates the data it needs and does not depend on data another test made.**

```ts
// Unique per worker AND per test — safe under --workers=8
const run = `${test.info().workerIndex}-${test.info().testId.slice(0, 6)}`
const email = `user-${run}@test.local`
```

Ordered by preference:

1. **Seed via API, assert via UI.** Creating a user through the signup UI to test checkout is 30 seconds of flake risk that tests nothing you meant to test. Use `request` to seed, then drive the UI for the part under test.
2. **Builders with defaults and overrides**, so each test states only what matters to it:
   ```ts
   const makeOrder = (over: Partial<Order> = {}): Order =>
     ({ id: 'o_1', total: 4200, status: 'draft', items: [makeItem()], ...over })
   ```
3. **Fresh state per test**, not shared setup that mutates. `beforeAll` that writes data is a cross-test dependency waiting to bite.
4. **Clean up, but never rely on cleanup for correctness.** A test that only passes because the previous test's cleanup ran is order-dependent.

Reference data (currencies, roles, config) can be seeded once. **Transactional data never can.**

## Exit criteria — when to stop

"Are we done testing" is unanswerable. "Have we met the exit criteria" is answerable. Define them before the run:

- Every `P0` requirement has at least one passing case, or a recorded reason why not.
- Zero open `high` severity defects on P0 paths.
- Smoke and sanity green on the release build in the release environment.
- Regression suite green, or every failure classified and accepted with a named owner.
- Every `NFR-` has a **measured number** recorded, not a pass/fail tick.
- Every `AC-` has the evidence type its Evidence column demands.
- Open decisions (`Q-`, `PM-`, `UX-`, `DS-`) affecting P0 behaviour are resolved — not defaulted.
- Coverage gaps and untested areas are **written down** in `00-SUMMARY.md` § Not covered.

That last one is what makes the rest honest. Shipping with known gaps is a legitimate business decision; shipping while *unaware* of them is not, and the difference is whether someone wrote them down.

## Suite health metrics

Track these per run in the result files. A suite that isn't measured degrades silently.

| Metric | Definition | Healthy | Action when bad |
|---|---|---|---|
| **Flake rate** | tests passing on retry ÷ total | < 1% | Above 5%, the team stops trusting red — fix before adding tests |
| **Escape rate** | defects found in prod ÷ (prod + test) | trending down | Rising means tests are testing the wrong things, not too few things |
| **Suite runtime** | wall clock for the CI gate | < 10 min | Beyond ~15 min people stop running it locally, and quality drops |
| **Mean time to detect** | commit → failing test | minutes | Slow detection means the gate is too late in the pipeline |
| **Mutation score** | killed mutants ÷ total | 60–80% on core logic | Low score with high line coverage = assertions are weak |

**Escape rate is the only metric that measures whether testing worked.** Everything else measures activity. A suite with 3,000 tests and a rising escape rate is testing the wrong things.

## Flaky test policy

Decide this once, in writing, or it gets decided ad hoc by whoever is annoyed:

1. A flake is **never** counted as a pass. Record it separately with a ticket.
2. Fix within a defined window (a week is typical). Diagnose the cause — see `review.md` § flakiness.
3. If it can't be fixed in the window, **quarantine explicitly**: move to a non-gating suite, tag it, link the ticket. Never silently `.skip`.
4. Quarantine has an expiry. A test quarantined for a quarter is a test nobody is going to fix — delete it and record the lost coverage as a gap.

The failure mode to avoid is the slow slide: one flake tolerated, then five, then the team reflexively re-runs red builds. At that point the suite has negative value — it costs CI time and catches nothing anyone acts on.
