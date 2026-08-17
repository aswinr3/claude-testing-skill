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
      if (!el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) continue
      const s = getComputedStyle(el)
      // Overflow must ACTUALLY be hidden on that axis. `overflow: visible`
      // content spills but stays readable — flagging it fails correct pages.
      const hidX = s.overflowX === 'hidden' || s.overflowX === 'clip'
      const hidY = s.overflowY === 'hidden' || s.overflowY === 'clip'
      const clippedX = hidX && el.scrollWidth > el.clientWidth + 1
      const clippedY = hidY && el.scrollHeight > el.clientHeight + 1
      if ((clippedX || clippedY) && s.textOverflow !== 'ellipsis') {
        out.push({
          rule: 'text-clipped', severity: 'high',
          detail: `Text is cut off with no ellipsis or scroll: "${el.textContent.trim().slice(0, 60)}"`,
          element: el.tagName.toLowerCase(),
        })
      }
    }
    return out.slice(0, 20)
  }))

  // ---- 4. Interactive elements that genuinely cannot be clicked
  // Rect intersection is NOT occlusion: a hidden drawer overlaps the content
  // beneath it on every SPA. Ask the browser who receives the click instead.
  // Also O(n) rather than O(n^2), and it catches the opacity:0 overlay that a
  // geometry-only check misses entirely.
  issues.push(...await page.evaluate(() => {
    const sel = 'a,button,input,select,textarea,[role="button"],[role="link"],[tabindex]:not([tabindex="-1"])'
    const out: any[] = []
    for (const el of Array.from(document.querySelectorAll<HTMLElement>(sel))) {
      if (!el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) continue
      const r = el.getBoundingClientRect()
      if (r.width <= 0 || r.height <= 0) continue
      const x = r.left + r.width / 2, y = r.top + r.height / 2
      if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) continue
      const top = document.elementFromPoint(x, y)
      if (top && top !== el && !el.contains(top) && !top.contains(el)) {
        out.push({
          rule: 'interactive-occluded', severity: 'high',
          detail: `${el.tagName} is covered at its centre by ${top.tagName} — the click lands on the wrong element`,
          element: el.tagName.toLowerCase(),
        })
      }
    }
    return out.slice(0, 20)
  }))

  // ---- 5. Touch targets below the minimum
  // WCAG 2.2 Level AA, SC 2.5.8 "Target Size (Minimum)" — the floor is 24x24 CSS px.
  // SC 2.5.8 has exceptions, and skipping them is most of this rule's noise:
  //  - inline targets inside a sentence are exempt
  //  - the target is the region that ACCEPTS the pointer, so a control wrapped
  //    by (or associated with) a label is as big as control union label
  issues.push(...await page.evaluate((min) => {
    const sel = 'a,button,input:not([type="hidden"]),select,[role="button"],[role="link"]'
    const labelOf = (e: HTMLElement) =>
      (e.id && document.querySelector<HTMLElement>(`label[for="${CSS.escape(e.id)}"]`)) || e.closest('label')
    const targetRect = (e: HTMLElement) => {
      const r = e.getBoundingClientRect(), l = labelOf(e)
      if (!l) return r
      const q = l.getBoundingClientRect()
      return { width: Math.max(r.right, q.right) - Math.min(r.left, q.left),
               height: Math.max(r.bottom, q.bottom) - Math.min(r.top, q.top) }
    }
    const out: any[] = []
    for (const e of Array.from(document.querySelectorAll<HTMLElement>(sel))) {
      if (!e.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) continue
      const box = e.getBoundingClientRect()
      if (box.width <= 0 || box.height <= 0) continue
      const r = targetRect(e)
      if (r.width >= min && r.height >= min) continue
      const st = getComputedStyle(e), p = e.parentElement
      const inlineInSentence = st.display === 'inline' && p &&
        p.textContent!.replace(e.textContent ?? '', '').trim().length > 0
      if (inlineInSentence) continue                       // SC 2.5.8 inline exception
      out.push({
        rule: 'touch-target-too-small', severity: 'medium',
        detail: `${Math.round(r.width)}x${Math.round(r.height)}px effective target, minimum ${min}x${min}`,
        element: `${e.tagName.toLowerCase()}: ${(e.textContent || e.getAttribute('aria-label') || '').trim().slice(0, 30)}`,
      })
    }
    return out.slice(0, 20)
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

  // ---- 7. Controls with no accessible name — nobody can address them by voice,
  //         by screen reader, or by a role-based locator. Full name computation:
  //         aria-label, aria-labelledby, associated <label>, value (for buttons),
  //         title, own text, then a nested img[alt].
  issues.push(...await page.evaluate(() => {
    const ISEL = 'a,button,input:not([type=hidden]),select,textarea,[role="button"],[role="link"]'
    const FORM = ['INPUT', 'SELECT', 'TEXTAREA']
    const nameOf = (e: HTMLElement): string => {
      const aria = e.getAttribute('aria-label'); if (aria?.trim()) return aria.trim()
      const by = e.getAttribute('aria-labelledby')
      if (by) {
        const t = by.split(/\s+/).map(id => document.getElementById(id)?.textContent || '').join(' ').trim()
        if (t) return t
      }
      const l = (e.id && document.querySelector(`label[for="${CSS.escape(e.id)}"]`)) || e.closest('label')
      if (l?.textContent?.trim()) return l.textContent!.trim()
      const inp = e as HTMLInputElement
      if (e.tagName === 'INPUT' && ['submit', 'button', 'reset'].includes(inp.type)) return (inp.value || '').trim()
      // A form control's own textContent is its OPTION text, not a name. Counting
      // it makes every unlabelled <select> look named — a false negative found on a
      // real site. Its `placeholder` IS part of the name computation (HTML-AAM).
      if (FORM.includes(e.tagName)) {
        const ph = e.getAttribute('placeholder'); if (ph?.trim()) return ph.trim()
      } else {
        if ((e.textContent || '').trim()) return e.textContent!.trim()
        const alt = e.querySelector('img[alt]')?.getAttribute('alt')?.trim(); if (alt) return alt
      }
      if (e.getAttribute('title')?.trim()) return e.getAttribute('title')!.trim()
      return ''
    }
    const out: any[] = []
    for (const e of Array.from(document.querySelectorAll<HTMLElement>(ISEL))) {
      if (!e.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) continue
      const r = e.getBoundingClientRect()
      if (r.width <= 0 || r.height <= 0) continue
      if (!nameOf(e)) out.push({
        rule: 'control-missing-accessible-name', severity: 'high',
        element: `${e.tagName.toLowerCase()}${e.className ? '.' + e.className : ''}`,
        detail: 'Interactive control has no accessible name',
      })
    }
    return out.slice(0, 20)
  }))

  // ---- 7b. placeholder carrying the label alone. The control HAS a name, so this
  //          is not rule 7 — it is the distinct defect that the name disappears the
  //          moment the user types into the field.
  issues.push(...await page.evaluate(() => {
    const out: any[] = []
    for (const e of Array.from(document.querySelectorAll<HTMLElement>('input[placeholder],textarea[placeholder]'))) {
      if (!e.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) continue
      const l = (e.id && document.querySelector(`label[for="${CSS.escape(e.id)}"]`)) || e.closest('label')
      if (l?.textContent?.trim() || e.getAttribute('aria-label')?.trim() || e.getAttribute('aria-labelledby')) continue
      out.push({
        rule: 'placeholder-as-only-label', severity: 'medium',
        element: `${e.tagName.toLowerCase()}[placeholder="${e.getAttribute('placeholder')}"]`,
        detail: 'The only label is the placeholder; it vanishes once the field has a value',
      })
    }
    return out.slice(0, 20)
  }))

  // ---- 8. Duplicate ids — silently break label[for], aria-labelledby, and anchors.
  issues.push(...await page.evaluate(() => {
    const seen = new Set<string>(), out: any[] = []
    for (const e of Array.from(document.querySelectorAll<HTMLElement>('[id]'))) {
      if (!e.id) continue
      if (seen.has(e.id)) out.push({
        rule: 'duplicate-id', severity: 'medium', element: `#${e.id}`,
        detail: `id "${e.id}" appears more than once`,
      })
      else seen.add(e.id)
    }
    return out.slice(0, 20)
  }))

  // ---- 9. The page itself pans sideways. Name the widest offender, not the body.
  issues.push(...await page.evaluate(() => {
    const de = document.documentElement
    if (de.scrollWidth <= de.clientWidth + 1) return []
    let worst: Element | null = null, max = de.clientWidth
    for (const e of Array.from(document.body.querySelectorAll('*'))) {
      const r = e.getBoundingClientRect()
      if (r.width > 0 && r.right > max + 1) { max = r.right; worst = e }
    }
    return [{
      rule: 'page-overflows-horizontally', severity: 'high',
      element: worst ? `${worst.tagName.toLowerCase()}.${(worst as HTMLElement).className}` : 'body',
      detail: `Document scrollWidth ${de.scrollWidth} exceeds viewport ${de.clientWidth}`,
    }]
  }))

  // ---- 10. Contrast (WCAG 1.4.3). SKIPPED, never guessed, when the backdrop is
  //          not knowable from computed style — a background image, a gradient,
  //          or a translucent stack. Guessing here is where contrast sweeps earn
  //          their reputation for noise.
  issues.push(...await page.evaluate(() => {
    const lum = (c: string) => {
      const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null
      const [r, g, b, a] = m[1].split(',').map(Number)
      if (a !== undefined && a < 1) return null
      const f = (v: number) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4 }
      return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
    }
    const backdrop = (el: Element): number | null => {
      for (let n: Element | null = el; n; n = n.parentElement) {
        const s = getComputedStyle(n)
        if (s.backgroundImage && s.backgroundImage !== 'none') return null   // unknowable
        const L = lum(s.backgroundColor)
        if (L !== null) return L
      }
      return null
    }
    const out: any[] = []
    for (const el of Array.from(document.body.querySelectorAll<HTMLElement>('*'))) {
      if (!(el.textContent || '').trim() || el.children.length > 0) continue
      if (!el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) continue
      const s = getComputedStyle(el)
      const fg = lum(s.color); if (fg === null) continue
      const bg = backdrop(el); if (bg === null) continue
      const size = parseFloat(s.fontSize), bold = parseInt(s.fontWeight, 10) >= 700
      const large = size >= 24 || (size >= 18.66 && bold)
      const ratio = (Math.max(fg, bg) + 0.05) / (Math.min(fg, bg) + 0.05)
      if (ratio < (large ? 3 : 4.5)) out.push({
        rule: 'contrast-below-aa', severity: 'medium',
        element: `${el.tagName.toLowerCase()}: ${(el.textContent || '').trim().slice(0, 30)}`,
        detail: `${ratio.toFixed(2)}:1, minimum ${large ? 3 : 4.5}:1`,
      })
    }
    return out.slice(0, 20)
  }))

  // ---- 11. Accessibility (roles, structure, and everything above not covered)
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

**Only functionally-verified conditions carry `high`.** A rule earns the right to fail a build
when it proves the defect rather than infers it: occlusion confirmed by hit test, an image that
returned 0x0, a console error, an axe critical/serious violation. Geometric and stylistic
heuristics report at `medium` and never gate — that is what stops a correct page going red.

Fail on `high` only at first; report `medium` and `low` without failing until the backlog is
clear, or the suite is red on day one and gets ignored.

**This sweep has its own eval — run it before trusting a run's findings.**
`evals/ui-audit/harness.mjs` scores the sweep against a correct page (any finding is a false
positive) and a page with seeded defects (any miss is a false negative). Current: precision 1.00,
recall 1.00. The version of these checks shipped before 2026-08-14 scored 0.50 / 0.67 — it
invented overlaps between hidden elements and missed the real ones. A detector with no tests is
exactly what this skill forbids everywhere else.

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
