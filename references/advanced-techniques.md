# Advanced techniques

Techniques beyond example-based testing. Each one covers a class of defect the nine standard types miss. Reach for them where the payoff is real — noted per technique.

---

## Property-based testing

Example-based tests check the cases you thought of. **Property-based tests generate hundreds of inputs and check that an invariant holds for all of them** — then, on failure, *shrink* the input to the smallest case that still fails.

**This maps directly onto your slice specs.** Every `Rules and Invariants` bullet and every `BR-` in the PRD is a property. That section is literally a list of things that must be true for all inputs — which is what this technique tests.

```bash
npm i -D fast-check
```

```ts
import fc from 'fast-check'
import { describe, it } from 'vitest'
import { applyDiscount, splitPayment } from '../src/pricing'

// SLICE-04:S04-03 "A discount never produces a negative total"
it('total is never negative', () => {
  fc.assert(
    fc.property(
      fc.nat({ max: 1_000_000 }),          // order total in paise
      fc.nat({ max: 100 }),                 // discount percent
      (total, percent) => applyDiscount(total, percent) >= 0,
    ),
    { numRuns: 1000 },
  )
})

// PRD:BR-11 "Split payments always sum to the order total"
it('splits reconcile exactly', () => {
  fc.assert(
    fc.property(
      fc.nat({ max: 1_000_000 }),
      fc.integer({ min: 1, max: 8 }),
      (total, ways) => {
        const parts = splitPayment(total, ways)
        return parts.length === ways && parts.reduce((a, b) => a + b, 0) === total
      },
    ),
  )
})
```

`fc.assert` throws on failure and prints the **shrunk counterexample** — the minimal input that breaks it — plus a seed to reproduce deterministically. That last part matters: a generative test that fails once and can't be reproduced is worse than no test, and the seed removes that problem.

Useful arbitraries: `fc.nat()`, `fc.integer({min,max})`, `fc.string()`, `fc.array()`, `fc.record({...})`, `fc.constantFrom(...)`, `fc.date()`. Filter with `.filter()` or `fc.pre()`. Async work uses `fc.asyncProperty`.

**Where it pays:** money arithmetic, rounding and splitting, date/timezone logic, parsers and serialisers, state machines, sorting and pagination, anything with a round-trip (`parse(format(x)) === x`).

**Where it doesn't:** UI flows, anything whose expected output you can only state by example. Don't force it.

**The trap:** a property that just reimplements the function under test proves nothing. `applyDiscount(t, p) === t - t*p/100` is not a property, it's a copy of the implementation. Good properties are *weaker* than the implementation — never negative, always sums, monotonic, idempotent, round-trips, invariant under reordering.

---

## Mutation testing — does the suite actually detect bugs?

The skill's core rule is *"a test that cannot fail is worse than none."* Mutation testing enforces it mechanically: it injects small defects (`>` → `>=`, `+` → `-`, removes a call, flips a boolean) and checks whether any test goes red. A surviving mutant is a bug your suite would ship.

```bash
npm init stryker@latest
npx stryker run
```

```js
// stryker.config.mjs
export default {
  testRunner: 'vitest',                       // or 'jest'
  mutate: ['src/**/*.ts', '!src/**/*.spec.ts'],
  thresholds: { high: 80, low: 60, break: 60 },
}
```

`break` fails the build below that score (exit code 1); `break: null` disables that. All three keys must be set together.

**Mutation score is the honest coverage metric.** Line coverage says code ran; mutation score says a defect in it would be caught. A module at 100% line coverage and 30% mutation score has tests that execute everything and assert almost nothing — and that combination is common.

**How to actually use it:** it's slow (it re-runs the suite once per mutant), so don't put it on every commit.

- Point `mutate` at **core business logic only** — pricing, permissions, state transitions, the `BR-` rules. Not UI glue, not config.
- Run it nightly or per-PR on changed files, not on every push.
- Treat surviving mutants as a **to-do list of missing assertions**, not a score to game.
- 60–80% on core logic is a realistic target. Chasing 100% produces tests written to kill mutants rather than to describe behaviour.

---

## Contract testing against your OpenAPI spec

Your template set makes API contracts authoritative (`document-map.md` puts them above the PRD). So validate real responses against the spec rather than against hand-written expectations — this catches drift automatically, across every endpoint, without writing a case per field.

```ts
import Ajv from 'ajv'
import addFormats from 'ajv-formats'
import { test, expect } from '@playwright/test'
import spec from '../openapi.json'

const ajv = addFormats(new Ajv({ strict: false }))

function validator(path: string, method: string, status: string) {
  const schema = spec.paths[path]?.[method]?.responses?.[status]?.content?.['application/json']?.schema
  if (!schema) throw new Error(`No schema for ${method.toUpperCase()} ${path} ${status}`)
  return ajv.compile({ ...schema, components: spec.components })
}

test('GET /orders response matches the contract', async ({ request }) => {
  const res = await request.get('/api/orders')
  expect(res.status()).toBe(200)

  const validate = validator('/orders', 'get', '200')
  const ok = validate(await res.json())
  expect(ok, JSON.stringify(validate.errors, null, 2)).toBe(true)
})
```

**Two findings this produces that nothing else does:**

- **Undocumented fields** — the API returns data the spec doesn't declare. Either the spec is stale or the endpoint is leaking. On an endpoint governed by `PERMISSIONS_MATRIX §6`, an undeclared field is a potential data-scope leak, so treat it as a security finding until proven otherwise.
- **Missing required fields** — the spec promises something the API doesn't send, and every consumer written from the spec is broken.

Drive it from the spec itself: enumerate `spec.paths` and generate one test per endpoint × documented status. Any documented response you never exercised is a coverage gap the spec can tell you about for free.

---

## Load, stress, and soak

`NFR-01` in your PRD template is explicitly *"[Operation] must complete within [target/percentile] at [volume/load]"* — a single-user Playwright timing check cannot verify that. Load is a different tool.

```bash
brew install k6     # or the platform equivalent
k6 run load/checkout.js
```

```js
import http from 'k6/http'
import { check } from 'k6'

export const options = {
  stages: [
    { duration: '2m', target: 100 },   // ramp
    { duration: '5m', target: 100 },   // hold at expected load
    { duration: '2m', target: 0 },     // ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],  // ← the number from NFR-01
    http_req_failed:   ['rate<0.01'],
  },
}

export default function () {
  const res = http.get(`${__ENV.BASE_URL}/api/orders`)
  check(res, { 'status 200': r => r.status === 200 })
}
```

Thresholds fail the run, so this works as a CI gate rather than a chart someone eyeballs.

Three distinct shapes, often conflated:

| Test | Question | Shape |
|---|---|---|
| **Load** | Does it meet the budget at expected volume? | Hold at target |
| **Stress** | Where does it break, and does it fail gracefully? | Ramp past target until failure |
| **Soak** | Does it degrade over hours? (leaks, connection exhaustion) | Hold at target for hours |

Soak catches what the other two structurally cannot: memory leaks, unclosed DB connections, disk filling, caches that never evict. Those defects don't exist at minute five.

**Always record the measured number in the result file**, not just pass/fail. The trend across runs is the signal; a single green tick tells you nothing about whether you're at 480ms or 80ms against a 500ms budget.

---

## Authorization testing depth

`PERMISSIONS_MATRIX.md` is the richest document you have, and its §9 already names the required cases. Two classes deserve calling out because they're where real breaches come from, and neither is caught by testing through the UI:

**Broken object-level authorization (IDOR).** Log in as user A, capture a record ID belonging to user B, request it directly as A.

```ts
test('cannot read another tenant\'s order by ID', async ({ request }) => {
  const theirs = await seedOrderFor('tenant-b')
  const res = await request.get(`/api/orders/${theirs.id}`, { headers: authAs('tenant-a') })
  expect([403, 404]).toContain(res.status())
  expect(await res.text()).not.toContain(theirs.reference)   // no leak in the error body
})
```

Prefer **404 over 403** for records outside scope: a 403 confirms the record exists, which is itself the information `PERMISSIONS_MATRIX §6.4` says not to reveal.

**Broken function-level authorization.** Every endpoint that a privileged role can call, called by an unprivileged one. Enumerate from the permission codes — every `—` and every `C` in the matrix is a test.

Also worth covering, straight from §7 and §9: self-approval, deactivated user retains no access, stale-state requests, repeated requests, and **mass-assignment** (POST a `role` or `tenant_id` field the client shouldn't control and confirm it's ignored).

---

## Accessibility — what automation cannot do

Be honest in the report about this. **Automated tools catch a minority of WCAG issues** — the exact figure varies by study and ruleset, but no credible source claims a majority. axe finds what is mechanically decidable, and the rest is structurally undecidable by a machine.

What axe **does** catch: colour contrast, missing form labels, missing alt attributes, invalid ARIA, duplicate IDs, heading-order violations, missing landmarks.

What it **cannot** catch, because each requires judgement:

- Whether `alt="chart"` is a *useful* description of that chart.
- Whether focus order is logical, as opposed to merely present.
- Whether an error message is understandable to a screen reader user in context.
- Whether a custom widget's keyboard model matches what users expect.
- Whether an animation triggers vestibular symptoms.
- Whether the reading order matches the visual order.

So report it accurately: **"0 axe violations"** is a true statement about axe, not a claim of accessibility. State it that way and list what needs manual verification:

1. **Keyboard-only pass** of every flow in `USER_FLOWS` — no mouse, complete the task.
2. **Screen reader spot-check** on critical flows (VoiceOver on macOS, NVDA on Windows).
3. **200% zoom / 320px reflow** — content must not be lost or require horizontal scrolling.
4. **Reduced-motion** honoured (`DESIGN_SYSTEM §10`).
5. Confirm every `DESIGN_SYSTEM §9` bullet that isn't mechanically checkable.

---

## Choosing among these

| Situation | Reach for |
|---|---|
| A `Rules and Invariants` bullet, or arithmetic/parsing/round-trip logic | Property-based |
| High line coverage but bugs still escape | Mutation testing |
| An OpenAPI/GraphQL contract exists | Schema validation per endpoint |
| An `NFR-` states a target at a volume | Load / stress / soak |
| A permissions matrix with roles and scopes | IDOR + function-level authz |
| A WCAG target in the PRD | axe **plus** the manual list |
| Expected output is hard to state, but relationships between outputs are known | Metamorphic (e.g. searching for "abc" must return a superset of "abcd") |

Don't adopt all of these at once. Take them in the order your escape rate points at — the defects actually reaching production tell you which technique you're missing.
