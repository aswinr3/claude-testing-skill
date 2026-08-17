# Bug evidence — capture, store, link into the sheet

A defect row with no evidence gets argued about; a defect row with a screenshot gets fixed. Every confirmed bug captures evidence, the evidence lands in the run folder, and the sheet gets a link.

---

## 1. What to capture

| Artefact | When | Why |
|---|---|---|
| **Full-page screenshot** | every bug | The state at failure |
| **Element-highlighted screenshot** | UI-audit issues | A full-page shot doesn't show *which* of 40 buttons is 18px tall |
| **Playwright trace** | every e2e bug | The highest-value artefact — DOM snapshots, network, console, timeline, step by step |
| **Video** | multi-step flow bugs | Shows the sequence that produced the state |
| **Console + network log** | every bug | The error is often not on screen |
| **DOM snippet** | layout/UI bugs | The computed styles that caused it |

Most of this is configuration, not code:

```ts
// playwright.config.ts
use: {
  screenshot: 'only-on-failure',
  video: 'retain-on-failure',
  trace: 'on-first-retry',      // 'retain-on-failure' if you don't retry
}
```

That covers **thrown** failures. UI-audit issues are *collected*, not thrown, so they need explicit capture — see below.

## 2. Capture helper

Highlights the offending element, screenshots, then restores the DOM so later assertions aren't affected.

```ts
// e2e/evidence.ts
import type { Page, TestInfo } from '@playwright/test'
import fs from 'node:fs/promises'
import path from 'node:path'

export type Evidence = { caseId: string; rule: string; file: string; absPath: string }

export async function captureIssue(
  page: Page,
  testInfo: TestInfo,
  issue: { caseId: string; rule: string; selector?: string },
): Promise<Evidence> {
  // Highlight the element so the screenshot is self-explanatory
  if (issue.selector) {
    await page.evaluate((sel) => {
      const el = document.querySelector<HTMLElement>(sel)
      if (!el) return
      el.dataset.evPrevStyle = el.getAttribute('style') ?? ''
      el.style.setProperty('outline', '3px solid #FF0055', 'important')
      el.style.setProperty('outline-offset', '2px', 'important')
      el.scrollIntoView({ block: 'center', behavior: 'instant' as ScrollBehavior })
    }, issue.selector)
  }

  const vp = page.viewportSize()
  const file = [
    issue.caseId,
    issue.rule.replace(/[^a-z0-9]+/gi, '-'),
    vp ? `${vp.width}x${vp.height}` : 'novp',
  ].join('__') + '.png'

  const absPath = testInfo.outputPath(file)
  await page.screenshot({ path: absPath, fullPage: true })

  // Restore — a left-behind outline pollutes every later screenshot in the test
  if (issue.selector) {
    await page.evaluate((sel) => {
      const el = document.querySelector<HTMLElement>(sel)
      if (!el) return
      const prev = el.dataset.evPrevStyle ?? ''
      prev ? el.setAttribute('style', prev) : el.removeAttribute('style')
      delete el.dataset.evPrevStyle
    }, issue.selector)
  }

  await testInfo.attach(`evidence-${issue.caseId}`, { path: absPath, contentType: 'image/png' })

  // Mirror into the run folder alongside the result files.
  // No default: `test-results/latest` is a symlink, and an un-moved Playwright
  // outputDir wipes `test-results/` before every run — defaulting there means
  // the evidence is deleted by the next run. Fail loudly instead.
  const runDir = process.env.RUN_DIR
  if (!runDir) throw new Error('RUN_DIR must point at this run\'s folder, e.g. test-results/2026-08-14-1432')
  const dest = path.join(runDir, 'screenshots', file)
  await fs.mkdir(path.dirname(dest), { recursive: true })
  await fs.copyFile(absPath, dest)

  return { caseId: issue.caseId, rule: issue.rule, file, absPath: dest }
}
```

Wire it into the UI sweep so every collected issue gets its own highlighted shot:

```ts
const issues = [...runtime, ...await auditPage(page)]
const evidence = []
for (const [i, issue] of issues.entries()) {
  if (issue.severity !== 'high') continue
  evidence.push(await captureIssue(page, testInfo, {
    caseId: `${caseId}-${String(i + 1).padStart(2, '0')}`,
    rule: issue.rule,
    selector: issue.element,
  }))
}
```

## 2b. Bugs that only appear after a sequence of actions

A single failure screenshot is close to useless for a bug that needs four steps to reach. It
shows the wreckage, not the route. **Nobody can reproduce a state they cannot see the path
to**, and "Steps" typed from memory after the fact is the field that most often turns out to
be wrong.

Wrap each action in `step()`. It captures a screenshot per action, records the sequence, and
emits the repro from what the test *actually did* rather than from what you remember it doing.

```ts
// e2e/evidence.ts (continued)
type Trail = { n: number; label: string; file: string; url: string; ms: number }

/**
 * `module` groups the case folder the same way the run record and the case
 * register group it, so a team opens one directory and sees only its own work.
 */
export function sequence(
  page: Page, testInfo: TestInfo, opts: { module: string; caseId: string },
) {
  const { module: mod, caseId } = opts
  const runDir = process.env.RUN_DIR
  if (!runDir) throw new Error('RUN_DIR must point at this run\'s folder')
  const dir = path.join(runDir, 'screenshots', 'sequences', mod, caseId)

  const trail: Trail[] = []
  const t0 = Date.now()
  const vpTag = () => { const v = page.viewportSize(); return v ? `${v.width}x${v.height}` : 'novp' }
  const slug = (s: string) => s.replace(/[^a-z0-9]+/gi, '-').slice(0, 40)

  const shoot = async (stem: string) => {
    const file = `${caseId}__${stem}__${vpTag()}.png`
    await fs.mkdir(dir, { recursive: true })
    await page.screenshot({ path: path.join(dir, file) })
    return file
  }

  const step = async (label: string, fn: () => Promise<void>) => {
    await test.step(label, fn)
    const n = trail.length + 1
    // Zero-padded so step 10 sorts after step 9, not after step 1.
    const file = await shoot(`s${String(n).padStart(2, '0')}__${slug(label)}`)
    trail.push({ n, label, file, url: page.url(), ms: Date.now() - t0 })
  }

  /** The outcome frame. `__FAIL__`, never `sNN` — it is not an action. */
  const fail = (reason: string) => shoot(`FAIL__${slug(reason)}`)

  const repro = () => trail.map(s =>
    `${s.n}. ${s.label} — \`${s.url}\` (+${s.ms}ms) → \`${s.file}\``).join('\n')

  /** Everything for this case, in this case's folder. Zip it and the story is complete. */
  const write = async (extra: Record<string, string> = {}) => {
    await fs.mkdir(dir, { recursive: true })
    await fs.writeFile(path.join(dir, 'repro.md'),
      `# ${caseId} — ${mod}\n\n## Steps (derived from the run)\n\n${repro()}\n` +
      Object.entries(extra).map(([k, v]) => `\n## ${k}\n\n${v}\n`).join(''))
    for (const [name, src] of Object.entries({
      'video.webm': testInfo.attachments.find(a => a.name === 'video')?.path,
      'trace.zip': testInfo.attachments.find(a => a.name === 'trace')?.path,
    })) if (src) await fs.copyFile(src, path.join(dir, name)).catch(() => {})
    return dir
  }

  return { step, fail, trail, repro, write, dir }
}
```

Used:

```ts
test('TC-0301 signup shows a success toast then the app crashes', async ({ page }, testInfo) => {
  const { step, fail, repro, write } = sequence(page, testInfo, {
    module: 'MOD-03-checkout', caseId: 'TC-0301',
  })

  await step('open the signup form',                    async () => { /* … */ })
  await step('enter full name and work email',          async () => { /* … */ })
  await step('choose the Pro plan',                     async () => { /* … */ })
  await step('submit and wait for the popup',           async () => { /* … */ })
  await step('observe the app 1s later',                async () => { /* … */ })

  const root = (await page.locator('#app').innerHTML()).trim()
  if (root === '') await fail('app-root-emptied')      // the outcome frame
  await write({ Runtime: '```json\n' + JSON.stringify(runtime, null, 2) + '\n```' })

  expect(root, 'the app root must not be torn down after a successful submit').not.toBe('')
})
```

Produces one self-contained folder for this case:

```
screenshots/sequences/MOD-03-checkout/TC-0301/
├── TC-0301__s01__open-the-signup-form__1280x720.png
├── TC-0301__s02__enter-full-name-and-work-email__1280x720.png
├── TC-0301__s03__choose-the-Pro-plan__1280x720.png
├── TC-0301__s04__submit-and-wait-for-the-popup__1280x720.png
├── TC-0301__s05__observe-the-app-1s-later__1280x720.png
├── TC-0301__FAIL__app-root-emptied__1280x720.png
├── repro.md
├── video.webm
└── trace.zip
```

### Which action actually caused it

With a per-step trail you can answer this instead of guessing. **Bisect the sequence** — drop
one step at a time and re-run:

```bash
# does it still fail without step 3?
STEPS=1,2,4 npx playwright test -g "TC-0301"
```

Gate each step on the variable, then report the **minimal failing sequence**, not the sequence
you happened to write. A four-step repro that is really a two-step repro sends the developer
looking in the wrong place.

Turn the artefacts off while bisecting or repeating — a `--repeat-each=10` run writes a full
trace and video **per attempt**, which is how a 7-file run record becomes a 99-file one:

```bash
npx playwright test -g "TC-0301" --repeat-each=10 --trace=off --video=off
```

### Ordering matters, and so does state

Two failure modes hide behind "it only breaks after a few actions":

- **Order-dependent** — the same actions in a different order pass. Say so explicitly, and
  give both orders. This is usually a state-machine or race defect.
- **Accumulation-dependent** — it needs *n* items, not those specific items. Find the
  threshold (2 items pass, 3 fail) and report the boundary. That converts a vague repro into
  a boundary-value case.

Never report a sequence bug without stating which of the two it is. Determinism still applies:
if the sequence only fails sometimes, it is a flake until proven otherwise — `--repeat-each=10`
before it goes in `defects.md`.

## 3. Naming and layout

Two kinds of evidence, two shapes. Mixing them is what makes a run record unreadable at scale:
one flat folder holding 200 single-shot bugs *and* 1,000 sequence frames is a folder nobody
opens twice.

### Single-shot evidence — one file per bug, flat

A UI-audit finding or a one-assertion failure needs exactly one image. These stay flat,
because there is nothing to group:

```
screenshots/single/
├── TC-0142__text-clipped__375x812.png
├── TC-0142__text-clipped__1280x800.png
└── TC-0155__interactive-occluded__1280x800.png
```

### Sequence evidence — one folder per case, grouped by module

A bug that takes four actions to reach produces a *set* of files that only make sense
together. Give the set its own folder, and group those folders **by module** — the same axis
the case register and the result files already use, so a team can open the one directory they
own:

```
screenshots/sequences/
├── MOD-03-checkout/
│   ├── TC-0301/
│   │   ├── TC-0301__s01__open-the-signup-form__1280x720.png
│   │   ├── TC-0301__s02__enter-full-name-and-work-email__1280x720.png
│   │   ├── TC-0301__s03__choose-the-Pro-plan__1280x720.png
│   │   ├── TC-0301__s04__submit-and-wait-for-the-popup__1280x720.png
│   │   ├── TC-0301__s05__observe-the-app-1s-later__1280x720.png
│   │   ├── TC-0301__FAIL__app-root-emptied__1280x720.png
│   │   ├── repro.md            ← generated from the run
│   │   ├── video.webm
│   │   └── trace.zip
│   └── TC-0307/…
└── MOD-05-payments/
    └── TC-0412/…
```

Rules that make this hold up across hundreds of cases:

- **The folder carries the identity; the filenames repeat it anyway.** Redundant inside the
  tree, essential outside it — evidence gets dragged into Slack and attached to tickets
  constantly, and `s01__open-the-form.png` on its own means nothing.
- **`sNN` is zero-padded** so the sequence sorts correctly past step 9.
- **The failure frame is `__FAIL__`, not `sNN`.** It is the outcome, not an action, and it
  must sort last and read differently at a glance.
- **Everything for one case lives in one folder** — frames, repro, video, trace. Zipping
  `TC-0301/` gives a developer the complete story with nothing missing.
- **Module folders match the module names in `modules/`** and the `Module (Slice)` column in
  the register. One vocabulary, three places.

Screenshots live **with** the run they came from. A screenshots folder detached from its run
is unusable within a week — nobody knows which build it shows.

## 4. Uploading to Drive

Google Sheets can't reference a local file, so evidence needs a URL.

Per run, create a Drive folder and upload the screenshots:

1. Create the folder — `create_file` with `mimeType: application/vnd.google-apps.folder`, titled to match the run (`test-run-2026-08-14-1432`). Keep the returned folder ID.
2. Upload each PNG — `create_file` with `parentId` set to that folder, `contentMimeType: image/png`, and the file base64-encoded into `base64Content`. Set `disableConversionToGoogleType: true`, or Drive may convert the upload into a Google-native type and the link stops being an image.
3. Share the folder once (`share_file` on the folder ID) rather than each file individually — permissions inherit, and one call beats forty.

**Keep screenshots small.** Base64 inflates by ~33%, and a full-page shot of a long dashboard can be several MB before encoding. Prefer element or viewport screenshots over `fullPage: true` for evidence, and only capture `high` severity issues automatically.

If Drive isn't wired up, any host with stable URLs works — CI build artifacts, S3, or the repo itself if screenshots are committed. The sheet only needs a URL.

## 5. Linking into the sheet — read this before choosing a formula

**`=IMAGE()` requires a publicly accessible URL that serves the image bytes with no authentication.** A Drive file shared with named people or a Workspace group does **not** qualify — the cell renders `#VALUE!` or an empty box, and it fails silently for anyone without access even when it works for you.

| Situation | Use |
|---|---|
| Drive, shared with the team | `=HYPERLINK("https://drive.google.com/file/d/<ID>/view", "TC-0142 ▸ text-clipped")` |
| Genuinely public host (public bucket, public CI artifact) | `=IMAGE("https://.../TC-0142.png")` for an inline thumbnail |
| Want thumbnails in-cell from Drive | **Insert ▸ Image ▸ Image in cell**, manually — this path handles Drive auth; formulas don't |
| Multiple artefacts for one bug | `=HYPERLINK(<folder-url>, "TC-0142 evidence (3)")` — link the folder, not each file |

Default to `=HYPERLINK()`. It always works, survives permission changes, and doesn't bloat the sheet with images that stop loading in three months.

### Columns

Extend the contract in `test-cases-sheet.md` with two columns:

| Col | Header | Content |
|---|---|---|
| U | `Evidence` | `=HYPERLINK("...", "TC-0142 ▸ text-clipped")`, or `—` |
| V | `Evidence Path` | `test-results/2026-08-14-1432/screenshots/TC-0142__text-clipped__375x812.png` |

Column `V` matters more than it looks: it's the offline record. When a Drive link dies, gets moved, or the sheet outlives the folder, `V` still says exactly which file in which run, and the run folder is in CI artifacts or on disk.

### Emitting the rows

`cases.tsv` carries the formula as literal text — Sheets evaluates it on paste, provided you use **Paste special ▸ Paste values only**:

```
Case ID	Status	Last Run	Defect Ref	Evidence	Evidence Path
TC-0142	Fail	2026-08-14	BUG-231	=HYPERLINK("https://drive.google.com/file/d/1a2b3c/view", "TC-0142 ▸ text-clipped")	test-results/2026-08-14-1432/screenshots/TC-0142__text-clipped__375x812.png
```

Two things that break this:

- **A plain paste** may keep the formula as text. Paste values only.
- **A comma inside the link label** splits the cell if anyone converts to CSV. Keep labels comma-free — use ` ▸ ` as the separator, as above.

## 6. What goes in `defects.md`

The sheet gets one link; the defect file gets the full story:

```markdown
### BUG-231 — Order total clipped on mobile

- **Case:** TC-0142
- **Requirement:** DS:§3 (typography), UX:Flow-04 screen requirements
- **Severity:** High — the user cannot read the amount they are agreeing to pay
- **Environment:** staging, commit `a91f2c3`, Chromium 128, 375×812
- **Steps (derived from the run, not from memory):**
  1. Log in as user_verified@test.local — `/login` (+0ms) → `TC-0142__s01__…png`
  2. Add SKU-9 and SKU-14 to the cart — `/products` (+1.2s) → `TC-0142__s02__…png`
  3. Apply discount code SAVE20 — `/cart` (+2.4s) → `TC-0142__s03__…png`
  4. Open /checkout — `/checkout` (+3.1s) → `TC-0142__s04__…png`
- **Minimal sequence:** steps 2 and 4 only — step 3 is not required to reproduce
- **Dependency:** accumulation — passes with 1 item, fails from 2 upward
- **Expected:** Full total visible, e.g. "₹1,24,999.00"
- **Actual:** Renders "₹1,24,9…" — clipped, no ellipsis affordance, no scroll
- **Cause:** `.order-total` has `width: 120px` fixed; DESIGN_SYSTEM §4 requires
  layouts to preserve required information when they adapt
- **Evidence:** `screenshots/TC-0142__text-clipped__375x812.png` ·
  `screenshots/traces/TC-0142.zip`
- **Classification:** Implementation drift — design file and spec both correct
```

Severity is stated as **user impact**, not as a label. "High" on its own starts an argument; "the user cannot read the amount they are agreeing to pay" ends one.

## 7. Honesty rules

- **Screenshot the failure, not a reconstruction.** A shot taken by re-running the steps by hand is a different run and may not show the same state. Capture at the moment of failure.
- **Don't crop away context.** The URL bar, viewport size, and surrounding layout are usually what makes the bug diagnosable.
- **Never edit a screenshot** beyond the highlight the helper adds. Annotate in `defects.md` instead.
- **If evidence capture failed, say so** in the row (`Evidence: capture failed — <reason>`). An empty cell reads as "no bug".
