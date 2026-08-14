# UI audit — deterministic defect sweep

Finding UI problems by looking at screenshots is slow and subjective. Most real UI defects are **mechanically detectable from the DOM and computed styles** — no baseline, no pixel diff, no flake, and the failure message names the element.

Run this sweep across every route at every declared breakpoint. It's the highest-yield UI testing you can automate, and it needs one dependency (`@axe-core/playwright`) rather than a new tool.

```bash
npm i -D @axe-core/playwright
```

---

## The sweep

```ts
// e2e/ui/audit.ts
import type { Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

export type Issue = { rule: string; severity: 'high' | 'medium' | 'low'; detail: string; element?: string }

export async function auditPage(page: Page, opts: { minTarget?: number } = {}): Promise<Issue[]> {
  const minTarget = opts.minTarget ?? 24          // WCAG 2.2 AA; raise to the design system's value
  const issues: Issue[] = []

  // ---- 1. Horizontal overflow — the page itself scrolls sideways
  const overflow = await page.evaluate(() => {
    const d = document.documentElement
    return d.scrollWidth > d.clientWidth ? { scroll: d.scrollWidth, client: d.clientWidth } : null
  })
  if (overflow) issues.push({
    rule: 'page-horizontal-overflow', severity: 'high',
    detail: `Page scrolls horizontally: content ${overflow.scroll}px in ${overflow.client}px viewport`,
  })

  // ---- 2. Elements escaping the viewport
  issues.push(...await page.evaluate(() => {
    const vw = document.documentElement.clientWidth
    const out: any[] = []
    for (const el of Array.from(document.body.querySelectorAll<HTMLElement>('*'))) {
      const r = el.getBoundingClientRect()
      if (r.width === 0 || r.height === 0) continue
      if (getComputedStyle(el).position === 'fixed') continue
      if (r.right > vw + 1 || r.left < -1) {
        out.push({
          rule: 'element-outside-viewport', severity: 'high',
          detail: `Extends to ${Math.round(r.right)}px (viewport ${vw}px)`,
          element: el.tagName.toLowerCase() + (el.className ? `.${String(el.className).split(' ')[0]}` : ''),
        })
      }
    }
    return out.slice(0, 20)
  }))

  // ---- 3. Clipped or truncated text without an ellipsis affordance
  issues.push(...await page.evaluate(() => {
    const out: any[] = []
    for (const el of Array.from(document.body.querySelectorAll<HTMLElement>('*'))) {
      if (!el.textContent?.trim()) continue
      if (el.children.length > 0) continue                      // leaf text nodes only
      const s = getComputedStyle(el)
      const clippedX = el.scrollWidth > el.clientWidth + 1
      const clippedY = el.scrollHeight > el.clientHeight + 1
      const handled = s.textOverflow === 'ellipsis' || s.overflow === 'auto' || s.overflow === 'scroll'
      if ((clippedX || clippedY) && !handled) {
        out.push({
          rule: 'text-clipped', severity: 'high',
          detail: `Text is cut off with no ellipsis or scroll: "${el.textContent.trim().slice(0, 60)}"`,
          element: el.tagName.toLowerCase(),
        })
      }
    }
    return out.slice(0, 20)
  }))

  // ---- 4. Overlapping interactive elements
  issues.push(...await page.evaluate(() => {
    const sel = 'a,button,input,select,textarea,[role="button"],[role="link"],[tabindex]:not([tabindex="-1"])'
    const els = Array.from(document.querySelectorAll<HTMLElement>(sel))
      .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 })
    const out: any[] = []
    for (let i = 0; i < els.length; i++) {
      for (let j = i + 1; j < els.length; j++) {
        if (els[i].contains(els[j]) || els[j].contains(els[i])) continue
        const a = els[i].getBoundingClientRect(), b = els[j].getBoundingClientRect()
        const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left)
        const oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top)
        if (ox > 2 && oy > 2) {
          out.push({
            rule: 'interactive-overlap', severity: 'high',
            detail: `${els[i].tagName} overlaps ${els[j].tagName} by ${Math.round(ox)}×${Math.round(oy)}px — one is unclickable`,
          })
        }
      }
    }
    return out.slice(0, 10)
  }))

  // ---- 5. Touch targets below the minimum
  issues.push(...await page.evaluate((min) => {
    const sel = 'a,button,input:not([type="hidden"]),select,[role="button"],[role="link"]'
    return Array.from(document.querySelectorAll<HTMLElement>(sel))
      .map(e => ({ e, r: e.getBoundingClientRect() }))
      .filter(({ r }) => r.width > 0 && r.height > 0 && (r.width < min || r.height < min))
      .slice(0, 20)
      .map(({ e, r }) => ({
        rule: 'touch-target-too-small', severity: 'medium',
        detail: `${Math.round(r.width)}×${Math.round(r.height)}px, minimum ${min}×${min}`,
        element: `${e.tagName.toLowerCase()}: ${(e.textContent || e.getAttribute('aria-label') || '').trim().slice(0, 30)}`,
      }))
  }, minTarget))

  // ---- 6. Broken images and images without alt
  issues.push(...await page.evaluate(() => {
    const out: any[] = []
    for (const img of Array.from(document.images)) {
      if (img.complete && img.naturalWidth === 0) {
        out.push({ rule: 'broken-image', severity: 'high', detail: `Failed to load: ${img.src}` })
      }
      if (!img.hasAttribute('alt')) {
        out.push({ rule: 'image-missing-alt', severity: 'medium', detail: `No alt attribute: ${img.src}` })
      }
    }
    return out
  }))

  // ---- 7. Accessibility (contrast, names, roles, structure)
  const { violations } = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag22aa']).analyze()
  issues.push(...violations.map(v => ({
    rule: `a11y:${v.id}`,
    severity: (v.impact === 'critical' || v.impact === 'serious' ? 'high' : 'medium') as 'high' | 'medium',
    detail: `${v.help} (${v.nodes.length} element${v.nodes.length === 1 ? '' : 's'})`,
    element: v.nodes[0]?.target.join(' '),
  })))

  return issues
}
```

### Console and network — attach before navigating

These must be wired before `goto`, or you miss everything that fires during load.

```ts
export function watchRuntime(page: Page) {
  const issues: Issue[] = []
  page.on('console', m => {
    if (m.type() === 'error') issues.push({ rule: 'console-error', severity: 'high', detail: m.text().slice(0, 200) })
  })
  page.on('pageerror', e => issues.push({ rule: 'uncaught-exception', severity: 'high', detail: e.message }))
  page.on('requestfailed', r => issues.push({
    rule: 'request-failed', severity: 'high',
    detail: `${r.method()} ${r.url()} — ${r.failure()?.errorText}`,
  }))
  page.on('response', r => {
    if (r.status() >= 400) issues.push({ rule: 'http-error', severity: 'high', detail: `${r.status()} ${r.url()}` })
  })
  return issues
}
```

### Driving it

```ts
// e2e/ui/audit.spec.ts
const ROUTES = ['/', '/login', '/dashboard', '/checkout']       // from USER_FLOWS §6
const VIEWPORTS = [
  { name: 'mobile',  width: 375,  height: 812 },
  { name: 'tablet',  width: 768,  height: 1024 },
  { name: 'desktop', width: 1280, height: 800 },
]                                                                // from DESIGN_SYSTEM §4

for (const route of ROUTES) {
  for (const vp of VIEWPORTS) {
    test(`UI audit ${route} @ ${vp.name}`, async ({ page }, testInfo) => {
      const runtime = watchRuntime(page)
      await page.setViewportSize(vp)
      await page.goto(route)
      await page.evaluate(() => document.fonts.ready)

      const issues = [...runtime, ...await auditPage(page)]
      await testInfo.attach('ui-issues', {
        body: JSON.stringify(issues, null, 2), contentType: 'application/json',
      })
      expect(issues.filter(i => i.severity === 'high'), JSON.stringify(issues, null, 2)).toEqual([])
    })
  }
}
```

Fail on `high` only at first; report `medium` and `low` without failing until the backlog is clear, or the suite is red on day one and gets ignored.

---

## Screen states — the biggest block of UI cases

`USER_FLOWS` (Shared Screen-State Matrix) and `DESIGN_SYSTEM §7` specify the same ten states. **Every applicable screen must implement all ten**, and this is the single most under-tested area in most products — teams build the default state and ship.

| State | How to trigger | Assert |
|---|---|---|
| Loading | `page.route` with a delayed `continue` | Layout preserved, progress shown, no "no data" message |
| Empty | Seed zero records | Explains *why* it's empty, offers a permitted next action |
| No results | Apply a filter matching nothing | Filters retained, clear reset control |
| Validation error | Submit invalid input | Valid input preserved, error tied to its field, correction stated |
| Permission denied | Log in as a role lacking the permission | Restricted data absent, safe destination offered, no existence leak |
| Stale / conflict | Modify the record out-of-band, then submit | Shows what changed, requires re-review, doesn't silently overwrite |
| Network failure | `route.abort('failed')` | Safe progress preserved, retry offered |
| Action in progress | Double-click the primary action | Second activation blocked, no duplicate effect |
| Completion uncertain | Abort mid-request after the write | Verifies final state before re-enabling retry |
| Success | Complete the flow | Result reference/status shown, logical next action present |

```ts
test('order list — empty state', async ({ page }) => {
  await page.route('**/api/orders*', r => r.fulfill({ json: { items: [], total: 0 } }))
  await page.goto('/orders')
  await expect(page.getByText(/no orders yet/i)).toBeVisible()
  await expect(page.getByRole('button', { name: /create order/i })).toBeEnabled()
  await expect(page.getByRole('table')).toBeHidden()
})

test('order list — loading preserves layout', async ({ page }) => {
  await page.route('**/api/orders*', async r => { await new Promise(x => setTimeout(x, 3000)); await r.continue() })
  await page.goto('/orders')
  await expect(page.getByRole('status')).toBeVisible()            // progress indicator
  await expect(page.getByText(/no orders yet/i)).toBeHidden()     // must NOT claim empty
})

test('submitting twice creates one order', async ({ page }) => {
  await page.goto('/orders/new')
  const posts: string[] = []
  page.on('request', r => { if (r.method() === 'POST' && r.url().includes('/api/orders')) posts.push(r.url()) })
  const submit = page.getByRole('button', { name: 'Place order' })
  await submit.click()
  await submit.click({ force: true })                              // user double-clicks
  await expect(page.getByText(/order #/i)).toBeVisible()
  expect(posts).toHaveLength(1)
})
```

---

## Checks straight from the design system

**Colour is never the only indicator** (`§3`, `§9`, `USER_FLOWS §4.4`). For every status element, assert a non-colour signal:

```ts
for (const el of await page.getByTestId('status-badge').all()) {
  const text = (await el.textContent())?.trim()
  const icon = await el.locator('svg, [class*="icon"]').count()
  expect(Boolean(text) || icon > 0, 'status conveyed by colour alone').toBe(true)
}
```

**Error copy shape** — `§11` requires *what happened → why → what to do next*. Assert the third part exists, since it's the one that's always missing:

```ts
const msg = await page.getByRole('alert').textContent()
expect(msg).toMatch(/\b(try|check|enter|select|contact|retry|remove|choose)\b/i)  // an actionable instruction
```

**One primary action per region** (`§5`):

```ts
expect(await page.locator('main button[data-variant="primary"]').count()).toBeLessThanOrEqual(1)
```

**Focus visible** (`§9`) — tab through and confirm each stop has a visible indicator:

```ts
for (let i = 0; i < 15; i++) {
  await page.keyboard.press('Tab')
  const ok = await page.evaluate(() => {
    const el = document.activeElement as HTMLElement
    if (!el || el === document.body) return true
    const s = getComputedStyle(el)
    return s.outlineStyle !== 'none' || s.boxShadow !== 'none' || Number(s.outlineWidth.replace('px','')) > 0
  })
  expect(ok, `no visible focus indicator at tab stop ${i + 1}`).toBe(true)
}
```

**Reduced motion** (`§10`) — under `prefers-reduced-motion`, non-essential animation must be removed. Set it in the Playwright project (`use: { reducedMotion: 'reduce' }`) and assert animation durations resolve to `0s`.

---

## What this catches that screenshots don't

Overflow on a viewport nobody opened, a button 18px tall on mobile, a link overlapped by an invisible container, an image 404ing behind a placeholder, contrast failures at 4.3:1, a focus ring removed by a CSS reset, a console error thrown only on the checkout route, an empty state that claims "no data" while still loading, and a double-submit creating two orders.

None of these are visible in a screenshot diff, all of them are real, and every one has a precise failure message naming the element.
