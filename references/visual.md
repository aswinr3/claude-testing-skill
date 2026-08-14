# Visual regression with AI diff triage

Screenshot diffing catches layout breakage nothing else does. It also generates enormous false-positive noise — an antialiasing shift, a one-pixel font-metric change, or an intentional redesign all fail exactly like a real bug, and a suite that cries wolf gets ignored within a sprint.

The fix is two layers: **pixel diffing decides that something changed; a vision model decides whether it matters.** The model only runs on failures, so cost tracks the failure rate rather than the suite size.

---

## Layer 1 — the pixel diff

Use `toHaveScreenshot`, not `toMatchSnapshot`. `toHaveScreenshot` is the purpose-built visual comparison: it re-takes the screenshot until two consecutive captures are identical (killing animation flake) and manages baselines per platform and project automatically.

```ts
import { test, expect } from '@playwright/test'

test.describe('visual — home', () => {
  for (const [label, viewport] of Object.entries({
    desktop: { width: 1280, height: 800 },
    mobile: { width: 375, height: 812 },
  })) {
    test(`home page matches baseline (${label})`, async ({ page }) => {
      await page.setViewportSize(viewport)
      await page.goto('/')                                  // baseURL comes from the config
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()

      await expect(page).toHaveScreenshot(`home-${label}.png`, {
        fullPage: true,
        maxDiffPixelRatio: 0.02,           // ≤2% of pixels may differ
        animations: 'disabled',
        mask: [page.getByTestId('live-timestamp')],
      })
    })
  }
})
```

**`threshold` and `maxDiffPixelRatio` are not the same knob** — conflating them is the most common misconfiguration:

| Option | Means | Typical |
|---|---|---|
| `threshold` | per-pixel colour distance (YIQ, 0–1) before a pixel counts as different | `0.2` (default) |
| `maxDiffPixels` | absolute count of differing pixels tolerated | scale to viewport |
| `maxDiffPixelRatio` | *proportion* of differing pixels tolerated | `0.01`–`0.02` |

Setting `threshold: 0.02` does not mean "allow 2% of the image to change" — it tightens per-pixel colour sensitivity and will fire on antialiasing.

**Stabilise before you diff**, or the model spends its budget explaining your own nondeterminism:

- `animations: 'disabled'` — freezes CSS animations and transitions.
- `mask: [...]` — paints over timestamps, avatars, ad slots, anything genuinely dynamic.
- Freeze the clock: `await page.clock.setFixedTime(new Date('2026-01-01T12:00:00Z'))`.
- Seed data deterministically; never screenshot a page backed by random or live content.
- Pin fonts — wait for `document.fonts.ready` before capturing.

Baselines belong in git. Regenerate deliberately with `--update-snapshots`, and **review the regenerated images in the diff** — blind regeneration is how a real regression becomes the new baseline.

---

## Layer 2 — vision triage on failure

On failure Playwright writes `-expected`, `-actual`, and `-diff` PNGs and attaches them to the test result. **Read them from `testInfo.attachments`** — don't guess file paths, and never share a fixed path like `screenshots/current.png` across tests, because parallel workers will overwrite each other's captures.

```ts
// e2e/visual-triage.ts
import { test as base, expect, type TestInfo } from '@playwright/test'
import Anthropic from '@anthropic-ai/sdk'
import { zodOutputFormat } from '@anthropic-ai/sdk/helpers/zod'
import { z } from 'zod'
import fs from 'node:fs/promises'

const Verdict = z.object({
  intentional: z.boolean()
    .describe('true if this looks like a deliberate redesign, false if it looks broken'),
  severity: z.enum(['high', 'medium', 'low']),
  summary: z.string().describe('One sentence a reviewer can read in the report'),
  defects: z.array(z.object({
    region: z.string().describe('Where on the page, in plain language'),
    kind: z.enum(['layout-shift', 'overlap', 'clipping', 'spacing', 'typography', 'color', 'missing-element', 'other']),
    detail: z.string(),
  })),
})

const client = new Anthropic()   // reads ANTHROPIC_API_KEY (or an `ant auth login` profile)

async function asImageBlock(path: string) {
  return {
    type: 'image' as const,
    source: {
      type: 'base64' as const,
      media_type: 'image/png' as const,
      data: (await fs.readFile(path)).toString('base64'),
    },
  }
}

export async function triageVisualFailure(testInfo: TestInfo) {
  if (testInfo.status !== 'failed' || !process.env.ANTHROPIC_API_KEY) return

  const find = (suffix: string) =>
    testInfo.attachments.find(a => a.name.endsWith(suffix) && a.path)?.path
  const expected = find('-expected.png')
  const actual = find('-actual.png')
  if (!expected || !actual) return          // not a screenshot failure

  const response = await client.messages.parse({
    model: 'claude-opus-5',
    max_tokens: 16000,
    output_config: { format: zodOutputFormat(Verdict) },
    messages: [{
      role: 'user',
      content: [
        { type: 'text', text: 'Baseline (expected UI):' },
        await asImageBlock(expected),
        { type: 'text', text: 'Current (actual UI):' },
        await asImageBlock(actual),
        {
          type: 'text',
          text: [
            'Compare these two screenshots of the same page and report a visual regression verdict.',
            'Look for: shifted or overlapping elements, clipped or truncated text, broken spacing and',
            'alignment, font rendering changes, colour or contrast changes, and missing elements.',
            'Ignore differences that are only antialiasing or sub-pixel rendering.',
            'Judge whether this reads as a deliberate redesign or as unintended breakage.',
          ].join(' '),
        },
      ],
    }],
  })

  const verdict = response.parsed_output
  if (!verdict) return

  await testInfo.attach('ai-visual-verdict', {
    body: JSON.stringify(verdict, null, 2),
    contentType: 'application/json',
  })
}

export const test = base.extend({})
test.afterEach(async ({}, testInfo) => { await triageVisualFailure(testInfo) })
export { expect }
```

Import `test` from this file instead of `@playwright/test` in your visual specs, and every screenshot failure arrives in the HTML report with a structured verdict beside the images.

### Why it's written this way

- **`claude-opus-5`** — current model ID, strong on vision. `claude-3-7-sonnet-20250219` and other dated IDs from older examples were **retired on 2026-02-19 and return 404**. Swap in `claude-sonnet-5` if you deliberately trade capability for cost; that's a decision to make explicitly, not a default.
- **`messages.parse()` + `zodOutputFormat`** — the response is schema-validated by the API, so there is no JSON to hand-parse and no "the model wrote prose around the JSON" failure mode. Reading `response.content[0].text` and `JSON.parse`-ing it is fragile in two ways: content blocks are a TypeScript union (`.text` doesn't exist on all of them), and with thinking enabled block 0 is a thinking block, not the text.
- **`testInfo.attachments`** — Playwright owns the baseline layout (per platform, per project, with its own naming). Hardcoding `../screenshots/homepage-baseline.png` reads a file that isn't there.
- **`testInfo.attach`** — a `console.log` scrolls past in CI and gates nothing. An attachment lands in the HTML report next to the images, where the reviewer already is.
- **`max_tokens: 16000`** — a ceiling, not a spend; you're billed for what's generated. Setting it low (say 1000) risks truncating mid-verdict on a busy page.
- **The API-key guard** — local runs without a key still get the pixel diff, just no triage. The suite must not fail because a secret is missing.

### ESM note

Playwright configs and specs are frequently ESM, where **`__dirname` and `__filename` are undefined** and throw at runtime. Use a path relative to cwd, or derive the directory:

```ts
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
const here = dirname(fileURLToPath(import.meta.url))
```

---

## Cost and CI

- The model runs **only on failures**. A stable suite costs nothing; a suite failing constantly is telling you to fix the stabilisation, not the budget.
- Full-page screenshots are large. Opus 5 accepts up to 2576px on the long edge and a single image can reach ~4784 tokens, so two full-page captures is a real input cost per failure. Capture the affected component (`expect(locator).toHaveScreenshot()`) rather than `fullPage: true` where you can.
- Cap the blast radius on a broadly-broken build — a global CSS change fails every visual test at once. Gate triage behind a count:

```ts
let triaged = 0
const TRIAGE_LIMIT = Number(process.env.VISUAL_TRIAGE_LIMIT ?? 10)
if (triaged++ >= TRIAGE_LIMIT) return   // log the skip; don't silently drop it
```

- The API key must be a CI secret. Never commit it, and never let a fork's PR run reach it.

---

## What this does and doesn't decide

The verdict is **advice for the reviewer, not a pass condition**. Do not auto-approve a baseline because the model called the change intentional — that hands the decision of what your product looks like to a screenshot comparison. The test still fails; the verdict just tells the human where to look first and whether to hurry.

Treat `intentional: true` as a prompt to check the design ticket, not as permission to run `--update-snapshots`.
