# Playwright — driving the platform

Mechanics for smoke, sanity, functional, regression, and non-functional work against the running app.

## Setup detection

Read `playwright.config.*` before writing anything. It tells you `baseURL`, the `webServer` command, the project/browser matrix, `testDir`, and timeouts. If there's no config, the platform isn't wired for e2e yet — say so rather than inventing paths.

```ts
// playwright.config.ts — the fields that matter to you
export default defineConfig({
  testDir: './e2e',
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',        // trace viewer for failures
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: { command: 'npm run dev', url: 'http://localhost:3000', reuseExistingServer: true },
  projects: [{ name: 'chromium', use: devices['Desktop Chrome'] }],
})
```

## Locators — the priority order

Query the way a user perceives the page. This makes tests survive refactors and doubles as an accessibility check.

1. `getByRole('button', { name: 'Submit' })` — role + accessible name. Default choice.
2. `getByLabel('Email')` — form fields.
3. `getByPlaceholder`, `getByText`, `getByTitle` — when no label exists.
4. `getByTestId('checkout-total')` — only when there's no accessible handle. Adding one is usually the better fix.
5. CSS/XPath — last resort. `page.locator('.btn-primary > div:nth-child(2)')` breaks on the next style change.

Chain and filter rather than reaching for indexes:

```ts
page.getByRole('listitem').filter({ hasText: 'Pro plan' }).getByRole('button', { name: 'Cancel' })
```

## Waiting — never sleep

Playwright auto-waits: every action retries until the element is attached, visible, stable, and enabled. Web-first assertions retry too.

```ts
await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()  // ✅ retries
expect(await page.getByRole('heading').isVisible()).toBe(true)                // ❌ one shot, flaky
await page.waitForTimeout(2000)                                               // ❌ never
```

`await expect(...)` on a locator is the retrying form. `expect(await ...)` evaluates once — the single most common source of Playwright flake.

For non-DOM conditions use `expect.poll` or `waitForResponse`, not a timeout:

```ts
await expect.poll(() => api.orderStatus(id)).toBe('shipped')
await page.waitForResponse(r => r.url().includes('/api/checkout') && r.ok())
```

## Structure — fixtures over page objects

Playwright's fixture system composes better than class-based POMs. Put the page object *in* a fixture so tests never construct it.

```ts
// e2e/fixtures.ts
export const test = base.extend<{ checkout: CheckoutPage; asUser: Page }>({
  checkout: async ({ page }, use) => { await use(new CheckoutPage(page)) },
  asUser: async ({ browser }, use) => {
    const ctx = await browser.newContext({ storageState: 'e2e/.auth/user.json' })
    await use(await ctx.newPage())
    await ctx.close()
  },
})
```

Keep page objects thin: locators and multi-step actions. **No assertions inside a page object** — the test owns the oracle, or failures become unreadable.

## Auth — log in once

Logging in through the UI in every test is the biggest avoidable cost in an e2e suite. Do it once in a setup project and reuse the storage state.

```ts
// e2e/auth.setup.ts
setup('authenticate', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Email').fill(process.env.TEST_USER!)
  await page.getByLabel('Password').fill(process.env.TEST_PASS!)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
  await page.context().storageState({ path: 'e2e/.auth/user.json' })
})
```

Wire it as a dependency: `projects: [{ name: 'setup', testMatch: /auth\.setup\.ts/ }, { name: 'chromium', dependencies: ['setup'], use: { storageState: 'e2e/.auth/user.json' } }]`. Keep one storage state per role.

## Network — mock, assert, and inject faults

`page.route` is how the Mock phase reaches the platform level.

```ts
// Stub a dependency
await page.route('**/api/pricing', r => r.fulfill({ json: { total: 4200 } }))

// Fault injection — the failure paths the PRD specifies
await page.route('**/api/payments', r => r.fulfill({ status: 503, json: { error: 'unavailable' } }))
await page.route('**/api/slow', async r => { await new Promise(res => setTimeout(res, 5000)); await r.continue() })
await page.route('**/api/orders', r => r.abort('failed'))   // network drop

// Block real third parties so a leak fails loudly instead of flaking
await page.route(/analytics|doubleclick|sentry/, r => r.abort())
```

To assert on outgoing requests, capture rather than mock:

```ts
const req = page.waitForRequest(r => r.url().includes('/api/track') && r.method() === 'POST')
await page.getByRole('button', { name: 'Buy' }).click()
expect((await req).postDataJSON()).toMatchObject({ event: 'purchase', amount: 4200 })
```

## API testing without a browser

Use `request` for integration-level checks and for seeding state fast.

```ts
test('rejects unregistered email without leaking existence', async ({ request }) => {
  const res = await request.post('/auth/reset', { data: { email: 'nobody@test.local' } })
  expect(res.status()).toBe(202)
  expect(await res.json()).toEqual({ ok: true })   // identical to the registered-email response
})
```

Seeding through the API rather than the UI turns a 30-second setup into 300ms and removes a whole class of flake.

## Isolation and parallelism

Each test gets a fresh browser context — cookies and storage don't leak. **Your backend data does.** Tests running in parallel against one database will collide unless each creates its own data:

```ts
const email = `user-${test.info().workerIndex}-${test.info().testId}@test.local`
```

Reach for `test.describe.serial` only when tests genuinely must share state; it turns one failure into a cascade of skips.

## Debugging failures

Configure once and use the artefacts instead of re-running blind:

- `trace: 'on-first-retry'` → `npx playwright show-trace trace.zip` gives DOM snapshots, network, console, and a timeline per step.
- `--ui` for the interactive runner; `--debug` to step through.
- `screenshot`/`video` on failure for a quick visual read.
- A trailing `await page.pause()` opens Inspector at that point.

## Accessibility and performance

```ts
import AxeBuilder from '@axe-core/playwright'

test('dashboard has no serious a11y violations', async ({ page }) => {
  await page.goto('/dashboard')
  const { violations } = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze()
  expect(violations.filter(v => ['serious', 'critical'].includes(v.impact!))).toEqual([])
})

test('dashboard loads within budget', async ({ page }) => {
  await page.goto('/dashboard')
  const lcp = await page.evaluate(() => new Promise<number>(res => {
    new PerformanceObserver(l => res(l.getEntries().at(-1)!.startTime)).observe({ type: 'largest-contentful-paint', buffered: true })
  }))
  expect(lcp).toBeLessThan(2500)   // budget from PRD §9
})
```

Record the measured number in the report, not just pass/fail — the trend is the useful signal.

## Anti-patterns

- `waitForTimeout` anywhere. It's a race you haven't diagnosed.
- `expect(await locator.isVisible())` instead of `await expect(locator).toBeVisible()`.
- Logging in through the UI in every test.
- CSS-selector chains tied to layout (`div > div:nth-child(3)`).
- Shared mutable backend fixtures across parallel workers.
- E2E tests for logic a unit test could cover — every extra e2e test is a recurring tax in runtime and flake.
- Conditional branching on page state (`if (await x.isVisible())`) — the test then passes without testing anything.
- `test.only` committed to the repo.
