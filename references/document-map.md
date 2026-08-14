# The document set — what to extract from each

This project uses a fixed template set. Each document has a known structure, a known ID scheme, and a known contribution to the test plan. Read them in the order below: each one constrains the next.

## Reading order and yield

| # | Document | Extract | Feeds |
|---|---|---|---|
| 1 | `GLOSSARY.md` | Preferred terms, discouraged synonyms, abbreviations | Naming in test titles and assertions; UI copy checks |
| 2 | `PRD.md` | `BR-`, `NFR-`, `AC-`, `G-`, `M-`, scope table, priorities | Product-wide rules, budgets, MVP acceptance |
| 3 | `PERMISSIONS_MATRIX.md` | Permission codes, role × capability grid, scoping rules | Authorization cases — the single richest source |
| 4 | `WORKFLOWS.md` | Per-workflow actors, preconditions, normal flow, status flow, exceptions | Integration + functional business cases |
| 5 | `USER_FLOWS.md` | Flow diagrams, screen requirements, screen-state matrix, confirmation matrix | E2E functional cases, UI state cases |
| 6 | `DESIGN_SYSTEM.md` | Tokens, component variants, screen states, a11y target, content rules | Design conformance + UI audit |
| 7 | `DATA_MODEL.md` | Constraints, lifecycles, state flows, indexes, retention | Integration + data-integrity cases |
| 8 | `ARCHITECTURE.md` | Invariants, auth model, API conventions, perf/reliability targets | Non-functional + contract cases |
| 9 | `docs/slices/NN-*.md` | Everything — this is the per-feature contract | The bulk of the case set |
| 10 | `docs/adr/ADR-NNN.md` | Decision, scope boundaries, verification | Constraints that override earlier docs |

**Precedence when documents disagree:** slice spec > ADR > PRD > everything else, *except* `PERMISSIONS_MATRIX.md` which is authoritative for authorization and `DESIGN_SYSTEM.md` which is authoritative for visual and interaction rules. Record every conflict as a finding — never resolve one silently.

---

## ID namespacing — do this first

The templates reuse `D-` for two different things: **PRD §12 dependencies** and **WORKFLOWS business decisions**. Never carry a bare ID into the matrix. Prefix every requirement with its source:

```
PRD:BR-03      WF:D-01       PRD:D-01      SLICE-04:S04-02
PM:PM-01       UX:UX-01      DS:DS-01      ADR-007
```

Full scheme:

| Prefix | Document | Section | What it is |
|---|---|---|---|
| `E-` | PRD | §3 | Evidence baseline to be collected |
| `G-` | PRD | §4 | Goal (outcome, not testable directly) |
| `M-` | PRD | §4 | Success metric — testable if a target exists |
| `BR-` | PRD | §9 | Product-wide business rule — **always testable** |
| `NFR-` | PRD | §10 | Non-functional requirement — **always testable** |
| `AC-` | PRD | §11 | MVP acceptance criterion, with required Evidence |
| `A-` / `D-` | PRD | §12 | Assumption / dependency |
| `R-` / `Q-` | PRD | §12 | Risk / open decision |
| `PM-` | Permissions | §8 | Conditional permission awaiting policy approval |
| `D-` | Workflows | §N+1 | Business decision affecting a workflow |
| `UX-` | User flows | §N+5 | Design decision pending |
| `DS-` | Design system | §12 | Design decision pending |
| `AR-` | Architecture | §12 | Architecture risk |
| `DM-` | Data model | §14 | Open data-model decision |
| `S[NN]-` | Slice NN | Open decisions | Slice-scoped decision or risk |
| `ADR-NNN` | ADR | — | Accepted architecture decision |

**Anything with an open `Q-`, `PM-`, `UX-`, `DS-`, `DM-`, or `S[NN]-` ID is undecided.** Do not write a test asserting the "safe default" as though it were the approved behaviour. Record it in the ambiguity log, and if you test the safe default, label the case `Provisional — pending <ID>`.

---

## Per-document extraction

### PRD

- **§5 scope table** — `P0` items are the MVP acceptance boundary. **Cases for P1/P2 items are out of scope** unless asked; writing them inflates the plan and the gap count.
- **§9 Business Rules (`BR-`)** — product-wide invariants. Each gets unit cases for the rule itself, plus at least one integration case proving it holds across a workflow. A `BR-` that only holds in one place was misfiled and is a finding.
- **§10 NFRs** — the five subsections map directly onto non-functional testing: Performance/scale → perf budgets; Reliability/recovery → atomicity, idempotency, RPO/RTO; Security → authz, encryption, audit, retention; Usability/accessibility → WCAG target, keyboard, devices; Observability → logging, alerting. Each `NFR-` needs a **measured number** recorded, not just pass/fail.
- **§11 Acceptance (`AC-`)** — note the **Evidence** column. It tells you the required verification type: "automated test" means you must produce one; "UAT" or "exercise" means manual, and you record it as manual rather than faking automation.

### Permissions matrix — mine this hard

The richest source of cases in the set, and the most commonly under-tested.

For **every cell** in every role × permission grid:

- `✓` → a positive case: role performs the action, succeeds.
- `—` → a negative case: role attempts the action, is **denied server-side**. Denial must not leak whether the record exists.
- `C` → **denied by default.** Test that it is denied, and label the case `Provisional — pending PM:PM-NN`.

Then §6 (scoping) and §7 (separation of duties) each generate their own cases, and §9 names the required set explicitly: **allowed, denied, wrong-scope, deactivated-user, self-approval, stale-state, repeated-request**. Run that list against every protected capability.

Two rules from §3.2 and §6 that must each become a test:

- **A hidden or disabled control is not an authorization control.** For every permission-hidden UI element, call the endpoint directly and assert a server-side denial. This catches the most common real vulnerability in this class of app.
- **Scope applies to lists, searches, totals, exports, notifications, audit results, and detail views** — not just detail views. A count that reveals out-of-scope records is a leak.

### Workflows

Per workflow: actors, preconditions, trigger, normal flow, status flow, exceptions, effects, result.

- **Normal flow** → one happy-path integration/functional case.
- **Status flow** (the `[INITIAL] → [NEXT] → [COMPLETED]` block) → state-transition cases: every legal transition, plus a representative illegal one per state.
- **Validation and exceptions** → one case each.
- **§4.3 integrity rules** are pre-written test cases: operation is atomic; repeating a confirmed request creates no duplicate; concurrent actions don't silently overwrite. Test all three per state-changing workflow.
- **§4.6 common validation failures** — six conditions, each a case, each asserting **no partial change**.
- **Result** → the oracle. Copy it into the case's expected result rather than paraphrasing.

### User flows

- **The flow block is a state machine.** Parse the notation directly: `[Screen]` = state, `→` = transition, `◇ Decision?` = branch (both arms are cases), `✓` = success oracle, `!` = recovery case.
- **Screen requirements** → per-screen assertions: must-see information, must-provide inputs, primary/secondary actions, permission and context indicators.
- **Shared Screen-State Matrix** — 10 states × every applicable screen. This is the biggest single block of UI cases and the one most often skipped. See `ui-audit.md`.
- **Confirmation Dialog Matrix** → for each row, assert the dialog shows the affected record, scope, consequence, and reason field; and that the confirming role is enforced.
- **§4.2 protect high-impact actions** → duplicate-submission and retry-after-slow-response cases.

### Design system

Feeds `design-conformance.md` and `ui-audit.md`:

- **§3 tokens** — the exact expected values for colour, type, spacing, radius, shadow. Assert computed styles against these; do not eyeball.
- **§4 breakpoints** — the viewport matrix for responsive cases. Test *at* each declared boundary.
- **§5 components** — variant rules (one primary action per region; destructive treatment; icon-only rules).
- **§7 screen states** — same 10 states as user flows, from the visual side.
- **§9 accessibility** — 11 bullets, each mechanically checkable.
- **§11 content** — error message shape **what happened → why → what to do next**; glossary terms; locale formats. Assert the shape of error copy, not just its presence.
- **§12 design acceptance criteria** — 9 bullets that are a ready-made UI review checklist.

### Slice specs — the primary source

Each slice is a self-contained test plan. Map its sections straight onto cases:

| Slice section | Produces |
|---|---|
| Outcome | The e2e functional case |
| Scope → Excluded | **Negative scope cases** — assert excluded behaviour is absent, and don't report it as a gap |
| Actors and Permissions | Authorization cases, cross-checked against the permissions matrix |
| Preconditions | Test fixtures and seed data |
| Primary Flow | Step-by-step functional case |
| Implementation Contract → Data | Integration cases: constraints, migrations, retention |
| → API/Events | Contract cases: validation, idempotency, concurrency, compatibility, errors |
| → UI | UI state cases, responsive, accessibility |
| → Background | Async, retry, timeout, reconciliation, flag/rollback cases |
| Rules and Invariants | Unit + integration cases, one per rule |
| Failure and Recovery States | One case per table row — invalid input, unauthorized, conflict/stale, dependency failure |
| Acceptance and Verification | **The four acceptance examples are already Given/When/Then cases.** Lift them verbatim. |
| Required evidence | Tells you which test types this slice owes |

**"Required evidence" maps onto the pipeline directly:** unit tests for rules → Unit; DB/migration tests → Integration; authorization and data-scope tests → Integration + Functional; contract tests → Integration; e2e of primary outcome and critical recovery → Functional; accessibility/performance/security → Non-functional; stakeholder demonstration → manual, recorded as manual.

A slice whose "Required evidence" lists a type you produced no cases for is an incomplete plan — say so.

### ADRs

Read last. An ADR's **Decision** and **Scope and Boundaries** can override what an earlier document implies, and its **Implementation and Verification** section often names the exact check to write. **Revisit Triggers** are worth a monitoring case where they're measurable.

---

## Coverage self-check

Before reporting, confirm you extracted at least:

- Every `BR-` and `NFR-` from the PRD.
- Every cell of every permissions grid, plus the seven case types from §9.
- Every status transition in every workflow, legal and illegal.
- Every `◇` branch and every `!` recovery path in every user flow.
- The screen-state matrix applied to every screen in the wireframe scope.
- Every row of every slice's Failure and Recovery table.
- Every slice's four acceptance examples.

If a document was unreadable or missing, say which and mark the areas it covered as **Unverified** — never as covered.
