# Writing tests — Jest / Vitest

Repo conventions win. These are the defaults for where the repo has no opinion.

## Runner differences

Mostly interchangeable; the traps are in mocking and config.

| | Jest | Vitest |
|---|---|---|
| Globals | on by default | need `globals: true` in config, else `import { describe, it, expect } from 'vitest'` |
| Mock namespace | `jest.fn()`, `jest.mock()`, `jest.spyOn()` | `vi.fn()`, `vi.mock()`, `vi.spyOn()` |
| Fake timers | `jest.useFakeTimers()` | `vi.useFakeTimers()` |
| Module mock hoisting | hoisted above imports | hoisted above imports — **factory cannot reference outer variables** |
| Reset between tests | `restoreMocks`/`resetMocks` in config | `restoreMocks: true` in config |
| ESM mocking | awkward | native |

Vitest's hoisting trap — this fails with "Cannot access before initialization":

```ts
const mockSend = vi.fn()                    // ❌ referenced inside a hoisted factory
vi.mock('./mailer', () => ({ send: mockSend }))
```

Use `vi.hoisted`:

```ts
const { mockSend } = vi.hoisted(() => ({ mockSend: vi.fn() }))   // ✅
vi.mock('./mailer', () => ({ send: mockSend }))
```

## Structure

```ts
describe('resetPassword', () => {           // the unit under test
  it('returns 202 when the email is unregistered', async () => {
    // Arrange
    const mailer = createMailerSpy()
    const svc = makeService({ mailer, users: [] })

    // Act
    const res = await svc.resetPassword('nobody@example.com')

    // Assert
    expect(res.status).toBe(202)
    expect(mailer.send).not.toHaveBeenCalled()
  })
})
```

- `describe` names the unit; nested `describe` names a condition ("when the token is expired").
- Test names read as a sentence: **behaviour + condition**. `it('throws when the amount is negative')`, not `it('works')` or `it('test 2')`.
- One behaviour per test. Multiple `expect`s are fine if they describe one behaviour; two unrelated behaviours mean two tests.
- No `if`/`for`/`try` in a test body. Branching in a test means it's testing two things, or silently testing nothing. Use `it.each` for table cases.

## Assertions

- Assert on observable output: return values, thrown errors, rendered DOM, emitted events, persisted rows, HTTP responses.
- Prefer specific matchers — `toEqual({...})` over `toBeTruthy()`, `toHaveBeenCalledWith(x)` over `toHaveBeenCalled()`. A vague matcher passes for the wrong reason.
- Errors: assert the type *and* something identifying. `await expect(fn()).rejects.toThrow(ValidationError)` — never a bare `rejects.toThrow()` that any crash satisfies.
- Snapshots are a supplement, never the primary assertion for logic. They pass on garbage as long as the garbage is stable, and get regenerated without being read. Inline snapshots for small, reviewable output only.
- Testing Library: query by role/label/text, not `data-testid`, unless there's no accessible handle. Use `userEvent` over `fireEvent`.

## Mocking

The rule: **mock at boundaries you don't own; use the real thing for code you do.**

- Mock: network, clock, filesystem, randomness, payment providers, email, third-party SDKs.
- Don't mock: your own pure functions, value objects, the module under test's collaborators when they're cheap and deterministic. Over-mocking produces tests that pass while the system is broken.
- Prefer a **fake** (a small working in-memory implementation — a Map-backed repository) over a pile of `mockReturnValue` calls. Fakes stay honest under refactor; mocks encode the current call sequence.
- Never assert on a mock's internals as the *only* assertion. `expect(mock).toHaveBeenCalled()` proves a call happened, not that the feature works.
- Reset between tests — `restoreMocks: true` in config, or `afterEach(() => vi.restoreAllMocks())`. Leaked mock state is a top cause of order-dependent failures.

## Determinism

Every one of these is a future flake:

| Source | Fix |
|---|---|
| `new Date()` / `Date.now()` | `vi.useFakeTimers(); vi.setSystemTime(new Date('2025-01-01T00:00:00Z'))` |
| `Math.random()` | inject a seeded RNG, or stub it |
| `setTimeout` waits | fake timers + `vi.advanceTimersByTime(n)` — never real `sleep` |
| Real network | MSW or a stubbed client; block real requests in setup so a leak fails loudly |
| Shared module state | reset in `beforeEach`; avoid module-level mutable singletons |
| Test order coupling | each test creates its own data; run with `--shuffle` occasionally to catch it |
| Timezone / locale | pin `TZ=UTC` in the test script; format with explicit locales |
| Async races | always `await`; use `findBy*` / `waitFor`, never a fixed delay |

## Test data

Use builders with sane defaults and per-test overrides:

```ts
const makeUser = (over: Partial<User> = {}): User => ({
  id: 'u_1', email: 'a@example.com', verified: true, ...over,
})

it('rejects unverified users', () => {
  expect(canPost(makeUser({ verified: false }))).toBe(false)
})
```

Each test states only what matters to it. Big shared fixture blobs hide the relevant field and couple every test to one shape.

## What to cover

For each function, walk this list rather than only the happy path:

- Happy path, one representative case
- Boundaries — 0, 1, n-1, n, n+1, empty collection, single element, max length
- Invalid input — null, undefined, wrong type, malformed string, negative, NaN
- Error paths — each `throw` and each rejected branch has a test
- Side effects — did it write what it claimed, once, with the right payload
- Idempotency / repeat calls, where the contract promises it
- Concurrency, where two callers can race

Coverage percentage is a smoke detector, not a goal. 100% line coverage with weak assertions catches nothing; the useful question is "if I break this line, does a test go red?"

## Anti-patterns

- Testing private methods or asserting internal call order — breaks on refactor, catches nothing.
- `expect(true).toBe(true)`, or a test with no assertion at all.
- Sharing mutable state across tests via module scope or `beforeAll`.
- A `catch` that swallows the failure so the test passes regardless.
- Committing `.only` (fails the rest of the suite silently in CI) or `.skip` without a linked reason.
- Bumping timeouts to fix flakiness — that hides the race instead of removing it.
