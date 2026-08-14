# Design conformance — spec ↔ design file ↔ live app

Three artefacts describe how the product should look, and any two of them can disagree:

```
DESIGN_SYSTEM.md   ──  the written spec (tokens, components, states, a11y)
design.html        ──  the visual artefact (what it actually looks like)
the running app    ──  the implementation
```

**Check all three pairs, not just design-file vs app.** Each disagreement is a different finding with a different owner:

| Disagreement | Finding | Who fixes |
|---|---|---|
| App ≠ design.html, spec agrees with design | **Implementation drift** | Engineering |
| App ≠ spec, design.html agrees with app | **Spec is stale** | Design |
| design.html ≠ spec, app follows spec | **Design file is stale** | Design |
| All three differ | Nobody owns the answer — escalate before writing tests | Product |

Reporting "the button is the wrong blue" is much less useful than "the app uses `#2563EB`, `design.html` uses `#1D4ED8`, and `DESIGN_SYSTEM.md §3` specifies `#1D4ED8` — implementation drift."

---

## Step 0 — check the design file is usable

```bash
wc -c design.html && grep -c '<' design.html
```

If `design.html` is empty or a stub, **say so and stop this mode.** Spec-vs-app checks (below) still work from `DESIGN_SYSTEM.md` alone; design-file comparison does not. Do not silently degrade to a spec-only check and report it as design conformance.

Also determine what the file *is*: a single page, a component gallery, or a multi-page export. That decides whether you compare route-to-route or component-to-component.

---

## Layer 1 — token conformance (deterministic, zero flake)

The highest-value check and the cheapest. Design tokens are exact values, so assert them exactly instead of comparing pixels.

Extract the declared tokens from the design file:

```ts
// e2e/design/tokens.ts
import { chromium } from '@playwright/test'
import { pathToFileURL } from 'node:url'

export type Tokens = Record<string, string>

export async function tokensFrom(url: string): Promise<Tokens> {
  const browser = await chromium.launch()
  const page = await browser.newPage()
  await page.goto(url)
  const tokens = await page.evaluate(() => {
    const style = getComputedStyle(document.documentElement)
    const out: Record<string, string> = {}
    for (const sheet of Array.from(document.styleSheets)) {
      let rules: CSSRuleList
      try { rules = sheet.cssRules } catch { continue }   // cross-origin sheet
      for (const rule of Array.from(rules)) {
        if (!(rule instanceof CSSStyleRule)) continue
        for (const prop of Array.from(rule.style)) {
          if (prop.startsWith('--')) out[prop] = style.getPropertyValue(prop).trim()
        }
      }
    }
    return out
  })
  await browser.close()
  return tokens
}

export const designTokens = () => tokensFrom(pathToFileURL('design.html').href)
```

Then assert the live app resolves the same values. Normalise before comparing — `#1D4ED8`, `#1d4ed8`, and `rgb(29, 78, 216)` are the same colour and a naive string compare produces false failures:

```ts
// e2e/design/tokens.spec.ts
import { test, expect } from '@playwright/test'
import { designTokens, tokensFrom } from './tokens'

const norm = (v: string) => {
  const m = v.match(/^rgba?\(([\d.\s,/]+)\)$/)
  if (!m) return v.trim().toLowerCase()
  const [r, g, b] = m[1].split(/[\s,/]+/).filter(Boolean).map(Number)
  return `#${[r, g, b].map(n => n.toString(16).padStart(2, '0')).join('')}`
}

test('live app resolves the design file tokens', async ({ page, baseURL }) => {
  const expected = await designTokens()
  const actual = await tokensFrom(baseURL!)

  // Tokens the design system declares as contract — from DESIGN_SYSTEM.md §3
  const contract = [
    '--background', '--foreground', '--surface', '--surface-foreground',
    '--primary', '--primary-foreground', '--secondary', '--secondary-foreground',
    '--muted', '--muted-foreground', '--border', '--input', '--focus-ring',
    '--destructive', '--destructive-foreground',
    '--status-success', '--status-warning', '--status-error', '--status-info',
  ]

  const mismatches = contract
    .filter(t => expected[t])                       // only tokens the design file defines
    .map(t => ({ token: t, design: norm(expected[t]), app: norm(actual[t] ?? '(missing)') }))
    .filter(r => r.design !== r.app)

  expect(mismatches, JSON.stringify(mismatches, null, 2)).toEqual([])
})
```

Do the same for `text-*`, `space-*`, `radius-*`, `shadow-*`, and `motion-*`. A missing token in the app is as much a finding as a wrong one — it usually means a component hardcoded a raw value instead of consuming the token, which is exactly what `DESIGN_SYSTEM.md §12` forbids.

**Cross-check against the spec too.** Read the token tables in `DESIGN_SYSTEM.md §3` and compare all three. This is what distinguishes "implementation drift" from "stale design file".

---

## Layer 2 — component conformance

Tokens can all match while a component still consumes the wrong one. Compare the *computed* properties of the same component in both places.

Give the design file and the app a shared handle. The most reliable is a `data-component` attribute in both; failing that, match on accessible role and name.

```ts
const PROPS = [
  'color', 'background-color', 'border-color', 'border-radius', 'border-width',
  'font-family', 'font-size', 'font-weight', 'line-height', 'letter-spacing',
  'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
  'box-shadow', 'text-transform',
] as const

async function computed(page: Page, selector: string) {
  return page.locator(selector).first().evaluate((el, props) => {
    const s = getComputedStyle(el)
    return Object.fromEntries(props.map(p => [p, s.getPropertyValue(p)]))
  }, PROPS as unknown as string[])
}

test('primary button matches the design file', async ({ page, context, baseURL }) => {
  const designPage = await context.newPage()
  await designPage.goto(pathToFileURL('design.html').href)
  await page.goto(baseURL!)

  const want = await computed(designPage, '[data-component="button-primary"]')
  const got  = await computed(page, 'button[data-variant="primary"]')

  const diff = Object.keys(want)
    .filter(k => norm(want[k]) !== norm(got[k]))
    .map(k => ({ property: k, design: want[k], app: got[k] }))

  expect(diff, JSON.stringify(diff, null, 2)).toEqual([])
})
```

Run this across the component baseline in `DESIGN_SYSTEM.md §5`: buttons (all four variants), form fields, tables, cards, dialogs, status labels. **Include the states** — hover, focus, disabled, loading, error — since those are where implementations most often diverge, and `§5` specifies each.

Property-level comparison beats pixel comparison here: it survives text and data differences between the design file and the real app, and its failure message names the exact property instead of "3,412 pixels differ".

---

## Layer 3 — side-by-side visual

For layout, hierarchy, and spacing rhythm that property checks can't capture, render both and compare.

```ts
test('checkout layout matches design', async ({ page, context, baseURL }, testInfo) => {
  const viewport = { width: 1280, height: 800 }

  const design = await context.newPage()
  await design.setViewportSize(viewport)
  await design.goto(pathToFileURL('design.html').href)
  const designShot = testInfo.outputPath('design.png')
  await design.screenshot({ path: designShot, fullPage: true })

  await page.setViewportSize(viewport)
  await page.goto('/checkout')
  await page.evaluate(() => document.fonts.ready)
  const appShot = testInfo.outputPath('app.png')
  await page.screenshot({ path: appShot, fullPage: true })

  await testInfo.attach('design', { path: designShot, contentType: 'image/png' })
  await testInfo.attach('app', { path: appShot, contentType: 'image/png' })
})
```

**Do not pixel-diff these two.** The design file has placeholder copy and fake data; the app has real content of different length. A pixel diff of design-vs-app is ~100% different and tells you nothing — pixel diffing is for app-vs-its-own-baseline (`visual.md`), not for design-vs-app.

Instead send both to the vision model and ask a structural question. Reuse the client setup from `visual.md`, with a schema aimed at design conformance:

```ts
const Conformance = z.object({
  matches: z.boolean().describe('true if the implementation faithfully realises the design'),
  deviations: z.array(z.object({
    element: z.string().describe('Which element or region, in plain language'),
    kind: z.enum([
      'spacing', 'alignment', 'hierarchy', 'typography', 'colour',
      'component-variant', 'missing-element', 'extra-element', 'ordering', 'other',
    ]),
    expected: z.string().describe('What the design shows'),
    actual: z.string().describe('What the app shows'),
    severity: z.enum(['high', 'medium', 'low']),
  })),
})
```

Prompt it to **ignore content differences and compare structure**:

> These two screenshots show the same screen: the first is the approved design, the second is the built implementation. The text content, data, and image assets differ deliberately — ignore those. Compare structure: element presence and ordering, spacing rhythm, alignment, visual hierarchy, component variants, and colour roles. Report each structural deviation with what the design shows and what the app shows. Do not report differences that are only copy, data values, or placeholder imagery.

That last sentence is doing most of the work — without it the model reports every text difference and the output is unusable.

---

## Responsive conformance

`DESIGN_SYSTEM.md §4` declares a breakpoint table. Test **at each declared boundary**, not at arbitrary device sizes, and assert the behaviour the table specifies rather than just taking a screenshot:

```ts
const BREAKPOINTS = [
  { name: 'sm',  width: 640,  nav: 'drawer' },
  { name: 'md',  width: 768,  nav: 'drawer' },
  { name: 'lg',  width: 1024, nav: 'rail'   },
  { name: 'xl',  width: 1280, nav: 'sidebar' },
]

for (const bp of BREAKPOINTS) {
  test(`navigation is a ${bp.nav} at ${bp.name} (${bp.width}px)`, async ({ page }) => {
    await page.setViewportSize({ width: bp.width, height: 900 })
    await page.goto('/')
    await expect(page.getByTestId(`nav-${bp.nav}`)).toBeVisible()
  })
}
```

Test one pixel either side of each boundary too — off-by-one breakpoint conditions (`min-width` vs `max-width` overlap) are a common and invisible bug.

`§4` also requires that adapting layouts **must not lose information, permissions, validation, or required actions**. That's directly assertable: at the narrowest supported width, confirm the primary action, validation messages, and record identity are all still reachable.

---

## What this mode reports

```
## Design conformance: Checkout

Sources: DESIGN_SYSTEM.md v0.4 §3–5 · design.html (2026-08-12) · app @ localhost:3000

Tokens        47 checked · 3 mismatched
Components    12 checked · 2 mismatched · 4 states unimplemented
Layout        4 viewports · 6 structural deviations (2 high)

### Implementation drift — app disagrees with both spec and design
- `--primary` — spec and design.html say #1D4ED8; app resolves #2563EB.
  Affects every primary button and link.
- Button destructive variant uses --primary background (`Button.tsx:41`);
  DESIGN_SYSTEM §5 requires --destructive.

### Stale design file — design.html disagrees with spec, app follows spec
- design.html `--radius-md` is 6px; DESIGN_SYSTEM §3 specifies 8px and the app
  uses 8px. Design file predates the token change.

### Unimplemented states — specified, absent
- Table loading state (DESIGN_SYSTEM §7): app shows a blank region, spec
  requires preserved layout with progress.
- Form field error state: no --status-error treatment found in any field.

### Structural deviations (from visual comparison)
- HIGH  Order summary sits below the form on desktop; design places it right.
- MED   Section spacing is 16px throughout; design alternates 24/16 for rhythm.
```

Every line names which artefact is wrong, so the finding routes to an owner without a follow-up conversation.
