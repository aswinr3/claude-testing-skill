# Documents → requirements → cases → traceability

The input is the PRD and everything around it. The output is a set of numbered requirements, precise test cases derived from them, and a matrix proving which are covered.

---

## 1. Read everything, completely

**Do not skim, and do not grep for keywords and call it read.** A requirement in a section you skipped becomes a "not specified" in your report, and you will be confidently wrong. Read each document end to end before extracting anything.

Collect in this precedence order — when two sources disagree, higher wins, but **record the conflict rather than silently resolving it**:

1. **API contracts** — `openapi.yaml`, GraphQL schema, protobuf, JSON Schema. Precise and machine-checkable.
2. **PRD / feature spec / RFC** — the primary statement of intent.
3. **Acceptance criteria on the ticket** — usually the most current.
4. **ADRs and design docs** — constraints rather than features ("must be idempotent", "must handle 10k rps").
5. **User-facing docs / README** — often the only written record of a behaviour.
6. **Existing tests** — a de-facto spec of what someone once believed.

Publish a **document inventory** so the reader knows what your findings are based on, and what they aren't:

| Document | Version / date | Sections read | Notes |
|---|---|---|---|
| `docs/PRD-checkout.md` | v2.3, 2026-06-02 | §1–9 (all) | — |
| `openapi.yaml` | commit `a91f2` | all paths | 3 endpoints absent from PRD |
| `docs/adr/004-idempotency.md` | 2025-11 | all | Constrains AC-11, AC-12 |

If no PRD exists, say so and offer to derive requirements from code plus tickets — but label that output **inferred**, never **specified**.

---

## 2. Extract requirements

Pull every **testable claim** and give it an ID. A claim is testable when you can state a concrete input and an observable expected output.

> PRD: "Users should be able to reset their password easily and securely."

| ID | Requirement | Source |
|---|---|---|
| REQ-01 | POST `/auth/reset` with a registered email returns 202 and sends exactly one email | PRD §4.2 |
| REQ-02 | POST `/auth/reset` with an unregistered email returns 202 and sends no email | PRD §4.2 + security doc §3 |
| REQ-03 | A reset token expires 30 minutes after issue | PRD §4.3 |
| REQ-04 | A reset token is single-use; the second attempt returns 400 | PRD §4.3 |
| REQ-05 | "easily" — no measurable definition | **AMBIGUOUS** |

Rules:

- **One assertion per requirement.** If it needs "and", split it.
- **Include the implied negatives and boundaries** the PRD doesn't spell out: expiry at exactly 30:00, reuse, concurrent requests, missing fields. This is where real bugs live.
- **Non-functional claims count** — performance budgets, rate limits, idempotency, accessibility, retention.
- **Keep an ambiguity log.** Anything too vague to test goes in a separate list with a proposed concrete interpretation. Never quietly invent a threshold and test against it; surface it and let a human decide.

---

## 3. Derive cases — the accuracy engine

Cases invented by intuition miss the same places every time. Apply a technique per requirement and say which one you used.

**Equivalence partitioning** — split the input domain into classes that should behave identically; one case per class. Age `< 18` / `18–64` / `≥ 65` is three cases, not thirty.

**Boundary value analysis** — bugs cluster at edges. For any boundary *n*, test `n-1`, `n`, `n+1`. For a 30-minute expiry: 29:59, 30:00, 30:01. Add empty, single-element, and max-length for collections and strings.

**Decision table** — when several conditions combine, tabulate every reachable combination and prune the impossible ones. Prevents the "we tested each flag but never both at once" gap.

| # | Logged in | Email verified | Has payment method | Expected |
|---|---|---|---|---|
| 1 | Y | Y | Y | Checkout proceeds |
| 2 | Y | Y | N | Redirect to add-card |
| 3 | Y | N | — | Verification banner, checkout blocked |
| 4 | N | — | — | Redirect to login |

**State transition** — for anything with a lifecycle (order, subscription, token). Enumerate states and the legal transitions, then test each legal one *and* a representative illegal one (cancel an already-shipped order).

**Pairwise** — when many independent parameters explode combinatorially (browser × locale × plan × role), cover every *pair* of values rather than every combination. Catches most interaction bugs at a fraction of the runs.

**Error guessing** — after the systematic passes, add cases from experience: unicode and emoji in names, double-submit, browser back after submit, expired session mid-flow, network drop mid-upload, clock skew.

---

## 4. Write the case

A case is not accurate unless every field below is filled. The **oracle** is the part people skip and the reason suites go green while the product is broken.

```
ID:            TC-014
Traces to:     REQ-03 (token expiry)
Technique:     Boundary value analysis
Level:         Integration
Preconditions: User u_1 exists, verified. Reset token issued at 2026-01-01T00:00:00Z.
               Clock frozen (fake timers / clock override).
Data:          token = <issued token>, attempt at T+29:59, T+30:00, T+30:01
Steps:         1. POST /auth/reset/confirm with the token and a new password
Oracle:        T+29:59 → 200, password hash in DB changes
               T+30:00 → 400, body.code === "token_expired", hash unchanged
               T+30:01 → 400, body.code === "token_expired", hash unchanged
```

Oracle rules:

- **Name the exact observable.** "Login works" is not an oracle. "Redirects to `/dashboard` and the header shows the user's email" is.
- **One case, one oracle.** Several assertions are fine if they describe one behaviour.
- **Include the negative side.** What must *not* happen — no email sent, no row written, no second charge.
- **Concrete data, never "some user".** `user_verified@test.local`, amount `0`, `-1`, `999999`.

---

## 5. Traceability matrix

The core artefact. Every requirement maps to code and tests, or it doesn't and that's a finding.

| ID | Requirement | Level | Implemented in | Covered by | Status |
|---|---|---|---|---|---|
| REQ-01 | 202 + one email | integration | `auth/reset.ts:34` | `reset.spec.ts` › "sends reset email" | ✅ Covered |
| REQ-02 | no enumeration | integration | `auth/reset.ts:41` | — | ❌ **Gap** |
| REQ-03 | 30-min expiry | unit | `auth/token.ts:12` | `token.test.ts` › "expires" | ⚠️ **Drift** — code uses 60 min |
| REQ-04 | single-use | integration | *not found* | — | ❌ **Not implemented** |
| REQ-05 | "easily" | — | — | — | 🔶 Ambiguous |

Find tests by searching for the **behaviour**, not the name — grep the assertion, the route, the error string. A test whose title mentions a requirement may not assert it; open it and check.

### The five findings

1. **Gap** — specified, implemented, untested. Write the test.
2. **Drift** — specified one way, implemented another. *The highest-value finding.* Report it before writing anything: the code may be wrong, or the PRD may be stale. Not your call to make silently.
3. **Not implemented** — specified, no code. A delivery gap, not a testing gap. Report it; don't paper over it with a skipped test.
4. **Orphan** — a test or feature asserting behaviour no document specifies. Either undocumented scope creep or a stale test guarding removed behaviour. Flag for a human; don't delete unilaterally.
5. **Conflict** — two documents disagree. Report both, with sources.

---

## 6. Verify — actually exercise it

Reading is not testing.

- Run the existing suites; record real pass/fail, not what the CI badge claims.
- For each **Covered** row, open the test and confirm it genuinely asserts the requirement.
- Spot-check that "Covered" tests can fail: break the behaviour, confirm red, restore.
- For integration/e2e requirements with no test, drive the running platform manually (Playwright, or by hand) and record observed vs specified. An observed drift beats a theoretical one.

---

## 7. Report

Lead with what's broken, not with what you read.

```
## Conformance: Checkout vs PRD v2.3

Documents read: 6/6 (PRD §1-9, openapi.yaml, 3 ADRs, security.md)
Requirements: 47 · Cases derived: 112
Covered 78 · Gaps 19 · Drift 6 · Not implemented 5 · Orphan 4 · Ambiguous 3

### Drift — code contradicts the document (fix one side)
- REQ-03 Token expiry — PRD §4.3 says 30 min; `auth/token.ts:12` uses 3600s (60 min).
  `token.test.ts:22` asserts 60 min, so the suite is green and wrong.
- REQ-19 Refund window — PRD says 14 days; API returns 400 after 7.

### Gaps — specified, built, untested
- REQ-02 User enumeration — unregistered-email path has no test.
  Proposed: integration test asserting 202 + zero mailer calls.

### Not implemented
- REQ-04 Single-use tokens — no invalidation logic in `auth/`.

### Conflicts
- REQ-11 — PRD §6 says idempotency key optional; openapi.yaml marks it required.

### Ambiguous — needs a decision
- REQ-05 "easily" — suggest ≤3 steps from the login screen; untestable as written.
```

Then ask which to act on, or proceed to writing tests for the gaps if that was already the ask.
