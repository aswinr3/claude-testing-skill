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

  // Mirror into the run folder alongside the result files
  const runDir = process.env.RUN_DIR ?? path.join('test-results', 'latest')
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

## 3. Naming and layout

Filenames must be traceable back to a case without opening them:

```
TC-0142__text-clipped__375x812.png
TC-0142__text-clipped__1280x800.png
```

```
test-results/2026-08-14-1432/
├── 00-SUMMARY.md
├── 06-functional.md
├── defects.md
├── cases.tsv
└── screenshots/
    ├── TC-0142__text-clipped__375x812.png
    ├── TC-0155__interactive-overlap__1280x800.png
    └── traces/
        └── TC-0142.zip
```

Screenshots live **with** the run they came from. A screenshots folder detached from its run is unusable within a week — nobody knows which build it shows.

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
- **Steps:** 1. Log in as user_verified@test.local → 2. Add SKU-9 to cart →
  3. Open /checkout
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
